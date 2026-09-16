/**
 * Formatting utilities for dashboard display.
 *
 * Centralized formatting logic to avoid duplication across components.
 */

/**
 * Format a number as percentage.
 */
export function formatPercent(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Format duration in seconds to human-readable string.
 */
export function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds.toString()}s`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;

  if (minutes < 60) {
    return remainingSeconds > 0
      ? `${minutes.toString()}m ${remainingSeconds.toString()}s`
      : `${minutes.toString()}m`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;

  return `${hours.toString()}h ${
    remainingMinutes > 0 ? `${remainingMinutes.toString()}m` : ""
  }`.trim();
}

/**
 * Format relative time from ISO timestamp.
 */
export function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);

  if (diffSecs < 60) {
    return "just now";
  } else if (diffMins < 60) {
    return `${diffMins.toString()}m ago`;
  } else if (diffHours < 24) {
    return `${diffHours.toString()}h ago`;
  }

  return date.toLocaleDateString();
}

/**
 * Format metric value with optional unit.
 */
export function formatMetricValue(
  value: number | string,
  unit?: string
): string {
  if (typeof value === "number") {
    // Format small decimals with more precision
    if (value < 1 && value > 0) {
      return `${value.toFixed(3)}${unit ?? ""}`;
    }
    // Format larger numbers
    return `${value.toFixed(1)}${unit ?? ""}`;
  }
  return `${value}${unit ?? ""}`;
}

/**
 * Format delta value with sign and direction indicator.
 */
export function formatDelta(
  value: number,
  direction: "higher-is-better" | "lower-is-better" | "neutral",
  unit?: string
): {
  text: string;
  isImprovement: boolean;
  isNeutral: boolean;
} {
  const sign = value >= 0 ? "+" : "";
  const unitStr = unit === "ms" ? "ms" : "";

  // Determine if this is an improvement based on direction
  let isImprovement = false;
  let isNeutral = false;

  switch (direction) {
    case "neutral":
      isNeutral = true;
      break;
    case "higher-is-better":
      isImprovement = value > 0;
      break;
    case "lower-is-better":
      isImprovement = value < 0;
      break;
  }

  return {
    text: `${sign}${value.toFixed(1)}${unitStr}`,
    isImprovement,
    isNeutral,
  };
}

/**
 * Format timestamp for display.
 */
export function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
