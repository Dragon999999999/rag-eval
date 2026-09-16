/**
 * Quick actions section for dashboard.
 *
 * Provides shortcuts to common actions.
 */
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";

export function QuickActions() {
  return (
    <section className="space-y-4">
      <h2 className="text-base font-medium text-text-primary">
        Quick Actions
      </h2>

      <Surface className="p-4">
        <div className="flex flex-wrap gap-3">
          <Button asChild>
            <Link to="/tests">New Evaluation</Link>
          </Button>

          <Button variant="secondary" asChild>
            <Link to="/datasets">Create Dataset</Link>
          </Button>

          <Button variant="secondary" asChild>
            <Link to="/targets">Add Target</Link>
          </Button>
        </div>
      </Surface>
    </section>
  );
}
