import { Page } from "@/components/layout/page-layout";
import { Card } from "@/components/layout/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { LayoutDashboard, FlaskConical, Database, Server } from "lucide-react";

/**
 * Dashboard page - main landing page for RAG-Eval.
 *
 * This is a placeholder that will be filled with real metrics
 * and activity data in later stages.
 */
export function DashboardPage() {
  return (
    <Page>
      <Page.Header
        title="Dashboard"
        description="Monitor evaluations and recent system performance."
      />

      <Page.Content>
        <div className="space-y-6">
          {/* Placeholder sections for future content */}
          <section>
            <h2 className="mb-3 text-sm font-medium text-text-tertiary">
              Recent Evaluations
            </h2>
            <EmptyState
              icon={<LayoutDashboard className="h-8 w-8" />}
              title="No recent evaluations"
              description="Run your first evaluation to see activity here."
              action={
                <Button size="sm" variant="secondary">
                  New Evaluation
                </Button>
              }
            />
          </section>

          <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <Card className="p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-accent-subtle">
                  <Server className="h-5 w-5 text-accent" />
                </div>
                <div>
                  <p className="text-sm font-medium text-text-secondary">
                    Targets
                  </p>
                  <p className="text-xs text-text-tertiary">
                    No targets configured
                  </p>
                </div>
              </div>
            </Card>

            <Card className="p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-accent-subtle">
                  <Database className="h-5 w-5 text-accent" />
                </div>
                <div>
                  <p className="text-sm font-medium text-text-secondary">
                    Datasets
                  </p>
                  <p className="text-xs text-text-tertiary">
                    No datasets available
                  </p>
                </div>
              </div>
            </Card>

            <Card className="p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-accent-subtle">
                  <FlaskConical className="h-5 w-5 text-accent" />
                </div>
                <div>
                  <p className="text-sm font-medium text-text-secondary">
                    Tests
                  </p>
                  <p className="text-xs text-text-tertiary">
                    No tests configured
                  </p>
                </div>
              </div>
            </Card>
          </section>
        </div>
      </Page.Content>
    </Page>
  );
}
