import { Link, useSearchParams } from "react-router-dom";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import { EmptyState } from "@/components/ui/empty-state";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { SearchInput } from "@/components/ui/search-input";
import { Skeleton } from "@/components/ui/skeleton";
import { TargetStatus } from "./target-status";
import { formatAdapterType, formatRelativeTime } from "../target-formatters";
import { useTargetList } from "../use-targets";
import type { TargetSummary } from "../target-types";

export function TargetList() {
  const [params, setParams] = useSearchParams();
  const search = params.get("search") ?? "";
  const { data: targets, isLoading, error, refetch } = useTargetList();

  if (isLoading) return <TargetListSkeleton />;
  if (error) {
    return (
      <Alert variant="error">
        <AlertDescription>
          Unable to load targets.{" "}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              void refetch();
            }}
          >
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }
  const filtered = (targets ?? []).filter((target) =>
    target.name.toLowerCase().includes(search.toLowerCase())
  );
  if (!targets?.length) {
    return (
      <EmptyState
        title="No targets registered"
        description="Create a target to connect a RAG system or LLM endpoint."
        action={
          <Button asChild>
            <Link to="/targets/new">Add Target</Link>
          </Button>
        }
      />
    );
  }
  return (
    <div className="space-y-4">
      <SearchInput
        value={search}
        onChange={(event) => {
          const next = new URLSearchParams(params);
          if (event.target.value) next.set("search", event.target.value);
          else next.delete("search");
          setParams(next);
        }}
        placeholder="Search targets..."
      />
      {!filtered.length ? (
        <EmptyState title="No matching targets" description="Try a different search." />
      ) : (
        <Surface>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Adapter</TableHead>
                <TableHead>Configuration</TableHead>
                <TableHead>Connection</TableHead>
                <TableHead>Enabled</TableHead>
                <TableHead>Version</TableHead>
                <TableHead>Updated</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((target) => (
                <TargetRow key={target.target_id} target={target} />
              ))}
            </TableBody>
          </Table>
        </Surface>
      )}
    </div>
  );
}

function TargetRow({ target }: { target: TargetSummary }) {
  return (
    <TableRow>
      <TableCell>
        <div className="font-medium text-text-primary">{target.name}</div>
        <div className="text-xs text-text-tertiary">{target.target_id}</div>
      </TableCell>
      <TableCell>{formatAdapterType(target.adapter_type)}</TableCell>
      <TableCell>
        <TargetStatus status={target.configuration_status} />
      </TableCell>
      <TableCell>
        <TargetStatus status={target.connection_status} />
      </TableCell>
      <TableCell>{target.enabled ? "Enabled" : "Disabled"}</TableCell>
      <TableCell>
        {target.current_config_version
          ? `v${String(target.current_config_version)}`
          : "—"}
      </TableCell>
      <TableCell className="text-text-tertiary">
        {formatRelativeTime(target.updated_at)}
      </TableCell>
      <TableCell className="text-right">
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/targets/${encodeURIComponent(target.target_id)}`}>Open</Link>
        </Button>
      </TableCell>
    </TableRow>
  );
}

function TargetListSkeleton() {
  return (
    <Surface className="space-y-3 p-6">
      {[1, 2, 3].map((row) => (
        <Skeleton key={row} className="h-10 w-full" />
      ))}
    </Surface>
  );
}
