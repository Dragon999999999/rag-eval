import { Page } from "@/components/layout/page-layout";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { useRouteError } from "react-router-dom";

/**
 * Not found page for unknown routes.
 */
export function NotFoundPage() {
  return (
    <Page>
      <Page.Content>
        <div className="flex min-h-[400px] items-center justify-center">
          <EmptyState
            title="Page not found"
            description="The requested RAG-Eval page does not exist."
            action={
              <Button variant="secondary" onClick={() => (window.location.href = "/")}>
                Back to Dashboard
              </Button>
            }
          />
        </div>
      </Page.Content>
    </Page>
  );
}

/**
 * Error boundary fallback for route errors.
 */
export function ErrorBoundaryPage() {
  const error = useRouteError() as Error | undefined;

  // Log error in development
  if (import.meta.env.DEV && error) {
    console.error("Route error:", error);
  }

  return (
    <Page>
      <Page.Content>
        <div className="flex min-h-[400px] items-center justify-center">
          <EmptyState
            title="Something went wrong"
            description="The page could not be loaded. Please try again."
            action={
              <Button
                variant="secondary"
                onClick={() => {
                  window.location.reload();
                }}
              >
                Try again
              </Button>
            }
          />
        </div>
      </Page.Content>
    </Page>
  );
}
