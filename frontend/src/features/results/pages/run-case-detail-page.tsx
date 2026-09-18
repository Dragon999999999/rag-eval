/**
 * Case detail page - shows individual case execution details.
 */
import { useParams } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Surface } from "@/components/layout/surface";
import { Spinner } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { StatusBadge } from "@/components/ui/status-badge";
import type { AttemptSummary } from "../run-types";
import { useRunCase, useCaseAttempts, useObservation, useCaseMetrics } from "../use-runs";
import { formatCaseStatus, formatAnswerability, getAnswerabilityVariant, formatElapsedTime, formatMetricValue } from "../run-formatters";

export function RunCaseDetailPage() {
  const { runId, caseId } = useParams<{ runId: string; caseId: string }>();

  const { data: caseExec, isLoading: caseLoading, error: caseError } = useRunCase(runId || "", caseId || "");
  const { data: attempts } = useCaseAttempts(runId || "", caseId || "");
  const { data: observation } = useObservation(runId || "", caseId || "");
  const { data: metrics } = useCaseMetrics(runId || "", caseId || "");

  if (caseLoading) {
    return (
      <Page>
        <Page.Content>
          <div className="flex items-center justify-center py-12">
            <Spinner size="lg" />
          </div>
        </Page.Content>
      </Page>
    );
  }

  if (caseError || !caseExec) {
    return (
      <Page>
        <Page.Content>
          <Alert variant="error">
            <AlertDescription>Case not found or error loading case.</AlertDescription>
          </Alert>
        </Page.Content>
      </Page>
    );
  }

  const started = caseExec.started_at ? new Date(caseExec.started_at).getTime() : Date.now();
  const finished = caseExec.finished_at ? new Date(caseExec.finished_at).getTime() : Date.now();
  const duration = caseExec.finished_at ? (finished - started) / 1000 : null;

  return (
    <Page>
      <Page.Header
        title={`Case: ${caseId}`}
        description={`${formatCaseStatus(caseExec.status)} · ${duration ? formatElapsedTime(duration) : "Duration unknown"}`}
        breadcrumbs={[
          { label: "Results", href: "/results" },
          { label: "Run", href: `/runs/${runId}` },
        ]}
      />

      <Page.Content>
        <div className="space-y-4">
          {/* Case Identity */}
          <Surface className="p-4">
            <div className="space-y-3">
              <div>
                <div className="text-xs text-text-tertiary">Query</div>
                <div className="mt-1 text-text-primary">{caseExec.query ?? "—"}</div>
              </div>

              <div className="flex gap-2">
                {caseExec.answerability && (
                  <StatusBadge status={getAnswerabilityVariant(caseExec.answerability)}>
                    {formatAnswerability(caseExec.answerability)}
                  </StatusBadge>
                )}
                {caseExec.tags.map((tag) => (
                  <span key={tag} className="rounded border border-border bg-surface px-1.5 py-0.5 text-xs text-text-tertiary">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </Surface>

          {/* Answers */}
          <div className="grid gap-4 md:grid-cols-2">
            <Surface className="p-4">
              <h3 className="mb-2 text-sm font-medium text-text-primary">Generated Answer</h3>
              {observation?.answer ? (
                <div className="text-sm text-text-secondary whitespace-pre-wrap">
                  {JSON.stringify(observation.answer, null, 2)}
                </div>
              ) : (
                <div className="text-sm text-text-tertiary">No answer generated</div>
              )}
            </Surface>

            <Surface className="p-4">
              <h3 className="mb-2 text-sm font-medium text-text-primary">Reference Answer</h3>
              {caseExec.reference_answer ? (
                <div className="text-sm text-text-secondary">{caseExec.reference_answer}</div>
              ) : (
                <div className="text-sm text-text-tertiary">No reference answer</div>
              )}
            </Surface>
          </div>

          {/* Evidence */}
          {observation && observation.retrieval && (
            <Surface className="p-4">
              <h3 className="mb-3 text-sm font-medium text-text-primary">Retrieved Evidence</h3>
              <div className="space-y-2">
                {Array.isArray(observation.retrieval) ? (
                  observation.retrieval.slice(0, 5).map((item: any, idx: number) => (
                    <div key={idx} className="rounded border border-border bg-surface p-3">
                      <div className="text-xs text-text-tertiary">Document {idx + 1}</div>
                      <div className="text-sm text-text-secondary line-clamp-2">
                        {JSON.stringify(item)}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-sm text-text-secondary">{JSON.stringify(observation.retrieval)}</div>
                )}
              </div>
            </Surface>
          )}

          {/* Citations */}
          {observation && observation.citations && observation.citations.length > 0 && (
            <Surface className="p-4">
              <h3 className="mb-3 text-sm font-medium text-text-primary">Citations</h3>
              <div className="space-y-2">
                {observation.citations.map((citation: any, idx: number) => (
                  <div key={idx} className="text-sm text-text-secondary">
                    <span className="font-medium">[{idx + 1}]</span> {JSON.stringify(citation)}
                  </div>
                ))}
              </div>
            </Surface>
          )}

          {/* Metrics */}
          {metrics && metrics.length > 0 && (
            <Surface className="p-4">
              <h3 className="mb-3 text-sm font-medium text-text-primary">Case Metrics</h3>
              <div className="space-y-2">
                {metrics.map((metric) => (
                  <div key={metric.metric_id} className="flex items-center justify-between border-b border-border pb-2">
                    <div>
                      <div className="font-medium text-text-primary">{metric.metric_id}</div>
                      <div className="text-xs text-text-tertiary">v{metric.metric_version}</div>
                    </div>
                    <div className="text-lg font-semibold text-text-primary">
                      {formatMetricValue(metric.value_summary, metric.metric_id)}
                    </div>
                  </div>
                ))}
              </div>
            </Surface>
          )}

          {/* Attempts */}
          {attempts && attempts.length > 0 && (
            <Surface className="p-4">
              <h3 className="mb-3 text-sm font-medium text-text-primary">Attempts ({attempts.length})</h3>
              <div className="space-y-2">
                {attempts.map((attempt: AttemptSummary) => (
                  <div key={attempt.attempt_id} className="flex items-center justify-between rounded border border-border p-3">
                    <div className="flex items-center gap-3">
                      <StatusBadge status={attempt.status === "completed" ? "success" : attempt.status === "failed" ? "error" : "neutral"}>
                        {attempt.status}
                      </StatusBadge>
                      <span className="text-sm text-text-secondary">Attempt #{attempt.attempt_number}</span>
                    </div>
                    <div className="text-sm text-text-tertiary">
                      {attempt.started_at && attempt.finished_at
                        ? formatElapsedTime(
                            (new Date(attempt.finished_at).getTime() -
                              new Date(attempt.started_at).getTime()) /
                              1000
                          )
                        : "—"}
                    </div>
                  </div>
                ))}
              </div>
            </Surface>
          )}

          {/* Technical Details */}
          <Surface className="p-4">
            <h3 className="mb-3 text-sm font-medium text-text-primary">Technical Details</h3>
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-text-tertiary">Case Execution ID:</span>
                  <span className="ml-2 font-mono text-text-secondary">{caseExec.case_execution_id}</span>
                </div>
                <div>
                  <span className="text-text-tertiary">Run ID:</span>
                  <span className="ml-2 font-mono text-text-secondary">{caseExec.run_id}</span>
                </div>
              </div>
            </div>
          </Surface>
        </div>
      </Page.Content>
    </Page>
  );
}
