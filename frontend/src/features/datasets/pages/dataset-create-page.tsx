/**
 * Create dataset page - /datasets/new
 */
import { useNavigate } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useCreateDataset } from "../use-datasets";
import { useForm } from "react-hook-form";
import { toast } from "@/lib/toast";

interface DatasetFormValues {
  name: string;
  version: string;
  source?: string;
  tags?: string;
}

export function DatasetCreatePage() {
  const navigate = useNavigate();
  const createDataset = useCreateDataset({
    onSuccess: (data) => {
      toast.success(`Dataset created: ${data.name}`);
      navigate(`/datasets/${data.dataset_id}`);
    },
    onError: (error) => {
      toast.error(`Failed to create dataset: ${error.message}`);
    },
  });

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<DatasetFormValues>({
    defaultValues: {
      name: "",
      version: "1.0",
      source: "",
      tags: "",
    },
  });

  const onSubmit = (data: DatasetFormValues) => {
    createDataset.mutate({
      name: data.name,
      version: data.version,
      schema_version: "1.0",
      source: data.source || undefined,
      tags:
        data.tags
          ?.split(",")
          .map((t) => t.trim())
          .filter(Boolean) ?? [],
      metadata: {},
    });
  };

  return (
    <Page>
      <Page.Header
        title="New Dataset"
        description="Create a new benchmark dataset."
        breadcrumbs={[{ label: "Datasets", href: "/datasets" }]}
      />

      <Page.Content>
        <div className="mx-auto max-w-2xl">
          <form
            onSubmit={(e) => {
              void handleSubmit(onSubmit)(e);
            }}
            className="space-y-6"
          >
            {createDataset.error && (
              <Alert variant="error">
                <AlertDescription>{createDataset.error.message}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-4">
              <div>
                <Label htmlFor="name">Name *</Label>
                <Input
                  id="name"
                  {...register("name", { required: "Name is required" })}
                  placeholder="e.g., QKD Grounding Benchmark"
                  error={errors.name?.message}
                />
              </div>

              <div>
                <Label htmlFor="version">Version *</Label>
                <Input
                  id="version"
                  {...register("version", { required: "Version is required" })}
                  placeholder="e.g., 1.0"
                  error={errors.version?.message}
                />
              </div>

              <div>
                <Label htmlFor="source">Source</Label>
                <Input
                  id="source"
                  {...register("source")}
                  placeholder="e.g., Internal Research"
                />
              </div>

              <div>
                <Label htmlFor="tags">Tags</Label>
                <Input
                  id="tags"
                  {...register("tags")}
                  placeholder="comma-separated tags"
                />
                <p className="mt-1 text-xs text-text-tertiary">
                  Separate tags with commas
                </p>
              </div>
            </div>

            <div className="border-border flex items-center gap-4 border-t pt-6">
              <Button type="submit" disabled={createDataset.isPending}>
                {createDataset.isPending ? "Creating..." : "Create Dataset"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  navigate("/datasets");
                }}
              >
                Cancel
              </Button>
            </div>
          </form>
        </div>
      </Page.Content>
    </Page>
  );
}
