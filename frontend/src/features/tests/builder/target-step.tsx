/**
 * Step 1: Target Selection component.
 */
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import { EmptyState } from "@/components/ui/empty-state";
import { Spinner } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useTargetList } from "@/features/targets/use-targets";
import {
  formatAdapterType,
  getCapabilityBadges,
} from "@/features/targets/target-formatters";
import type { Target } from "@/features/targets/target-types";
import type { UseFormReturn } from "react-hook-form";
import type { TestBuilderValues } from "../test-builder-form";

interface TargetStepProps {
  form: UseFormReturn<TestBuilderValues>;
  onNext: () => void;
}

export function TargetStep({ form, onNext }: TargetStepProps) {
  const { data: targets, isLoading, error, refetch } = useTargetList();

  const selectedTargetId = form.watch("target_id");
  const setSelectedTargetId = (targetId: string) => {
    form.setValue("target_id", targetId, { shouldValidate: true, shouldDirty: true });
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">Select Target</h2>
        </div>
        <Surface>
          <div className="flex items-center justify-center py-12">
            <Spinner size="lg" />
          </div>
        </Surface>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="error">
        <AlertDescription>
          An error occurred while fetching targets.
          <Button
            variant="secondary"
            size="sm"
            onClick={() => { void refetch(); }}
            className="ml-4"
          >
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (!targets || targets.length === 0) {
    return (
      <EmptyState
        title="No targets configured"
        description="You need to create at least one target before building a test."
        action={
          <Button asChild>
            <Link to="/targets/new">Create Target</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">Select Target</h2>
          <p className="text-sm text-text-tertiary">
            Choose the target system to evaluate against the benchmark.
          </p>
        </div>
        <Button asChild variant="secondary">
          <Link to="/targets/new">+ New Target</Link>
        </Button>
      </div>

      <Surface>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[50px]">Select</TableHead>
              <TableHead>Name</TableHead>
              <TableHead className="w-[120px]">Type</TableHead>
              <TableHead>Capabilities</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {targets.map((target: Target) => (
              <TargetRow
                key={target.targetId}
                target={target}
                isSelected={selectedTargetId === target.targetId}
                onSelect={() => { setSelectedTargetId(target.targetId); }}
              />
            ))}
          </TableBody>
        </Table>
      </Surface>

      <div className="flex justify-end">
        <Button onClick={onNext} disabled={!selectedTargetId}>
          Next: Select Dataset
        </Button>
      </div>
    </div>
  );
}

interface TargetRowProps {
  target: Target;
  isSelected: boolean;
  onSelect: () => void;
}

function TargetRow({ target, isSelected, onSelect }: TargetRowProps) {
  const capabilities = getCapabilityBadges({
    query: true,
    retrieval: true,
    // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment, @typescript-eslint/no-explicit-any, @typescript-eslint/no-unnecessary-condition, @typescript-eslint/no-unsafe-member-access
    citations: (target.metadata?.capabilities as any)?.citations ?? false,
    // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment, @typescript-eslint/no-explicit-any, @typescript-eslint/no-unnecessary-condition, @typescript-eslint/no-unsafe-member-access
    usage: (target.metadata?.capabilities as any)?.usage ? { tokens: true } : undefined,
    // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment, @typescript-eslint/no-explicit-any, @typescript-eslint/no-unnecessary-condition, @typescript-eslint/no-unsafe-member-access
    target_trace: (target.metadata?.capabilities as any)?.trace ?? false,
  });

  return (
    <TableRow
      className="cursor-pointer transition-colors hover:bg-surface-hover"
      onClick={onSelect}
    >
      <TableCell>
        <input
          type="radio"
          name="target_selection"
          checked={isSelected}
          onChange={onSelect}
          className="h-4 w-4"
          aria-label={`Select ${target.name}`}
        />
      </TableCell>
      <TableCell>
        <div>
          <div className="font-medium text-text-primary">{target.name}</div>
          {target.version && (
            <div className="text-xs text-text-tertiary">v{target.version}</div>
          )}
        </div>
      </TableCell>
      <TableCell>
        <span className="text-sm text-text-secondary">
          {formatAdapterType(target.adapter)}
        </span>
      </TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {capabilities.slice(0, 5).map((cap: string) => (
            <span
              key={cap}
              className="rounded bg-surface-hover px-1.5 py-0.5 text-xs text-text-tertiary"
            >
              {cap}
            </span>
          ))}
          {capabilities.length > 5 && (
            <span className="text-xs text-text-tertiary">
              +{capabilities.length - 5}
            </span>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}
