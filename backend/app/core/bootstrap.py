from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.role.models import Role
from backend.app.auth.models import User
from backend.app.user_role.models import UserRole
from backend.app.auth.schema import SecurityQuestionsSchema, AccountStatusSchema
from backend.app.role.schema import RoleChoicesSchema
from backend.app.core.config import settings
from backend.app.auth.utils import generate_password_hash
from backend.app.core.logging import get_logger

logger = get_logger()

async def create_initial_admin_user(db: AsyncSession) -> None:
    """Tạo Account Admin của hệ thống(Nếu chưa tồn tại)"""
    admin_email = settings.INITIAL_ADMIN_EMAIL
    admin_password = settings.INITIAL_ADMIN_PASSWORD
    if not admin_email or not admin_password:
        logger.warning("Thiếu thông tin tạo tài khoản admin ban đầu!")
        return
    try:
        stmt = select(User).where(User.email == admin_email)
        admin_system = await db.exec(stmt)
        if admin_system.first():
            logger.info("Tài khoản admin đã tồn tại!")
            return
        hashed_password_admin = generate_password_hash(admin_password)
        new_admin = User(
            email=admin_email,
            hashed_password=hashed_password_admin,
            is_active=True,
            first_name="System",
            last_name="Admin",
            id_no="SYSTEM_ADMIN_0001",
            is_superuser=True,
            must_change_password=True,
            account_status=AccountStatusSchema.ACTIVE,
            security_question=SecurityQuestionsSchema.FAVORITE_COLOR,
            security_answer="Blue"
        )
        db.add(new_admin)
        await db.flush()
        admin_role = UserRole(
            user_id=new_admin.id,
            role_code=RoleChoicesSchema.SUPER_ADMIN.value
        )
        db.add(admin_role)
        await db.commit()
        logger.info("Tạo tài khoản admin thành công!")
    except Exception as e:
        await db.rollback()
        logger.error(f"Tạo tài khoản admin thất bại: {e}")
