import uuid
from typing import TypedDict

import cloudinary
import cloudinary.uploader

from backend.app.core.celery_app import celery_app
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger()


class UploadResponse(TypedDict):
    url: str
    image_type: str
    public_id: str
    thumbnail_url: str | None

# Celery task để upload ảnh hồ sơ người dùng lên Cloudinary
@celery_app.task(
    name="upload_profile_image_task",  # Tên task hiển thị trong Celery
    bind=True,                         # Cho phép truy cập self (retry, request)
    max_retries=3,                     # Số lần retry tối đa khi lỗi
    soft_time_limit=10,                # Giới hạn thời gian thực thi (giây)
    autoretry_for=(Exception,),        # Tự động retry khi gặp Exception
    retry_backoff=True,                # Retry theo cấp số nhân
    retry_backoff_max=60,              # Thời gian chờ tối đa giữa các lần retry
)

def upload_profile_image_task(
    self, file_data: bytes, image_type: str, user_id: str, content_type: str
) -> UploadResponse:
    """Task bất đồng bộ dùng để upload ảnh hồ sơ người dùng lên Cloudinary."""
    try:
        logger.info(f"Bắt đầu upload ảnh cho người dùng '{user_id}', loại ảnh: {image_type}")
        # Kiểm tra định dạng file upload (chỉ cho phép các MIME type hợp lệ)
        if content_type not in settings.ALLOWED_MIME_TYPES:
            error_msg = f"Định dạng file không hợp lệ: {content_type}. Các định dạng được phép: {', '.join(settings.ALLOWED_MIME_TYPES)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        # Kiểm tra dung lượng file upload để tránh quá tải hệ thống
        file_size_mb = len(file_data) / (1024 * 1024)
        max_size_mb = settings.MAX_FILE_SIZE / (1024 * 1024)

        if file_size_mb > max_size_mb:
            error_msg = f"File quá lớn: {file_size_mb:.2f}MB. Dung lượng tối đa cho phép: {max_size_mb}MB"
            logger.error(error_msg)
            raise ValueError(error_msg)
        # Cấu hình upload ảnh lên Cloudinary:
        # - Lưu theo thư mục user
        # - Sinh public_id duy nhất
        # - Tự động resize và tạo thumbnail
        upload_options = {
            "resource_type": "image",
            "folder": f"{settings.CLOUDINARY_CLOUD_NAME}/profiles/{user_id}",
            "public_id": f"{image_type}_{uuid.uuid4()}",
            "overwrite": True,
            "allowed_formats": ["jpg", "jpeg", "png"],
            "eager": [
                {"width": 800, "height": 800, "crop": "limit"},
                {"width": 200, "height": 200, "crop": "fill"},
            ],
            "tags": [f"user_{user_id}", image_type],
            "quality": "auto:good",
            "fetch_format": "auto",
        }

        logger.debug(f"Đang upload ảnh với cấu hình: {upload_options}")
        # Thực hiện upload ảnh lên Cloudinary
        result = cloudinary.uploader.upload(
            file_data,
            **upload_options,
        )

        logger.debug(f"Kết quả upload từ Cloudinary: {result}")

        if not result.get("secure_url"):
            raise Exception(
                "Tải lên thành công nhưng không nhận được URL an toàn từ Cloudinar"
            )
        # Chuẩn hoá dữ liệu trả về cho backend (URL gốc + thumbnail)
        response: UploadResponse = {
            "url": result["secure_url"],
            "image_type": image_type,
            "public_id": result["public_id"],
            # Lấy URL thumbnail từ eager transformations (nếu tồn tại)
            "thumbnail_url": (
                result.get("eager", [{}])[1].get("secure_url")
                if len(result.get("eager", [])) > 1
                else None
            ),
        }
        # Kiểm tra các trường bắt buộc trong response upload
        for key in ["url", "image_type", "public_id"]:
            if not response.get(key):
                raise Exception(f"Thiếu trường bắt buộc '{key}' trong dữ liệu phản hồi upload")

        logger.info(
            f"Upload ảnh '{image_type}' cho người dùng '{user_id}' thành công. "
            f"URL: {response['url']}, "
            f"Thumbnail: {response.get('thumbnail_url', 'Không có thumbnail')}, "
            f"Public ID: {response['public_id']}"
        )
        return response
    except ValueError as e:
        logger.error(f"Lỗi xác thực dữ liệu khi upload ảnh hồ sơ: {e}")
        raise
    except Exception as e:
        attempt = self.request.retries + 1
        logger.error(
            f"Lỗi khi upload ảnh hồ sơ (lần thử {attempt}/{self.max_retries + 1}): {e}"
        )
        # Nếu đã đạt số lần retry tối đa, ghi log lỗi cuối cùng
        if attempt > self.max_retries:
            logger.error(
                f"Lần upload cuối cùng thất bại cho người dùng '{user_id}', "
                f"loại ảnh '{image_type}': {e}"
            )
        raise self.retry(exc=e)