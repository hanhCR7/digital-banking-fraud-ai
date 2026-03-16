import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { toast } from "react-toastify";
import OtpForm from "./OtpForm";
import { useAuthContext } from "../../contexts/AuthContext";

function getErrorMessage(detail) {
  if (detail == null) return null;
  if (typeof detail === "string") return detail;
  if (typeof detail === "object" && "message" in detail) return detail.message;
  if (Array.isArray(detail)) {
    return detail.map((d) => (d?.msg != null ? d.msg : String(d))).join(". ");
  }
  if (typeof detail === "object" && "msg" in detail) return detail.msg;
  return String(detail);
}

const LoginForm = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [otpSent, setOtpSent] = useState(false);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const navigate = useNavigate();
  const { register, handleSubmit } = useForm();
  const { requestOtp, verifyOtp } = useAuthContext();

  const onSubmit = async (data) => {
    setIsLoading(true);
    setError(null);

    try {
      await requestOtp(data.email, data.password);
      setLoginEmail(data.email);
      setLoginPassword(data.password);
      setOtpSent(true);
      toast.success("Đã gửi OTP, vui lòng kiểm tra email.");
    } catch (submitError) {
      const message =
        getErrorMessage(submitError?.response?.data?.detail) ??
        submitError?.response?.data?.message ??
        submitError?.message ??
        "Đăng nhập thất bại.";
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyOtp = async (otp) => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await verifyOtp(loginEmail, otp);
      const data = result?.data ?? result;

      if (data?.require_password_change) {
        toast.info(data?.message ?? "Cần đổi mật khẩu trước khi sử dụng.");
        navigate("/auth/change-password", { replace: true });
        return;
      }

      toast.success("Đăng nhập thành công!");
      const user = result?.user;
      const role = (user?.roles?.[0] ?? user?.role ?? "").toString().toLowerCase();
      if (role === "super_admin") {
        navigate("/admin", { replace: true });
      } else {
        navigate("/dashboard", { replace: true });
      }
    } catch (submitError) {
      const message =
        getErrorMessage(submitError?.response?.data?.detail) ??
        submitError?.response?.data?.message ??
        submitError?.message ??
        "Xác thực OTP thất bại.";
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendOtp = async () => {
    setIsLoading(true);
    setError(null);

    try {
      await requestOtp(loginEmail, loginPassword);
      toast.success("Đã gửi lại OTP.");
    } catch (submitError) {
      const message =
        getErrorMessage(submitError?.response?.data?.detail) ??
        submitError?.response?.data?.message ??
        submitError?.message ??
        "Gửi lại OTP thất bại.";
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  if (otpSent) {
    return (
      <OtpForm
        email={loginEmail}
        onSubmit={handleVerifyOtp}
        onResend={handleResendOtp}
        isLoading={isLoading}
        error={error}
        onBack={() => setOtpSent(false)}
      />
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow">
        <h1 className="mb-6 text-center text-2xl font-semibold text-gray-900">
          Login
        </h1>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <input
            type="email"
            placeholder="Email"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
            {...register("email", { required: true })}
          />
          <input
            type="password"
            placeholder="Password"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
            {...register("password", { required: true })}
          />
          <button
            type="submit"
            disabled={isLoading}
            className="w-full rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Gửi OTP
          </button>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </form>
        <button
          type="button"
          onClick={() => {
            navigate("/auth/forgot-password");
          }}
          className="mt-4 w-full text-sm text-gray-500 hover:text-gray-700"
        >
          Quên mật khẩu?
        </button>
        <button
          type="button"
          onClick={() => {
            navigate("/auth/register");
          }}
          className="mt-2 w-full text-sm text-gray-500 hover:text-gray-700"
        >
          Chưa có tài khoản? Đăng ký
        </button>
      </div>
    </div>
  );
};

export default LoginForm;
