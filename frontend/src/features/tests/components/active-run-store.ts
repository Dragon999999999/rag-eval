import { useSyncExternalStore } from "react";

export interface ActiveRunReference {
  testId: string;
  runId: string;
  testName: string;
}

const storageKey = "rag-eval.active-run";

const listeners = new Set<() => void>();

let cachedRaw: string | null | undefined;
let cachedReference: ActiveRunReference | null = null;

function read(): ActiveRunReference | null {
  try {
    const raw = window.localStorage.getItem(storageKey);

    // Nothing changed since the previous snapshot.
    if (raw === cachedRaw) {
      return cachedReference;
    }

    cachedRaw = raw;

    if (raw === null) {
      cachedReference = null;
      return cachedReference;
    }

    cachedReference = JSON.parse(raw) as ActiveRunReference;
    return cachedReference;
  } catch {
    cachedRaw = null;
    cachedReference = null;
    return null;
  }
}

function notify() {
  listeners.forEach((listener) => {
    listener();
  });
}

function subscribe(listener: () => void) {
  listeners.add(listener);

  return () => {
    listeners.delete(listener);
  };
}

export function setActiveRun(
  reference: ActiveRunReference | null
) {
  if (reference) {
    const raw = JSON.stringify(reference);

    window.localStorage.setItem(storageKey, raw);

    // Update the snapshot cache immediately.
    cachedRaw = raw;
    cachedReference = reference;
  } else {
    window.localStorage.removeItem(storageKey);

    cachedRaw = null;
    cachedReference = null;
  }

  notify();
}

export function useActiveRunReference() {
  return useSyncExternalStore(
    subscribe,
    read,
    () => null
  );
}