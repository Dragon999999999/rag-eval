import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ToastProvider, useToast, toast } from "@/lib/toast";

function TestComponent() {
  const { addToast } = useToast();

  return (
    <div>
      <button
        onClick={() => {
          addToast({ message: "Test message", variant: "success" });
        }}
      >
        Show Toast
      </button>
    </div>
  );
}

describe("Toast system", () => {
  it("renders ToastProvider without crashing", () => {
    render(
      <ToastProvider>
        <div>Test</div>
      </ToastProvider>
    );
    expect(screen.getByText("Test")).toBeInTheDocument();
  });

  it("shows toast when triggered", async () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );

    fireEvent.click(screen.getByText("Show Toast"));
    await waitFor(() => {
      expect(screen.getByText("Test message")).toBeInTheDocument();
    });
  });

  it("displays success variant correctly", async () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );

    fireEvent.click(screen.getByText("Show Toast"));
    await waitFor(() => {
      const toast = screen.getByText("Test message").closest("[role='status']");
      expect(toast).toBeInTheDocument();
    });
  });

  it("can be triggered via programmatic API", async () => {
    render(
      <ToastProvider>
        <div>
          <button
            onClick={() => {
              toast.success("Programmatic toast");
            }}
          >
            Trigger
          </button>
        </div>
      </ToastProvider>
    );

    fireEvent.click(screen.getByText("Trigger"));
    await waitFor(() => {
      expect(screen.getByText("Programmatic toast")).toBeInTheDocument();
    });
  });

  it("shows error toast", async () => {
    render(
      <ToastProvider>
        <div>
          <button
            onClick={() => {
              toast.error("Error occurred");
            }}
          >
            Show Error
          </button>
        </div>
      </ToastProvider>
    );

    fireEvent.click(screen.getByText("Show Error"));
    await waitFor(() => {
      expect(screen.getByText("Error occurred")).toBeInTheDocument();
    });
  });

  it("shows info toast", async () => {
    render(
      <ToastProvider>
        <div>
          <button
            onClick={() => {
              toast.info("Info message");
            }}
          >
            Show Info
          </button>
        </div>
      </ToastProvider>
    );

    fireEvent.click(screen.getByText("Show Info"));
    await waitFor(() => {
      expect(screen.getByText("Info message")).toBeInTheDocument();
    });
  });

  it("shows warning toast", async () => {
    render(
      <ToastProvider>
        <div>
          <button
            onClick={() => {
              toast.warning("Warning message");
            }}
          >
            Show Warning
          </button>
        </div>
      </ToastProvider>
    );

    fireEvent.click(screen.getByText("Show Warning"));
    await waitFor(() => {
      expect(screen.getByText("Warning message")).toBeInTheDocument();
    });
  });
});
