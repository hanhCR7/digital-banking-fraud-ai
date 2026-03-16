from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.profile import (
    initiate_image_upload,
    update_profile_image_url,
)
from backend.app.core.celery_app import celery_app
from backend.app.core.config import settings
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.core.utils.image import validate_image
from backend.app.user_profile.enums import ImageTypeEnum
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema

router = APIRouter(prefix="/profile", tags=["Profile"])

logger = get_logger()


@router.post(
    "/upload/{image_type}",
    status_code=status.HTTP_202_ACCEPTED,
)
# Trả về HTTP 202 vì upload được xử lý bất đồng bộ (Celery)
async def upload_profile_image(
    image_type: ImageTypeEnum,
    current_user = Depends(require_permission(PermissionChoicesSchema.UPLOAD_PROFILE_IMAGE)),
    file: UploadFile = File(...),
) -> dict:
    """API khởi tạo quá trình upload ảnh hồ sơ người dùng."""
    try:
        if not file.content_type or file.content_type not in settings.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Định dạng ảnh không hợp lệ.",
                    "allowed_types": settings.ALLOWED_MIME_TYPES,
                },
            )
        # Đọc toàn bộ nội dung file upload vào bộ nhớ
        file_content = await file.read()
        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "File tải lên rỗng."},
            )
        # Kiểm tra tính hợp lệ của ảnh (format, size, dimension)
        is_valid, error_message = validate_image(file_content)
        # Nếu ảnh không hợp lệ thì trả lỗi ngay, không tạo task upload
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": error_message},
            )
        # Khởi tạo task Celery để upload ảnh bất đồng bộ
        task_id = initiate_image_upload(
            file_content,
            image_type,
            file.content_type or "application/octet-stream",
            current_user.id,
        )
        # Trả về trạng thái pending và task_id để client polling
        return {
            "message": "Đã lên lịch tải ảnh lên.",
            "task_id": task_id,
            "status": "pending",
        }
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Lỗi khi xử lý upload ảnh: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi khi xử lý upload ảnh"},
        )
    finally:
        await file.close()


@router.get(
    "/upload/{task_id}/status", 
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(PermissionChoicesSchema.VIEW_UPLOAD_STATUS))]
    )
async def get_upload_status(
    task_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """ API kiểm tra trạng thái upload ảnh theo task_id."""
    try:
        # Lấy trạng thái task từ Celery thông qua task_id
        task = celery_app.AsyncResult(task_id)
        # Kiểm tra task đã hoàn thành hay chưa
        if task.ready():
            # Task đã hoàn thành thành công
            if task.successful():
                result = task.get()
                logger.debug(f"Kết quả task: {result}")
                # Validate dữ liệu trả về từ Celery task
                if not isinstance(result, dict):
                    raise ValueError(f"Kiểu dữ liệu kết quả không hợp lệ: {type(result)}")
                # Kiểm tra các trường bắt buộc trong kết quả upload
                if not result.get("url") or not result.get("image_type"):
                    raise ValueError("Thiếu các trường bắt buộc trong kết quả upload")
                # Cập nhật URL ảnh vào hồ sơ người dùng sau khi upload thành công
                await update_profile_image_url(
                    user_id=current_user.id,
                    image_type=ImageTypeEnum(result["image_type"]),
                    image_url=result["url"],
                    session=session,
                )
                # Trả về trạng thái completed nếu upload thành công
                return {
                    "status": "completed",
                    "image_url": result["url"],
                    "thumbnail_url": result.get("thumbnail_url"),
                    "image_type": result["image_type"],
                }
            else:
                error = str(task.result) if task.result else "Lỗi xảy ra"
                return {"status": "failed", "error": error}

        return {"status": "pending", "task_id": task_id}

    except ValueError as ve:
        logger.error(f"Lỗi khi kiểm tra trạng thái upload: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(ve)},
        )
    except Exception as e:
        logger.error(f"Lỗi khi lấy trạng thái upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi khi lấy trạng thái upload"},
        )