/**
 * Tests list page - displays all test definitions.
 */
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import { EmptyState } from "@/components/ui/empty-state";
import { Spinner } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { SearchInput } from "@/components/ui/search-input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { FlaskConical } from "lucide-react";
import { useTests } from "../use-tests";
import { formatRelativeTime, formatExecutionConfig } from "../test-formatters";
import type { TestDefinitionInfo } from "../test-types";

export function TestsPage() {
  const { data: tests, isLoading, error, refetch } = useTests();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="error">
        <AlertDescription>
          An error occurred while fetching tests.
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

  if (!tests || tests.length === 0) {
    return (
      <EmptyState
        icon={<FlaskConical className="h-8 w-8" />}
        title="No tests configured"
        description="Create a test to define an evaluation configuration combining a target, dataset, and metrics."
        action={
          <Button asChild>
            <Link to="/tests/new">New Test</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="w-64">
          <SearchInput placeholder="Search tests..." />
        </div>
        <Button asChild>
          <Link to="/tests/new">+ New Test</Link>
        </Button>
      </div>

      <Surface>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Target</TableHead>
              <TableHead>Dataset</TableHead>
              <TableHead>Metrics</TableHead>
              <TableHead>Execution</TableHead>
              <TableHead>Tags</TableHead>
              <TableHead>Last Updated</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tests.map((test: TestDefinitionInfo) => (
              <TestRow key={test.test_definition_id} test={test} />
            ))}
          </TableBody>
        </Table>
      </Surface>
    </div>
  );
}

interface TestRowProps {
  test: TestDefinitionInfo;
}

function TestRow({ test }: TestRowProps) {
  return (
    <TableRow>
      <TableCell>
        <div>
          <div className="font-medium text-text-primary">{test.name}</div>
          {test.description && (
            <div className="line-clamp-1 text-xs text-text-tertiary">
              {test.description}
            </div>
          )}
        </div>
      </TableCell>
      <TableCell>
        <div className="text-sm text-text-secondary">{test.target_id}</div>
      </TableCell>
      <TableCell>
        <div className="text-sm text-text-secondary">{test.benchmark_id}</div>
      </TableCell>
      <TableCell>
        <span className="rounded bg-surface-hover px-1.5 py-0.5 text-xs text-text-tertiary">
          {test.metric_config_id}
        </span>
      </TableCell>
      <TableCell>
        <div className="text-sm text-text-tertiary">
          {formatExecutionConfig(test.execution_config)}
        </div>
      </TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {test.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="border-border rounded border bg-surface px-1.5 py-0.5 text-xs text-text-tertiary"
            >
              {tag}
            </span>
          ))}
          {test.tags.length > 3 && (
            <span className="text-xs text-text-tertiary">+{test.tags.length - 3}</span>
          )}
        </div>
      </TableCell>
      <TableCell>
        <span className="text-sm text-text-tertiary">
          {formatRelativeTime(test.updated_at)}
        </span>
      </TableCell>
      <TableCell className="text-right">
        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" asChild>
            <Link to={`/tests/${test.test_definition_id}`}>View</Link>
          </Button>
          <Button variant="ghost" size="sm" asChild>
            <Link to={`/tests/${test.test_definition_id}/edit`}>Edit</Link>
          </Button>
          <Button variant="secondary" size="sm" asChild>
            <Link to={`/tests/${test.test_definition_id}/run`}>Run</Link>
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
}
