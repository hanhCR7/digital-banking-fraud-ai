import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  HiOutlineUser,
  HiOutlineLogout,
  HiOutlineChevronDown,
} from "react-icons/hi";

import { HEADER_MENU_ITEMS } from "../constants/header.constants";
import { formatRoleLabel } from "../utils/role.utils";

const ENV = process.env.REACT_APP_ENV || "PROD";

export default function Header({ user, onLogout }) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);
  const navigate = useNavigate();

  const displayName = user?.username ?? user?.email ?? "Người dùng";
  const roleLabel = formatRoleLabel(user?.roles?.[0] ?? user?.role);

  useEffect(() => {
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleMenuClick = (item) => {
    setDropdownOpen(false);
    if (item.path) navigate(item.path);
  };

  const handleLogout = async () => {
    setDropdownOpen(false);
    if (typeof onLogout === "function") {
      await onLogout();
    }
    navigate("/login", { replace: true });
  };

  return (
    <header className="fixed left-0 right-0 top-0 z-40 flex h-16 items-center justify-between border-b border-border bg-background px-6 dark:border-gray-700 dark:bg-card">
      {/* Left */}
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold tracking-tight text-foreground">
          Core Banking – Giám sát gian lận
        </h1>
        <span
          className="rounded bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground dark:bg-gray-700 dark:text-gray-400"
          title={`Môi trường: ${ENV}`}
        >
          {ENV}
        </span>
      </div>

      {/* User menu */}
      <div className="relative" ref={dropdownRef}>
        <button
          type="button"
          onClick={() => setDropdownOpen((v) => !v)}
          className="flex items-center gap-3 rounded-md px-3 py-2 transition-colors hover:bg-muted dark:hover:bg-gray-700"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-muted-foreground dark:bg-gray-700 dark:text-gray-300">
            <HiOutlineUser className="h-4 w-4" />
          </div>

          <div className="hidden text-left sm:block">
            <p className="text-sm font-medium text-foreground">{displayName}</p>
            <p className="text-xs text-muted-foreground">{roleLabel}</p>
          </div>

          <HiOutlineChevronDown
            className={`h-4 w-4 text-muted-foreground transition-transform ${
              dropdownOpen ? "rotate-180" : ""
            }`}
          />
        </button>

        {dropdownOpen && (
          <div className="absolute right-0 top-full mt-1 w-52 rounded-md border border-border bg-background py-1 shadow-lg dark:border-gray-700 dark:bg-card">
            {HEADER_MENU_ITEMS.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => handleMenuClick(item)}
                className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-foreground hover:bg-muted dark:hover:bg-gray-700"
              >
                <item.icon className="h-4 w-4 text-muted-foreground" />
                {item.label}
              </button>
            ))}

            <hr className="my-1 border-border dark:border-gray-700" />

            <button
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-foreground hover:bg-muted dark:hover:bg-gray-700"
            >
              <HiOutlineLogout className="h-4 w-4 text-muted-foreground" />
              Đăng xuất
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
