/**
 * Step 2: Dataset Selection component.
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
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useDatasetList } from "@/features/datasets/use-datasets";
import type { DatasetInfo } from "@/features/datasets/dataset-types";
import type { UseFormReturn } from "react-hook-form";
import type { TestBuilderValues } from "../test-builder-form";
import type { CaseScope } from "../test-types";

interface DatasetStepProps {
  form: UseFormReturn<TestBuilderValues>;
  onPrevious: () => void;
  onNext: () => void;
}

export function DatasetStep({ form, onPrevious, onNext }: DatasetStepProps) {
  const {
    data: datasets,
    isLoading,
    error,
    refetch,
  } = useDatasetList();

  const selectedBenchmarkId = form.watch("benchmark_id");
  const caseScope = form.watch("case_scope");

  const setSelectedBenchmarkId = (benchmarkId: string) => {
    form.setValue("benchmark_id", benchmarkId, { shouldValidate: true, shouldDirty: true });
  };

  const setCaseScope = (scope: CaseScope) => {
    form.setValue("case_scope", scope as any, { shouldValidate: true, shouldDirty: true });
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">Select Dataset</h2>
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
          An error occurred while fetching datasets.
          <Button variant="secondary" size="sm" onClick={() => refetch()} className="ml-4">
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (!datasets || datasets.length === 0) {
    return (
      <EmptyState
        title="No datasets available"
        description="You need to upload or register at least one benchmark dataset."
        action={
          <Button asChild>
            <Link to="/datasets/new">Upload Dataset</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">Select Dataset</h2>
          <p className="text-sm text-text-tertiary">
            Choose the benchmark dataset to evaluate against.
          </p>
        </div>
      </div>

      <Surface>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[50px]">Select</TableHead>
              <TableHead>Name</TableHead>
              <TableHead className="w-[120px]">Cases</TableHead>
              <TableHead className="w-[120px]">Version</TableHead>
              <TableHead>Tags</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {datasets.map((dataset: DatasetInfo) => (
              <DatasetRow
                key={dataset.dataset_id}
                dataset={dataset}
                isSelected={selectedBenchmarkId === dataset.dataset_id}
                onSelect={() => setSelectedBenchmarkId(dataset.dataset_id)}
              />
            ))}
          </TableBody>
        </Table>
      </Surface>

      {selectedBenchmarkId && (
        <Surface className="p-4">
          <h3 className="mb-3 text-sm font-medium text-text-primary">Case Scope</h3>
          <div className="space-y-3">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="radio"
                name="case_scope_mode"
                checked={caseScope?.mode === "all"}
                onChange={() => setCaseScope({ mode: "all" })}
                className="mt-1 h-4 w-4"
              />
              <div className="flex-1">
                <div className="font-medium text-text-primary">All Cases</div>
                <div className="text-sm text-text-tertiary">
                  Run evaluation on all cases in the dataset.
                </div>
              </div>
            </label>

            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="radio"
                name="case_scope_mode"
                checked={caseScope?.mode === "sample"}
                onChange={() =>
                  setCaseScope({ mode: "sample", sample_size: 50, seed: Math.floor(Math.random() * 10000) })
                }
                className="mt-1 h-4 w-4"
              />
              <div className="flex-1">
                <div className="font-medium text-text-primary">Sample</div>
                <div className="text-sm text-text-tertiary">
                  Run on a random sample of cases.
                </div>
                {caseScope?.mode === "sample" && (
                  <div className="mt-2 flex items-center gap-2">
                    <Input
                      type="number"
                      min="1"
                      value={caseScope.sample_size}
                      onChange={(e) =>
                        setCaseScope({
                          mode: "sample",
                          sample_size: parseInt(e.target.value) || 1,
                          seed: caseScope.seed,
                        })
                      }
                      className="h-8 w-24"
                      placeholder="Sample size"
                    />
                    <span className="text-sm text-text-tertiary">cases</span>
                    <Input
                      type="number"
                      min="0"
                      value={caseScope.seed ?? ""}
                      onChange={(e) =>
                        setCaseScope({
                          mode: "sample",
                          sample_size: caseScope.sample_size ?? 50,
                          seed: parseInt(e.target.value) || undefined,
                        })
                      }
                      className="h-8 w-32"
                      placeholder="Seed (optional)"
                    />
                  </div>
                )}
              </div>
            </label>

            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="radio"
                name="case_scope_mode"
                checked={caseScope?.mode === "filtered"}
                onChange={() => setCaseScope({ mode: "filtered", filters: {} })}
                className="mt-1 h-4 w-4"
              />
              <div className="flex-1">
                <div className="font-medium text-text-primary">Filtered</div>
                <div className="text-sm text-text-tertiary">
                  Run on cases matching specific criteria.
                </div>
                {caseScope?.mode === "filtered" && (
                  <div className="mt-2">
                    <Input
                      type="text"
                      placeholder="Filter by tags..."
                      className="h-8"
                    />
                  </div>
                )}
              </div>
            </label>
          </div>
        </Surface>
      )}

      <div className="flex justify-between">
        <Button variant="secondary" onClick={onPrevious}>
          Back
        </Button>
        <Button onClick={onNext} disabled={!selectedBenchmarkId}>
          Next: Configure Metrics
        </Button>
      </div>
    </div>
  );
}

interface DatasetRowProps {
  dataset: DatasetInfo;
  isSelected: boolean;
  onSelect: () => void;
}

function DatasetRow({ dataset, isSelected, onSelect }: DatasetRowProps) {
  const caseCount = dataset.case_count ?? 0;
  const tags = dataset.tags ?? [];

  return (
    <TableRow
      className="cursor-pointer transition-colors hover:bg-surface-hover"
      onClick={onSelect}
    >
      <TableCell>
        <input
          type="radio"
          name="dataset_selection"
          checked={isSelected}
          onChange={onSelect}
          className="h-4 w-4"
          aria-label={`Select ${dataset.name}`}
        />
      </TableCell>
      <TableCell>
        <div>
          <div className="font-medium text-text-primary">{dataset.name}</div>
        </div>
      </TableCell>
      <TableCell>
        <Badge variant="info">{caseCount.toLocaleString()}</Badge>
      </TableCell>
      <TableCell>
        <span className="text-sm text-text-secondary">{dataset.version}</span>
      </TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {tags.slice(0, 3).map((tag: string) => (
            <span key={tag} className="rounded border border-border bg-surface px-1.5 py-0.5 text-xs text-text-tertiary">
              {tag}
            </span>
          ))}
          {tags.length > 3 && (
            <span className="text-xs text-text-tertiary">
              +{tags.length - 3}
            </span>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}
