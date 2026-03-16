import { HiOutlineRefresh, HiOutlineFilter } from "react-icons/hi";
import { useState } from "react";
import PropTypes from "prop-types";

const TYPE_OPTIONS = [
  { value: "deposit", label: "Nạp tiền" },
  { value: "withdrawal", label: "Rút tiền" },
  { value: "transfer", label: "Chuyển khoản" },
  { value: "reversal", label: "Hoàn tiền" },
  { value: "fee_charged", label: "Phí dịch vụ" },
  { value: "loan_disbursement", label: "Giải ngân" },
  { value: "loan_repayment", label: "Trả nợ" },
  { value: "interest_credited", label: "Lãi suất" },
];

const CATEGORY_OPTIONS = [
  { value: "credit", label: "Có" },
  { value: "debit", label: "Nợ" },
];

const STATUS_OPTIONS = [
  { value: "pending", label: "Đang xử lý" },
  { value: "completed", label: "Hoàn thành" },
  { value: "failed", label: "Thất bại" },
  { value: "reversed", label: "Đã hoàn" },
  { value: "cancelled", label: "Đã hủy" },
];

const STATUS_COLORS = {
  pending:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  completed:
    "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  reversed: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  cancelled: "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400",
};

function formatAmount(amount, currency = "VND") {
  const n = Number(amount);
  if (Number.isNaN(n)) return "-";
  return `${n.toLocaleString("vi-VN")} ${currency}`;
}

