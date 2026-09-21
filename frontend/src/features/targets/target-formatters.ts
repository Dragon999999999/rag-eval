/** Presentation helpers for API-backed target state. */
import type { Target, TargetConnectionStatus } from "./target-types";

export function formatAdapterType(adapter: string | null): string {
  if (!adapter) return "Not configured";
  return adapter
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatTargetStatus(status: string | null | undefined): string {
  return (status ?? "unknown")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function getConnectionStatus(target: Target): TargetConnectionStatus {
  return target.connection?.status ?? "not_tested";
}

export function formatTargetEndpoint(target: Target): string {
  if (target.metadata.endpoint && typeof target.metadata.endpoint === "string") {
    return target.metadata.endpoint;
  }
  return target.adapter_type ?? "Not configured";
}

export function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const diffSeconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diffSeconds < 60) return "just now";
  const minutes = Math.floor(diffSeconds / 60);
  if (minutes < 60) return `${String(minutes)}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${String(hours)}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${String(days)}d ago`;
  return date.toLocaleDateString();
}

export function statusVariant(
  status: string | null | undefined
): "success" | "error" | "warning" | "neutral" {
  switch (status) {
    case "connected":
    case "configured":
      return "success";
    case "disconnected":
    case "invalid":
      return "error";
    case "unverified":
      return "warning";
    default:
      return "neutral";
  }
}
