import uuid
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.role.models import Role
from backend.app.user_role.models import UserRole
from backend.app.role.schema import RoleChoicesSchema


class UserRoleService:

    async def get_roles(self, session: AsyncSession) -> list[Role]:
        """Lấy tất cả role (trừ SUPER_ADMIN)."""
        stmt = (
            select(Role)
            .where(Role.code != RoleChoicesSchema.SUPER_ADMIN.value)
            .order_by(Role.code)
        )
        result = await session.exec(stmt)
        return list(result.all())

    async def get_role_by_code(
        self,
        session: AsyncSession,
        role_code: str,
    ) -> Role | None:
        """Lấy role theo code."""
        stmt = select(Role).where(Role.code == role_code)
        result = await session.exec(stmt)
        return result.first()

    async def get_user_role(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> RoleChoicesSchema | None:
        """
        Lấy role của user.
        """

        stmt = select(UserRole.role_code).where(UserRole.user_id == user_id)
        result = await session.exec(stmt)
        role_code = result.first()

        return RoleChoicesSchema(role_code) if role_code else None

    async def assign_role_to_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        role: RoleChoicesSchema,
    ) -> None:
        """
        Gán (hoặc thay thế) role cho user.
        """

        # Check role tồn tại trong DB
        db_role = await self.get_role_by_code(session, role.value)
        if not db_role:
            raise ValueError("Vai trò không tồn tại")

        # Tìm role hiện tại của user
        stmt = select(UserRole).where(UserRole.user_id == user_id)
        result = await session.exec(stmt)
        user_role = result.first()

        if user_role:
            # Ghi đè role
            user_role.role_code = role.value
        else:
            # Chưa có role -> tạo mới
            session.add(
                UserRole(
                    user_id=user_id,
                    role_code=role.value,
                )
            )

        await session.commit()


user_role_service = UserRoleService()
