import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "react-toastify";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/auth/useAuth";

const ChangePassword = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState("");
  const { register, handleSubmit } = useForm();
  const { changePassword } = useAuth();
  const navigate = useNavigate();

  const onSubmit = async (data) => {
    setIsLoading(true);
    setMessage("");

    try {
      const response = await changePassword(
        data.current_password,
        data.new_password,
        data.confirm_password
      );
      const text =
        response?.message || "Mật khẩu đã được thay đổi thành công.";
      setMessage(text);
      toast.success(text);
      setTimeout(() => {
        navigate("/login");
      }, 1500);
    } catch (submitError) {
      const errorMessage =
        submitError?.response?.data?.detail?.message ||
        submitError?.response?.data?.message ||
        "Không thể thay đổi mật khẩu.";
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
          Đổi mật khẩu
        </h1>
        <p className="mb-6 text-center text-sm text-gray-600">
          Nhập mật khẩu hiện tại và mật khẩu mới.
        </p>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <input
            type="password"
            placeholder="Mật khẩu hiện tại"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
            {...register("current_password", { required: true, minLength: 8 })}
          />
          <input
            type="password"
            placeholder="Mật khẩu mới"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
            {...register("new_password", { required: true, minLength: 8 })}
          />
          <input
            type="password"
            placeholder="Xác nhận mật khẩu mới"
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

export default ChangePassword;
