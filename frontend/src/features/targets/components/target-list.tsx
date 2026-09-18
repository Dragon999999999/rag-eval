/**
 * Target list component for /targets page.
 *
 * Displays targets in a dense table format with status, capabilities, and actions.
 */
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
import { StatusBadge } from "@/components/ui/status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { SearchInput } from "@/components/ui/search-input";
import {
  formatAdapterType,
  formatTargetEndpoint,
  formatRelativeTime,
  getCapabilityBadges,
} from "../target-formatters";
import { useTargetList } from "../use-targets";
import type { Target } from "../target-types";

interface TargetListProps {}

export function TargetList({}: TargetListProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get("search") ?? "";
  const typeFilter = searchParams.get("type") ?? "";
  const statusFilter = searchParams.get("status") ?? "";

  const { data: targets, isLoading, error, refetch } = useTargetList();

  // Client-side filtering (backend doesn't support server-side search yet)
  const filteredTargets = targets?.filter((target: Target) => {
    // Search filter
    if (search && !target.name.toLowerCase().includes(search.toLowerCase())) {
      return false;
    }

    // Type filter
    if (typeFilter && target.adapter !== typeFilter) {
      return false;
    }

    // Status filter - for now all targets are considered "active"
    if (statusFilter && statusFilter !== "all") {
      // Could implement more sophisticated status filtering
      return false;
    }

    return true;
  });

  // Handle search input
  const handleSearchChange = (value: string) => {
    const newParams = new URLSearchParams(searchParams);
    if (value) {
      newParams.set("search", value);
    } else {
      newParams.delete("search");
    }
    setSearchParams(newParams);
  };

  // Handle type filter
  const handleTypeChange = (value: string) => {
    const newParams = new URLSearchParams(searchParams);
    if (value && value !== "all") {
      newParams.set("type", value);
    } else {
      newParams.delete("type");
    }
    setSearchParams(newParams);
  };

  if (isLoading) {
    return <TargetListSkeleton />;
  }

  if (error) {
    return (
      <Alert variant="error">
        <AlertDescription>
          An error occurred while fetching targets.
          <Button
            variant="secondary"
            size="sm"
            onClick={() => refetch()}
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
        description="Targets define the RAG or LLM systems that RAG-Eval sends benchmark queries to."
        action={
          <Button asChild>
            <Link to="/targets/new">Add Target</Link>
          </Button>
        }
      />
    );
  }

  if (!filteredTargets || filteredTargets.length === 0) {
    return (
      <EmptyState
        title="No matching targets"
        description="Try adjusting your search or filters."
        action={
          <Button variant="secondary" size="sm" onClick={() => setSearchParams({})}>
            Clear filters
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="w-64">
          <SearchInput
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search targets..."
          />
        </div>

        <select
          value={typeFilter}
          onChange={(e) => handleTypeChange(e.target.value)}
          className="border-border focus:ring-ring h-9 rounded-md border bg-surface px-3 text-sm text-text-primary focus:outline-none focus:ring-2"
        >
          <option value="">All Types</option>
          <option value="http">HTTP</option>
          <option value="python">Python</option>
        </select>
      </div>

      {/* Target table */}
      <Surface>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[200px]">Name</TableHead>
              <TableHead className="w-[150px]">Type</TableHead>
              <TableHead>Endpoint / Adapter</TableHead>
              <TableHead className="w-[120px]">Status</TableHead>
              <TableHead className="w-[200px]">Capabilities</TableHead>
              <TableHead className="w-[120px]">Last Checked</TableHead>
              <TableHead className="w-[80px] text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredTargets.map((target: Target) => (
              <TargetRow key={target.targetId} target={target} />
            ))}
          </TableBody>
        </Table>
      </Surface>
    </div>
  );
}

interface TargetRowProps {
  target: Target;
}

function TargetRow({ target }: TargetRowProps) {
  // For mock data, assume connected if we have the target
  // Real implementation would check capabilities cache

  const capabilities = getCapabilityBadges({
    query: true, // Mock - real impl would check capabilities
    retrieval: true,
    citations: true,
    usage: { tokens: true },
    streaming: target.adapter === "http",
    target_trace: target.adapter === "http",
  });

  return (
    <TableRow>
      <TableCell>
        <div>
          <div className="font-medium text-text-primary">{target.name}</div>
          {target.version && (
            <div className="text-xs text-text-tertiary">{target.version}</div>
          )}
        </div>
      </TableCell>
      <TableCell>
        <span className="text-sm text-text-secondary">
          {formatAdapterType(target.adapter)}
        </span>
      </TableCell>
      <TableCell>
        <div
          className="truncate text-sm text-text-secondary"
          title={formatTargetEndpoint(target)}
        >
          {formatTargetEndpoint(target)}
        </div>
      </TableCell>
      <TableCell>
        <StatusBadge status="success" showDot>
          Connected
        </StatusBadge>
      </TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {capabilities.slice(0, 4).map((cap: string) => (
            <span
              key={cap}
              className="rounded bg-surface-hover px-1.5 py-0.5 text-xs text-text-tertiary"
            >
              {cap}
            </span>
          ))}
          {capabilities.length > 4 && (
            <span className="text-xs text-text-tertiary">
              +{capabilities.length - 4}
            </span>
          )}
        </div>
      </TableCell>
      <TableCell>
        <span className="text-sm text-text-tertiary">
          {formatRelativeTime(target.updated_at)}
        </span>
      </TableCell>
      <TableCell className="text-right">
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/targets/${target.targetId}`}>Open</Link>
        </Button>
      </TableCell>
    </TableRow>
  );
}

function TargetListSkeleton() {
  return (
    <Surface>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[200px]">Name</TableHead>
            <TableHead className="w-[150px]">Type</TableHead>
            <TableHead>Endpoint / Adapter</TableHead>
            <TableHead className="w-[120px]">Status</TableHead>
            <TableHead className="w-[200px]">Capabilities</TableHead>
            <TableHead className="w-[120px]">Last Checked</TableHead>
            <TableHead className="w-[80px] text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {[...Array(5)].map((_, i) => (
            <TableRow key={i}>
              <TableCell>
                <Skeleton className="h-4 w-32" />
              </TableCell>
              <TableCell>
                <Skeleton className="h-4 w-24" />
              </TableCell>
              <TableCell>
                <Skeleton className="h-4 w-48" />
              </TableCell>
              <TableCell>
                <Skeleton className="h-5 w-20" />
              </TableCell>
              <TableCell>
                <div className="flex gap-1">
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-4 w-12" />
                </div>
              </TableCell>
              <TableCell>
                <Skeleton className="h-4 w-16" />
              </TableCell>
              <TableCell>
                <Skeleton className="ml-auto h-7 w-14" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Surface>
  );
}
