import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "react-toastify";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../hooks/auth/useAuth";

const ResetPassword = ({ token: tokenProp }) => {
  const { token: tokenParam } = useParams();
  const token = tokenProp ?? tokenParam;
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState("");
  const { register, handleSubmit } = useForm();
  const { resetPasswordWithToken } = useAuth();

  const onSubmit = async (data) => {
    if (!token) {
      setMessage("Liên kết đặt lại mật khẩu không hợp lệ.");
      return;
    }

    setIsLoading(true);
    setMessage("");

    try {
      const response = await resetPasswordWithToken(
        token,
        data.new_password,
        data.confirm_password
      );
      const text = response?.message || "Đặt lại mật khẩu thành công.";
      setMessage(text);
      toast.success(text);
      navigate("/login");
    } catch (submitError) {
      const errorMessage =
        submitError?.response?.data?.detail?.message ||
        submitError?.response?.data?.message ||
        "Không thể đặt lại mật khẩu.";
      setMessage(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow">
        <h1 className="mb-2 text-center text-2xl font-semibold text-gray-900">
          Đặt lại mật khẩu
        </h1>
        <p className="mb-6 text-center text-sm text-gray-600">
          Nhập mật khẩu mới để hoàn tất.
        </p>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <input
            type="password"
            placeholder="Mật khẩu mới"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
            {...register("new_password", { required: true, minLength: 8 })}
          />
          <input
            type="password"
            placeholder="Xác nhận mật khẩu"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
            {...register("confirm_password", { required: true, minLength: 8 })}
          />
          <button
            type="submit"
            disabled={isLoading}
            className="w-full rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Xác nhận
          </button>
          {message && (
            <p className="text-center text-sm text-gray-600">{message}</p>
          )}
        </form>
      </div>
    </div>
  );
};

export default ResetPassword;
