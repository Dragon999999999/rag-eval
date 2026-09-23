import { useSyncExternalStore } from "react";

export interface ActiveRunReference {
  testId: string;
  runId: string;
  testName: string;
}

const storageKey = "rag-eval.active-run";
const listeners = new Set<() => void>();

function read(): ActiveRunReference | null {
  try {
    const value = window.localStorage.getItem(storageKey);
    return value ? (JSON.parse(value) as ActiveRunReference) : null;
  } catch {
    return null;
  }
}

function notify() {
  listeners.forEach((listener) => {
    listener();
  });
}

export function setActiveRun(reference: ActiveRunReference | null) {
  if (reference) window.localStorage.setItem(storageKey, JSON.stringify(reference));
  else window.localStorage.removeItem(storageKey);
  notify();
}

export function useActiveRunReference() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    read,
    () => null
  );
}
