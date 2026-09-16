import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppProviders } from "@/app/providers";
import { DashboardPage } from "@/pages/dashboard-page";
import { TargetsPage } from "@/pages/targets-page";
import { DatasetsPage } from "@/pages/datasets-page";
import { TestsPage } from "@/pages/tests-page";
import { ResultsPage } from "@/pages/results-page";
import { SettingsPage } from "@/pages/settings-page";

function renderWithRouter(ui: React.ReactElement, route = "/") {
  window.history.pushState({}, "Test page", route);
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AppProviders>{ui}</AppProviders>
    </MemoryRouter>
  );
}

describe("Page routing", () => {
  it("renders Dashboard at /", () => {
    renderWithRouter(<DashboardPage />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(
      screen.getByText(/Monitor evaluations and recent system performance/i)
    ).toBeInTheDocument();
  });

  it("renders Targets page at /targets", () => {
    renderWithRouter(<TargetsPage />);
    expect(screen.getByText("Targets")).toBeInTheDocument();
    expect(
      screen.getByText(/Connect RAG or LLM systems/i)
    ).toBeInTheDocument();
  });

  it("renders Datasets page at /datasets", () => {
    renderWithRouter(<DatasetsPage />);
    expect(screen.getByText("Datasets")).toBeInTheDocument();
    expect(
      screen.getByText(/Manage benchmark datasets/i)
    ).toBeInTheDocument();
  });

  it("renders Tests page at /tests", () => {
    renderWithRouter(<TestsPage />);
    expect(screen.getByText("Tests")).toBeInTheDocument();
    expect(
      screen.getByText(/Define evaluations by combining/i)
    ).toBeInTheDocument();
  });

  it("renders Results page at /results", () => {
    renderWithRouter(<ResultsPage />);
    expect(screen.getByText("Results")).toBeInTheDocument();
    expect(
      screen.getByText(/Review completed evaluations/i)
    ).toBeInTheDocument();
  });

  it("renders Settings page at /settings", () => {
    renderWithRouter(<SettingsPage />);
    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(
      screen.getByText(/Configure application preferences/i)
    ).toBeInTheDocument();
  });
});
