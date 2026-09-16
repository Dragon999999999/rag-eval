/**
 * Create target page - /targets/new
 */
import { useNavigate } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { useCreateTarget } from "../use-targets";
import { TargetForm, type TargetFormValues } from "../components/target-form";
import { toast } from "@/lib/toast";

export function TargetCreatePage() {
  const navigate = useNavigate();
  const createTarget = useCreateTarget({
    onSuccess: (data) => {
      toast.success(`Target created: ${data.name}`);
      navigate(`/targets/${data.targetId}`);
    },
    onError: (error) => {
      toast.error(`Failed to create target: ${error.message}`);
    },
  });

  const handleSubmit = (data: TargetFormValues) => {
    // Convert form values to TargetCreate payload
    const payload = {
      name: data.name,
      version: data.version || undefined,
      implementation: data.implementation || undefined,
      adapter: data.adapter,
      base_url: data.base_url || undefined,
      python_target: data.python_target || undefined,
      authentication_env:
        data.auth_type !== "none"
          ? data.auth_type === "bearer"
            ? "BEARER_TOKEN"
            : "API_KEY"
          : undefined,
      corpus_mode: data.corpus_mode,
      parameters: data.parameters || {},
      metadata: {
        ...data.metadata,
        auth_type: data.auth_type,
        api_key_header: data.api_key_header,
      },
    };

    createTarget.mutate(payload);
  };

  const handleCancel = () => {
    navigate("/targets");
  };

  return (
    <Page>
      <Page.Header
        title="Add Target"
        description="Configure a new RAG or LLM system to evaluate."
        breadcrumbs={[{ label: "Targets", href: "/targets" }]}
      />

      <Page.Content>
        <div className="mx-auto max-w-3xl">
          <TargetForm
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            isSubmitting={createTarget.isPending}
            error={createTarget.error?.message ?? null}
          />
        </div>
      </Page.Content>
    </Page>
  );
}
