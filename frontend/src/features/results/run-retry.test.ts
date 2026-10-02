import { describe, expect, it } from "vitest";
import { canRetryFailedCases } from "./run-retry";

describe("canRetryFailedCases", () => {
  it("allows failed cases on retryable terminal runs", () => {
    expect(canRetryFailedCases("FAILED", 2)).toBe(true);
    expect(canRetryFailedCases("completed_with_errors", 1)).toBe(true);
  });

  it("rejects runs without failed cases or with non-retryable statuses", () => {
    expect(canRetryFailedCases("FAILED", 0)).toBe(false);
    expect(canRetryFailedCases("COMPLETE", 2)).toBe(false);
    expect(canRetryFailedCases("RUNNING", 2)).toBe(false);
  });
});
