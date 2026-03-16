import PropTypes from "prop-types";
import {
  HiOutlineCurrencyDollar,
  HiOutlineDocumentText,
  HiOutlineExclamation,
  HiOutlineTrendingDown,
} from "react-icons/hi";

const LOCALE = "vi-VN";
const FRAUD_RATE_DECIMALS = 1;

const METRIC_CONFIG = [
  {
    key: "total_transactions",
    label: "Tổng giao dịch",
    icon: HiOutlineDocumentText,
    format: (v) => Number(v ?? 0).toLocaleString(LOCALE),
    color: "blue",
  },
  {
    key: "suspicious_transactions",
    label: "Nghi ngờ",
    icon: HiOutlineExclamation,
    format: (v) => Number(v ?? 0).toLocaleString(LOCALE),
    color: "amber",
  },
  {
    key: "fraud_rate",
    label: "Tỷ lệ gian lận",
    icon: HiOutlineTrendingDown,
    format: (v) => `${Number(v ?? 0).toFixed(FRAUD_RATE_DECIMALS)}%`,
    color: "red",
  },
  {
    key: "total_amount",
    label: "Tổng số tiền",
    icon: HiOutlineCurrencyDollar,
    format: (v) => `${Number(v ?? 0).toLocaleString(LOCALE)} ₫`,
    color: "emerald",
  },
];

const COLOR_STYLES = {
  blue: {
    bg: "bg-blue-50 dark:bg-blue-950/30",
    icon: "text-blue-600 dark:text-blue-400",
    border: "border-blue-200 dark:border-blue-800",
  },
  amber: {
    bg: "bg-amber-50 dark:bg-amber-950/30",
    icon: "text-amber-600 dark:text-amber-400",
    border: "border-amber-200 dark:border-amber-800",
  },
  red: {
    bg: "bg-red-50 dark:bg-red-950/30",
    icon: "text-red-600 dark:text-red-400",
    border: "border-red-200 dark:border-red-800",
  },
  emerald: {
    bg: "bg-emerald-50 dark:bg-emerald-950/30",
    icon: "text-emerald-600 dark:text-emerald-400",
    border: "border-emerald-200 dark:border-emerald-800",
  },
};

function MetricSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {METRIC_CONFIG.map(({ key }) => (
        <div
          key={key}
          className="rounded-lg border border-border bg-card p-5 dark:border-gray-700"
        >
          <div className="mb-3 h-4 w-24 animate-pulse rounded bg-muted" />
          <div className="h-8 w-20 animate-pulse rounded bg-muted" />
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-border bg-card p-12 text-center dark:border-gray-700">
      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
        <HiOutlineDocumentText className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="mb-2 text-lg font-semibold text-foreground">
        Chưa Có Giao Dịch
      </h3>
      <p className="text-sm text-muted-foreground">
        Không có giao dịch nào trong khoảng thời gian này
      </p>
    </div>
  );
}

function MetricCard({ metric, value }) {
  const { label, icon: Icon, format, color } = metric;
  const styles = COLOR_STYLES[color];

  return (
    <div className="rounded-lg border border-border bg-card p-5 transition-shadow hover:shadow-md dark:border-gray-700">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="mb-2 text-sm text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold text-foreground">{format(value)}</p>
        </div>
        <div className={`rounded-lg ${styles.bg} p-3`}>
          <Icon className={`h-6 w-6 ${styles.icon}`} />
        </div>
      </div>
    </div>
  );
}

MetricCard.propTypes = {
  metric: PropTypes.shape({
    key: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired,
    icon: PropTypes.elementType.isRequired,
    format: PropTypes.func.isRequired,
    color: PropTypes.string.isRequired,
  }).isRequired,
  value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
};

export default function TransactionMetrics({ data, loading }) {
  if (loading) {
    return <MetricSkeleton />;
  }

  const isEmpty = !data || Object.keys(data).length === 0;

  if (isEmpty) {
    return <EmptyState />;
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {METRIC_CONFIG.map((metric) => (
        <MetricCard key={metric.key} metric={metric} value={data[metric.key]} />
      ))}
    </div>
  );
}

TransactionMetrics.propTypes = {
  data: PropTypes.shape({
    total_transactions: PropTypes.number,
    suspicious_transactions: PropTypes.number,
    fraud_rate: PropTypes.number,
    total_amount: PropTypes.number,
  }),
  loading: PropTypes.bool,
};

TransactionMetrics.defaultProps = {
  data: null,
  loading: false,
};
