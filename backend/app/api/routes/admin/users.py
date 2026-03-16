import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.db import get_session
from backend.app.api.services.user_management import user_management_service
from backend.app.api.services.create_file import create_list_users_excel
from backend.app.api.services.security import require_role
from backend.app.role.schema import RoleChoicesSchema
from backend.app.core.logging import get_logger
from backend.app.auth.schema import AdminUserCreateSchema, AdminUserUpdateSchema, AdminUserResponse, AdminUserListResponse
logger = get_logger()
router = APIRouter(
    prefix="/admin",
    tags=["Users"],
)
@router.get(
    "/users",
    status_code=status.HTTP_200_OK,
    response_model=AdminUserListResponse,
    dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))]
)
async def get_users(
    session: AsyncSession = Depends(get_session),
    page: int = 1,
    limit: int = 20,
    search: str | None = None,
    is_active: bool | None = None,
):
    """Lấy danh sách người dùng"""
    try:
        users_response = await user_management_service.get_all_users(session, page, limit, search, is_active)
        return AdminUserListResponse.model_validate({
            "danh_sach_user": users_response,
        })
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách người dùng: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi khi lấy danh sách người dùng"}
        )
@router.get(
    "/users/{user_id}", 
    status_code=status.HTTP_200_OK, 
    response_model=AdminUserResponse,
    dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))]
)
async def get_user_by_id(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Lấy thông tin người dùng qua id"""
    try:
        user = await user_management_service.get_user_by_id(session, user_id)
        return AdminUserResponse.model_validate(user)
    except Exception as e:
        logger.error(f"Lỗi khi lấy thông tin người dùng qua id: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi khi lấy thông tin người dùng qua id"}
        )
@router.post(
    "/users", 
    status_code=status.HTTP_201_CREATED, 
    response_model=AdminUserResponse,
    dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))]
)
async def create_user(
    user_data: AdminUserCreateSchema,
    session: AsyncSession = Depends(get_session),
):
    """Tạo người dùng mới"""
    try:
        user = await user_management_service.create_user(session, user_data)
        return AdminUserResponse.model_validate(user)
    except Exception as e:
        logger.error(f"Lỗi khi tạo người dùng mới: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi khi tạo người dùng mới"}
        )
@router.put(
    "/users/{user_id}", 
    status_code=status.HTTP_200_OK, 
    response_model=AdminUserResponse,
    dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))]
)
async def update_user(
    user_id: uuid.UUID,
    user_data: AdminUserUpdateSchema,
    session: AsyncSession = Depends(get_session),
):
    """Cập nhật thông tin người dùng"""
    try:
        user = await user_management_service.update_user(session, user_id, user_data)
        return AdminUserResponse.model_validate(user)
    except Exception as e:
        logger.error(f"Lỗi khi cập nhật thông tin người dùng: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi khi cập nhật thông tin người dùng"}
        )
@router.delete(
    "/users/{user_id}", 
    status_code=status.HTTP_200_OK, 
    response_model=AdminUserResponse,
    dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))]
)
async def delete_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Xóa người dùng"""
    try:
        user = await user_management_service.delete_user(session, user_id)
        return AdminUserResponse.model_validate(user)
    except Exception as e:
        logger.error(f"Lỗi khi xóa người dùng: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Lỗi khi xóa người dùng"}
        )
@router.get("/list-users/export", status_code=status.HTTP_200_OK, dependencies=[Depends(require_role(RoleChoicesSchema.SUPER_ADMIN))])
async def export_list_users_for_excel(
    session: AsyncSession = Depends(get_session),
):
    """Xuất toàn bộ danh sách người dùng thành file Excel"""
    try:
        users = await user_management_service.get_all_users_for_excel(
            session=session
        )
        if not users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Không tìm thấy người dùng"}
            )
        excel_file = create_list_users_excel(users)

        filename = f"list_users_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.xlsx"

        return StreamingResponse(
            excel_file,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )

    except Exception as e:
        logger.error(f"Lỗi khi xuất danh sách người dùng thành file Excel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Lỗi khi xuất danh sách người dùng thành file Excel",
            },
        )