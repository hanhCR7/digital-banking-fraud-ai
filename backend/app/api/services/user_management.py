import uuid
from typing import List
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlmodel import select, inspect, col
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.logging import get_logger
from backend.app.auth.models import User
from backend.app.auth.schema import AdminUserCreateSchema, AdminUserUpdateSchema, AccountStatusSchema
from backend.app.auth.utils import generate_password_hash, generate_username

logger = get_logger()
class UserManagemet:
    async def get_all_users(
        self, 
        session:AsyncSession,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
        is_active: bool | None = None
    ) -> List[User]:
        """"Lấy tất cả thông tin người dùng"""
        try:
            stmt = select(User)
            email_col = inspect(User).columns.email
            if search:
                stmt = stmt.where(email_col.ilike(f"%{search}%"))
            if is_active is not None:
                stmt = stmt.where(
                    inspect(User).columns.is_active == is_active
                )
            stmt = stmt.offset((page - 1) * limit).limit(limit)
            result = await session.exec(stmt)
            users = list(result.all())
            return users
        except Exception as e:
            logger.error(f"Lỗi khi lấy all user: {e}")
            raise 
    async def get_user_by_id(
        self,
        session:AsyncSession,
        user_id:uuid.UUID,
    ) -> User | None:
        """Lấy thông tin người dùng qua id"""
        try:
            stmt = select(User).where(User.id == user_id)
            result = await session.exec(stmt)
            user = result.first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"status": "error", "message": "Người dùng không tìm thấy"}
                )
            return user
        except Exception as e:
            logger.error(f"Lỗi khi lấy user by id: {e}")
            raise 
    async def create_user(
        self,
        session:AsyncSession,
        user_data:AdminUserCreateSchema,
    ) -> User:
        """Tạo người dùng mới"""
        try:
            new_user = User(**user_data.model_dump())
            new_user.hashed_password = generate_password_hash(user_data.password)
            new_user.is_active = user_data.is_active
            new_user.username=generate_username()
            new_user.account_status=AccountStatusSchema.ACTIVE
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            return new_user
        except Exception as e:
            logger.error(f"Lỗi khi tạo user: {e}")
            raise 
    async def update_user(
        self,
        session:AsyncSession,
        user_id:uuid.UUID,
        user_data:AdminUserUpdateSchema,
    ) -> User:
        """Cập nhật thông tin người dùng"""
        try:
            user = await self.get_user_by_id(session, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"status": "error", "message": "Người dùng không tìm thấy"}
                )
            update_data = user_data.model_dump(exclude_unset=True)
            if user_data.password:
                user.hashed_password = generate_password_hash(user_data.password)
            for field, value in update_data.items():
                setattr(user, field, value)
            await session.commit()
            await session.refresh(user)
            return user
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật user: {e}")
            raise
    async def delete_user(
        self,
        session:AsyncSession,
        user_id:uuid.UUID,
    ) -> User:
        """Xóa người dùng"""
        try:
            user = await self.get_user_by_id(session, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"status": "error", "message": "Người dùng không tìm thấy"}
                )
            user.deleted_at = datetime.now(timezone.utc)
            user.is_active = False
            await session.commit()
            await session.refresh(user)
            return user
        except Exception as e:
            logger.error(f"Lỗi khi xóa user: {e}")
            raise 
    async def restore_user(
        self,
        session:AsyncSession,
        user_id:uuid.UUID,
    ) -> User:
        """Khôi phục người dùng"""
        try:
            user = await self.get_user_by_id(session, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"status": "error", "message": "Người dùng không tìm thấy"}
                )
            user.deleted_at = None
            user.is_active = True
            await session.commit()
            await session.refresh(user)
            return user
        except Exception as e:
            logger.error(f"Lỗi khi khôi phục user: {e}")    
            raise 
    async def get_all_deleted_users(
        self,
        session:AsyncSession,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
    ) -> List[User]:
        """Lấy tất cả người dùng đã xóa"""
        try:
            stmt = select(User).where(User.deleted_at is not None)
            if search:
                stmt = stmt.where(col(User.email).ilike(f"%{search}%"))
            stmt = stmt.offset((page - 1) * limit).limit(limit)
            result = await session.exec(stmt)
            users = list(result.all())
            return users
        except Exception as e:
            logger.error(f"Lỗi khi lấy all deleted users: {e}")
            raise 
    async def get_deleted_user_by_id(
        self,
        session:AsyncSession,
        user_id:uuid.UUID,
    ) -> User | None:
        """Lấy người dùng đã xóa qua id"""
        try:
            stmt = select(User).where(User.id == user_id and User.deleted_at is not None)
            result = await session.exec(stmt)
            user = result.first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"status": "error", "message": "Người dùng không tìm thấy"}
                )
            return user
        except Exception as e:
            logger.error(f"Lỗi khi lấy deleted user by id: {e}")
            raise 
    async def get_all_users_for_excel(
        self,
        session:AsyncSession,
    ) -> List[User]:
        """Lấy tất cả người dùng để xuất thành file Excel"""
        try:
            stmt = select(User)
            result = await session.exec(stmt)
            users = list(result.all())
            return users
        except Exception as e:
            logger.error(f"Lỗi khi lấy all users for excel: {e}")
            raise 
    async def export_list_users_for_excel(
        self,
        session:AsyncSession,
    ) -> List[User]:
        """Xuất danh sách người dùng thành file Excel"""
        try:
            stmt = select(User)
            result = await session.exec(stmt)
            users = list(result.all())
            return users
        except Exception as e:
            logger.error(f"Lỗi khi xuất danh sách người dùng thành file Excel: {e}")
            raise
user_management_service = UserManagemet()