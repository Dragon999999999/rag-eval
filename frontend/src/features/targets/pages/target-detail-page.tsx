/**
 * Target detail page - /targets/:targetId
 *
 * Shows target configuration, status, capabilities, and actions.
 */
import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { CapabilityList } from "../components/capability-list";
import { ConnectionTestResult } from "../components/connection-test-result";
import {
  useTarget,
  useTargetCapabilities,
  useRefreshCapabilities,
  useDeleteTarget,
} from "../use-targets";
import {
  formatAdapterType,
  formatCorpusMode,
  formatTargetEndpoint,
  formatRelativeTime,
} from "../target-formatters";
import { toast } from "@/lib/toast";
import { Waypoints, Copy, Trash2 } from "lucide-react";
import { IconButton } from "@/components/ui/icon-button";
import {
  Dialog,
  DialogTrigger,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

export function TargetDetailPage() {
  const { targetId } = useParams<{ targetId: string }>();
  const navigate = useNavigate();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  const {
    data: target,
    isLoading: isLoadingTarget,
    error: targetError,
  } = useTarget(targetId ?? "");

  const {
    data: capabilitiesData,
    isLoading: isLoadingCapabilities,
    refetch: refetchCapabilities,
  } = useTargetCapabilities(targetId ?? "");

  const refreshCapabilities = useRefreshCapabilities({
    onSuccess: () => {
      toast.success("Connection test successful");
      refetchCapabilities();
    },
    onError: (error) => {
      toast.error(`Connection test failed: ${error.message}`);
    },
  });

  // Connection test result for display
  const connectionTestResult = refreshCapabilities.data
    ? {
        success: true,
        target_id: targetId ?? "",
        response_time_ms: 100, // Mock - real impl would get from backend
        tested_at: new Date().toISOString(),
      }
    : undefined;

  const deleteTarget = useDeleteTarget({
    onSuccess: () => {
      toast.success("Target deleted");
      navigate("/targets");
    },
    onError: (error) => {
      toast.error(`Failed to delete target: ${error.message}`);
    },
  });

  const handleTestConnection = () => {
    if (targetId) {
      refreshCapabilities.mutate(targetId);
    }
  };

  const handleDelete = () => {
    if (targetId) {
      deleteTarget.mutate(targetId);
      setShowDeleteDialog(false);
    }
  };

  const handleCopyEndpoint = () => {
    if (target) {
      const endpoint = formatTargetEndpoint(target);
      navigator.clipboard.writeText(endpoint);
      toast.success("Endpoint copied to clipboard");
    }
  };

  if (isLoadingTarget) {
    return (
      <Page>
        <Page.Header
          title="Loading..."
          description="Loading target configuration."
          breadcrumbs={[{ label: "Targets", href: "/targets" }]}
        />
        <Page.Content>
          <div className="space-y-4">
            <Surface className="p-6">
              <Spinner />
            </Surface>
          </div>
        </Page.Content>
      </Page>
    );
  }

  if (targetError || !target) {
    return (
      <Page>
        <Page.Header
          title="Target not found"
          description="The requested target does not exist or was removed."
          breadcrumbs={[{ label: "Targets", href: "/targets" }]}
          actions={
            <Button variant="secondary" asChild>
              <Link to="/targets">Back to Targets</Link>
            </Button>
          }
        />
        <Page.Content>
          <EmptyState
            icon={<Waypoints className="h-8 w-8" />}
            title="Target not found"
            description="This target may have been deleted or the URL is incorrect."
            action={
              <Button asChild>
                <Link to="/targets">Browse Targets</Link>
              </Button>
            }
          />
        </Page.Content>
      </Page>
    );
  }

  return (
    <Page>
      <Page.Header
        title={target.name}
        description="Target configuration and capabilities"
        breadcrumbs={[{ label: "Targets", href: "/targets" }]}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleTestConnection}
              disabled={refreshCapabilities.isPending}
            >
              {refreshCapabilities.isPending ? "Testing..." : "Test Connection"}
            </Button>
            <Button variant="secondary" size="sm" asChild>
              <Link to={`/targets/${targetId}/edit`}>Edit</Link>
            </Button>
            <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
              <DialogTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-error hover:text-error"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </DialogTrigger>
              <DialogPortal>
                <DialogOverlay />
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Delete target?</DialogTitle>
                    <DialogDescription>
                      <p>
                        <strong>{target.name}</strong> will be permanently removed.
                      </p>
                      <p className="mt-2">
                        Existing evaluation runs will remain available because they
                        contain immutable target/configuration snapshots.
                      </p>
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <Button
                      variant="secondary"
                      onClick={() => setShowDeleteDialog(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="danger"
                      onClick={handleDelete}
                      disabled={deleteTarget.isPending}
                    >
                      {deleteTarget.isPending ? "Deleting..." : "Delete Target"}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </DialogPortal>
            </Dialog>
          </div>
        }
      />

      <Page.Content>
        <div className="space-y-6">
          {/* Connection test result */}
          {connectionTestResult && (
            <ConnectionTestResult result={connectionTestResult} />
          )}

          {/* Identity section */}
          <Surface className="p-6">
            <h3 className="text-base font-medium text-text-primary">Overview</h3>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <InfoRow label="Name" value={target.name} />
              <InfoRow label="Version" value={target.version ?? "—"} />
              <InfoRow label="Adapter Type" value={formatAdapterType(target.adapter)} />
              <InfoRow
                label="Corpus Mode"
                value={formatCorpusMode(target.corpus_mode)}
              />
              <InfoRow
                label="Endpoint"
                value={formatTargetEndpoint(target)}
                action={
                  <IconButton
                    icon={<Copy className="h-4 w-4" />}
                    onClick={handleCopyEndpoint}
                    aria-label="Copy endpoint"
                  />
                }
              />
              <InfoRow label="Created" value={formatRelativeTime(target.created_at)} />
              <InfoRow
                label="Last Updated"
                value={formatRelativeTime(target.updated_at)}
              />
            </div>
          </Surface>

          {/* Configuration section */}
          <Surface className="p-6">
            <h3 className="text-base font-medium text-text-primary">Configuration</h3>
            <div className="mt-4 space-y-4">
              {target.adapter === "http" && (
                <>
                  <InfoRow label="Base URL" value={target.base_url ?? "—"} />
                  <InfoRow
                    label="Authentication"
                    value={
                      target.authentication_env
                        ? `Configured (${target.authentication_env})`
                        : "None"
                    }
                  />
                </>
              )}
              {target.adapter === "python" && (
                <InfoRow label="Python Target" value={target.python_target ?? "—"} />
              )}
              {target.implementation && (
                <InfoRow label="Implementation" value={target.implementation} />
              )}
            </div>
          </Surface>

          {/* Capabilities section */}
          {isLoadingCapabilities ? (
            <Surface className="p-6">
              <div className="flex items-center gap-2 text-text-tertiary">
                <Spinner size="sm" />
                <span>Loading capabilities...</span>
              </div>
            </Surface>
          ) : capabilitiesData ? (
            <CapabilityList capabilities={capabilitiesData.capabilities} />
          ) : (
            <Alert variant="info">
              <AlertDescription>
                Capabilities have not been discovered yet. Click "Test Connection" to
                discover target capabilities.
              </AlertDescription>
            </Alert>
          )}
        </div>
      </Page.Content>
    </Page>
  );
}

interface InfoRowProps {
  label: string;
  value: string;
  action?: React.ReactNode;
}

function InfoRow({ label, value, action }: InfoRowProps) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-sm text-text-tertiary">{label}</p>
        <p className="mt-1 font-medium text-text-primary">{value}</p>
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  );
}
