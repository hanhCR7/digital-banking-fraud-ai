import { useState, useEffect, useCallback } from "react";
import { useTransaction } from "../hooks/transaction/useTransaction";
import TransactionTable from "../components/transaction/TransactionTable";

const DEFAULT_HISTORY_FILTERS = {
  start_date: "",
  end_date: "",
  transaction_type: "",
  transaction_category: "",
  status: "",
  min_amount: "",
  max_amount: "",
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

export default function TransactionsPage() {
  const { getAllUserTransactionHistory } = useTransaction();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState(DEFAULT_HISTORY_FILTERS);
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 20,
  });

  const fetchHistory = useCallback(
    async (nextFilters, nextPagination) => {
      setLoading(true);
      try {
        const res = await getAllUserTransactionHistory(
          buildHistoryParams(nextFilters, nextPagination),
        );
        setData(res);
        setPagination(nextPagination);
      } catch {
        setData(null);
      } finally {
        setLoading(false);
      }
    },
    [getAllUserTransactionHistory],
  );

  const load = useCallback(async () => {
    await fetchHistory(filters, pagination);
  }, [fetchHistory, filters, pagination]);

  useEffect(() => {
    fetchHistory(DEFAULT_HISTORY_FILTERS, { page: 1, pageSize: 10 });
  }, [fetchHistory]);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-foreground">Transactions</h1>
      <TransactionTable
        data={data}
        loading={loading}
        onReload={load}
        filters={filters}
        onFilterChange={setFilters}
        onApplyFilters={() => fetchHistory(filters, { ...pagination, page: 1 })}
        onResetFilters={() => {
          setFilters(DEFAULT_HISTORY_FILTERS);
          fetchHistory(DEFAULT_HISTORY_FILTERS, { page: 1, pageSize: 10 });
        }}
        pagination={{
          page: pagination.page,
          pageSize: pagination.pageSize,
          total: data?.total ?? 0,
        }}
        onPageChange={(page) =>
          fetchHistory(filters, {
            ...pagination,
            page,
          })
        }
      />
    </div>
  );
}
