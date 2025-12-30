from uuid import UUID
from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.logging import get_logger
from backend.app.next_of_kin.models import NextOfKin
from backend.app.next_of_kin.schema import (
    NextOfKinCreateSchema,
    NextOfKinReadSchema,
    NextOfKinUpdateSchema,
)

logger = get_logger()


async def get_next_of_kin_count(user_id: UUID, session: AsyncSession) -> int:
    """Lấy số lượng người thân của người dùng."""
    statement = select(NextOfKin).where(NextOfKin.user_id == user_id)
    result = await session.exec(statement)
    return len(result.all())


async def get_primary_next_of_kin(
    user_id: UUID, session: AsyncSession
) -> NextOfKin | None:
    """Lấy người thân chính của người dùng (Nếu có)."""
    # Chỉ lấy người thân được đánh dấu là primary
    statement = select(NextOfKin).where(
        NextOfKin.user_id == user_id, NextOfKin.is_primary
    )
    result = await session.exec(statement)
    return result.first()


async def validate_next_of_kin_creation(
    user_id: UUID, is_primary: bool, session: AsyncSession
) -> None:
    """Xác thực nghiệp vụ trước khi tạo người thân mới."""
    # Kiểm tra số lượng người thân hiện tại
    current_count = await get_next_of_kin_count(user_id, session)
    # Giới hạn tối đa 3 người thân
    if current_count >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": "Maximum number of kin (3) already reached.",
            },
        )
    # Nếu người thân mới được đánh dấu là primary,
    # kiểm tra xem đã tồn tại primary hay chưa
    if is_primary:
        existing_primary = await get_primary_next_of_kin(user_id, session)
        if existing_primary:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "A primary next of kin already exists.",
                },
            )


async def create_next_of_kin(
    user_id: UUID, next_of_kin_data: NextOfKinCreateSchema, session: AsyncSession
) -> NextOfKinReadSchema:
    """Tạo mới người thân cho người dùng."""
    try:
        # Validate nghiệp vụ trước khi tạo
        current_count = await validate_next_of_kin_creation(
            user_id, next_of_kin_data.is_primary, session
        )
        # Nếu đây là người thân đầu tiên, tự động gán là primary
        if current_count == 0:
            next_of_kin_data.is_primary = True
        # Tạo entity NextOfKin từ dữ liệu request
        next_of_kin = NextOfKin(**next_of_kin_data.model_dump())
        next_of_kin.user_id = user_id
        # Lưu dữ liệu vào database
        session.add(next_of_kin)
        await session.commit()
        await session.refresh(next_of_kin)

        logger.info(f"Next of kin created successfully for user: {user_id}")

        return NextOfKinReadSchema.model_validate(next_of_kin)

    except HTTPException as http_ex:
        raise http_ex

    except Exception as e:
        logger.error(f"Failed to create next of kin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to create next of kin"},
        )


async def get_user_next_of_kins(
    user_id: UUID, session: AsyncSession
) -> list[NextOfKin]:
    """Lấy danh sách tất cả người thân của người dùng."""
    try:
        # Truy vấn danh sách người thân theo user_id
        statement = select(NextOfKin).where(NextOfKin.user_id == user_id)
        result = await session.exec(statement)
        next_of_kins = list(result.all())
        return next_of_kins
    except Exception as e:
        logger.error(f"Failed to retrieve next of kins: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to get user next of kins"},
        )


async def get_user_next_of_kin(
    user_id: UUID, next_of_kin_id: UUID, session: AsyncSession
) -> NextOfKin:
    """Lấy thông tin chi tiết một người thân của người dùng."""
    # Đảm bảo người thân thuộc về đúng user
    statement = select(NextOfKin).where(
        NextOfKin.user_id == user_id, NextOfKin.id == next_of_kin_id
    )
    result = await session.exec(statement)

    next_of_kin = result.first()

    if not next_of_kin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "message": "Next of kin not found"},
        )
    return next_of_kin


async def update_next_of_kin(
    user_id: UUID,
    next_of_kin_id: UUID,
    update_data: NextOfKinUpdateSchema,
    session: AsyncSession,
) -> NextOfKin:
    """Cập nhật thông tin người thân."""
    try:
        next_of_kin = await get_user_next_of_kin(user_id, next_of_kin_id, session)

        # Xử lý logic cập nhật trạng thái primary
        if update_data.is_primary is not None:
            if update_data.is_primary:
                # Nếu set primary mới → bỏ primary cũ
                existing_primary = await get_primary_next_of_kin(user_id, session)
                if existing_primary and existing_primary.id != next_of_kin_id:
                    existing_primary.is_primary = False
                    session.add(existing_primary)
            else:
                # Không cho bỏ primary nếu chỉ còn 1 người thân
                total_count = await get_next_of_kin_count(user_id, session)
                if total_count == 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "status": "error",
                            "message": "Cannot unset primary next of kin when there is only one",
                        },
                    )
        update_dict = update_data.model_dump(exclude_unset=True)

        for key, value in update_dict.items():
            setattr(next_of_kin, key, value)

        session.add(next_of_kin)
        await session.commit()
        await session.refresh(next_of_kin)

        logger.info(f"Updated next of kin: {next_of_kin_id} for user: {user_id}")

        return next_of_kin

    except HTTPException as http_ex:
        raise http_ex

    except Exception as e:
        logger.error(f"Failed to update next of kin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to update next of kin"},
        )


async def delete_next_of_kin(
    user_id: UUID, next_of_kin_id: UUID, session: AsyncSession
) -> dict[str, str]:
    """Xoá người thân của người dùng."""
    try:
        total_count = await get_next_of_kin_count(user_id, session)
        # Không cho phép xoá người thân cuối cùng
        if total_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Cannot delete the only next of kin",
                    "action": "At least one next of kin must be maintained",
                },
            )
        next_of_kin = await get_user_next_of_kin(user_id, next_of_kin_id, session)
        await session.delete(next_of_kin)
        await session.commit()
        logger.info(f"Next of kin deleted: {next_of_kin_id} for user: {user_id}")
        return {"status": "success", "message": "Next of kin deleted successfully"}
    except HTTPException as http_ex:
        raise http_ex

    except Exception as e:
        logger.error(f"Failed to delete next of kin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to delete next of kin"},
        )