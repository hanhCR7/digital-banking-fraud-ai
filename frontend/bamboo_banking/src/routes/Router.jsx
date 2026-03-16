import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  Outlet,
  useLocation,
} from "react-router-dom";

import { AuthProvider, useAuthContext } from "../contexts/AuthContext";
import { BankingLayout } from "../layouts";

// Auth pages
import LoginForm from "../components/auth/LoginForm";
import RegisterForm from "../components/auth/RegisterForm";
import ForgotPassword from "../components/auth/ForgotPassword";
import ChangePassword from "../components/auth/ChangePassword";
import ActivateAccount from "../components/auth/ActivateAccount";
import ResetPassword from "../components/auth/ResetPassword";
import ChangeInitialPassword from "../components/auth/ChangeInitialPassword";

// App pages
import {
  DashboardPage,
  TransactionsPage,
  RiskHistoryPage,
} from "../pages";

/* =========================
   Auth helpers
========================= */

function useIsAuthenticated() {
  return !!localStorage.getItem("access_token");
}

function ProtectedRoute({ children }) {
  const isAuth = useIsAuthenticated();
  const location = useLocation();

  if (!isAuth) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children ?? <Outlet />;
}

function PublicRoute({ children }) {
  const isAuth = useIsAuthenticated();

  if (isAuth) {
    return <Navigate to="/dashboard" replace />;
  }

  return children ?? <Outlet />;
}

/* =========================
   Layout wrapper
========================= */

function DashboardLayoutWrapper() {
  const { user, logout } = useAuthContext();

  return (
    <BankingLayout user={user} onLogout={logout}>
      <Outlet />
    </BankingLayout>
  );
}

/* =========================
   Routes
========================= */

function AppRoutes() {
  return (
    <Routes>
      {/* Root */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* Public routes */}
      <Route element={<PublicRoute />}>
        <Route path="/login" element={<LoginForm />} />
      </Route>

      <Route path="/auth">
        <Route
          path="register"
          element={
            <PublicRoute>
              <RegisterForm />
            </PublicRoute>
          }
        />
        <Route
          path="forgot-password"
          element={
            <PublicRoute>
              <ForgotPassword />
            </PublicRoute>
          }
        />
        <Route path="change-password" element={<ChangePassword />} />
        <Route path="activate/:token" element={<ActivateAccount />} />
        <Route path="reset-password/:token" element={<ResetPassword />} />
        <Route
          path="change-initial-password"
          element={<ChangeInitialPassword />}
        />
      </Route>

      {/* Protected app */}
      <Route element={<ProtectedRoute />}>
        <Route element={<DashboardLayoutWrapper />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="/risk-history" element={<RiskHistoryPage />} />
        </Route>
      </Route>

      {/* Aliases */}
      <Route path="/admin" element={<Navigate to="/dashboard" replace />} />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

/* =========================
   Root Router
========================= */

export default function Router() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
