import { useMemo, useState } from "react";
import PropTypes from "prop-types";

/**
 * Biểu đồ xu hướng giao dịch đơn giản
 */
export default function TransactionTrendChart({ data, loading }) {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  const chartData = useMemo(() => {
    const trend = data?.transaction_trend ?? data ?? [];
    if (!Array.isArray(trend)) return [];
    return trend;
  }, [data]);

  const stats = useMemo(() => {
    if (!chartData.length) return { maxTotal: 1, totalSum: 0, fraudSum: 0 };

    const maxTotal = Math.max(...chartData.map((d) => Number(d.total ?? 0)), 1);
    const totalSum = chartData.reduce(
      (sum, d) => sum + Number(d.total ?? 0),
      0,
    );
    const fraudSum = chartData.reduce(
      (sum, d) => sum + Number(d.fraud ?? 0),
      0,
    );

    return { maxTotal, totalSum, fraudSum };
  }, [chartData]);

  const formatDate = (d) => {
    if (!d) return "";
    const str = String(d).slice(0, 10);
    return new Date(str).toLocaleDateString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
    });
  };

  const formatFullDate = (d) => {
    if (!d) return "";
    const str = String(d).slice(0, 10);
    return new Date(str).toLocaleDateString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  };

  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-card p-6 dark:border-gray-700">
        <div className="mb-4 h-6 w-48 animate-pulse rounded bg-muted" />
        <div className="mb-4 grid grid-cols-2 gap-4">
          <div className="h-16 animate-pulse rounded bg-muted" />
          <div className="h-16 animate-pulse rounded bg-muted" />
        </div>
        <div className="flex h-56 items-end justify-around gap-2">
          {[40, 70, 50, 90, 60, 80, 55].map((h, i) => (
            <div
              key={i}
              className="flex-1 animate-pulse rounded-t bg-muted"
              style={{ height: `${h}%` }}
            />
          ))}
        </div>
      </div>
    );
  }

  if (!chartData.length) {
    return (
      <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground dark:border-gray-700">
        Chưa có dữ liệu xu hướng
      </div>
    );
  }

  const fraudRate =
    stats.totalSum > 0
      ? ((stats.fraudSum / stats.totalSum) * 100).toFixed(1)
      : 0;

  return (
    <div className="rounded-lg border border-border bg-card p-6 dark:border-gray-700">
      {/* Tiêu đề */}
      <h3 className="mb-4 text-base font-semibold text-foreground">
        Xu hướng giao dịch ({chartData.length} ngày)
      </h3>

      {/* Thống kê tổng quan */}
      <div className="mb-6 grid grid-cols-2 gap-4">
        <div className="rounded-lg bg-blue-50 p-3 dark:bg-blue-950/30">
          <p className="text-xs text-muted-foreground">Tổng giao dịch</p>
          <p className="mt-1 text-xl font-bold text-foreground">
            {stats.totalSum.toLocaleString("vi-VN")}
          </p>
        </div>
        <div className="rounded-lg bg-amber-50 p-3 dark:bg-amber-950/30">
          <p className="text-xs text-muted-foreground">Nghi ngờ</p>
          <p className="mt-1 text-xl font-bold text-amber-600 dark:text-amber-500">
            {stats.fraudSum.toLocaleString("vi-VN")} ({fraudRate}%)
          </p>
        </div>
      </div>

      {/* Biểu đồ */}
      <div className="relative">
        {/* Trục Y */}
        <div className="absolute -left-2 top-0 flex h-56 flex-col justify-between text-xs text-muted-foreground">
          <span>{stats.maxTotal.toLocaleString("vi-VN")}</span>
          <span>{Math.round(stats.maxTotal / 2).toLocaleString("vi-VN")}</span>
          <span>0</span>
        </div>

        {/* Các cột */}
        <div className="ml-10 flex h-56 items-end justify-around gap-1.5">
          {chartData.map((item, i) => {
            const total = Number(item.total ?? 0);
            const fraud = Number(item.fraud ?? 0);
            const height = stats.maxTotal ? (total / stats.maxTotal) * 100 : 0;
            const fraudHeight = total ? (fraud / total) * height : 0;
            const normalHeight = height - fraudHeight;
            const isHovered = hoveredIndex === i;

            return (
              <div
                key={i}
                className="group relative flex flex-1 flex-col items-center"
                onMouseEnter={() => setHoveredIndex(i)}
                onMouseLeave={() => setHoveredIndex(null)}
              >
                {/* Tooltip */}
                {isHovered && (
                  <div className="absolute -top-24 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap rounded-lg border border-border bg-card p-2.5 text-xs shadow-lg dark:border-gray-600">
                    <p className="mb-1.5 font-medium text-foreground">
                      {formatFullDate(item.date)}
                    </p>
                    <div className="space-y-1">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-muted-foreground">Tổng:</span>
                        <span className="font-semibold">
                          {total.toLocaleString("vi-VN")}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-muted-foreground">Nghi ngờ:</span>
                        <span className="font-semibold text-amber-600">
                          {fraud.toLocaleString("vi-VN")}
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Cột */}
                <div
                  className={`w-full rounded-t transition-all ${
                    isHovered ? "shadow-md" : ""
                  }`}
                  style={{ height: `${Math.max(height, 2)}%` }}
                >
                  {/* Phần nghi ngờ */}
                  {fraud > 0 && (
                    <div
                      className="w-full rounded-t bg-amber-500"
                      style={{
                        height: `${fraudHeight}%`,
                        minHeight: fraudHeight ? 2 : 0,
                      }}
                    />
                  )}
                  {/* Phần bình thường */}
                  <div
                    className="w-full bg-blue-500"
                    style={{
                      height: `${normalHeight}%`,
                      minHeight: normalHeight ? 2 : 0,
                      borderRadius: fraud > 0 ? "0" : "0.25rem 0.25rem 0 0",
                    }}
                  />
                </div>

                {/* Ngày */}
                <span
                  className={`mt-2 text-xs ${
                    isHovered
                      ? "font-semibold text-foreground"
                      : "text-muted-foreground"
                  }`}
                >
                  {formatDate(item.date)}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Chú thích */}
      <div className="mt-6 flex items-center justify-center gap-6 text-sm">
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded bg-blue-500" />
          <span className="text-muted-foreground">Bình thường</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded bg-amber-500" />
          <span className="text-muted-foreground">Nghi ngờ</span>
        </div>
      </div>
    </div>
  );
}

TransactionTrendChart.propTypes = {
  data: PropTypes.oneOfType([
    PropTypes.arrayOf(
      PropTypes.shape({
        date: PropTypes.string,
        total: PropTypes.number,
        fraud: PropTypes.number,
      }),
    ),
    PropTypes.shape({
      transaction_trend: PropTypes.arrayOf(
        PropTypes.shape({
          date: PropTypes.string,
          total: PropTypes.number,
          fraud: PropTypes.number,
        }),
      ),
    }),
  ]),
  loading: PropTypes.bool,
};

TransactionTrendChart.defaultProps = {
  data: null,
  loading: false,
};
