import { useEffect, useState, useCallback, useMemo } from "react";
import { useTransaction } from "../../hooks/transaction/useTransaction";
import TransactionMetrics from "../transaction/TransactionMetrics";
import TransactionTrendChart from "../transaction/TransactionTrendChart";
import TransactionTable from "../transaction/TransactionTable";
import RiskTransactionTable from "../transaction/RiskTransactionTable";

const DEFAULT_HISTORY_FILTERS = {
  start_date: "",
  end_date: "",
  transaction_type: "",
  transaction_category: "",
  status: "",
  min_amount: "",
  max_amount: "",
};

const DEFAULT_PAGINATION = {
  page: 1,
  pageSize: 10,
};

function buildHistoryParams(filters, pagination) {
  const { page, pageSize } = pagination;

  const params = {
    skip: (page - 1) * pageSize,
    limit: pageSize,
  };

  if (filters.start_date) params.start_date = `${filters.start_date}T00:00:00`;
  if (filters.end_date) params.end_date = `${filters.end_date}T23:59:59`;
  if (filters.transaction_type)
    params.transaction_type = filters.transaction_type;
  if (filters.transaction_category)
    params.transaction_category = filters.transaction_category;
  if (filters.status) params.status = filters.status;
  if (filters.min_amount !== "") params.min_amount = filters.min_amount;
  if (filters.max_amount !== "") params.max_amount = filters.max_amount;

  return params;
}

export default function TransactionDashboard() {
  const {
    getTransactionMetrics,
    getTransactionTrend,
    getAllUserTransactionHistory,
    getAllUserRiskHistory,
  } = useTransaction();

  const [metrics, setMetrics] = useState(null);
  const [trendData, setTrendData] = useState(null);
  const [historyData, setHistoryData] = useState(null);
  const [riskData, setRiskData] = useState(null);
  const [historyFilters, setHistoryFilters] = useState(DEFAULT_HISTORY_FILTERS);
  const [historyPagination, setHistoryPagination] =
    useState(DEFAULT_PAGINATION);

  const [loading, setLoading] = useState({
    metrics: false,
    trend: false,
    history: false,
    risk: false,
  });

  const [errors, setErrors] = useState({
    metrics: null,
    trend: null,
    history: null,
    risk: null,
  });

  // ===== Tải Metrics + Trend =====
  useEffect(() => {
    let cancelled = false;

    (async () => {
      setLoading((s) => ({ ...s, metrics: true, trend: true }));
      setErrors((s) => ({ ...s, metrics: null, trend: null }));

      try {
        const [m, t] = await Promise.all([
          getTransactionMetrics(),
          getTransactionTrend(),
        ]);
        if (!cancelled) {
          setMetrics(m);
          setTrendData(t);
        }
      } catch (err) {
        if (!cancelled) {
          setErrors((s) => ({
            ...s,
            metrics: "Không thể tải chỉ số thống kê",
            trend: "Không thể tải xu hướng",
          }));
        }
      } finally {
        if (!cancelled) {
          setLoading((s) => ({ ...s, metrics: false, trend: false }));
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [getTransactionMetrics, getTransactionTrend]);

  // ===== Tải Lịch Sử Giao Dịch =====
  const fetchHistory = useCallback(
    async (filters, pagination) => {
      setLoading((s) => ({ ...s, history: true }));
      setErrors((s) => ({ ...s, history: null }));

      try {
        const data = await getAllUserTransactionHistory(
          buildHistoryParams(filters, pagination),
        );
        setHistoryData(data);
        setHistoryPagination(pagination);
      } catch (err) {
        setHistoryData(null);
        setErrors((s) => ({
          ...s,
          history: "Không thể tải lịch sử giao dịch",
        }));
      } finally {
        setLoading((s) => ({ ...s, history: false }));
      }
    },
    [getAllUserTransactionHistory],
  );

  const loadHistory = useCallback(() => {
    fetchHistory(historyFilters, historyPagination);
  }, [fetchHistory, historyFilters, historyPagination]);

  // ===== Tải Giao Dịch Rủi Ro =====
  const loadRisk = useCallback(async () => {
    setLoading((s) => ({ ...s, risk: true }));
    setErrors((s) => ({ ...s, risk: null }));

    try {
      const data = await getAllUserRiskHistory({
        skip: 0,
        limit: 50,
      });
      setRiskData(data);
    } catch (err) {
      setRiskData(null);
      setErrors((s) => ({ ...s, risk: "Không thể tải lịch sử rủi ro" }));
    } finally {
      setLoading((s) => ({ ...s, risk: false }));
    }
  }, [getAllUserRiskHistory]);

  // ===== Tải Dữ Liệu Ban Đầu =====
  useEffect(() => {
    fetchHistory(DEFAULT_HISTORY_FILTERS, DEFAULT_PAGINATION);
    loadRisk();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ===== Xử Lý Sự Kiện =====
  const handleApplyFilters = useCallback(() => {
    fetchHistory(historyFilters, { ...historyPagination, page: 1 });
  }, [fetchHistory, historyFilters, historyPagination]);

  const handleResetFilters = useCallback(() => {
    setHistoryFilters(DEFAULT_HISTORY_FILTERS);
    fetchHistory(DEFAULT_HISTORY_FILTERS, DEFAULT_PAGINATION);
  }, [fetchHistory]);

  const handlePageChange = useCallback(
    (page) => {
      fetchHistory(historyFilters, { ...historyPagination, page });
    },
    [fetchHistory, historyFilters, historyPagination],
  );

  // ===== Thông Báo Lỗi =====
  const errorMessage = useMemo(() => {
    const errorList = Object.values(errors).filter(Boolean);
    return errorList.length > 0 ? errorList.join(". ") : null;
  }, [errors]);

  return (
    <div className="min-h-screen bg-gray-50 p-6 dark:bg-gray-900">
      <div className="mx-auto max-w-7xl space-y-6">
        {/* Header */}
        <div className="rounded-lg border border-border bg-card p-6 dark:border-gray-700">
          <h1 className="text-2xl font-bold text-foreground">
            Giám Sát Giao Dịch & Gian Lận
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Theo dõi và phân tích các giao dịch nghi ngờ
          </p>
        </div>

        {/* Error Message */}
        {errorMessage && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-950/30">
            <p className="text-sm text-red-800 dark:text-red-400">
              {errorMessage}
            </p>
          </div>
        )}

        {/* Metrics */}
        <TransactionMetrics data={metrics} loading={loading.metrics} />

        {/* Trend Chart */}
        <TransactionTrendChart data={trendData} loading={loading.trend} />

        {/* Tables */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Transaction History */}
          <TransactionTable
            data={historyData}
            loading={loading.history}
            onReload={loadHistory}
            filters={historyFilters}
            onFilterChange={setHistoryFilters}
            onApplyFilters={handleApplyFilters}
            onResetFilters={handleResetFilters}
            pagination={{
              page: historyPagination.page,
              pageSize: historyPagination.pageSize,
              total: historyData?.total ?? 0,
            }}
            onPageChange={handlePageChange}
          />

          {/* Risk Transactions */}
          <RiskTransactionTable
            data={riskData}
            loading={loading.risk}
            onReload={loadRisk}
            highlightHighRisk
          />
        </div>
      </div>
    </div>
  );
}
