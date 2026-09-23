import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Surface } from "@/components/layout/surface";
import { Textarea } from "@/components/ui/textarea";
import { useBenchmarkList } from "@/features/datasets/use-datasets";
import type { BenchmarkInfo } from "@/features/datasets/dataset-types";
import { useTargetList } from "@/features/targets/use-targets";
import type { TargetSummary } from "@/features/targets/target-types";
import {
  isPersistentRunStatus,
  useCancelRun,
  useImportTestYaml,
  usePauseRun,
  useRecoverRun,
  useResumeRun,
  useRunStatus,
  useSelectAllMetrics,
  useSetTestMetrics,
  useStartTestRun,
  useTest,
  useTestMetrics,
  useTestRuns,
  useTestValidation,
  useUpdateTest,
} from "../use-tests";
import type {
  ExecutionConfig,
  MetricImportResult,
  RunStatus,
  RunStatusResponse,
  TestDefinitionInfo,
} from "../test-types";
import { setActiveRun } from "./active-run-store";
import { MetricSelector } from "./metric-selector";
import { RunProgress, terminalRunStatuses } from "./run-progress";
import { SearchableResourceSelect } from "./searchable-resource-select";
import { TestValidationStatus } from "./test-validation-status";

interface TestEditorProps {
  testId: string;
}

interface Draft {
  name: string;
  description: string;
  target_id: string | null;
  benchmark_id: string | null;
  execution_config: ExecutionConfig;
  seed: number | null;
  tags: string[];
  metadata: Record<string, unknown>;
}

function draftFromTest(test: TestDefinitionInfo): Draft {
  return {
    name: test.name,
    description: test.description ?? "",
    target_id: test.target_id,
    benchmark_id: test.benchmark_id,
    execution_config: test.execution_config,
    seed: test.seed,
    tags: test.tags,
    metadata: test.metadata,
  };
}

function hasBlockingRun(status: RunStatus | undefined): boolean {
  return (
    status === "PENDING" ||
    status === "QUEUED" ||
    status === "RUNNING" ||
    status === "PAUSING" ||
    status === "pending" ||
    status === "queued" ||
    status === "running"
  );
}

