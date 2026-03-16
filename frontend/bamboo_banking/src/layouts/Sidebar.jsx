import { NavLink } from "react-router-dom";
import { useState } from "react";
import {
  HiOutlineViewGrid,
  HiOutlineSwitchHorizontal,
  HiOutlineShieldExclamation,
  HiOutlineChevronLeft,
  HiOutlineChevronRight,
} from "react-icons/hi";

const SIDEBAR_MENU = [
  { path: "/dashboard", label: "Dashboard", icon: HiOutlineViewGrid },
  { path: "/transactions", label: "Transactions", icon: HiOutlineSwitchHorizontal },
  { path: "/risk-history", label: "Risk History", icon: HiOutlineShieldExclamation },
];

const SIDEBAR_WIDTH = 260;
const SIDEBAR_COLLAPSED_WIDTH = 72;

export default function Sidebar({ collapsed = false, onToggleCollapse }) {
  const [isCollapsed, setIsCollapsed] = useState(collapsed);
  const width = isCollapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH;

  const handleToggle = () => {
    const next = !isCollapsed;
    setIsCollapsed(next);
    if (typeof onToggleCollapse === "function") onToggleCollapse(next);
  };

  return (
    <aside
      className="fixed left-0 top-16 z-30 flex h-[calc(100vh-4rem)] flex-col border-r border-gray-700 bg-gray-800 dark:border-gray-600 dark:bg-gray-900"
      style={{ width: `${width}px` }}
    >
      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-2 py-4">
        {SIDEBAR_MENU.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/dashboard"}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-gray-600 text-white dark:bg-gray-700"
                  : "text-gray-300 hover:bg-gray-600/70 hover:text-white dark:text-gray-400 dark:hover:bg-gray-700/70 dark:hover:text-gray-200"
              }`
            }
          >
            <item.icon className="h-5 w-5 shrink-0" aria-hidden />
            {!isCollapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-gray-700 px-2 py-2 dark:border-gray-600">
        <button
          type="button"
          onClick={handleToggle}
          className="flex w-full items-center justify-center gap-2 rounded-md px-3 py-2 text-sm text-gray-400 transition-colors hover:bg-gray-700 hover:text-white dark:hover:bg-gray-800 dark:hover:text-gray-300"
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {isCollapsed ? (
            <HiOutlineChevronRight className="h-5 w-5" />
          ) : (
            <>
              <HiOutlineChevronLeft className="h-5 w-5" />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}

export { SIDEBAR_WIDTH, SIDEBAR_COLLAPSED_WIDTH };
