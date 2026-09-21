/** Create a target and optionally configure it in the same flow. */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Page } from "@/components/layout/page-layout";
import { Spinner } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  TargetForm,
  buildTargetYaml,
  type TargetFormValues,
} from "../components/target-form";
import { TargetService } from "../target-service";
import { targetQueryKeys, useTargetAdapters } from "../use-targets";
import { toast } from "@/lib/toast";

export function TargetCreatePage() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const adapters = useTargetAdapters();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submit = async (values: TargetFormValues) => {
    setIsSubmitting(true);
    try {
      const target = await TargetService.createTarget({
        name: values.name,
        metadata: values.metadata,
      });
      if (values.pythonFile)
        await TargetService.uploadPythonAdapter(target.target_id, values.pythonFile);
      else if (values.yamlFile)
        await TargetService.saveConfiguration(
          target.target_id,
          await values.yamlFile.text()
        );
      else if (values.yaml.trim() || values.draft.adapter)
        await TargetService.saveConfiguration(
          target.target_id,
          values.mode === "yaml" ? values.yaml : buildTargetYaml(values.draft)
        );
      await client.invalidateQueries({ queryKey: targetQueryKeys.all });
      toast.success(`Target created: ${target.name}`);
      navigate(`/targets/${encodeURIComponent(target.target_id)}`);
    } catch (error) {
      toast.error(
        `Failed to create target: ${error instanceof Error ? error.message : "Unknown error"}`
      );
    } finally {
      setIsSubmitting(false);
    }
  };
  return (
    <Page>
      <Page.Header
        title="Add Target"
        description="Register a target and optionally configure it now."
        breadcrumbs={[{ label: "Targets", href: "/targets" }]}
      />
      <Page.Content>
        <div className="mx-auto max-w-4xl">
          {adapters.isLoading ? (
            <Spinner />
          ) : adapters.error ? (
            <Alert variant="error">
              <AlertDescription>
                Unable to load adapter types: {adapters.error.message}
              </AlertDescription>
            </Alert>
          ) : (
            <TargetForm
              adapters={adapters.data ?? []}
              onSubmit={(values) => {
                void submit(values);
              }}
              isSubmitting={isSubmitting}
              onCancel={() => {
                navigate("/targets");
              }}
            />
          )}
        </div>
      </Page.Content>
    </Page>
  );
}