/** Persisted test editor and run monitor. */
export function TestEditor({ testId }: TestEditorProps) {
  const navigate = useNavigate();
  const { data: test, isLoading, error } = useTest(testId);
  const { data: metrics, isLoading: metricsLoading } = useTestMetrics(testId);
  const {
    data: benchmarks,
    isLoading: benchmarksLoading,
    error: benchmarksError,
  } = useBenchmarkList();
  const {
    data: targets,
    isLoading: targetsLoading,
    error: targetsError,
  } = useTargetList();
  const { data: runs, isLoading: runsLoading } = useTestRuns(testId);
  const { data: validation, isLoading: validationLoading } = useTestValidation(testId);
  const updateTest = useUpdateTest(testId);
  const setMetrics = useSetTestMetrics(testId);
  const selectAllMetrics = useSelectAllMetrics(testId);
  const importYaml = useImportTestYaml(testId);
  const startRun = useStartTestRun(testId);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [selectedMetricIds, setSelectedMetricIds] = useState<string[]>([]);
  const [dirty, setDirty] = useState(false);
  const [metricsDirty, setMetricsDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<MetricImportResult>();
  const [latestRunId, setLatestRunId] = useState("");

  useEffect(() => {
    if (!test) return;
    setDraft(draftFromTest(test));
    setDirty(false);
    setSaveError(null);
  }, [test]);

  useEffect(() => {
    if (!metrics || metricsDirty) return;
    setSelectedMetricIds(metrics.selected_metric_ids);
  }, [metrics, metricsDirty]);

  const latestRun = runs?.[0];
  useEffect(() => {
    setLatestRunId(latestRun?.run_id ?? "");
  }, [latestRun?.run_id]);
  const { data: runStatus } = useRunStatus(latestRunId);
  const currentRunStatus = runStatus?.status ?? latestRun?.status;
  const blockingRun = hasBlockingRun(currentRunStatus);

  useEffect(() => {
    if (!test || !latestRun || !currentRunStatus) return;
    if (isPersistentRunStatus(currentRunStatus)) {
      setActiveRun({ testId, runId: latestRun.run_id, testName: test.name });
    } else if (terminalRunStatuses.has(currentRunStatus)) {
      setActiveRun(null);
    }
  }, [currentRunStatus, latestRun, test, testId]);

  const saveDraft = useCallback(async () => {
    if (!draft || !test || saving) return;
    setSaving(true);
    setSaveError(null);
    try {
      await updateTest.mutateAsync({
        name: draft.name,
        description: draft.description || null,
        target_id: draft.target_id,
        benchmark_id: draft.benchmark_id,
        execution_config: draft.execution_config,
        seed: draft.seed,
        tags: draft.tags,
        metadata: draft.metadata,
      });
      if (metricsDirty) {
        await setMetrics.mutateAsync({
          mode: "EXPLICIT",
          selected_metrics: selectedMetricIds,
          judge_config: metrics?.judge_config ?? {},
          retrieval_config: metrics?.retrieval_config ?? {},
        });
      }
      setDirty(false);
      setMetricsDirty(false);
    } catch (saveFailure) {
      setSaveError(
        saveFailure instanceof Error ? saveFailure.message : "Unable to save changes."
      );
      throw saveFailure;
    } finally {
      setSaving(false);
    }
  }, [
    draft,
    metrics,
    metricsDirty,
    saving,
    selectedMetricIds,
    setMetrics,
    test,
    updateTest,
  ]);

  useEffect(() => {
    if (!dirty || !draft || blockingRun) return;
    const timer = window.setTimeout(() => {
      void saveDraft().catch(() => undefined);
    }, 900);
    return () => {
      window.clearTimeout(timer);
    };
  }, [blockingRun, dirty, draft, saveDraft]);

  const updateDraft = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    setDraft((current) => (current ? { ...current, [key]: value } : current));
    setDirty(true);
  };

  const updateExecution = (key: string, value: unknown) => {
    setDraft((current) =>
      current
        ? {
            ...current,
            execution_config: { ...current.execution_config, [key]: value },
          }
        : current
    );
    setDirty(true);
  };

  const toggleMetric = (metricId: string) => {
    const metric = metrics?.metrics.find(
      (candidate) => candidate.metric_id === metricId
    );
    if (!metric?.applicable) return;
    setSelectedMetricIds((current) =>
      current.includes(metric.metric_id)
        ? current.filter((metricId) => metricId !== metric.metric_id)
        : [...current, metric.metric_id]
    );
    setMetricsDirty(true);
  };

  const handleImport = async (file: File) => {
    try {
      const result = await importYaml.mutateAsync(file);
      setImportResult(result);
      setMetricsDirty(false);
    } catch (failure) {
      setSaveError(
        failure instanceof Error ? failure.message : "Unable to import YAML."
      );
    }
  };

  const handleSelectAll = async () => {
    try {
      const result = await selectAllMetrics.mutateAsync();
      setSelectedMetricIds(result.selected_metric_ids);
      setMetricsDirty(false);
    } catch (failure) {
      setSaveError(
        failure instanceof Error ? failure.message : "Unable to select metrics."
      );
    }
  };

  if (isLoading || !draft) {
    return (
      <div className="flex justify-center py-16">
        <Spinner size="lg" />
      </div>
    );
  }
  if (error || !test) {
    return (
      <Alert variant="error">
        <AlertDescription>
          Unable to load this test. {error instanceof Error ? error.message : ""}
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-text-primary">{test.name}</h1>
            <Badge
              variant={test.configuration_status === "READY" ? "success" : "warning"}
            >
              {test.configuration_status === "READY"
                ? "Ready"
                : "Not configured / Incomplete"}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-text-tertiary">
            Changes save automatically. You can return to this test any time.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              navigate("/tests");
            }}
          >
            Back to tests
          </Button>
          <Button
            variant="secondary"
            loading={saving}
            disabled={!draft.name.trim() || blockingRun}
            onClick={() => void saveDraft().catch(() => undefined)}
          >
            {dirty ? "Save changes" : "Saved"}
          </Button>
          <Button
            disabled={
              !validation?.valid ||
              dirty ||
              metricsDirty ||
              validationLoading ||
              blockingRun ||
              startRun.isPending
            }
            loading={startRun.isPending}
            onClick={() => void handleStart()}
          >
            Start
          </Button>
        </div>
      </div>

      {saveError && (
        <Alert variant="error">
          <AlertTitle>Could not save</AlertTitle>
          <AlertDescription>{saveError}</AlertDescription>
        </Alert>
      )}

      <Surface className="p-4">
        <div className="grid gap-4 md:grid-cols-2">
          <Input
            label="Test name"
            value={draft.name}
            onChange={(event) => {
              updateDraft("name", event.target.value);
            }}
            disabled={blockingRun}
          />
          <div className="space-y-1.5">
            <Label htmlFor="test-status">Configuration status</Label>
            <div
              id="test-status"
              className="flex min-h-10 items-center text-sm text-text-secondary"
            >
              {test.configuration_status.replaceAll("_", " ")}
            </div>
          </div>
        </div>
        <div className="mt-4">
          <Textarea
            label="Description (optional)"
            value={draft.description}
            onChange={(event) => {
              updateDraft("description", event.target.value);
            }}
            disabled={blockingRun}
            rows={3}
            placeholder="What is this evaluation for?"
          />
        </div>
      </Surface>

      <div className="grid gap-4 lg:grid-cols-2">
        <Surface className="p-4">
          <SearchableResourceSelect
            label="Benchmark"
            value={draft.benchmark_id}
            items={benchmarks ?? []}
            loading={benchmarksLoading}
            error={
              benchmarksError instanceof Error ? benchmarksError.message : undefined
            }
            placeholder="Choose one benchmark"
            getId={(benchmark: BenchmarkInfo) => benchmark.benchmark_id}
            getLabel={(benchmark: BenchmarkInfo) => benchmark.name}
            getMeta={(benchmark: BenchmarkInfo) =>
              `${benchmark.benchmark_id} · ${benchmark.case_count.toLocaleString()} cases`
            }
            onChange={(value) => {
              updateDraft("benchmark_id", value);
            }}
          />
        </Surface>
        <Surface className="p-4">
          <SearchableResourceSelect
            label="Target"
            value={draft.target_id}
            items={targets ?? []}
            loading={targetsLoading}
            error={targetsError instanceof Error ? targetsError.message : undefined}
            placeholder="Choose one configured target"
            getId={(target: TargetSummary) => target.target_id}
            getLabel={(target: TargetSummary) => target.name}
            getMeta={(target: TargetSummary) =>
              `${target.target_id} · ${target.configuration_status.replaceAll("_", " ")}`
            }
            onChange={(value) => {
              updateDraft("target_id", value);
            }}
          />
        </Surface>
      </div>

      <MetricSelector
        metrics={metrics}
        loading={metricsLoading}
        selected={selectedMetricIds}
        onToggle={toggleMetric}
        onSelectAll={() => void handleSelectAll()}
        onImport={(file) => void handleImport(file)}
        importResult={importResult}
        importing={importYaml.isPending}
      />

      <Surface className="p-4">
        <h2 className="text-sm font-semibold text-text-primary">Execution settings</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <Input
            label="Concurrency"
            type="number"
            min={1}
            value={String(draft.execution_config.concurrency ?? 1)}
            disabled={blockingRun}
            onChange={(event) => {
              updateExecution("concurrency", Number(event.target.value) || 1);
            }}
          />
          <Input
            label="Timeout per request (seconds)"
            type="number"
            min={1}
            value={String(draft.execution_config.timeout_per_request ?? 30)}
            disabled={blockingRun}
            onChange={(event) => {
              updateExecution("timeout_per_request", Number(event.target.value) || 30);
            }}
          />
          <Input
            label="Retries"
            type="number"
            min={0}
            value={String(draft.execution_config.retries ?? 0)}
            disabled={blockingRun}
            onChange={(event) => {
              updateExecution("retries", Number(event.target.value) || 0);
            }}
          />
        </div>
      </Surface>

      <Surface className="p-4">
        <h2 className="text-sm font-semibold text-text-primary">Readiness</h2>
        <div className="mt-3">
          <TestValidationStatus validation={validation} loading={validationLoading} />
        </div>
      </Surface>

      {latestRun && (
        <RunPanel
          testId={testId}
          testName={test.name}
          run={latestRun}
          status={runStatus}
          runsLoading={runsLoading}
        />
      )}

      {runs && runs.length > 1 && (
        <Surface className="p-4">
          <h2 className="text-sm font-semibold text-text-primary">Historical runs</h2>
          <div className="mt-3 divide-y divide-border-default">
            {runs.slice(1).map((run) => (
              <div
                key={run.run_id}
                className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
              >
                <span className="text-text-secondary">
                  {run.name}{" "}
                  <span className="text-xs text-text-tertiary">{run.run_id}</span>
                </span>
                <span className="text-xs capitalize text-text-tertiary">
                  {run.status.toLowerCase()}
                </span>
              </div>
            ))}
          </div>
        </Surface>
      )}
    </div>
  );

  async function handleStart() {
    if (!validation?.valid) return;
    try {
      if (dirty || metricsDirty) await saveDraft();
      const run = await startRun.mutateAsync();
      setLatestRunId(run.run_id);
      setActiveRun({ testId, runId: run.run_id, testName: test?.name ?? "Test" });
    } catch (failure) {
      setSaveError(
        failure instanceof Error ? failure.message : "Unable to start the run."
      );
    }
  }
}

interface RunPanelProps {
  testId: string;
  testName: string;
  run: { run_id: string; status: RunStatus };
  status?: RunStatusResponse;
  runsLoading: boolean;
}

function RunPanel({ testId, testName, run, status, runsLoading }: RunPanelProps) {
  const pause = usePauseRun(run.run_id, testId);
  const resume = useResumeRun(run.run_id, testId);
  const recover = useRecoverRun(run.run_id, testId);
  const cancel = useCancelRun(run.run_id, testId);
  const busy =
    pause.isPending || resume.isPending || recover.isPending || cancel.isPending;

  return (
    <Surface className="p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-text-primary">Latest run</h2>
          <p className="text-xs text-text-tertiary">
            {testName} · {run.run_id}
          </p>
        </div>
        {runsLoading && <Spinner size="sm" />}
      </div>
      <RunProgress
        status={run.status}
        progress={status}
        onPause={() => void pause.mutateAsync()}
        onResume={() => void resume.mutateAsync()}
        onRecover={() => void recover.mutateAsync()}
        onCancel={() => void cancel.mutateAsync()}
        busy={busy}
      />
    </Surface>
  );
}
