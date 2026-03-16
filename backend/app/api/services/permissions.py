import uuid
from sqlalchemy import ColumnElement
from typing import cast
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.permission.models import Permission
from backend.app.role_permission.models import RolePermission
from backend.app.user_role.models import UserRole


class PermissionService:
    async def get_user_permission(
        self,
        session: AsyncSession,
        user_id: uuid.UUID
    ) -> list[str]:
        """Lấy thông tin quyền của người dùng"""
        stmt = (
            select(Permission.code)
            .select_from(UserRole)
            .join_from(
                UserRole,
                RolePermission,
                cast(
                    ColumnElement,
                    RolePermission.role_code == UserRole.role_code,
                ),
            )
            .join_from(
                RolePermission,
                Permission,
                cast(
                    ColumnElement,
                    Permission.code == RolePermission.permission_code,
                ),
            )
            .where(
                UserRole.user_id == user_id,
            )
            .distinct()
        )

        result = await session.exec(stmt)
        return list(result.all())
permission_service = PermissionService()

