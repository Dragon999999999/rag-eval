/** Helpers for turning benchmark API errors into actionable UI messages. */

/**
 * Return a persistent-friendly message for an HTTP 409 conflict.
 *
 * FastAPI returns conflicts as a JSON object with a `detail` field, while the
 * shared API client keeps the original response body in the error message.
 */
export function getConflictMessage(error: unknown, subject: string): string | null {
  const message = error instanceof Error ? error.message : String(error);
  const match = message.match(/API error:\s*409\b\s*-\s*(.*)$/is);
  if (!match && !/\b(already exists|duplicate|conflict)\b/i.test(message)) {
    return null;
  }

  const body = (match?.[1] ?? message.replace(/^API error:\s*\d+\s*-\s*/i, "")).trim();
  let detail = body;
  try {
    const parsed: unknown = JSON.parse(body);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      "detail" in parsed &&
      typeof parsed.detail === "string"
    ) {
      detail = parsed.detail;
    }
  } catch {
    // Keep the raw response when the API returned non-JSON error text.
  }

  return detail
    ? `${subject} conflict: ${detail}`
    : `${subject} conflicts with records already in this benchmark.`;
}

/** Return a user-facing message for a specific HTTP status response. */
export function getStatusMessage(
  error: unknown,
  status: number,
  subject: string
): string | null {
  const message = error instanceof Error ? error.message : String(error);
  const pattern = new RegExp(`API error:\\s*${String(status)}\\b\\s*-\\s*(.*)$`, "is");
  const match = message.match(pattern);
  if (!match) return null;

  const body = (match[1] ?? "").trim();
  let detail = body;
  try {
    const parsed: unknown = JSON.parse(body);
    if (typeof parsed === "object" && parsed !== null && "detail" in parsed) {
      const parsedDetail = parsed.detail;
      detail =
        typeof parsedDetail === "string" ? parsedDetail : JSON.stringify(parsedDetail);
    }
  } catch {
    // Keep the raw response when the API returned non-JSON error text.
  }

  return detail ? `${subject}: ${detail}` : `${subject} was rejected.`;
}
