/**
 * Shared metric metadata for result views.
 *
 * Metric values are persisted as numeric values without display metadata. This
 * catalog is the frontend boundary that makes their meaning explicit and
 * prevents statistics such as a sum of percentages from being presented as a
 * useful result.
 */

export type MetricUnit =
  "percent" | "tokens" | "milliseconds" | "seconds" | "currency" | "count" | "number";

export type MetricDirection = "higher_is_better" | "lower_is_better" | "neutral";

export type MetricStatistic =
  "count" | "sum" | "mean" | "median" | "min" | "max" | "p50" | "p95" | "p99";

export interface MetricCatalogEntry {
  metricId: string;
  family: string;
  label: string;
  unit: MetricUnit;
  direction: MetricDirection;
  validStatistics: readonly MetricStatistic[];
}

const DISTRIBUTION_STATISTICS: readonly MetricStatistic[] = [
  "count",
  "mean",
  "median",
  "min",
  "max",
  "p50",
  "p95",
  "p99",
];

const RATE_STATISTICS: readonly MetricStatistic[] = [
  "count",
  "mean",
  "median",
  "min",
  "max",
  "p50",
  "p95",
  "p99",
];

const TOKEN_STATISTICS: readonly MetricStatistic[] = [
  "count",
  "sum",
  ...DISTRIBUTION_STATISTICS.filter((statistic) => statistic !== "count"),
];

const COST_STATISTICS: readonly MetricStatistic[] = [
  "count",
  "sum",
  ...DISTRIBUTION_STATISTICS.filter((statistic) => statistic !== "count"),
];

const CATALOG: Record<string, MetricCatalogEntry> = {
  "answer.exact_match": {
    metricId: "answer.exact_match",
    family: "Answer",
    label: "Exact match",
    unit: "percent",
    direction: "higher_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "answer.normalized_exact_match": {
    metricId: "answer.normalized_exact_match",
    family: "Answer",
    label: "Normalized exact match",
    unit: "percent",
    direction: "higher_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "answer.token_f1": {
    metricId: "answer.token_f1",
    family: "Answer",
    label: "Token F1",
    unit: "percent",
    direction: "higher_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "answer.token_precision": {
    metricId: "answer.token_precision",
    family: "Answer",
    label: "Token precision",
    unit: "percent",
    direction: "higher_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "answer.token_recall": {
    metricId: "answer.token_recall",
    family: "Answer",
    label: "Token recall",
    unit: "percent",
    direction: "higher_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "citation.attribution_rate": {
    metricId: "citation.attribution_rate",
    family: "Citations",
    label: "Attribution rate",
    unit: "percent",
    direction: "higher_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "citation.broken": {
    metricId: "citation.broken",
    family: "Citations",
    label: "Broken citations",
    unit: "percent",
    direction: "lower_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "citation.resolution": {
    metricId: "citation.resolution",
    family: "Citations",
    label: "Resolution rate",
    unit: "percent",
    direction: "higher_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "cost.per_token": {
    metricId: "cost.per_token",
    family: "Cost",
    label: "Cost per token",
    unit: "currency",
    direction: "lower_is_better",
    validStatistics: DISTRIBUTION_STATISTICS,
  },
  "cost.total": {
    metricId: "cost.total",
    family: "Cost",
    label: "Total cost",
    unit: "currency",
    direction: "lower_is_better",
    validStatistics: COST_STATISTICS,
  },
  "performance.generation_latency_ms": {
    metricId: "performance.generation_latency_ms",
    family: "Performance",
    label: "Generation latency",
    unit: "milliseconds",
    direction: "lower_is_better",
    validStatistics: DISTRIBUTION_STATISTICS,
  },
  "performance.retrieval_latency_ms": {
    metricId: "performance.retrieval_latency_ms",
    family: "Performance",
    label: "Retrieval latency",
    unit: "milliseconds",
    direction: "lower_is_better",
    validStatistics: DISTRIBUTION_STATISTICS,
  },
  "performance.tokens_per_second": {
    metricId: "performance.tokens_per_second",
    family: "Performance",
    label: "Tokens per second",
    unit: "number",
    direction: "higher_is_better",
    validStatistics: DISTRIBUTION_STATISTICS,
  },
  "performance.total_latency_ms": {
    metricId: "performance.total_latency_ms",
    family: "Performance",
    label: "Total latency",
    unit: "milliseconds",
    direction: "lower_is_better",
    validStatistics: DISTRIBUTION_STATISTICS,
  },
  "reliability.availability": {
    metricId: "reliability.availability",
    family: "Reliability",
    label: "Availability",
    unit: "percent",
    direction: "higher_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "reliability.error_rate": {
    metricId: "reliability.error_rate",
    family: "Reliability",
    label: "Error rate",
    unit: "percent",
    direction: "lower_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "reliability.latency_p50": {
    metricId: "reliability.latency_p50",
    family: "Reliability",
    label: "Latency (p50)",
    unit: "milliseconds",
    direction: "lower_is_better",
    validStatistics: DISTRIBUTION_STATISTICS,
  },
  "reliability.latency_p99": {
    metricId: "reliability.latency_p99",
    family: "Reliability",
    label: "Latency (p99)",
    unit: "milliseconds",
    direction: "lower_is_better",
    validStatistics: DISTRIBUTION_STATISTICS,
  },
  "reliability.success_rate": {
    metricId: "reliability.success_rate",
    family: "Reliability",
    label: "Success rate",
    unit: "percent",
    direction: "higher_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "usage.input_tokens": {
    metricId: "usage.input_tokens",
    family: "Usage",
    label: "Input tokens",
    unit: "tokens",
    direction: "neutral",
    validStatistics: TOKEN_STATISTICS,
  },
  "usage.output_tokens": {
    metricId: "usage.output_tokens",
    family: "Usage",
    label: "Output tokens",
    unit: "tokens",
    direction: "neutral",
    validStatistics: TOKEN_STATISTICS,
  },
  "usage.total_tokens": {
    metricId: "usage.total_tokens",
    family: "Usage",
    label: "Total tokens",
    unit: "tokens",
    direction: "neutral",
    validStatistics: TOKEN_STATISTICS,
  },
  "retrieval.hit_at_k": {
    metricId: "retrieval.hit_at_k",
    family: "Retrieval",
    label: "Hit rate (at k)",
    unit: "percent",
    direction: "higher_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "retrieval.map_at_k": {
    metricId: "retrieval.map_at_k",
    family: "Retrieval",
    label: "Mean average precision (at k)",
    unit: "percent",
    direction: "higher_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "retrieval.mrr": {
    metricId: "retrieval.mrr",
    family: "Retrieval",
    label: "Mean reciprocal rank",
    unit: "percent",
    direction: "higher_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "retrieval.ndcg_at_k": {
    metricId: "retrieval.ndcg_at_k",
    family: "Retrieval",
    label: "NDCG (at k)",
    unit: "percent",
    direction: "higher_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "retrieval.precision_at_k": {
    metricId: "retrieval.precision_at_k",
    family: "Retrieval",
    label: "Precision (at k)",
    unit: "percent",
    direction: "higher_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "retrieval.r_precision": {
    metricId: "retrieval.r_precision",
    family: "Retrieval",
    label: "R-precision",
    unit: "percent",
    direction: "higher_is_better",
    validStatistics: RATE_STATISTICS,
  },
  "retrieval.recall_at_k": {
    metricId: "retrieval.recall_at_k",
    family: "Retrieval",
    label: "Recall (at k)",
    unit: "percent",
    direction: "higher_is_better",
    validStatistics: RATE_STATISTICS,
  },
};

