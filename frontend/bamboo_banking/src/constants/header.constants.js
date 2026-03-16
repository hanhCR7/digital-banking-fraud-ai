import { HiOutlineUser, HiOutlineKey } from "react-icons/hi";

export const HEADER_MENU_ITEMS = [
  {
    key: "profile",
    label: "Hồ sơ cá nhân",
    icon: HiOutlineUser,
    path: "/profile",
  },
  {
    key: "change-password",
    label: "Đổi mật khẩu",
    icon: HiOutlineKey,
    path: "/auth/change-password",
  },
];

export const ROLE_LABELS = {
    super_admin: "Quản trị viên cấp cao",
    admin: "Quản trị hệ thống",
    branch_manageer: "Quản lý chi nhánh",
    account_executive: "Nhân viên CSKH",
    teller: "Giao dịch viên",
    customer: "Khách hàng",
};
