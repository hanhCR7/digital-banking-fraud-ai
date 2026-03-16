import { useCallback, useEffect, useState } from "react";
import { useTransaction } from "../hooks/transaction/useTransaction";
import RiskTransactionTable from "../components/transaction/RiskTransactionTable";

const DEFAULT_RISK_FILTERS = {
  start_date: "",
  end_date: "",
  min_risk_score: "",
};

function buildRiskParams(filters, pagination) {
  const { page, pageSize } = pagination;
  const params = {
    page,
    limit: pageSize,
  };

  if (filters.start_date) params.start_date = `${filters.start_date}T00:00:00`;
  if (filters.end_date) params.end_date = `${filters.end_date}T23:59:59`;
  if (filters.min_risk_score !== "")
    params.min_risk_score = Number(filters.min_risk_score);

  return params;
}

export default function RiskHistoryPage() {
  const { getAllUserRiskHistory, reviewTransaction } =
    useTransaction();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [reviewingId, setReviewingId] = useState(null);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(DEFAULT_RISK_FILTERS);
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 20,
  });

  const fetchRiskHistory = useCallback(
    async (nextFilters, nextPagination, cancelledRef) => {
      setLoading(true);
      try {
        const res = await getAllUserRiskHistory(
          buildRiskParams(nextFilters, nextPagination),
        );
        if (!cancelledRef?.current) setError(null);
        if (!cancelledRef?.current) setData(res);
        if (!cancelledRef?.current) setPagination(nextPagination);
      } catch {
        if (!cancelledRef?.current) setError("Failed to load risk history");
        if (!cancelledRef?.current) setData(null);
      } finally {
        if (!cancelledRef?.current) setLoading(false);
      }
    },
    [getAllUserRiskHistory],
  );

  const load = useCallback(async () => {
    await fetchRiskHistory(filters, pagination);
  }, [fetchRiskHistory, filters, pagination]);

  const handleReview = useCallback(
    async (transactionId, payload) => {
      setReviewingId(transactionId);
      try {
        await reviewTransaction(transactionId, payload);
        setError(null);
        await fetchRiskHistory(filters, pagination);
      } catch (err) {
        const detail = err?.response?.data?.detail;
        setError(
          detail?.message || detail || "Failed to review transaction",
        );
      } finally {
        setReviewingId(null);
      }
    },
    [fetchRiskHistory, filters, pagination, reviewTransaction],
  );

  useEffect(() => {
    const cancelledRef = { current: false };

    fetchRiskHistory(DEFAULT_RISK_FILTERS, { page: 1, pageSize: 20 }, cancelledRef);
    return () => {
      cancelledRef.current = true;
    };
  }, [fetchRiskHistory]);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-foreground">Risk History</h1>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <RiskTransactionTable
        data={data}
        loading={loading}
        highlightHighRisk
        onReload={load}
        filters={filters}
        onFilterChange={setFilters}
        onApplyFilters={() => fetchRiskHistory(filters, { ...pagination, page: 1 })}
        onResetFilters={() => {
          setFilters(DEFAULT_RISK_FILTERS);
          fetchRiskHistory(DEFAULT_RISK_FILTERS, { page: 1, pageSize: 20 });
        }}
        pagination={{
          page: pagination.page,
          pageSize: pagination.pageSize,
          total: data?.total ?? 0,
        }}
        onPageChange={(page) =>
          fetchRiskHistory(filters, {
            ...pagination,
            page,
          })
        }
        onReview={handleReview}
        reviewingId={reviewingId}
      />
    </div>
  );
}
