import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "react-toastify";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/auth/useAuth";

const ForgotPassword = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState("");
  const { register, handleSubmit } = useForm();
  const { resetPassword } = useAuth();
  const navigate = useNavigate();

  const onSubmit = async (data) => {
    setIsLoading(true);
    setMessage("");
    try {
      const response = await resetPassword(data.email);
      const text =
        response?.message ||
        "Nếu có tài khoản tồn tại với email này, bạn sẽ nhận được hướng dẫn.";
      setMessage(text);
      toast.success("Đã gửi yêu cầu đặt lại mật khẩu.");
    } catch (submitError) {
      const errorMessage =
        submitError?.response?.data?.detail?.message ||
        submitError?.response?.data?.message ||
        "Không thể gửi yêu cầu.";
      setMessage(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleBack = () => {
    navigate("/login");
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow">
        <h1 className="mb-2 text-center text-2xl font-semibold text-gray-900">
          Quên mật khẩu
        </h1>
        <p className="mb-6 text-center text-sm text-gray-600">
          Nhập email để nhận liên kết đặt lại mật khẩu.
        </p>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <input
            type="email"
            placeholder="Email"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
            {...register("email", { required: true })}
          />
          <button
            type="submit"
            disabled={isLoading}
            className="w-full rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Gửi yêu cầu
          </button>
          {message && (
            <p className="text-center text-sm text-gray-600">{message}</p>
          )}
        </form>
        <button
          type="button"
          onClick={handleBack}
          className="mt-4 w-full text-sm text-gray-500 hover:text-gray-700"
        >
          Quay lại đăng nhập
        </button>
      </div>
    </div>
  );
};

export default ForgotPassword;
