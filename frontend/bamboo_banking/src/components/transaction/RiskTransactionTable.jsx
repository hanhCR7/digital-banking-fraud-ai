import { Fragment, useMemo, useState } from "react";
import { HiOutlineFilter, HiOutlineRefresh } from "react-icons/hi";
import RiskReviewForm from "../transaction/RiskReviewForm";
import { getRiskMeta } from "../../constants/risk.constants";

function formatAmount(amount) {
  if (typeof amount === "string" && amount.includes(",")) return amount;
  const n = Number(amount);
  if (Number.isNaN(n)) return String(amount ?? "-");
  return n.toLocaleString("vi-VN");
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

function getReviewStatusMeta(status) {
  const s = String(status ?? "").toLowerCase();
  if (s === "flagged") return { label: "Cần duyệt", canReview: true };
  if (s === "cleared") return { label: "Đã an toàn", canReview: false };
  if (s === "confirmed_fraud") {
    return { label: "Đã xác nhận gian lận", canReview: false };
  }
  if (s === "pending") return { label: "Chờ xử lý", canReview: false };
  return { label: status ?? "-", canReview: false };
}

export default function RiskTransactionTable({
  data,
  loading,
  highlightHighRisk = false,
  onReload,
  filters,
  onFilterChange,
  onApplyFilters,
  onResetFilters,
  pagination,
  onPageChange,
  onReview,
  reviewingId = null,
}) {
  const [expandedId, setExpandedId] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [showFilters, setShowFilters] = useState(false);

  const items = Array.isArray(data?.items)
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
  const canReview = typeof onReview === "function";
  const tableCols = canReview ? 6 : 5;

  const reviewingSet = useMemo(
    () =>
      new Set(
        Array.isArray(reviewingId)
          ? reviewingId
          : [reviewingId].filter(Boolean),
      ),
    [reviewingId],
  );

  const getDraft = (id) =>
    drafts[id] ?? {
      is_fraud: true,
      approve_transaction: false,
      notes: "",
    };

  const updateDraft = (id, patch) => {
    setDrafts((prev) => ({
      ...prev,
      [id]: { ...getDraft(id), ...patch },
    }));
  };

  const handleFilterChange = (key, value) => {
    if (!canFilter) return;
    onFilterChange((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (id) => {
    if (!id || !canReview) return;
    const draft = getDraft(id);
    await onReview(id, {
      is_fraud: draft.is_fraud,
      approve_transaction: draft.is_fraud ? false : draft.approve_transaction,
      notes: draft.notes?.trim() || null,
    });
    setExpandedId(null);
  };

  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-card dark:border-gray-700">
        <div className="border-b border-border px-4 py-3 dark:border-gray-700">
          <div className="h-5 w-40 animate-pulse rounded bg-muted" />
        </div>
        <div className="divide-y divide-border p-4 dark:divide-gray-700">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex justify-between py-3">
              <div className="h-4 flex-1 animate-pulse rounded bg-muted" />
              <div className="ml-4 h-4 w-16 animate-pulse rounded bg-muted" />
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
              type="button"
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center gap-2 text-sm font-medium text-foreground"
            >
              <HiOutlineFilter className="h-4 w-4" />
              Bộ lọc
            </button>
          </div>
        )}
        {canFilter && showFilters && (
          <div className="border-b border-border bg-muted/30 p-4 dark:border-gray-700">
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              <input
                type="date"
                value={filters.start_date}
                onChange={(e) => handleFilterChange("start_date", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground dark:border-gray-700"
              />
              <input
                type="date"
                value={filters.end_date}
                onChange={(e) => handleFilterChange("end_date", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground dark:border-gray-700"
              />
              <input
                type="number"
                min="0"
                max="1"
                step="0.01"
                placeholder="Min risk score (0-1)"
                value={filters.min_risk_score}
                onChange={(e) =>
                  handleFilterChange("min_risk_score", e.target.value)
                }
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground dark:border-gray-700"
              />
            </div>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={onApplyFilters}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                Áp dụng
              </button>
              <button
                type="button"
                onClick={onResetFilters}
                className="rounded-lg border border-border px-4 py-2 text-sm text-foreground hover:bg-muted dark:border-gray-700"
              >
                Đặt lại
              </button>
            </div>
          </div>
        )}
        <div className="p-12 text-center">
          <p className="text-muted-foreground">Không có giao dịch rủi ro cao</p>
          {typeof onReload === "function" && (
            <button
              type="button"
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
      <div className="flex items-center justify-between border-b border-border px-4 py-3 dark:border-gray-700">
        <h3 className="text-base font-semibold text-foreground">Lịch sử rủi ro</h3>
        <div className="flex items-center gap-2">
          {canFilter && (
            <button
              type="button"
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
              type="button"
              onClick={onReload}
              className="rounded-lg border border-border px-3 py-1.5 text-sm text-foreground hover:bg-muted dark:border-gray-700"
            >
              <HiOutlineRefresh className="inline h-4 w-4" />
            </button>
          )}
        </div>
      </div>

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
                onChange={(e) => handleFilterChange("start_date", e.target.value)}
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
                Điểm rủi ro tối thiểu (0-1)
              </label>
              <input
                type="number"
                min="0"
                max="1"
                step="0.01"
                placeholder="Vi du: 0.6"
                value={filters.min_risk_score}
                onChange={(e) =>
                  handleFilterChange("min_risk_score", e.target.value)
                }
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground dark:border-gray-700"
              />
            </div>
          </div>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={onApplyFilters}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Ap dung
            </button>
            <button
              type="button"
              onClick={onResetFilters}
              className="rounded-lg border border-border px-4 py-2 text-sm text-foreground hover:bg-muted dark:border-gray-700"
            >
              Đặt lại
            </button>
          </div>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50 text-left text-xs font-medium text-muted-foreground dark:border-gray-700">
              <th className="px-4 py-3">Mã giao dịch</th>
              <th className="px-4 py-3">Số tiền</th>
              <th className="px-4 py-3">Diểm rủi ro</th>
              <th className="px-4 py-3">Trạng thái</th>
              <th className="px-4 py-3">Thời gian</th>
              {canReview && <th className="px-4 py-3">Thao tác</th>}
            </tr>
          </thead>

          <tbody className="divide-y divide-border dark:divide-gray-700">
            {items.map((row) => {
              const txId = row.transaction_id;
              const riskScore = Number(row.risk_score ?? 0);
              const riskMeta = getRiskMeta(riskScore);
              const riskClass = highlightHighRisk ? riskMeta.color : "";
              const isOpen = expandedId === txId;
              const isSubmitting = reviewingSet.has(txId);
              const reviewStatusMeta = getReviewStatusMeta(row.review_status);
              const isFlagged = reviewStatusMeta.canReview;

              return (
                <Fragment key={txId ?? row.reference}>
                  <tr className="hover:bg-muted/30 dark:hover:bg-gray-800/30">
                    <td className="px-4 py-3 font-mono text-xs text-blue-600 dark:text-blue-400">
                      {row.reference ?? "-"}
                    </td>
                    <td className="px-4 py-3 font-semibold">
                      {formatAmount(row.amount)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${riskClass}`}
                      >
                        {(riskScore * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {reviewStatusMeta.label}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {formatDate(row.created_at)}
                    </td>

                    {canReview && (
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          disabled={!isFlagged || isSubmitting}
                          onClick={() => setExpandedId(isOpen ? null : txId)}
                          className="rounded-lg border border-border px-3 py-1.5 text-xs text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700"
                        >
                          {!isFlagged
                            ? "Đã duyệt"
                            : isOpen
                            ? "Đóng"
                            : "Duyệt"}
                        </button>
                      </td>
                    )}
                  </tr>

                  {canReview && isOpen && isFlagged && (
                    <tr>
                      <td className="px-4 pb-4" colSpan={tableCols}>
                        <RiskReviewForm
                          draft={getDraft(txId)}
                          submitting={isSubmitting}
                          onChange={(patch) => updateDraft(txId, patch)}
                          onSubmit={() => handleSubmit(txId)}
                        />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between border-t border-border px-4 py-3 text-sm text-muted-foreground dark:border-gray-700">
        <span>
          Hiển thị {items.length} / {effectiveTotal} giao dịch
        </span>
        {canPaginate && totalPages > 1 && (
          <div className="flex items-center gap-2">
            <button
              type="button"
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
              type="button"
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
