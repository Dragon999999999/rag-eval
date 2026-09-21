/** Edit target identity and create a new configuration version. */
import { useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import {
  TargetForm,
  buildTargetYaml,
  type TargetFormValues,
} from "../components/target-form";
import { TargetService } from "../target-service";
import {
  targetQueryKeys,
  useTarget,
  useTargetAdapters,
  useTargetConfiguration,
} from "../use-targets";
import { toast } from "@/lib/toast";

export function TargetEditPage() {
  const { targetId = "" } = useParams<{ targetId: string }>();
  const navigate = useNavigate();
  const client = useQueryClient();
  const target = useTarget(targetId);
  const adapters = useTargetAdapters();
  const configuration = useTargetConfiguration(targetId, { retry: false });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submit = async (values: TargetFormValues) => {
    setIsSubmitting(true);
    try {
      await TargetService.updateTarget(targetId, {
        name: values.name,
        metadata: values.metadata,
      });
      if (values.pythonFile)
        await TargetService.uploadPythonAdapter(targetId, values.pythonFile);
      else if (values.yamlFile)
        await TargetService.saveConfiguration(targetId, await values.yamlFile.text());
      else if (values.mode !== "python")
        await TargetService.saveConfiguration(
          targetId,
          values.mode === "yaml" ? values.yaml : buildTargetYaml(values.draft)
        );
      await client.invalidateQueries({ queryKey: targetQueryKeys.all });
      toast.success("Target updated");
      navigate(`/targets/${encodeURIComponent(targetId)}`);
    } catch (error) {
      toast.error(
        `Failed to update target: ${error instanceof Error ? error.message : "Unknown error"}`
      );
    } finally {
      setIsSubmitting(false);
    }
  };
  if (target.isLoading || adapters.isLoading || configuration.isLoading)
    return (
      <Page>
        <Page.Header title="Loading..." />
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
  return (
    <Page>
      <Page.Header
        title="Edit Target"
        description={`Editing ${target.data.name}`}
        breadcrumbs={[
          { label: "Targets", href: "/targets" },
          { label: target.data.name, href: `/targets/${encodeURIComponent(targetId)}` },
          { label: "Edit", href: "#" },
        ]}
      />
      <Page.Content>
        <div className="mx-auto max-w-4xl">
          <TargetForm
            target={target.data}
            adapters={adapters.data ?? []}
            initialYaml={configuration.data?.yaml ?? ""}
            onSubmit={(values) => {
              void submit(values);
            }}
            isSubmitting={isSubmitting}
            onCancel={() => {
              navigate(`/targets/${encodeURIComponent(targetId)}`);
            }}
            error={
              configuration.error && configuration.error.message.includes("404")
                ? null
                : configuration.error?.message
            }
          />
        </div>
      </Page.Content>
    </Page>
  );
}
