import { createContext, useContext, useState, useCallback } from "react";
import { useAuth } from "../hooks/auth/useAuth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const { login, verifyOtp: verifyOtpApi, logout: logoutApi } = useAuth();
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem("user");
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });

  const requestOtp = useCallback(
    async (email, password) => {
      const res = await login(email, password);
      return res;
    },
    [login]
  );

  const verifyOtp = useCallback(
    async (email, otp) => {
      const res = await verifyOtpApi(email, otp);
      const data = res?.data ?? res;
      const payload = data ?? res;
      const token = payload?.access_token;
      if (token) {
        localStorage.setItem("access_token", token);
      }
      const userData = payload?.user ?? res?.user;
      if (userData) {
        setUser(userData);
        localStorage.setItem("user", JSON.stringify(userData));
      }
      return res;
    },
    [verifyOtpApi]
  );

  const logout = useCallback(async () => {
    try {
      await logoutApi();
    } finally {
      setUser(null);
      localStorage.removeItem("access_token");
      localStorage.removeItem("user");
    }
  }, [logoutApi]);

  const value = {
    user,
    setUser,
    requestOtp,
    verifyOtp,
    logout,
    isAuthenticated: !!localStorage.getItem("access_token"),
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuthContext must be used within AuthProvider");
  }
  return ctx;
}
