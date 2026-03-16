import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "react-toastify";
import { useNavigate, useParams } from "react-router-dom";
import { useActiveAccount } from "../../hooks/auth/useActiveAccount";

const ActivateAccount = ({ token: tokenProp }) => {
  const { token: tokenParam } = useParams();
  const token = tokenProp ?? tokenParam;
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [isActivating, setIsActivating] = useState(false);
  const [message, setMessage] = useState("");
  const [showResend, setShowResend] = useState(false);
  const { register, handleSubmit } = useForm();
  const { activeAccount, resendActivation } = useActiveAccount();

  useEffect(() => {
    if (!token) {
      setMessage("Liên kết kích hoạt không hợp lệ.");
      setShowResend(true);
      return;
    }

    const activate = async () => {
      setIsActivating(true);
      setMessage("");
      setShowResend(false);

      try {
        const response = await activeAccount(token);
        const text =
          response?.message || "Tài khoản đã được kích hoạt thành công!";
        setMessage(text);
        toast.success(text);
        const timer = setTimeout(() => {
          navigate("/login");
        }, 3000);
        return () => clearTimeout(timer);
      } catch (submitError) {
        const detail = submitError?.response?.data?.detail;
        const errorMessage =
          detail?.message ||
          submitError?.response?.data?.message ||
          "Kích hoạt thất bại.";
        setMessage(errorMessage);
        setShowResend(Boolean(detail?.email_required));
        toast.error(errorMessage);
      } finally {
        setIsActivating(false);
      }
    };

    const cleanup = activate();
    return () => {
      if (typeof cleanup === "function") {
        cleanup();
      }
    };
  }, [token, activeAccount, navigate]);

  const onResend = async (data) => {
    setIsLoading(true);
    setMessage("");

    try {
      const response = await resendActivation(data.email);
      const text =
        response?.message ||
        "Nếu tồn tại tài khoản, bạn sẽ nhận được liên kết kích hoạt.";
      setMessage(text);
      toast.success(text);
    } catch (submitError) {
      const detail = submitError?.response?.data?.detail;
      const errorMessage =
        detail?.message ||
        submitError?.response?.data?.message ||
        "Gửi lại liên kết thất bại.";
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
          Kích hoạt tài khoản
        </h1>
        <p className="mb-6 text-center text-sm text-gray-600">
          Xác nhận tài khoản của bạn trước khi đăng nhập.
        </p>

        {isActivating ? (
          <p className="text-center text-sm text-gray-600">
            Đang kích hoạt tài khoản...
          </p>
        ) : (
          message && <p className="text-center text-sm text-gray-600">{message}</p>
        )}

        {showResend && (
          <form onSubmit={handleSubmit(onResend)} className="mt-6 space-y-4">
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
              Gửi lại liên kết
            </button>
          </form>
        )}

        <button
          type="button"
          onClick={() => {
            navigate("/login");
          }}
          className="mt-6 w-full text-sm text-gray-500 hover:text-gray-700"
        >
          Quay lại đăng nhập
        </button>
      </div>
    </div>
  );
};

export default ActivateAccount;
