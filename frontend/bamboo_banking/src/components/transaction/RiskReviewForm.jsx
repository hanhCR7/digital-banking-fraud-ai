export default function RiskReviewForm({
  draft,
  onChange,
  onSubmit,
  submitting,
}) {
  return (
    <div className="rounded-md border border-border bg-muted/30 p-3 dark:border-gray-700 dark:bg-gray-800/30">
      <div className="grid gap-3 md:grid-cols-3">
        <label className="space-y-1 text-xs text-muted-foreground">
          Quyết định
          <select
            value={draft.is_fraud ? "fraud" : "safe"}
            onChange={(e) => onChange({ is_fraud: e.target.value === "fraud" })}
            className="w-full rounded border px-2 py-1"
          >
            <option value="fraud">Gian lận</option>
            <option value="safe">An toàn</option>
          </select>
        </label>

        <label className="space-y-1 text-xs text-muted-foreground">
          Phê duyệt giao dịch
          <select
            value={draft.approve_transaction ? "yes" : "no"}
            onChange={(e) =>
              onChange({
                approve_transaction: e.target.value === "yes",
              })
            }
            className="w-full rounded border px-2 py-1"
          >
            <option value="no">Không</option>
            <option value="yes">Có</option>
          </select>
        </label>

        <label className="space-y-1 text-xs text-muted-foreground">
          Ghi chú
          <input
            type="text"
            value={draft.notes}
            onChange={(e) => onChange({ notes: e.target.value })}
            placeholder="Ghi chú (không bắt buộc)"
            className="w-full rounded border px-2 py-1"
          />
        </label>
      </div>

      <div className="mt-3 flex justify-end">
        <button
          onClick={onSubmit}
          disabled={submitting}
          className="rounded bg-foreground px-3 py-1.5 text-xs text-background disabled:opacity-60"
        >
          {submitting ? "Đang gửi..." : "Gửi đánh giá"}
        </button>
      </div>
    </div>
  );
}
