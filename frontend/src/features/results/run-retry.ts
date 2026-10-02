/** Shared eligibility rules for retrying failed cases in an evaluation run. */

const retryableRunStatuses = new Set(["FAILED", "COMPLETED_WITH_ERRORS"]);

/**
 * Return whether a run can retry its failed cases.
 *
 * The backend only permits retries for terminal runs that have at least one
 * failed case. Keeping this rule in one place prevents different UI surfaces
 * from offering actions the API will reject.
 */
export function canRetryFailedCases(
  status: string | undefined,
  failedCases: number | null | undefined
): boolean {
  return (
    (failedCases ?? 0) > 0 && retryableRunStatuses.has((status ?? "").toUpperCase())
  );
}
