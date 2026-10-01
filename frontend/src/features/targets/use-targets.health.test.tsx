import { describe, it, expect, vi, afterEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TargetService } from "./target-service";
import { useTargetList } from "./use-targets";
import type { TargetConnectionInfo, TargetSummary } from "./target-types";

function makeTarget(
  overrides: Partial<TargetSummary> & { target_id: string }
): TargetSummary {
  return {
    name: overrides.target_id,
    adapter_type: "generic_http",
    configuration_status: "configured",
    connection_status: "connected",
    current_config_version: 1,
    enabled: true,
    created_at: "",
    updated_at: "",
    ...overrides,
  };
}

const connectionResult: TargetConnectionInfo = {
  status: "connected",
  checked_at: new Date().toISOString(),
  last_successful_at: null,
  health: null,
  error: null,
};

function renderList(options?: Parameters<typeof useTargetList>[0]) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  function Harness() {
    const { data } = useTargetList(options);
    return <div data-testid="count">{data ? data.length : 0}</div>;
  }

  return render(
    <QueryClientProvider client={client}>
      <Harness />
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useTargetList automatic connection checks", () => {
  it("fires a live connection check for each enabled, configured target on load", async () => {
    vi.spyOn(TargetService, "listTargets").mockResolvedValue([
      makeTarget({ target_id: "t1" }),
      makeTarget({
        target_id: "t2",
        current_config_version: null,
        connection_status: "not_tested",
      }),
      makeTarget({ target_id: "t3", enabled: false }),
    ]);

    const check = vi
      .spyOn(TargetService, "testConnection")
      .mockResolvedValue(connectionResult);

    renderList();

    await waitFor(() => expect(check).toHaveBeenCalledWith("t1"));

    // Unconfigured and disabled targets should not be health-checked.
    expect(check).not.toHaveBeenCalledWith("t2");
    expect(check).not.toHaveBeenCalledWith("t3");
  });

  it("skips connection checks when autoHealthCheck is disabled", async () => {
    vi.spyOn(TargetService, "listTargets").mockResolvedValue([
      makeTarget({ target_id: "t1" }),
    ]);

    const check = vi
      .spyOn(TargetService, "testConnection")
      .mockResolvedValue(connectionResult);

    renderList({ autoHealthCheck: false });

    await waitFor(() =>
      expect(check).not.toHaveBeenCalled()
    );

    // Give the mount effect a moment; no live checks should ever fire.
    await new Promise((resolve) => setTimeout(resolve, 25));
    expect(check).not.toHaveBeenCalled();
  });
});
