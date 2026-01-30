from enum import Enum

# định nghĩa vai trò (role) của người dùng trong hệ thống
class RoleChoicesSchema(str, Enum):
    CUSTOMER = "customer" # khách hàng
    ACCOUNT_EXECUTIVE = "account_executive"# Nhân viên chăm sóc khách hàng
    BRANCH_MANAGER = "branch_manager"# Quản lý chi nhánh
    ADMIN = "admin"# QTV
    SUPER_ADMIN = "super_admin"# QTV cấp cao
    TELLER = "teller"# giao dịch viên
