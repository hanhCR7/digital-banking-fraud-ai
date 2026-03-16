import uuid

from fastapi import HTTPException, status
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.logging import get_logger
from backend.app.core.tasks.image_upload import upload_profile_image_task
from backend.app.user_profile.enums import ImageTypeEnum
from backend.app.user_profile.models import Profile
from backend.app.auth.models import User
from backend.app.user_profile.schema import (
    ProfileCreateSchema,
    ProfileUpdateSchema
)

logger = get_logger()

# Lấy hồ sơ người dùng theo user_id
async def get_user_profile(user_id: uuid.UUID, session: AsyncSession) -> Profile | None:
    try:
        statement = select(Profile).where(Profile.user_id == user_id)
        result = await session.exec(statement)
        return result.first()

    except Exception as e:
        logger.error(f"Lỗi khi lấy thông tin hồ sơ người dùng: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi khi lấy thông tin hồ sơ người dùng"},
        )

# Tạo hồ sơ người dùng mới
async def create_user_profile(
    user_id: uuid.UUID, profile_data: ProfileCreateSchema, session: AsyncSession
) -> Profile:
    try:
        existing_profile = await get_user_profile(user_id, session)

        if existing_profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Hồ sơ người dùng đã tồn tại",
                },
            )
        # Chuyển đổi dữ liệu schema thành dict
        profile_data_dict = profile_data.model_dump()

        profile = Profile(**profile_data_dict)
        profile.user_id = user_id
        session.add(profile)

        await session.commit()
        await session.refresh(profile)

        logger.info(f"Hồ sơ người dùng đã được tạo: {user_id}")
        return profile

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Lỗi khi tạo thông tin hồ sơ người dùng: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi khi tạo thông tin hồ sơ người dùng"},
        )
# Cập nhật hồ sơ người dùng
async def update_user_profile(
    user_id: uuid.UUID, profile_data: ProfileUpdateSchema, session: AsyncSession
) -> Profile:
    try:
        # Lấy hồ sơ của người dùng hiện tại
        profile = await get_user_profile(user_id, session)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "Hồ sơ người dùng không tìm thấy",
                    "action": "Vui lòng tạo hồ sơ người dùng trước",
                },
            )
        # Cập nhật các trường từ profile_data nếu chúng được cung cấp
        update_data = profile_data.model_dump(exclude_unset=True)
        # Loại trừ các trường hình ảnh khỏi việc cập nhật trực tiếp
        for field, value in update_data.items():
            if field not in [
                "profile_photo_url",
                "id_photo_url",
                "signature_photo_url",
            ]:
                setattr(profile, field, value)

        await session.commit()
        await session.refresh(profile)

        logger.info(f"Hồ sơ người dùng đã được cập nhật: {user_id}")
        return profile

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Lỗi khi cập nhật thông tin hồ sơ người dùng: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi khi cập nhật thông tin hồ sơ người dùng"},
        )


def initiate_image_upload(
    file_content: bytes,
    image_type: ImageTypeEnum,
    content_type: str,
    user_id: uuid.UUID,
) -> str:
    """Khởi tạo task upload ảnh hồ sơ người dùng lên Cloudinary."""
    try:
        # Gửi task upload ảnh sang Celery worker để xử lý bất đồng bộ
        task = upload_profile_image_task.delay(
            file_content, image_type.value, str(user_id), content_type
        )
        return task.id
    except Exception as e:
        logger.error(f"Lỗi khi khởi tạo task upload ảnh: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi khi khởi tạo task upload ảnh"},
        )


async def update_profile_image_url(
    user_id: uuid.UUID,
    image_type: ImageTypeEnum,
    image_url: str,
    session: AsyncSession,
) -> Profile:
    """ Cập nhật URL ảnh tương ứng trong hồ sơ người dùng."""
    try:
        # Lấy thông tin hồ sơ người dùng theo user_id
        profile = await get_user_profile(user_id, session)
        # Nếu người dùng chưa có hồ sơ thì không thể cập nhật ảnh
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "Hồ sơ người dùng không tìm thấy",
                    "action": "Vui lòng tạo hồ sơ người dùng trước",
                },
            )
        # Ánh xạ loại ảnh sang trường tương ứng trong bảng Profile
        field_mapping = {
            ImageTypeEnum.PROFILE_PHOTO: "profile_photo_url",
            ImageTypeEnum.ID_PHOTO: "id_photo_url",
            ImageTypeEnum.SIGNATURE_PHOTO: "signature_photo_url",
        }
        # Kiểm tra image_type có hợp lệ hay không
        field_name = field_mapping.get(image_type)

        if not field_name:
            raise ValueError(f"Invalid image type: {image_type}")
        # Gán động URL ảnh vào đúng trường của profile
        setattr(profile, field_name, image_url)

        await session.commit()

        await session.refresh(profile)

        return profile
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Lỗi khi cập nhật URL ảnh trong hồ sơ người dùng: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi khi cập nhật URL ảnh trong hồ sơ người dùng"},
        )


async def get_user_with_profile(user_id: uuid.UUID, session: AsyncSession) -> User:
    """Lấy thông tin người dùng kèm theo hồ sơ (profile)"""
    try:
        # Tạo câu truy vấn lấy User theo user_id
        statement = select(User).where(User.id == user_id)
        result = await session.exec(statement)
        # Lấy bản ghi User đầu tiên (nếu tồn tại)
        user = result.first()

        if user:
            # Load quan hệ profile của user từ database
            await session.refresh(user, ["profile"])
            return user
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Người dùng không tìm thấy"},
            )
    except Exception as e:
        logger.error(f"Lỗi khi lấy thông tin người dùng kèm theo hồ sơ: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi khi lấy thông tin người dùng kèm theo hồ sơ"},
        )


async def get_all_user_profiles(
    session: AsyncSession,
    current_user: User,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[User], int]:
    """Lấy danh sách toàn bộ người dùng kèm profile (có phân quyền)."""
    try:
        # Truy vấn tổng số người dùng để phục vụ phân trang
        count_statement = select(User)
        # Thực thi query và lấy tổng số bản ghi
        result = await session.exec(count_statement)
        total_count = len(result.all())
        # Truy vấn danh sách user theo phân trang và sắp xếp mới nhất
        statement = (
            select(User).offset(skip).limit(limit).order_by(col(User.created_at).desc())
        )
        result = await session.exec(statement)
        # Lấy danh sách user từ kết quả truy vấn
        users = result.all()
        # Load quan hệ profile cho từng user
        for user in users:
            await session.refresh(user, ["profile"])
        # Trả về danh sách user và tổng số bản ghi
        return list(users), total_count

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách toàn bộ người dùng kèm profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Lỗi khi lấy danh sách toàn bộ người dùng kèm profile.",
                "action": "Vui lòng thử lại sau.",
            },
        )