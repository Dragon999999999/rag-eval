import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { FlaskConical, Plus } from "lucide-react";
import { Page } from "@/components/layout/page-layout";
import { EmptyState } from "@/components/ui/empty-state";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SearchInput } from "@/components/ui/search-input";
import { Spinner } from "@/components/ui/spinner";
import { Surface } from "@/components/layout/surface";
import { useTests } from "../use-tests";
import type { TestDefinitionInfo } from "../test-types";

/** Saved test definitions with a compact readiness overview. */
export function TestsPage() {
  const { data: tests, isLoading, error, refetch } = useTests();
  const [query, setQuery] = useState("");
  const filtered = useMemo(
    () =>
      (tests ?? []).filter((test) =>
        `${test.name} ${test.test_definition_id}`
          .toLowerCase()
          .includes(query.toLowerCase())
      ),
    [query, tests]
  );

  return (
    <Page>
      <Page.Header
        title="Tests"
        description="Create saved evaluation configurations and monitor their runs."
        actions={
          <Button asChild>
            <Link to="/tests/new">
              <Plus className="h-4 w-4" /> Create Test
            </Link>
          </Button>
        }
      />
      <Page.Content>
        {isLoading && (
          <div className="flex justify-center py-16">
            <Spinner size="lg" />
          </div>
        )}
        {error && (
          <Alert variant="error">
            <AlertDescription>
              Unable to load tests.{" "}
              <Button size="sm" variant="secondary" onClick={() => void refetch()}>
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        )}
        {!isLoading && !error && tests?.length === 0 && (
          <EmptyState
            icon={<FlaskConical className="h-8 w-8" />}
            title="No tests yet"
            description="Create a test with only a name, then finish its configuration when you are ready."
            action={
              <Button asChild>
                <Link to="/tests/new">Create Test</Link>
              </Button>
            }
          />
        )}
        {!isLoading && !error && tests && tests.length > 0 && (
          <div className="space-y-4">
            <div className="max-w-sm">
              <SearchInput
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                }}
                onClear={() => {
                  setQuery("");
                }}
                placeholder="Search tests..."
              />
            </div>
            <Surface className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-border-default bg-surface-elevated text-xs uppercase tracking-wide text-text-tertiary">
                    <tr>
                      <th className="px-4 py-3">Test</th>
                      <th className="px-4 py-3">Configuration</th>
                      <th className="px-4 py-3">Benchmark</th>
                      <th className="px-4 py-3">Target</th>
                      <th className="px-4 py-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-default">
                    {filtered.map((test) => (
                      <TestRow key={test.test_definition_id} test={test} />
                    ))}
                  </tbody>
                </table>
              </div>
              {filtered.length === 0 && (
                <p className="p-6 text-sm text-text-tertiary">
                  No tests match that search.
                </p>
              )}
            </Surface>
          </div>
        )}
      </Page.Content>
    </Page>
  );
}

function TestRow({ test }: { test: TestDefinitionInfo }) {
  const ready = test.configuration_status === "READY";
  return (
    <tr className="hover:bg-surface-hover">
      <td className="px-4 py-4">
        <Link
          className="font-medium text-text-primary hover:text-accent"
          to={`/tests/${test.test_definition_id}`}
        >
          {test.name}
        </Link>
        <div className="mt-1 text-xs text-text-tertiary">{test.test_definition_id}</div>
      </td>
      <td className="px-4 py-4">
        <Badge variant={ready ? "success" : "warning"}>
          {ready ? "Ready" : "Not configured"}
        </Badge>
      </td>
      <td className="px-4 py-4 text-text-secondary">
        {test.benchmark_id ?? "Not selected"}
      </td>
      <td className="px-4 py-4 text-text-secondary">
        {test.target_id ?? "Not selected"}
      </td>
      <td className="px-4 py-4 text-right">
        <Button size="sm" variant="secondary" asChild>
          <Link to={`/tests/${test.test_definition_id}`}>Open</Link>
        </Button>
      </td>
    </tr>
  );
}
