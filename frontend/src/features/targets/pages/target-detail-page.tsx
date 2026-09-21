/** Target detail page backed entirely by the target-management API. */
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Surface } from "@/components/layout/surface";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { CapabilityList } from "../components/capability-list";
import { ConnectionTestResult } from "../components/connection-test-result";
import { TargetStatus } from "../components/target-status";
import { formatAdapterType, formatRelativeTime } from "../target-formatters";
import { TargetService } from "../target-service";
import {
  targetQueryKeys,
  useDiscoverCapabilities,
  useTarget,
  useTargetAdapterSource,
  useTargetCapabilities,
  useTargetConfiguration,
  useTargetConfigurationVersions,
  useTargetConnection,
  useDeleteTarget,
  useSaveTargetConfiguration,
  useTestConnection,
  useUpdateTarget,
  useUploadPythonAdapter,
} from "../use-targets";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "@/lib/toast";

export function TargetDetailPage() {
  const { targetId = "" } = useParams<{ targetId: string }>();
  const navigate = useNavigate();
  const client = useQueryClient();
  const target = useTarget(targetId);
  const configuration = useTargetConfiguration(targetId, { retry: false });
  const versions = useTargetConfigurationVersions(targetId);
  const source = useTargetAdapterSource(targetId, {
    enabled: target.data?.adapter_type === "uploaded_python",
    retry: false,
  });
  const connection = useTargetConnection(targetId);
  const capabilities = useTargetCapabilities(targetId, { retry: false });
  const [yaml, setYaml] = useState("");
  const [showYaml, setShowYaml] = useState(false);
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  useEffect(() => {
    if (configuration.data?.yaml) setYaml(configuration.data.yaml);
  }, [configuration.data?.yaml]);
  const reportError = (action: string) => (error: Error) => {
    toast.error(`${action}: ${error.message}`);
  };
  const save = useSaveTargetConfiguration(targetId, {
    onSuccess: () => {
      toast.success("Configuration version saved");
      setShowYaml(false);
    },
    onError: reportError("Could not save configuration"),
  });
  const upload = useUploadPythonAdapter(targetId, {
    onSuccess: () => {
      toast.success("Python adapter uploaded");
      setSourceFile(null);
    },
    onError: reportError("Could not upload adapter"),
  });
  const test = useTestConnection({
    onSuccess: () => {
      toast.success("Connection state refreshed");
      void client.invalidateQueries({ queryKey: targetQueryKeys.connection(targetId) });
    },
    onError: reportError("Connection test failed"),
  });
  const discover = useDiscoverCapabilities({
    onSuccess: () => {
      toast.success("Capabilities discovered");
    },
    onError: reportError("Capability discovery failed"),
  });
  const update = useUpdateTarget(targetId, {
    onSuccess: () => {
      toast.success("Target updated");
    },
    onError: reportError("Could not update target"),
  });
  const remove = useDeleteTarget({
    onSuccess: () => {
      toast.success("Target deleted");
      navigate("/targets");
    },
    onError: reportError("Could not delete target"),
  });
  if (target.isLoading)
    return (
      <Page>
        <Page.Header title="Loading target..." />
        <Page.Content>
          <Spinner />
        </Page.Content>
      </Page>
    );
  if (target.error || !target.data)
    return (
      <Page>
        <Page.Header
          title="Target not found"
          actions={
            <Button variant="secondary" asChild>
              <Link to="/targets">Back to Targets</Link>
            </Button>
          }
        />
        <Page.Content>
          <EmptyState
            title="Target not found"
            description="This target may have been deleted."
          />
        </Page.Content>
      </Page>
    );
  const item = target.data;
  const isUploaded = item.adapter_type === "uploaded_python";
  return (
    <Page>
      <Page.Header
        title={item.name}
        description="Evaluator-managed target"
        breadcrumbs={[{ label: "Targets", href: "/targets" }]}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={() => {
                test.mutate(targetId);
              }}
              disabled={test.isPending || item.configuration_status !== "configured"}
            >
              {test.isPending ? "Testing..." : "Test connection"}
            </Button>
            <Button variant="secondary" asChild>
              <Link to={`/targets/${encodeURIComponent(targetId)}/edit`}>Edit</Link>
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                if (window.confirm(`Delete ${item.name}?`)) remove.mutate(targetId);
              }}
            >
              Delete
            </Button>
          </div>
        }
      />
      <Page.Content>
        <div className="space-y-6">
          <Surface className="p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-medium text-text-primary">Status</h2>
                <div className="mt-3 flex flex-wrap gap-2">
                  <TargetStatus status={item.configuration_status} />
                  <TargetStatus
                    status={
                      connection.data?.status ?? item.connection?.status ?? "not_tested"
                    }
                  />
                  <Badge variant={item.enabled ? "success" : "default"}>
                    {item.enabled ? "Enabled" : "Disabled"}
                  </Badge>
                  {item.current_config_version && (
                    <Badge variant="info">
                      Config v{String(item.current_config_version)}
                    </Badge>
                  )}
                </div>
              </div>
              <Button
                variant="secondary"
                onClick={() => {
                  update.mutate({ enabled: !item.enabled });
                }}
              >
                {item.enabled ? "Disable target" : "Enable target"}
              </Button>
            </div>
            <div className="mt-5 grid gap-4 sm:grid-cols-3">
              <Info label="Target ID" value={item.target_id} />
              <Info label="Adapter" value={formatAdapterType(item.adapter_type)} />
              <Info label="Updated" value={formatRelativeTime(item.updated_at)} />
            </div>
          </Surface>
          {connection.data && <ConnectionTestResult connection={connection.data} />}
          {connection.error && !connection.data && (
            <Alert
              variant={connection.error.message.includes("404") ? "info" : "error"}
            >
              <AlertDescription>
                {connection.error.message.includes("404")
                  ? "Connection has not been tested yet."
                  : `Unable to load connection state: ${connection.error.message}`}
              </AlertDescription>
            </Alert>
          )}
          {isUploaded ? (
            <Surface className="p-6">
              <h2 className="text-lg font-medium text-text-primary">
                Uploaded Python adapter
              </h2>
              {source.data ? (
                <div className="mt-3 space-y-2 text-sm">
                  <Info label="File" value={source.data.filename} />
                  <Info label="Artifact" value={source.data.artifact_id} />
                  <Info label="Hash" value={source.data.content_hash ?? "—"} />
                </div>
              ) : (
                <p className="mt-3 text-sm text-text-tertiary">
                  No adapter source metadata is available.
                </p>
              )}
              <div className="mt-4 flex items-center gap-3">
                <input
                  type="file"
                  accept=".py"
                  onChange={(event) => {
                    setSourceFile(event.target.files?.[0] ?? null);
                  }}
                  className="text-sm"
                />
                <Button
                  variant="secondary"
                  disabled={!sourceFile || upload.isPending}
                  onClick={() => {
                    if (sourceFile) upload.mutate(sourceFile);
                  }}
                >
                  {upload.isPending ? "Uploading..." : "Upload replacement"}
                </Button>
              </div>
            </Surface>
          ) : (
            <Surface className="p-6">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-medium text-text-primary">
                    Configuration
                  </h2>
                  <p className="text-sm text-text-tertiary">
                    Secrets remain write-only references in this sanitized YAML.
                  </p>
                </div>
                <Button
                  variant="secondary"
                  onClick={() => {
                    setShowYaml((value) => !value);
                  }}
                >
                  {showYaml ? "Close YAML editor" : "Edit YAML"}
                </Button>
              </div>
              {showYaml && (
                <div className="mt-4 space-y-3">
                  <Textarea
                    value={yaml}
                    onChange={(event) => {
                      setYaml(event.target.value);
                    }}
                    rows={18}
                    className="font-mono text-xs"
                  />
                  <Button
                    onClick={() => {
                      save.mutate(yaml);
                    }}
                    disabled={save.isPending}
                  >
                    {save.isPending ? "Saving..." : "Save new version"}
                  </Button>
                </div>
              )}
              {!showYaml && (
                <div className="mt-4 rounded bg-surface-hover p-4">
                  <pre className="max-h-72 overflow-auto whitespace-pre-wrap text-xs text-text-secondary">
                    {yaml || "No configuration saved yet."}
                  </pre>
                </div>
              )}
            </Surface>
          )}
          <Surface className="p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-medium text-text-primary">
                Configuration history
              </h2>
              <span className="text-sm text-text-tertiary">
                {versions.data?.length ?? 0} versions
              </span>
            </div>
            {versions.data?.length ? (
              <div className="mt-4 space-y-2">
                {versions.data.map((version) => (
                  <div
                    key={version.config_version_id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded border border-border-default p-3 text-sm"
                  >
                    <span className="font-medium">v{String(version.version)}</span>
                    <code className="text-xs text-text-tertiary">
                      {version.config_hash.slice(0, 12)}...
                    </code>
                    <span className="text-text-tertiary">
                      {formatRelativeTime(version.created_at)}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        void TargetService.getConfigurationVersion(
                          targetId,
                          version.version
                        ).then((detail) => {
                          setYaml(detail.yaml);
                          setShowYaml(true);
                        });
                      }}
                    >
                      View
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-text-tertiary">
                No configuration versions yet.
              </p>
            )}
          </Surface>
          {capabilities.data ? (
            <CapabilityList
              capabilities={capabilities.data.capabilities}
              refreshing={discover.isPending}
              onRefresh={() => {
                discover.mutate(targetId);
              }}
            />
          ) : (
            <Surface className="p-6">
              <h2 className="text-lg font-medium text-text-primary">Capabilities</h2>
              <p className="mt-2 text-sm text-text-tertiary">
                Discover capabilities after configuring the target.
              </p>
              <Button
                className="mt-4"
                variant="secondary"
                onClick={() => {
                  discover.mutate(targetId);
                }}
                disabled={
                  discover.isPending || item.configuration_status !== "configured"
                }
              >
                {discover.isPending ? "Discovering..." : "Discover capabilities"}
              </Button>
            </Surface>
          )}
          <Surface className="p-6">
            <h2 className="text-lg font-medium text-text-primary">Metadata</h2>
            <pre className="mt-3 whitespace-pre-wrap text-xs text-text-secondary">
              {JSON.stringify(item.metadata, null, 2)}
            </pre>
          </Surface>
        </div>
      </Page.Content>
    </Page>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-text-tertiary">{label}</div>
      <div className="mt-1 break-all text-sm text-text-primary">{value}</div>
    </div>
  );
}
