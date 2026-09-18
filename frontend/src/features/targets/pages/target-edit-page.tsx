/**
 * Edit target page - /targets/:targetId/edit
 */
import { useParams, useNavigate, Link } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { useTarget, useUpdateTarget } from "../use-targets";
import { TargetForm, type TargetFormValues } from "../components/target-form";
import { toast } from "@/lib/toast";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { Waypoints } from "lucide-react";

export function TargetEditPage() {
  const { targetId } = useParams<{ targetId: string }>();
  const navigate = useNavigate();

  const { data: target, isLoading, error } = useTarget(targetId ?? "");

  const updateTarget = useUpdateTarget(targetId ?? "", {
    onSuccess: (data) => {
      toast.success(`Target updated: ${data.name}`);
      navigate(`/targets/${targetId ?? ''}`);
    },
    onError: (error) => {
      toast.error(`Failed to update target: ${error.message}`);
    },
  });

  const handleSubmit = (data: TargetFormValues) => {
    // Convert form values to TargetUpdate payload
    const payload = {
      name: data.name,
      version: data.version || null,
      implementation: data.implementation || null,
      parameters: data.parameters || undefined,
      metadata: {
        ...data.metadata,
        auth_type: data.auth_type,
        api_key_header: data.api_key_header,
      },
    };

    updateTarget.mutate(payload);
  };

  const handleCancel = () => {
    navigate(`/targets/${targetId ?? ''}`);
  };

  if (isLoading) {
    return (
      <Page>
        <Page.Header
          title="Loading..."
          description="Loading target configuration."
          breadcrumbs={[
            { label: "Targets", href: "/targets" },
            { label: "Edit", href: "#" },
          ]}
        />
        <Page.Content>
          <div className="space-y-4">
            <div className="border-border rounded-lg border bg-surface p-6">
              <Spinner />
            </div>
          </div>
        </Page.Content>
      </Page>
    );
  }

  if (error || !target) {
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
        title="Edit Target"
        description={`Editing ${target.name}`}
        breadcrumbs={[
          { label: "Targets", href: "/targets" },
          { label: target.name, href: `/targets/${targetId ?? ''}` },
          { label: "Edit", href: "#" },
        ]}
      />

      <Page.Content>
        <div className="mx-auto max-w-3xl">
          <TargetForm
            target={target}
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            isSubmitting={updateTarget.isPending}
            error={updateTarget.error?.message ?? null}
          />
        </div>
      </Page.Content>
    </Page>
  );
}
