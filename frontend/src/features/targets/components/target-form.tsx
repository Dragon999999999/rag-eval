/**
 * Target form for create/edit operations.
 *
 * Reusable form component driven by React Hook Form and Zod validation.
 * Supports both HTTP and Python adapter configurations.
 */
import { useEffect } from "react";
import { useForm, type UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { Target } from "../target-types";
import { isValidPythonTarget, isValidUrl } from "../target-formatters";

/**
 * Zod schema for target form validation.
 */
const targetFormSchema = z
  .object({
    name: z.string().min(1, "Name is required").max(255, "Name must be less than 255 characters"),
    version: z.string().optional(),
    implementation: z.string().optional(),
    adapter: z.enum(["http", "python"]),
    
    // HTTP adapter fields
    base_url: z.string().optional(),
    auth_type: z.enum(["none", "bearer", "api-key"]).default("none"),
    bearer_token: z.string().optional(),
    api_key: z.string().optional(),
    api_key_header: z.string().default("X-API-Key"),
    
    // Python adapter fields
    python_target: z.string().optional(),
    
    // Common fields
    corpus_mode: z.enum(["DOCUMENTS", "CHUNKS", "EXTERNAL"]),
    parameters: z.record(z.unknown()).optional(),
    metadata: z.record(z.unknown()).optional(),
  })
  .refine(
    (data) => {
      if (data.adapter === "http") {
        return !!data.base_url;
      }
      return true;
    },
    {
      message: "Base URL is required for HTTP adapter",
      path: ["base_url"],
    }
  )
  .refine(
    (data) => {
      if (data.adapter === "python") {
        return !!data.python_target;
      }
      return true;
    },
    {
      message: "Python target is required for Python adapter",
      path: ["python_target"],
    }
  )
  .refine(
    (data) => {
      if (data.base_url && !isValidUrl(data.base_url)) {
        return false;
      }
      return true;
    },
    {
      message: "Must be a valid URL",
      path: ["base_url"],
    }
  )
  .refine(
    (data) => {
      if (data.python_target && !isValidPythonTarget(data.python_target)) {
        return false;
      }
      return true;
    },
    {
      message: "Must be in format module:Symbol (e.g., package.module:TargetClass)",
      path: ["python_target"],
    }
  );

export type TargetFormValues = z.infer<typeof targetFormSchema>;

interface TargetFormProps {
  /** Existing target for edit mode, undefined for create mode */
  target?: Target;
  /** Submit handler */
  onSubmit: (data: TargetFormValues) => void;
  /** Cancel handler */
  onCancel?: () => void;
  /** Is submitting */
  isSubmitting?: boolean;
  /** Server error message */
  error?: string | null;
}

/**
 * Create form instance with react-hook-form.
 */
export function useTargetForm(props: TargetFormProps): UseFormReturn<TargetFormValues> {
  const form = useForm<TargetFormValues>({
    resolver: zodResolver(targetFormSchema),
    defaultValues: {
      name: "",
      version: "",
      implementation: "",
      adapter: "http",
      base_url: "",
      auth_type: "none",
      bearer_token: "",
      api_key: "",
      api_key_header: "X-API-Key",
      python_target: "",
      corpus_mode: "DOCUMENTS",
      parameters: {},
      metadata: {},
    },
  });

  // Populate form when editing existing target
  useEffect(() => {
    if (props.target) {
      const target = props.target;
      form.reset({
        name: target.name,
        version: target.version ?? "",
        implementation: target.implementation ?? "",
        adapter: target.adapter,
        base_url: target.base_url ?? "",
        auth_type: target.authentication_env ? "api-key" : "none",
        bearer_token: "", // Never populate secrets
        api_key: "", // Never populate secrets
        api_key_header: "X-API-Key",
        python_target: target.python_target ?? "",
        corpus_mode: target.corpus_mode,
        parameters: target.parameters as Record<string, unknown> | undefined,
        metadata: target.metadata as Record<string, unknown> | undefined,
      });
    }
  }, [props.target, form]);

  return form;
}

/**
 * Target form component.
 */
export function TargetForm({
  target,
  onSubmit,
  onCancel,
  isSubmitting = false,
  error = null,
}: TargetFormProps) {
  const form = useTargetForm({ target, onSubmit, onCancel, isSubmitting, error });
  const { register, handleSubmit, formState, watch, setValue } = form;
  const { errors } = formState;
  
  const adapter = watch("adapter");
  const authType = watch("auth_type");

  const handleSave = (data: TargetFormValues) => {
    onSubmit(data);
  };

  return (
    <form onSubmit={handleSubmit(handleSave)} className="space-y-6">
      {/* Server error */}
      {error && (
        <Alert variant="error">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* General section */}
      <section className="space-y-4">
        <h3 className="text-base font-medium text-text-primary">General</h3>
        
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="name">Name *</Label>
            <Input
              id="name"
              {...register("name")}
              placeholder="e.g., Grounding RAG Development"
              error={errors.name?.message}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="version">Version</Label>
            <Input
              id="version"
              {...register("version")}
              placeholder="e.g., v3.0"
              error={errors.version?.message}
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="implementation">Implementation</Label>
          <Input
            id="implementation"
            {...register("implementation")}
            placeholder="e.g., rag_eval.adapters.http:HttpTargetAdapter"
            error={errors.implementation?.message}
          />
          <p className="text-xs text-text-tertiary">
            Optional implementation identifier for documentation purposes.
          </p>
        </div>
      </section>

      {/* Adapter selection */}
      <section className="space-y-4">
        <h3 className="text-base font-medium text-text-primary">Adapter Type</h3>
        
        <div className="grid gap-4 sm:grid-cols-2">
          <AdapterOption
            name="HTTP Target Protocol"
            description="Remote HTTP endpoint implementing Target Protocol v1"
            selected={adapter === "http"}
            onSelect={() => setValue("adapter", "http")}
          />
          <AdapterOption
            name="Python Adapter"
            description="In-process Python target implementation"
            selected={adapter === "python"}
            onSelect={() => setValue("adapter", "python")}
          />
        </div>
      </section>

      {/* HTTP adapter configuration */}
      {adapter === "http" && (
        <section className="space-y-4">
          <h3 className="text-base font-medium text-text-primary">HTTP Configuration</h3>
          
          <div className="space-y-2">
            <Label htmlFor="base_url">Base URL *</Label>
            <Input
              id="base_url"
              {...register("base_url")}
              placeholder="e.g., http://localhost:8000"
              error={errors.base_url?.message}
            />
            <p className="text-xs text-text-tertiary">
              The target will be called at {`{base_url}/eval/v1/`}
            </p>
          </div>

          {/* Authentication */}
          <div className="space-y-4">
            <h4 className="text-sm font-medium text-text-secondary">Authentication</h4>
            
            <div className="space-y-2">
              <Label>Auth Type</Label>
              <div className="flex gap-4">
                <button
                  type="button"
                  onClick={() => setValue("auth_type", "none")}
                  className={`rounded-md border px-3 py-2 text-sm ${
                    authType === "none"
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-surface text-text-secondary"
                  }`}
                >
                  None
                </button>
                <button
                  type="button"
                  onClick={() => setValue("auth_type", "bearer")}
                  className={`rounded-md border px-3 py-2 text-sm ${
                    authType === "bearer"
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-surface text-text-secondary"
                  }`}
                >
                  Bearer Token
                </button>
                <button
                  type="button"
                  onClick={() => setValue("auth_type", "api-key")}
                  className={`rounded-md border px-3 py-2 text-sm ${
                    authType === "api-key"
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-surface text-text-secondary"
                  }`}
                >
                  API Key
                </button>
              </div>
            </div>

            {authType === "bearer" && (
              <div className="space-y-2">
                <Label htmlFor="bearer_token">Bearer Token</Label>
                <Input
                  id="bearer_token"
                  type="password"
                  {...register("bearer_token")}
                  placeholder="sk-..."
                  error={errors.bearer_token?.message}
                />
                {target && (
                  <p className="text-xs text-text-tertiary">
                    Leave blank to keep existing configuration.
                  </p>
                )}
              </div>
            )}

            {authType === "api-key" && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="api_key">API Key</Label>
                  <Input
                    id="api_key"
                    type="password"
                    {...register("api_key")}
                    placeholder="Your API key"
                    error={errors.api_key?.message}
                  />
                  {target && (
                    <p className="text-xs text-text-tertiary">
                      Leave blank to keep existing configuration.
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="api_key_header">Header Name</Label>
                  <Input
                    id="api_key_header"
                    {...register("api_key_header")}
                    placeholder="X-API-Key"
                    error={errors.api_key_header?.message}
                  />
                </div>
              </>
            )}
          </div>
        </section>
      )}

      {/* Python adapter configuration */}
      {adapter === "python" && (
        <section className="space-y-4">
          <h3 className="text-base font-medium text-text-primary">Python Configuration</h3>
          
          <div className="space-y-2">
            <Label htmlFor="python_target">Python Import Target *</Label>
            <Input
              id="python_target"
              {...register("python_target")}
              placeholder="e.g., rag_eval.example_target:ExampleTarget"
              error={errors.python_target?.message}
            />
            <p className="text-xs text-text-tertiary">
              Format: module.path:TargetClass
            </p>
          </div>
        </section>
      )}

      {/* Corpus mode */}
      <section className="space-y-4">
        <h3 className="text-base font-medium text-text-primary">Corpus Configuration</h3>
        
        <div className="space-y-2">
          <Label>Corpus Mode</Label>
          <div className="flex gap-4">
            <button
              type="button"
              onClick={() => setValue("corpus_mode", "DOCUMENTS")}
              className={`rounded-md border px-3 py-2 text-sm ${
                watch("corpus_mode") === "DOCUMENTS"
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border bg-surface text-text-secondary"
              }`}
            >
              Documents
            </button>
            <button
              type="button"
              onClick={() => setValue("corpus_mode", "CHUNKS")}
              className={`rounded-md border px-3 py-2 text-sm ${
                watch("corpus_mode") === "CHUNKS"
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border bg-surface text-text-secondary"
              }`}
            >
              Chunks
            </button>
            <button
              type="button"
              onClick={() => setValue("corpus_mode", "EXTERNAL")}
              className={`rounded-md border px-3 py-2 text-sm ${
                watch("corpus_mode") === "EXTERNAL"
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border bg-surface text-text-secondary"
              }`}
            >
              External
            </button>
          </div>
          <p className="text-xs text-text-tertiary">
            DOCUMENTS: Target accepts document uploads.
            CHUNKS: Target accepts pre-chunked data.
            EXTERNAL: Target uses external/corpus-less mode.
          </p>
        </div>
      </section>

      {/* Form actions */}
      <div className="flex items-center gap-4 border-t border-border pt-6">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving..." : target ? "Save Changes" : "Create Target"}
        </Button>
        {onCancel && (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}

interface AdapterOptionProps {
  id: string;
  name: string;
  description: string;
  selected: boolean;
  onSelect: () => void;
}

function AdapterOption({ name, description, selected, onSelect }: Omit<AdapterOptionProps, 'id'>) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`flex flex-col items-start gap-2 rounded-md border p-4 text-left transition-colors ${
        selected
          ? "border-primary bg-primary/10"
          : "border-border bg-surface hover:bg-surface-hover"
      }`}
    >
      <div className="flex items-center gap-2">
        <div
          className={`h-4 w-4 rounded-full border ${
            selected ? "border-primary bg-primary" : "border-border"
          }`}
        />
        <span className="font-medium text-text-primary">{name}</span>
      </div>
      <p className="text-sm text-text-tertiary">{description}</p>
    </button>
  );
}
