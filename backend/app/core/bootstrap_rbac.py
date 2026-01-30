from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.role.models import Role
from backend.app.permission.models import Permission
from backend.app.role_permission.models import RolePermission
from backend.app.role.schema import RoleChoicesSchema
from backend.app.permission.schema import PermissionChoicesSchema
from backend.app.core.logging import get_logger

logger = get_logger()

ROLE_SEED: dict[RoleChoicesSchema, str] = {
    RoleChoicesSchema.SUPER_ADMIN: "Quản trị hệ thống cấp cao",
    RoleChoicesSchema.ADMIN: "Quản trị hệ thống",
    RoleChoicesSchema.BRANCH_MANAGER: "Quản lý chi nhánh",
    RoleChoicesSchema.TELLER: "Giao dịch viên",
    RoleChoicesSchema.ACCOUNT_EXECUTIVE: "Chăm sóc khách hàng",
    RoleChoicesSchema.CUSTOMER: "Khách hàng"
}

PERMISSION_SEED: dict[str, str] = {
    perm.value: perm.name.replace("_", " ").title()
    for perm in PermissionChoicesSchema
}


ROLE_PERMISSIONS_SEED: dict[
    RoleChoicesSchema, list[PermissionChoicesSchema]
] = {
    # CUSTOMER – chỉ thao tác của chính mình
    RoleChoicesSchema.CUSTOMER: [
        PermissionChoicesSchema.CREATE_PROFILE,
        PermissionChoicesSchema.VIEW_MY_PROFILE,
        PermissionChoicesSchema.UPDATE_MY_PROFILE,

        PermissionChoicesSchema.VIEW_TRANSACTION_HISTORY,
        PermissionChoicesSchema.GENERATE_STATEMENT,
        PermissionChoicesSchema.INITIATE_MONEY_TRANSFER,
        PermissionChoicesSchema.COMPLETE_MONEY_TRANSFER,
        PermissionChoicesSchema.GENERATE_STATEMENT,
        PermissionChoicesSchema.CREATE_WITHDRAWAL,

        PermissionChoicesSchema.CREATE_VIRTUAL_CARD,
        PermissionChoicesSchema.TOP_UP_CARD,
        PermissionChoicesSchema.BLOCK_CARD,

        PermissionChoicesSchema.UPLOAD_PROFILE_IMAGE,
        PermissionChoicesSchema.VIEW_UPLOAD_STATUS,

        PermissionChoicesSchema.VIEW_NEXT_OF_KIN,
        PermissionChoicesSchema.CREATE_NEXT_OF_KIN,
        PermissionChoicesSchema.UPDATE_NEXT_OF_KIN,
        PermissionChoicesSchema.DELETE_NEXT_OF_KIN,
    ],

    # ACCOUNT EXECUTIVE – CSKH (không đụng tiền)
    RoleChoicesSchema.ACCOUNT_EXECUTIVE: [
        PermissionChoicesSchema.VIEW_ALL_PROFILES,
        PermissionChoicesSchema.VIEW_TRANSACTION_HISTORY,
        PermissionChoicesSchema.VIEW_NEXT_OF_KIN,
        PermissionChoicesSchema.REVIEW_TRANSACTION,
    ],

    # TELLER – giao dịch viên
    RoleChoicesSchema.TELLER: [
        PermissionChoicesSchema.CREATE_DEPOSIT,
        PermissionChoicesSchema.COMPLETE_MONEY_TRANSFER,
    ],

    # BRANCH MANAGER – phê duyệt & risk
    RoleChoicesSchema.BRANCH_MANAGER: [
        PermissionChoicesSchema.ACTIVATE_ACCOUNT,
        PermissionChoicesSchema.ACTIVATE_CARD,
        PermissionChoicesSchema.BLOCK_CARD,

        PermissionChoicesSchema.REVIEW_TRANSACTION,
        PermissionChoicesSchema.REVIEW_FRAUD_CASE,
        PermissionChoicesSchema.VIEW_RISK_HISTORY,

        PermissionChoicesSchema.COMPLETE_MONEY_TRANSFER,
    ],

    # ADMIN – quản trị hệ thống
    RoleChoicesSchema.ADMIN: [
        p for p in PermissionChoicesSchema
        if not p.value.startswith("ai_")
    ],

    # SUPER ADMIN – full + override
    RoleChoicesSchema.SUPER_ADMIN: list(PermissionChoicesSchema),
}
async def seed_roles(db: AsyncSession) -> None:
    for role, desc in ROLE_SEED.items():
        result = await db.exec(
            select(Role).where(Role.code == role.value)
        )
        exists = result.first()

        if not exists:
            db.add(Role(code=role.value, description=desc))

    await db.commit()
    logger.info("Hoàn tất khởi tạo dữ liệu vai trò")


async def seed_permissions(db: AsyncSession) -> None:
    for code, desc in PERMISSION_SEED.items():
        result = await db.exec(
            select(Permission).where(Permission.code == code)
        )
        exists = result.first()

        if not exists:
            db.add(Permission(code=code, description=desc))

    await db.commit()
    logger.info("Hoàn tất khởi tạo dữ liệu quyền hạn")


async def seed_role_permissions(db: AsyncSession) -> None:
    for role, permissions in ROLE_PERMISSIONS_SEED.items():
        for perm in permissions:
            await _ensure_mapping(db, role.value, perm.value)

    await db.commit()
    logger.info("Hoàn tất khởi tạo dữ liệu phân quyền vai trò")


async def _ensure_mapping(
    db: AsyncSession,
    role_code: str,
    permission_code: str
) -> None:
    result = await db.exec(
        select(RolePermission).where(
            RolePermission.role_code == role_code,
            RolePermission.permission_code == permission_code,
        )
    )
    exists = result.first()

    if not exists:
        db.add(
            RolePermission(
                role_code=role_code,
                permission_code=permission_code,
            )
        )

