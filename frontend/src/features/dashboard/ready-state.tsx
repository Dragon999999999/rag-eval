/**
 * Ready-to-evaluate state for dashboard.
 *
 * Shown when resources exist but no runs have been executed yet.
 */
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Surface } from "@/components/layout/surface";
import { Check, Database, Server } from "lucide-react";
import type { ResourceSummary } from "./dashboard-types";

interface ReadyToEvaluateStateProps {
  resources: ResourceSummary;
}

export function ReadyToEvaluateState({ resources }: ReadyToEvaluateStateProps) {
  return (
    <div className="space-y-6">
      <EmptyState
        title="Ready to evaluate"
        description="You have the prerequisites to run your first evaluation."
      />

      <div className="grid gap-4 md:grid-cols-2">
        {resources.targets.total > 0 && (
          <ResourceReady
            label="Target"
            secondary={resources.targets.secondaryLabel}
            icon={Server}
            href="/targets"
          />
        )}

        {resources.datasets.total > 0 && (
          <ResourceReady
            label="Dataset"
            secondary={resources.datasets.secondaryLabel}
            icon={Database}
            href="/datasets"
          />
        )}
      </div>

      <div className="flex justify-center">
        <Button size="lg" asChild>
          <Link to="/tests">Create First Evaluation</Link>
        </Button>
      </div>
    </div>
  );
}

interface ResourceReadyProps {
  label: string;
  secondary?: string;
  icon: React.ComponentType<{ className?: string }>;
  href: string;
}

function ResourceReady({
  label,
  secondary,
  icon: Icon,
  href,
}: ResourceReadyProps) {
  return (
    <a href={href}>
      <Surface className="group p-6 transition-colors hover:bg-surface-hover">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-success-bg">
            <Check className="h-6 w-6 text-success" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <Icon className="h-5 w-5 text-text-tertiary" />
              <p className="font-medium text-text-primary">{label}</p>
            </div>
            {secondary && (
              <p className="mt-1 truncate text-sm text-text-tertiary">
                {secondary}
              </p>
            )}
          </div>
        </div>
      </Surface>
    </a>
  );
}
