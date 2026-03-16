export const RISK_LEVELS = [
  {
    min: 0.0,
    max: 0.3,
    level: "Thấp",
    color:
      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
    description: "Giao dịch bình thường, rủi ro thấp",
  },
  {
    min: 0.3,
    max: 0.6,
    level: "Trung bình",
    color:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
    description: "Có dấu hiệu bất thường, cần theo dõi",
  },
  {
    min: 0.6,
    max: 0.8,
    level: "Cao",
    color:
      "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
    description: "Nguy cơ gian lận cao, cần rà soát",
  },
  {
    min: 0.8,
    max: 1.0,
    level: "Rất cao",
    color: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
    description: "Khả năng gian lận nghiêm trọng (AML Alert)",
  },
];

export function getRiskMeta(score = 0) {
  const s = Number(score);
  return (
    RISK_LEVELS.find((r) => s >= r.min && s < r.max) ??
    RISK_LEVELS[RISK_LEVELS.length - 1]
  );
}