const DEFAULT_STATISTICS: readonly MetricStatistic[] = [
  "count",
  "sum",
  "mean",
  "median",
  "min",
  "max",
  "p50",
  "p95",
  "p99",
];

const FAMILY_LABELS: Record<string, string> = {
  answer: "Answer",
  citation: "Citations",
  cost: "Cost",
  performance: "Performance",
  reliability: "Reliability",
  retrieval: "Retrieval",
  usage: "Usage",
};

function humanizeMetricPart(part: string): string {
  return part
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/** Return catalog metadata, with an explicit neutral fallback for new metrics. */
export function getMetricCatalogEntry(metricId: string): MetricCatalogEntry {
  const known = CATALOG[metricId];
  if (known) return known;

  const [familyId, ...parts] = metricId.split(".");
  return {
    metricId,
    family: FAMILY_LABELS[familyId ?? ""] ?? humanizeMetricPart(familyId ?? "Other"),
    label: humanizeMetricPart(parts.join(" ") || metricId),
    unit: "number",
    direction: "neutral",
    validStatistics: DEFAULT_STATISTICS,
  };
}

/** Return the readable family and metric label for a result metric. */
export function getMetricDisplayName(metricId: string): string {
  const entry = getMetricCatalogEntry(metricId);
  return `${entry.family} · ${entry.label}`;
}

/** Return the readable label for an aggregate statistic. */
export function formatMetricStatistic(statistic: string): string {
  if (statistic.toLowerCase() === "count") return "Count";
  if (/^p\d+$/i.test(statistic)) return statistic.toLowerCase();
  return humanizeMetricPart(statistic.toLowerCase());
}

/** Return whether a statistic is meaningful for the metric. */
export function isMetricStatisticAllowed(
  metricId: string,
  statistic: string
): statistic is MetricStatistic {
  return getMetricCatalogEntry(metricId).validStatistics.includes(
    statistic.toLowerCase() as MetricStatistic
  );
}

/** Return the preferred order for statistics in tabular result views. */
export function getMetricStatistics(metricIds: string[]): MetricStatistic[] {
  const order = DEFAULT_STATISTICS;
  return order.filter((statistic) =>
    metricIds.some((metricId) => isMetricStatisticAllowed(metricId, statistic))
  );
}

function formatNumber(value: number, maximumFractionDigits = 2): string {
  return value.toLocaleString(undefined, { maximumFractionDigits });
}

/** Format a metric value using its catalog unit and statistic context. */
export function formatCatalogMetricValue(
  value: unknown,
  metricId?: string,
  _statistic?: string
): string {
  if (value === null || value === undefined) return "—";

  if (typeof value === "number") {
    const entry = metricId ? getMetricCatalogEntry(metricId) : null;
    switch (entry?.unit) {
      case "percent":
        return `${(value * 100).toFixed(1)}%`;
      case "tokens":
        return `${formatNumber(value, 0)} tok`;
      case "milliseconds":
        return `${formatNumber(value, 0)} ms`;
      case "seconds":
        return `${formatNumber(value, 2)} s`;
      case "currency":
        return `$${value.toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 6,
        })}`;
      case "count":
        return formatNumber(value, 0);
      default:
        return formatNumber(value);
    }
  }

  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") return JSON.stringify(value);

  // eslint-disable-next-line @typescript-eslint/no-base-to-string
  return String(value);
}
