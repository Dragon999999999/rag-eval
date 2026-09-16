/**
 * Target formatters and utilities.
 *
 * Centralized formatting logic for target display.
 */
import type { Target, TargetConnectionStatus, TargetAdapterType, CorpusMode } from "./target-types";

/**
 * Format adapter type for display.
 */
export function formatAdapterType(adapter: TargetAdapterType): string {
  switch (adapter) {
    case "http":
      return "HTTP Target Protocol";
    case "python":
      return "Python Adapter";
    default:
      return adapter;
  }
}

/**
 * Format corpus mode for display.
 */
export function formatCorpusMode(mode: CorpusMode): string {
  switch (mode) {
    case "DOCUMENTS":
      return "Documents";
    case "CHUNKS":
      return "Chunks";
    case "EXTERNAL":
      return "External Corpus";
    default:
      return mode;
  }
}

/**
 * Determine connection status from target data.
 *
 * This is a frontend presentation helper - actual status
 * comes from backend capability discovery.
 */
export function getConnectionStatus(
  _target: Target,
  hasCapabilities: boolean,
  _lastTestedAt?: string
): TargetConnectionStatus {
  // If we have capabilities, target was successfully tested
  if (hasCapabilities) {
    return "connected";
  }

  // Newly created target with no test yet
  return "unknown";
}

/**
 * Format endpoint/display URL for target.
 */
export function formatTargetEndpoint(target: Target): string {
  if (target.adapter === "http" && target.base_url) {
    return target.base_url;
  }
  if (target.adapter === "python" && target.python_target) {
    return target.python_target;
  }
  return "Not configured";
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
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) {
    return "just now";
  } else if (diffMins < 60) {
    return `${diffMins}m ago`;
  } else if (diffHours < 24) {
    return `${diffHours}h ago`;
  } else if (diffDays < 7) {
    return `${diffDays}d ago`;
  }

  return date.toLocaleDateString();
}

/**
 * Get capability badges for display.
 */
export function getCapabilityBadges(capabilities?: {
  query?: boolean;
  retrieval?: boolean;
  citations?: boolean;
  usage?: { tokens?: boolean };
  streaming?: boolean;
  target_trace?: boolean;
}): string[] {
  const badges: string[] = [];

  if (capabilities?.query) badges.push("Query");
  if (capabilities?.retrieval) badges.push("Retrieval");
  if (capabilities?.citations) badges.push("Citations");
  if (capabilities?.usage?.tokens) badges.push("Usage");
  if (capabilities?.streaming) badges.push("Streaming");
  if (capabilities?.target_trace) badges.push("Trace");

  return badges;
}

/**
 * Validate Python target import format (module:Symbol).
 */
export function isValidPythonTarget(importPath: string): boolean {
  // Basic validation: should contain exactly one colon
  const parts = importPath.split(":");
  if (parts.length !== 2) return false;

  const [module, symbol] = parts;

  // Module should contain at least one dot and no spaces
  if (!module || !module.includes(".") || /\s/.test(module)) return false;

  // Symbol should be a valid identifier
  if (!symbol || !/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(symbol)) return false;

  return true;
}

/**
 * Validate URL format.
 */
export function isValidUrl(url: string): boolean {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}
