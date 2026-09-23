import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";

describe("Breadcrumbs", () => {
  it("does not render for root path", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Breadcrumbs />
      </MemoryRouter>
    );
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("does not render for single-segment paths", () => {
    render(
      <MemoryRouter initialEntries={["/targets"]}>
        <Breadcrumbs />
      </MemoryRouter>
    );
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("renders for nested paths", () => {
    render(
      <MemoryRouter initialEntries={["/targets/123"]}>
        <Breadcrumbs />
      </MemoryRouter>
    );
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(screen.getByText("Targets")).toBeInTheDocument();
  });

  it("renders correct hierarchy for nested paths", () => {
    render(
      <MemoryRouter initialEntries={["/benchmarks/benchmark-123"]}>
        <Breadcrumbs />
      </MemoryRouter>
    );
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(screen.getByText("Benchmarks")).toBeInTheDocument();
    expect(screen.getByText("benchmark-123")).toBeInTheDocument();
  });

  it("marks current page with aria-current", () => {
    render(
      <MemoryRouter initialEntries={["/tests/test-456"]}>
        <Breadcrumbs />
      </MemoryRouter>
    );
    const currentPage = screen.getByText("test-456");
    expect(currentPage).toHaveAttribute("aria-current", "page");
  });

  it("renders provided items when passed explicitly", () => {
    render(
      <MemoryRouter initialEntries={["/custom"]}>
        <Breadcrumbs
          items={[
            { label: "Home", href: "/" },
            { label: "Custom", href: "/custom" },
          ]}
        />
      </MemoryRouter>
    );
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Custom")).toBeInTheDocument();
  });
});