function formatDate(dateStr) {
  if (!dateStr) return "-";
  return new Date(dateStr).toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getStatusLabel(status) {
  const found = STATUS_OPTIONS.find((s) => s.value === status);
  return found ? found.label : status;
}

function getTypeLabel(type) {
  const found = TYPE_OPTIONS.find((t) => t.value === type);
  return found ? found.label : type;
}

export default function TransactionTable({
  data,
  loading,
  onReload,
  filters,
  onFilterChange,
  onApplyFilters,
  onResetFilters,
  pagination,
  onPageChange,
}) {
  const [showFilters, setShowFilters] = useState(false);

  const items = Array.isArray(data?.transactions)
    ? data.transactions
    : Array.isArray(data?.items)
    ? data.items
    : Array.isArray(data)
    ? data
    : [];

  const total = data?.total ?? items.length;
  const currentPage = pagination?.page ?? 1;
  const pageSize = pagination?.pageSize ?? (items.length || 1);
  const effectiveTotal = pagination?.total ?? total;
  const totalPages = Math.max(1, Math.ceil(effectiveTotal / pageSize));

  const canPaginate =
    typeof onPageChange === "function" && Number.isFinite(totalPages);
  const canFilter =
    filters &&
    typeof onFilterChange === "function" &&
    typeof onApplyFilters === "function" &&
    typeof onResetFilters === "function";

  const handleFilterChange = (key, value) => {
    if (!canFilter) return;
    onFilterChange((prev) => ({ ...prev, [key]: value }));
  };

  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-card dark:border-gray-700">
        <div className="border-b border-border px-4 py-3 dark:border-gray-700">
          <div className="h-5 w-40 animate-pulse rounded bg-muted" />
        </div>
        <div className="divide-y divide-border p-4 dark:divide-gray-700">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex gap-4 py-3">
              <div className="h-4 w-24 animate-pulse rounded bg-muted" />
              <div className="h-4 flex-1 animate-pulse rounded bg-muted" />
              <div className="h-4 w-20 animate-pulse rounded bg-muted" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="rounded-lg border border-border bg-card dark:border-gray-700">
        {canFilter && (
          <div className="border-b border-border px-4 py-3 dark:border-gray-700">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center gap-2 text-sm font-medium text-foreground"
            >
              <HiOutlineFilter className="h-4 w-4" />
              Bộ lọc
            </button>
          </div>
        )}
        <div className="p-12 text-center">
          <p className="text-muted-foreground">Không tìm thấy giao dịch nào</p>
          {typeof onReload === "function" && (
            <button
              onClick={onReload}
              className="mt-4 inline-flex items-center gap-2 rounded-lg border border-border bg-background px-4 py-2 text-sm text-foreground hover:bg-muted dark:border-gray-700"
            >
              <HiOutlineRefresh className="h-4 w-4" />
              Tải lại
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card dark:border-gray-700">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3 dark:border-gray-700">
        <h3 className="text-base font-semibold text-foreground">
          Giao dịch gần đây
        </h3>
        <div className="flex items-center gap-2">
          {canFilter && (
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
                showFilters
                  ? "bg-primary text-primary-foreground"
                  : "border border-border text-foreground hover:bg-muted dark:border-gray-700"
              }`}
            >
              <HiOutlineFilter className="inline h-4 w-4" />
            </button>
          )}
          {typeof onReload === "function" && (
            <button
              onClick={onReload}
              className="rounded-lg border border-border px-3 py-1.5 text-sm text-foreground hover:bg-muted dark:border-gray-700"
            >
              <HiOutlineRefresh className="inline h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      {canFilter && showFilters && (
        <div className="border-b border-border bg-muted/30 p-4 dark:border-gray-700">
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Từ ngày
              </label>
              <input
                type="date"
                value={filters.start_date}
                onChange={(e) =>
                  handleFilterChange("start_date", e.target.value)
                }
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground dark:border-gray-700"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Đến ngày
              </label>
              <input
                type="date"
                value={filters.end_date}
                onChange={(e) => handleFilterChange("end_date", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground dark:border-gray-700"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Loại giao dịch
              </label>
              <select
                value={filters.transaction_type}
                onChange={(e) =>
                  handleFilterChange("transaction_type", e.target.value)
                }
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground dark:border-gray-700"
              >
                <option value="">Tất cả</option>
                {TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Danh mục
              </label>
              <select
                value={filters.transaction_category}
                onChange={(e) =>
                  handleFilterChange("transaction_category", e.target.value)
                }
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground dark:border-gray-700"
              >
                <option value="">Tất cả</option>
                {CATEGORY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Trạng thái
              </label>
              <select
                value={filters.status}
                onChange={(e) => handleFilterChange("status", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground dark:border-gray-700"
              >
                <option value="">Tất cả</option>
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Số tiền
              </label>
              <div className="flex gap-2">
                <input
                  type="number"
                  min="0"
                  placeholder="Tối thiểu"
                  value={filters.min_amount}
                  onChange={(e) =>
                    handleFilterChange("min_amount", e.target.value)
                  }
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground dark:border-gray-700"
                />
                <input
                  type="number"
                  min="0"
                  placeholder="Tối đa"
                  value={filters.max_amount}
                  onChange={(e) =>
                    handleFilterChange("max_amount", e.target.value)
                  }
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground dark:border-gray-700"
                />
              </div>
            </div>
          </div>
          <div className="mt-3 flex gap-2">
            <button
              onClick={onApplyFilters}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Áp dụng
            </button>
            <button
              onClick={onResetFilters}
              className="rounded-lg border border-border px-4 py-2 text-sm text-foreground hover:bg-muted dark:border-gray-700"
            >
              Đặt lại
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-muted/50 text-left text-xs font-medium text-muted-foreground dark:border-gray-700">
              <th className="px-4 py-3">Mã tham chiếu</th>
              <th className="px-4 py-3">Số tiền</th>
              <th className="px-4 py-3">Loại</th>
              <th className="px-4 py-3">Trạng thái</th>
              <th className="px-4 py-3">Mô tả</th>
              <th className="px-4 py-3">Thời gian</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border dark:divide-gray-700">
            {items.map((row) => (
              <tr
                key={row.id ?? row.reference ?? JSON.stringify(row)}
                className="text-sm text-foreground hover:bg-muted/30 dark:hover:bg-gray-800/30"
              >
                <td className="px-4 py-3 font-mono text-xs text-blue-600 dark:text-blue-400">
                  {row.reference ?? row.user ?? "-"}
                </td>
                <td className="px-4 py-3 font-semibold">
                  {formatAmount(row.amount)}
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {getTypeLabel(row.transaction_type ?? row.channel)}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-block rounded-full px-2 py-1 text-xs font-medium ${
                      STATUS_COLORS[row.transaction_status ?? row.status] ??
                      "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400"
                    }`}
                  >
                    {getStatusLabel(row.transaction_status ?? row.status)}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {row.description ?? "-"}
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground">
                  {formatDate(row.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-border px-4 py-3 text-sm text-muted-foreground dark:border-gray-700">
        <span>
          Hiển thị {items.length} / {effectiveTotal} giao dịch
        </span>
        {canPaginate && totalPages > 1 && (
          <div className="flex items-center gap-2">
            <button
              disabled={currentPage <= 1}
              onClick={() => onPageChange(currentPage - 1)}
              className="rounded-lg border border-border px-3 py-1.5 text-sm text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700"
            >
              Trước
            </button>
            <span className="text-sm">
              Trang {currentPage} / {totalPages}
            </span>
            <button
              disabled={currentPage >= totalPages}
              onClick={() => onPageChange(currentPage + 1)}
              className="rounded-lg border border-border px-3 py-1.5 text-sm text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700"
            >
              Sau
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

TransactionTable.propTypes = {
  data: PropTypes.oneOfType([
    PropTypes.arrayOf(PropTypes.object),
    PropTypes.shape({
      transactions: PropTypes.arrayOf(PropTypes.object),
      items: PropTypes.arrayOf(PropTypes.object),
      total: PropTypes.number,
    }),
  ]),
  loading: PropTypes.bool,
  onReload: PropTypes.func,
  filters: PropTypes.object,
  onFilterChange: PropTypes.func,
  onApplyFilters: PropTypes.func,
  onResetFilters: PropTypes.func,
  pagination: PropTypes.shape({
    page: PropTypes.number,
    pageSize: PropTypes.number,
    total: PropTypes.number,
  }),
  onPageChange: PropTypes.func,
};
