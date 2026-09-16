/**
 * Mock dashboard service for development.
 *
 * Provides deterministic mock data that can be replaced by
 * real HTTP implementation without changing dashboard components.
 */
import type { DashboardSummary } from "./dashboard-types";

/**
 * Deterministic mock data generator.
 * Returns the same data on every call for consistent UI testing.
 */
export function getMockDashboardSummary(): DashboardSummary {
  return {
    resources: {
      targets: {
        total: 3,
        secondaryLabel: "2 connected",
      },
      datasets: {
        total: 5,
        secondaryLabel: "1 updated today",
      },
      tests: {
        total: 12,
        secondaryLabel: "8 active",
      },
    },
    activeRuns: [
      {
        runId: "run-001",
        testName: "Grounding Regression",
        targetName: "Grounding-RAG v3",
        datasetName: "QKD Benchmark",
        status: "running",
        progress: {
          completed: 162,
          total: 250,
          percent: 64.8,
        },
        metrics: {
          completed: 160,
          failed: 2,
          remaining: 88,
          running: 4,
        },
        keyMetrics: [
          {
            metricId: "recall-at-5",
            label: "Recall@5",
            value: 0.91,
            unit: "",
          },
          {
            metricId: "faithfulness",
            label: "Faithfulness",
            value: 0.94,
            unit: "",
          },
        ],
        startedAt: new Date(Date.now() - 222000).toISOString(), // 3m 42s ago
      },
    ],
    recentRuns: [
      {
        runId: "run-002",
        testName: "Grounding Regression",
        targetName: "Grounding-RAG v3",
        datasetName: "QKD Benchmark",
        status: "completed",
        progress: {
          completed: 250,
          total: 250,
          percent: 100,
        },
        metrics: {
          completed: 248,
          failed: 2,
          remaining: 0,
        },
        keyMetrics: [
          {
            metricId: "recall-at-5",
            label: "Recall@5",
            value: 0.912,
            unit: "",
            delta: { value: 0.031, direction: "higher-is-better" },
          },
        ],
        startedAt: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
        duration: 221, // 3m 41s
      },
      {
        runId: "run-003",
        testName: "Citation Benchmark",
        targetName: "RAG v2",
        datasetName: "Citation Set",
        status: "completed",
        progress: {
          completed: 100,
          total: 100,
          percent: 100,
        },
        metrics: {
          completed: 100,
          failed: 0,
          remaining: 0,
        },
        keyMetrics: [
          {
            metricId: "recall-at-5",
            label: "Recall@5",
            value: 0.884,
            unit: "",
            delta: { value: -0.028, direction: "higher-is-better" },
          },
        ],
        startedAt: new Date(Date.now() - 7200000).toISOString(), // 2 hours ago
        duration: 78, // 1m 18s
      },
      {
        runId: "run-004",
        testName: "Full Benchmark",
        targetName: "RAG v3",
        datasetName: "Benchmark v1",
        status: "failed",
        progress: {
          completed: 42,
          total: 250,
          percent: 16.8,
        },
        metrics: {
          completed: 40,
          failed: 2,
          remaining: 208,
        },
        keyMetrics: [],
        startedAt: new Date(Date.now() - 14400000).toISOString(), // 4 hours ago
        duration: 42,
      },
    ],
    latestCompletedRun: {
      runId: "run-002",
      testName: "Grounding Regression · Run #37",
      targetName: "Grounding-RAG v3",
      datasetName: "QKD Benchmark · v1",
      status: "completed",
      metrics: [
        {
          metricId: "recall-at-5",
          label: "Recall@5",
          value: 0.912,
          unit: "",
          delta: { value: 0.031, direction: "higher-is-better" },
        },
        {
          metricId: "faithfulness",
          label: "Faithfulness",
          value: 0.941,
          unit: "",
          delta: { value: 0.017, direction: "higher-is-better" },
        },
        {
          metricId: "correctness",
          label: "Correctness",
          value: 0.863,
          unit: "",
          delta: { value: -0.004, direction: "higher-is-better" },
        },
        {
          metricId: "latency",
          label: "Latency",
          value: 760,
          unit: "ms",
          delta: { value: -60, direction: "lower-is-better" },
        },
      ],
      startedAt: new Date(Date.now() - 3600000).toISOString(),
      completedAt: new Date().toISOString(),
      duration: 221,
    },
    latestComparison: {
      baselineRunId: "run-001",
      baselineName: "Run #36",
      comparisonRunId: "run-002",
      comparisonName: "Run #37",
      metrics: [
        {
          metricId: "recall-at-5",
          label: "Recall@5",
          previousValue: 0.863,
          currentValue: 0.912,
          absoluteDelta: 0.049,
          relativeDelta: 5.7,
          direction: "higher-is-better",
        },
        {
          metricId: "faithfulness",
          label: "Faithfulness",
          previousValue: 0.924,
          currentValue: 0.941,
          absoluteDelta: 0.017,
          relativeDelta: 1.8,
          direction: "higher-is-better",
        },
        {
          metricId: "correctness",
          label: "Correctness",
          previousValue: 0.87,
          currentValue: 0.863,
          absoluteDelta: -0.007,
          relativeDelta: -0.8,
          direction: "higher-is-better",
        },
        {
          metricId: "latency",
          label: "Latency",
          previousValue: 820,
          currentValue: 760,
          absoluteDelta: -60,
          relativeDelta: -7.3,
          direction: "lower-is-better",
          unit: "ms",
        },
      ],
      comparedAt: new Date().toISOString(),
    },
  };
}

/**
 * Mock empty state - no resources at all.
 */
export function getMockEmptyDashboard(): DashboardSummary {
  return {
    resources: {
      targets: { total: 0 },
      datasets: { total: 0 },
      tests: { total: 0 },
    },
    activeRuns: [],
    recentRuns: [],
    latestCompletedRun: null,
    latestComparison: null,
  };
}

/**
 * Mock ready-to-evaluate state - resources exist but no runs yet.
 */
export function getMockReadyDashboard(): DashboardSummary {
  return {
    resources: {
      targets: { total: 1, secondaryLabel: "Grounding-RAG" },
      datasets: { total: 1, secondaryLabel: "QKD Benchmark · 250 cases" },
      tests: { total: 0 },
    },
    activeRuns: [],
    recentRuns: [],
    latestCompletedRun: null,
    latestComparison: null,
  };
}
