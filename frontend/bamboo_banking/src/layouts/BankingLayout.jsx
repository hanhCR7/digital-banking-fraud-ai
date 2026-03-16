import { useState } from "react";
import Header from "./Header";
import Sidebar, { SIDEBAR_WIDTH, SIDEBAR_COLLAPSED_WIDTH } from "./Sidebar";

export default function BankingLayout({ children, user, onLogout }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const sidebarWidth = sidebarCollapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH;

  return (
    <div className="min-h-screen bg-muted dark:bg-gray-900">
      <Header user={user} onLogout={onLogout} />
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggleCollapse={setSidebarCollapsed}
      />
      <main
        className="min-h-screen pt-16 transition-[margin-left] duration-200"
        style={{ marginLeft: `${sidebarWidth}px` }}
      >
        <div className="p-6">
          {children}
        </div>
      </main>
    </div>
  );
}
