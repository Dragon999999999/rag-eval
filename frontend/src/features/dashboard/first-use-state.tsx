/**
 * First-use onboarding state for dashboard.
 *
 * Shown when no resources exist at all.
 */
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Surface } from "@/components/layout/surface";
import { FlaskConical, Database, Server, ArrowRight } from "lucide-react";

export function FirstUseState() {
  return (
    <div className="space-y-6">
      <EmptyState
        title="Start evaluating your RAG system"
        description="RAG-Eval measures retrieval quality, answer quality, grounding and operational performance across reusable benchmark datasets."
      />

      <div className="grid gap-4 md:grid-cols-3">
        <StepCard
          step={1}
          title="Connect a target"
          description="Add your RAG or LLM system to evaluate"
          icon={Server}
          href="/targets"
        />

        <StepCard
          step={2}
          title="Add an evaluation dataset"
          description="Upload or import benchmark cases"
          icon={Database}
          href="/benchmarks"
        />

        <StepCard
          step={3}
          title="Run your first evaluation"
          description="Execute and analyze results"
          icon={FlaskConical}
          href="/tests"
        />
      </div>

      <div className="flex justify-center gap-3">
        <Button asChild>
          <Link to="/targets">
            Connect Target
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>

        <Button variant="secondary" asChild>
          <Link to="/benchmarks">Import Benchmark</Link>
        </Button>
      </div>
    </div>
  );
}

interface StepCardProps {
  step: number;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  href: string;
}

function StepCard({ step, title, description, icon: Icon, href }: StepCardProps) {
  return (
    <a href={href}>
      <Surface className="group p-6 transition-colors hover:bg-surface-hover">
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-sm font-semibold text-white">
              {step}
            </div>
            <Icon className="h-5 w-5 text-text-tertiary transition-colors group-hover:text-accent" />
          </div>
          <div>
            <h3 className="font-medium text-text-primary">{title}</h3>
            <p className="mt-1 text-sm text-text-tertiary">{description}</p>
          </div>
        </div>
      </Surface>
    </a>
  );
}
