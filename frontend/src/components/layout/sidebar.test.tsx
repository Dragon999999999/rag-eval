import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Sidebar } from "@/components/layout/sidebar";

function renderSidebar(route = "/") {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Sidebar />
    </MemoryRouter>
  );
}

describe("Sidebar navigation", () => {
  it("renders branding", () => {
    renderSidebar();
    expect(screen.getByText("RAG-Eval")).toBeInTheDocument();
  });

  it("renders all primary navigation links", () => {
    renderSidebar();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Targets")).toBeInTheDocument();
    expect(screen.getByText("Datasets")).toBeInTheDocument();
    expect(screen.getByText("Tests")).toBeInTheDocument();
    expect(screen.getByText("Results")).toBeInTheDocument();
  });

  it("renders secondary navigation", () => {
    renderSidebar();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("highlights active route for /", () => {
    renderSidebar("/");
    const navItem = screen.getByText("Dashboard").closest("a");
    expect(navItem).toHaveClass("bg-accent-subtle");
  });

  it("highlights active route for /targets", () => {
    renderSidebar("/targets");
    const navItem = screen.getByText("Targets").closest("a");
    expect(navItem).toHaveClass("bg-accent-subtle");
  });

  it("highlights active route for nested paths like /targets/123", () => {
    renderSidebar("/targets/123");
    const navItem = screen.getByText("Targets").closest("a");
    expect(navItem).toHaveClass("bg-accent-subtle");
  });

  it("highlights active route for /datasets", () => {
    renderSidebar("/datasets");
    const navItem = screen.getByText("Datasets").closest("a");
    expect(navItem).toHaveClass("bg-accent-subtle");
  });

  it("highlights active route for /tests", () => {
    renderSidebar("/tests");
    const navItem = screen.getByText("Tests").closest("a");
    expect(navItem).toHaveClass("bg-accent-subtle");
  });

  it("highlights active route for /results", () => {
    renderSidebar("/results");
    const navItem = screen.getByText("Results").closest("a");
    expect(navItem).toHaveClass("bg-accent-subtle");
  });

  it("highlights active route for /settings", () => {
    renderSidebar("/settings");
    const navItem = screen.getByText("Settings").closest("a");
    expect(navItem).toHaveClass("bg-accent-subtle");
  });
});
