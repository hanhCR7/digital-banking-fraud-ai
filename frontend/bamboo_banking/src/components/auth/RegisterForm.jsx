import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "react-toastify";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/auth/useAuth";

const securityQuestions = [
  { value: "mother_maiden_name", label: "Tên mẹ là gì?" },
  { value: "childhood_friend", label: "Tên bạn thời thơ ấu là gì?" },
  { value: "favorite_color", label: "Màu yêu thích của bạn là gì?" },
  { value: "birth_city", label: "Bạn sinh ra ở thành phố nào?" },
];

const RegisterForm = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState("");
  const { register, handleSubmit } = useForm();
  const { register: registerUser } = useAuth();
  const navigate = useNavigate();

  const onSubmit = async (data) => {
    setIsLoading(true);
    setMessage("");

    try {
      const response = await registerUser({
        email: data.email,
        first_name: data.first_name,
        middle_name: data.middle_name || null,
        last_name: data.last_name,
        id_no: data.id_no,
        security_question: data.security_question,
        security_answer: data.security_answer,
        password: data.password,
        confirm_password: data.confirm_password,
      });
      const text =
        response?.message ||
        "Bạn đã đăng ký thành công! Vui lòng kiểm tra mail để kích hoạt tài khoản.";
      setMessage(text);
      toast.success(text);
      navigate("/login");
    } catch (submitError) {
      const errorMessage =
        submitError?.response?.data?.detail?.message ||
        submitError?.response?.data?.detail ||
        submitError?.response?.data?.message ||
        "Đăng ký thất bại.";
      setMessage(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow">
        <h1 className="mb-2 text-center text-2xl font-semibold text-gray-900">
          Đăng ký tài khoản
        </h1>
        <p className="mb-6 text-center text-sm text-gray-600">
          Điền thông tin để tạo tài khoản mới.
        </p>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <input
            type="email"
            placeholder="Email"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
            {...register("email", { required: true })}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <input
              type="text"
              placeholder="Họ"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
              {...register("last_name", { required: true })}
            />
            <input
              type="text"
              placeholder="Tên"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
              {...register("first_name", { required: true })}
            />
          </div>
          <input
            type="text"
            placeholder="Tên đệm (tuỳ chọn)"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
            {...register("middle_name")}
          />
          <input
            type="text"
            placeholder="CCCD/CMND"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
            {...register("id_no", { required: true })}
          />
          <select
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
            defaultValue=""
            {...register("security_question", { required: true })}
          >
            <option value="" disabled>
              Chọn câu hỏi bảo mật
            </option>
            {securityQuestions.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Câu trả lời bảo mật"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
            {...register("security_answer", { required: true })}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <input
              type="password"
              placeholder="Mật khẩu"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
              {...register("password", { required: true, minLength: 8 })}
            />
            <input
              type="password"
              placeholder="Xác nhận mật khẩu"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
              {...register("confirm_password", { required: true, minLength: 8 })}
            />
          </div>
          <button
            type="submit"
            disabled={isLoading}
            className="w-full rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Đăng ký
          </button>
          {message && (
            <p className="text-center text-sm text-gray-600">{message}</p>
          )}
        </form>
        <button
          type="button"
          onClick={() => {
            navigate("/login");
          }}
          className="mt-4 w-full text-sm text-gray-500 hover:text-gray-700"
        >
          Đã có tài khoản? Đăng nhập
        </button>
      </div>
    </div>
  );
};

export default RegisterForm;
