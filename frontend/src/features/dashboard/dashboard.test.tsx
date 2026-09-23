import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/query-client";
import { DashboardPage } from "./dashboard-page";

function renderDashboard(ui: React.ReactElement) {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
    </MemoryRouter>
  );
}

describe("DashboardPage", () => {
  it("renders loading skeleton initially", () => {
    renderDashboard(<DashboardPage />);
    // Skeleton should appear while data loads
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("renders operational dashboard with mock data", async () => {
    renderDashboard(<DashboardPage />);

    // Wait for data to load
    await waitFor(
      () => {
        expect(screen.getByText("Evaluation Overview")).toBeInTheDocument();
      },
      { timeout: 2000 }
    );

    // Resource summary should appear
    expect(await screen.findByText("Targets")).toBeInTheDocument();
    expect(await screen.findByText("Benchmarks")).toBeInTheDocument();
    expect(await screen.findByText("Tests")).toBeInTheDocument();
  });
});
