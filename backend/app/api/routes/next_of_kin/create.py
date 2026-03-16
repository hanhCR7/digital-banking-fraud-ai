from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.next_of_kin import create_next_of_kin
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.next_of_kin.schema import NextOfKinCreateSchema, NextOfKinReadSchema
from backend.app.api.services.security import require_permission
from backend.app.permission.schema import PermissionChoicesSchema
logger = get_logger()

router = APIRouter(prefix="/next-of-kin", tags=["Next of Kin"])

@router.post(
    "/create",
    response_model=NextOfKinReadSchema,
    status_code=status.HTTP_201_CREATED,
    description="Tạo mới người thân (Next of Kin) cho người dùng hiện tại. \n"
                "Mỗi người dùng có thể tạo tối đa 3 người thân, chỉ có một người thân có thể là người thân chính.",
)
async def create_next_of_kin_route(
    next_of_kin_data: NextOfKinCreateSchema,
    current_user = Depends(require_permission(PermissionChoicesSchema.CREATE_NEXT_OF_KIN)),
    session: AsyncSession = Depends(get_session),
) -> NextOfKinReadSchema:
    """API tạo mới người thân (Next of Kin) cho người dùng hiện tại."""
    try:
        # Gọi service layer để xử lý toàn bộ nghiệp vụ tạo Next of Kin
        next_of_kin = await create_next_of_kin(
            user_id=current_user.id,
            next_of_kin_data=next_of_kin_data,
            session=session,
        )
        logger.info(
            f"User {current_user.email} tạo thành công người thân (Next of Kin): {next_of_kin.full_name}"
        )
        return next_of_kin
    except HTTPException as http_ex:
        logger.warning(
            f"Tạo người thân (Next of Kin) thất bại cho người dùng {current_user.email}: {http_ex.detail}"
        )
        raise http_ex
    except Exception as e:
        logger.error(f"Lỗi hệ thống: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Tạo người thân (Next of Kin) thất bại.",
            },
        )
