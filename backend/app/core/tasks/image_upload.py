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
        logger.info(f"Starting image upload for user {user_id}, type: {image_type}")
        # Kiểm tra định dạng file upload (chỉ cho phép các MIME type hợp lệ)
        if content_type not in settings.ALLOWED_MIME_TYPES:
            error_msg = f"Invalid file type: {content_type}. Allowed types: {', '.join(settings.ALLOWED_MIME_TYPES)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        # Kiểm tra dung lượng file upload để tránh quá tải hệ thống
        file_size_mb = len(file_data) / (1024 * 1024)
        max_size_mb = settings.MAX_FILE_SIZE / (1024 * 1024)

        if file_size_mb > max_size_mb:
            error_msg = f"File too large: {file_size_mb:.2f}MB. Maximum allowed: {max_size_mb}MB"
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

        logger.debug(f"Uploading image with options: {upload_options}")
        # Thực hiện upload ảnh lên Cloudinary
        result = cloudinary.uploader.upload(
            file_data,
            **upload_options,
        )

        logger.debug(f"Cloudinary upload result: {result}")

        if not result.get("secure_url"):
            raise Exception(
                "Upload successful but secure URL not received from Cloudinary"
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
                raise Exception(f"Required firld {key} missiong in upload response")

        logger.info(
            f"Successfully uploaded {image_type} image for user {user_id}."
            f"URL: {response['url']}, "
            f"Thumbnail: {response.get('thumbnail_url', 'No thumbnail')}, "
            f"Public ID: {response['public_id']}"
        )
        return response
    except ValueError as e:
        logger.error(f"Validation error in profile image upload: {str(e)}")
        raise
    except Exception as e:
        attempt = self.request.retries + 1
        logger.error(
            f"Error uploading profile image (attempt {attempt}/{self.max_retries + 1}): {str(e)}"
        )
        # Nếu đã đạt số lần retry tối đa, ghi log lỗi cuối cùng
        if attempt > self.max_retries:
            logger.error(
                f"Final upload attempt failed for the user {user_id}, "
                f"image_type {image_type}: {str(e)}"
            )
        raise self.retry(exc=e)