import { useEffect, useRef, useState } from "react";

const OTP_LENGTH = 6;
const RESEND_SECONDS = 60;

const OtpForm = ({
  email,
  onSubmit,
  onResend,
  isLoading = false,
  error,
  onBack,
}) => {
  const [digits, setDigits] = useState(() => Array(OTP_LENGTH).fill(""));
  const [resendTimer, setResendTimer] = useState(RESEND_SECONDS);
  const inputsRef = useRef([]);

  /* =========================
   * Focus input đầu tiên
   * ========================= */
  useEffect(() => {
    inputsRef.current[0]?.focus();
  }, []);

  /* =========================
   * Clear OTP khi có lỗi
   * ========================= */
  useEffect(() => {
    if (error) {
      setDigits(Array(OTP_LENGTH).fill(""));
      inputsRef.current[0]?.focus();
    }
  }, [error]);

  /* =========================
   * Countdown resend OTP
   * ========================= */
  useEffect(() => {
    if (resendTimer <= 0) return;

    const timer = setInterval(() => {
      setResendTimer((prev) => prev - 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [resendTimer]);

  const submitIfComplete = (nextDigits) => {
    const code = nextDigits.join("");
    if (
      code.length === OTP_LENGTH &&
      !nextDigits.includes("") &&
      !isLoading
    ) {
      onSubmit(code);
    }
  };

  const handleChange = (index, value) => {
    if (isLoading) return;

    const numbers = value.replace(/\D/g, "");
    if (!numbers) {
      const next = [...digits];
      next[index] = "";
      setDigits(next);
      return;
    }

    const next = [...digits];
    numbers
      .split("")
      .slice(0, OTP_LENGTH - index)
      .forEach((num, i) => {
        next[index + i] = num;
      });

    setDigits(next);
    submitIfComplete(next);

    const nextIndex = Math.min(index + numbers.length, OTP_LENGTH - 1);
    inputsRef.current[nextIndex]?.focus();
    inputsRef.current[nextIndex]?.select();
  };

  const handleKeyDown = (e, index) => {
    if (isLoading) return;

    if (e.key === "Backspace" && !digits[index] && index > 0) {
      inputsRef.current[index - 1]?.focus();
      inputsRef.current[index - 1]?.select();
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (isLoading) return;

    const code = digits.join("");
    if (code.length === OTP_LENGTH && !digits.includes("")) {
      onSubmit(code);
    }
  };

  const handleResend = () => {
    if (resendTimer > 0 || isLoading) return;
    onResend();
    setResendTimer(RESEND_SECONDS);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow">
        {/* Header */}
        <div className="flex flex-col items-center">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-blue-50 text-blue-600">
            <svg
              className="h-8 w-8"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path d="M12 3l7 4v5c0 4.418-3.134 8.223-7 9-3.866-.777-7-4.582-7-9V7l7-4z" />
              <path d="M9.5 12.5l1.5 1.5 3.5-3.5" />
            </svg>
          </div>

          <h1 className="text-xl font-semibold text-gray-900">
            XÁC THỰC OTP
          </h1>

          <p className="mt-2 text-center text-sm text-gray-600">
            Nhập mã OTP đã gửi đến{" "}
            <span className="font-medium text-gray-900">{email}</span>.  
            Mã có hiệu lực trong 5 phút.
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="mt-6 space-y-5">
          <div className="flex justify-center gap-3">
            {digits.map((value, index) => (
              <input
                key={index}
                ref={(el) => (inputsRef.current[index] = el)}
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={value}
                disabled={isLoading}
                onChange={(e) => handleChange(index, e.target.value)}
                onKeyDown={(e) => handleKeyDown(e, index)}
                className="h-12 w-12 rounded-lg border border-gray-300 text-center text-lg font-semibold text-gray-900 outline-none
                  focus:border-orange-400 focus:ring-2 focus:ring-orange-100
                  disabled:bg-gray-100 disabled:cursor-not-allowed"
              />
            ))}
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full rounded-full bg-orange-500 px-4 py-2 text-sm font-semibold text-white
              transition hover:bg-orange-600 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isLoading ? "Đang xác thực..." : "Tiếp tục"}
          </button>

          {error && (
            <p className="text-center text-sm text-red-600">{error}</p>
          )}

          <div className="flex justify-center gap-2 text-sm text-gray-600">
            <span>Chưa nhận được mã?</span>
            <button
              type="button"
              onClick={handleResend}
              disabled={resendTimer > 0 || isLoading}
              className="font-semibold text-orange-600 disabled:text-gray-400"
            >
              {resendTimer > 0
                ? `Gửi lại (${resendTimer}s)`
                : "Gửi lại"}
            </button>
          </div>

          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="w-full text-sm text-gray-500 hover:text-gray-700"
            >
              Quay lại
            </button>
          )}
        </form>
      </div>
    </div>
  );
};

export default OtpForm;
