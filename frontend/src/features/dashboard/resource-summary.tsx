/**
 * Resource summary section for dashboard.
 *
 * Shows counts for targets, datasets, and tests.
 */
import { Link } from "react-router-dom";
import { Surface } from "@/components/layout/surface";
import { Server, Database, FlaskConical } from "lucide-react";
import type { ResourceSummary } from "./dashboard-types";

interface ResourceSummarySectionProps {
  resources: ResourceSummary;
}

export function ResourceSummarySection({ resources }: ResourceSummarySectionProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <ResourceCard
        label="Targets"
        count={resources.targets.total}
        secondaryLabel={resources.targets.secondaryLabel}
        icon={Server}
        href="/targets"
      />

      <ResourceCard
        label="Benchmarks"
        count={resources.datasets.total}
        secondaryLabel={resources.datasets.secondaryLabel}
        icon={Database}
        href="/benchmarks"
      />

      <ResourceCard
        label="Tests"
        count={resources.tests.total}
        secondaryLabel={resources.tests.secondaryLabel}
        icon={FlaskConical}
        href="/tests"
      />
    </div>
  );
}

interface ResourceCardProps {
  label: string;
  count: number;
  secondaryLabel?: string;
  icon: React.ComponentType<{ className?: string }>;
  href: string;
}

function ResourceCard({
  label,
  count,
  secondaryLabel,
  icon: Icon,
  href,
}: ResourceCardProps) {
  return (
    <Link to={href}>
      <Surface className="group p-4 transition-colors hover:bg-surface-hover">
        <div className="flex items-center gap-3">
          <div className="group-hover:bg-accent-subtle/80 flex h-10 w-10 items-center justify-center rounded-md bg-accent-subtle transition-colors">
            <Icon className="h-5 w-5 text-accent" />
          </div>
          <div>
            <p className="text-sm font-medium text-text-secondary">{label}</p>
            <p className="text-lg font-semibold text-text-primary">{count}</p>
            {secondaryLabel && (
              <p className="text-xs text-text-tertiary">{secondaryLabel}</p>
            )}
          </div>
        </div>
      </Surface>
    </Link>
  );
}
