import { useMemo, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  Target,
  TargetAdapterInfo,
  TargetConfigurationDraft,
} from "../target-types";

export interface TargetFormValues {
  name: string;
  metadata: Record<string, unknown>;
  adapter: string;
  yaml: string;
  yamlFile: File | null;
  pythonFile: File | null;
  mode: "form" | "yaml" | "python";
  draft: TargetConfigurationDraft;
}

interface TargetFormProps {
  target?: Target;
  adapters: TargetAdapterInfo[];
  initialYaml?: string;
  onSubmit: (values: TargetFormValues) => void;
  onCancel?: () => void;
  isSubmitting?: boolean;
  error?: string | null;
}

const emptyDraft: TargetConfigurationDraft = {
  adapter: "",
  base_url: "",
  timeout_seconds: "",
  verify_tls: true,
  auth_type: "",
  bearer_token: "",
  api_key: "",
  api_key_header: "X-API-Key",
  model: "",
  endpoint: "",
  protocol_json: "{}",
  overrides_json: "{}",
  parameters_json: "{}",
  metadata_json: "{}",
  existing_auth: {},
};

export function buildTargetYaml(draft: TargetConfigurationDraft): string {
  const parse = (value: string): Record<string, unknown> => {
    if (!value.trim()) return {};
    const parsed: unknown = JSON.parse(value);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
      throw new Error("JSON fields must contain an object");
    return parsed as Record<string, unknown>;
  };
  const config: Record<string, unknown> = {
    adapter: { type: draft.adapter },
    connection: {
      ...(draft.base_url ? { base_url: draft.base_url } : {}),
      ...(draft.timeout_seconds
        ? { timeout_seconds: Number(draft.timeout_seconds) }
        : {}),
      verify_tls: draft.verify_tls,
    },
    parameters: {
      ...parse(draft.parameters_json),
      ...(draft.model ? { model: draft.model } : {}),
      ...(draft.endpoint ? { endpoint: draft.endpoint } : {}),
    },
    overrides: parse(draft.overrides_json),
    metadata: parse(draft.metadata_json),
  };
  const existingAuth = draft.existing_auth;
  const existingParameters =
    existingAuth.parameters &&
    typeof existingAuth.parameters === "object" &&
    !Array.isArray(existingAuth.parameters)
      ? (existingAuth.parameters as Record<string, unknown>)
      : {};
  if (
    draft.auth_type ||
    draft.bearer_token ||
    draft.api_key ||
    Object.keys(existingAuth).length > 0
  ) {
    config.auth = {
      ...existingAuth,
      ...(draft.auth_type ? { type: draft.auth_type } : {}),
      ...(draft.bearer_token ? { bearer_token: draft.bearer_token } : {}),
      ...(draft.api_key ? { api_key: draft.api_key } : {}),
      ...(draft.api_key_header
        ? {
            parameters: {
              ...existingParameters,
              api_key_header: draft.api_key_header,
            },
          }
        : {}),
    };
  }
  if (draft.protocol_json.trim() && draft.protocol_json.trim() !== "{}")
    config.protocol = parse(draft.protocol_json);
  // JSON is valid YAML and preserves nested structures without a client YAML dependency.
  return `${JSON.stringify(config, null, 2)}\n`;
}

function parseYamlValue(value: string): unknown {
  const trimmed = value.trim();
  if (!trimmed) return {};
  if (trimmed === "{}" || trimmed === "[]") return JSON.parse(trimmed);
  if (trimmed === "true") return true;
  if (trimmed === "false") return false;
  if (trimmed === "null" || trimmed === "~") return null;
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) return Number(trimmed);
  if (
    (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
    (trimmed.startsWith("[") && trimmed.endsWith("]"))
  ) {
    try {
      return JSON.parse(trimmed);
    } catch {
      /* fall through to a string */
    }
  }
  if (
    (trimmed.startsWith("'") && trimmed.endsWith("'")) ||
    (trimmed.startsWith('"') && trimmed.endsWith('"'))
  )
    return trimmed.slice(1, -1);
  return trimmed;
}

/** Parse the simple mapping/list YAML emitted by the backend without exposing secrets. */
function parseTargetYaml(yaml: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(yaml);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    /* backend emits YAML, not JSON */
  }

  const root: Record<string, unknown> = {};
  const stack: Array<{ indent: number; value: Record<string, unknown> | unknown[] }> = [
    { indent: -1, value: root },
  ];
  const lines = yaml
    .split(/\r?\n/)
    .map((line) => line.replace(/\s+#.*$/, ""))
    .filter((line) => line.trim());
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line) continue;
    const indent = line.search(/\S/);
    const content = line.trim();
    while (stack.length > 1) {
      const top = stack[stack.length - 1];
      if (!top || indent > top.indent) break;
      stack.pop();
    }
    const parentEntry = stack[stack.length - 1];
    if (!parentEntry) continue;
    const parent = parentEntry.value;
    if (content.startsWith("- ") && Array.isArray(parent)) {
      parent.push(parseYamlValue(content.slice(2)));
      continue;
    }
    const separator = content.indexOf(":");
    if (separator <= 0 || Array.isArray(parent)) continue;
    const key = content.slice(0, separator).trim();
    const rawValue = content.slice(separator + 1).trim();
    if (rawValue) {
      parent[key] = parseYamlValue(rawValue);
      continue;
    }
    const next = lines[index + 1];
    const nextIsList = next
      ? next.search(/\S/) > indent && next.trim().startsWith("- ")
      : false;
    const child: Record<string, unknown> | unknown[] = nextIsList ? [] : {};
    parent[key] = child;
    stack.push({ indent, value: child });
  }
  return root;
}

function draftFromYaml(yaml: string, adapter: string): TargetConfigurationDraft {
  const draft = { ...emptyDraft, adapter };
  const value = parseTargetYaml(yaml);
  if (!value) return draft;
  const connection = (value.connection ?? {}) as Record<string, unknown>;
  const parameters = (value.parameters ?? {}) as Record<string, unknown>;
  const auth =
    value.auth && typeof value.auth === "object" && !Array.isArray(value.auth)
      ? (value.auth as Record<string, unknown>)
      : {};
  return {
    ...draft,
    adapter:
      typeof (value.adapter as Record<string, unknown> | undefined)?.type === "string"
        ? String((value.adapter as Record<string, unknown>).type)
        : adapter,
    base_url: typeof connection.base_url === "string" ? connection.base_url : "",
    timeout_seconds:
      typeof connection.timeout_seconds === "number"
        ? String(connection.timeout_seconds)
        : "",
    verify_tls: connection.verify_tls !== false,
    auth_type: typeof auth.type === "string" ? auth.type : "",
    model: typeof parameters.model === "string" ? parameters.model : "",
    endpoint: typeof parameters.endpoint === "string" ? parameters.endpoint : "",
    parameters_json: JSON.stringify(parameters, null, 2),
    protocol_json: JSON.stringify(value.protocol ?? {}, null, 2),
    overrides_json: JSON.stringify(value.overrides ?? {}, null, 2),
    metadata_json: JSON.stringify(value.metadata ?? {}, null, 2),
    existing_auth: auth,
  };
}

export function TargetForm({
  target,
  adapters,
  initialYaml = "",
  onSubmit,
  onCancel,
  isSubmitting = false,
  error,
}: TargetFormProps) {
  // A newly-created target remains EMPTY until the user explicitly chooses an
  // adapter or uploads a configuration.
  const initialAdapter = target?.adapter_type ?? "";
  const [name, setName] = useState(target?.name ?? "");
  const [metadata, setMetadata] = useState(
    JSON.stringify(target?.metadata ?? {}, null, 2)
  );
  const [draft, setDraft] = useState<TargetConfigurationDraft>(() =>
    draftFromYaml(initialYaml, initialAdapter)
  );
  const [yaml, setYaml] = useState(initialYaml);
  const [yamlFile, setYamlFile] = useState<File | null>(null);
  const [pythonFile, setPythonFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"form" | "yaml" | "python">(
    target?.adapter_type === "uploaded_python" ? "python" : "form"
  );
  const [validationError, setValidationError] = useState<string | null>(null);
  const selectedAdapter = useMemo(
    () => adapters.find((item) => item.type === draft.adapter),
    [adapters, draft.adapter]
  );

  const update = <K extends keyof TargetConfigurationDraft>(
    key: K,
    value: TargetConfigurationDraft[K]
  ) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setValidationError(null);
    let parsedMetadata: Record<string, unknown> = {};
    try {
      const parsed: unknown = metadata.trim() ? JSON.parse(metadata) : {};
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
        throw new Error("Metadata must be a JSON object.");
      parsedMetadata = parsed as Record<string, unknown>;
    } catch {
      setValidationError("Metadata must be valid JSON with an object at the root.");
      return;
    }
    let serialized = yaml;
    if (mode === "form" && draft.adapter) {
      try {
        serialized = buildTargetYaml(draft);
      } catch (error) {
        setValidationError(
          error instanceof Error
            ? error.message
            : "Configuration contains invalid JSON."
        );
        return;
      }
    }
    onSubmit({
      name,
      metadata: parsedMetadata,
      adapter: draft.adapter,
      yaml: serialized,
      yamlFile,
      pythonFile,
      mode,
      draft,
    });
  };

  return (
    <form onSubmit={submit} className="space-y-6">
      {(error ?? validationError) && (
        <Alert variant="error">
          <AlertDescription>{error ?? validationError}</AlertDescription>
        </Alert>
      )}
      <section className="space-y-4">
        <h3 className="text-base font-medium text-text-primary">Target identity</h3>
        <div className="space-y-2">
          <Label htmlFor="target-name">Name *</Label>
          <Input
            id="target-name"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
            }}
            required
            placeholder="Production RAG"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="target-metadata">Metadata (JSON)</Label>
          <Textarea
            id="target-metadata"
            value={metadata}
            onChange={(event) => {
              setMetadata(event.target.value);
            }}
            rows={3}
            placeholder='{"environment":"staging"}'
          />
        </div>
      </section>
      <section className="space-y-4">
        <div>
          <h3 className="text-base font-medium text-text-primary">Configuration</h3>
          <p className="text-sm text-text-tertiary">
            The backend stores every save as an immutable configuration version.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant={mode === "form" ? "primary" : "secondary"}
            size="sm"
            onClick={() => {
              setMode("form");
            }}
          >
            Structured form
          </Button>
          <Button
            type="button"
            variant={mode === "yaml" ? "primary" : "secondary"}
            size="sm"
            onClick={() => {
              setMode("yaml");
            }}
          >
            Edit YAML
          </Button>
          <Button
            type="button"
            variant={mode === "python" ? "primary" : "secondary"}
            size="sm"
            onClick={() => {
              setMode("python");
            }}
          >
            Upload Python
          </Button>
        </div>
        {mode === "form" && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Adapter</Label>
              <Select
                value={draft.adapter}
                onValueChange={(value) => {
                  update("adapter", value);
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select adapter" />
                </SelectTrigger>
                <SelectContent>
                  {adapters.map((adapter) => (
                    <SelectItem key={adapter.type} value={adapter.type}>
                      {adapter.type}
                      {adapter.description ? ` — ${adapter.description}` : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedAdapter && (
                <div className="space-y-2 text-xs text-text-tertiary">
                  <p>
                    {selectedAdapter.supports_full_protocol
                      ? "Supports a full declarative protocol."
                      : "Uses adapter defaults with optional overrides."}
                  </p>
                  {Object.keys(selectedAdapter.defaults).length > 0 && (
                    <details>
                      <summary className="cursor-pointer hover:text-text-secondary">
                        Adapter defaults
                      </summary>
                      <pre className="mt-2 max-h-32 overflow-auto rounded bg-surface-hover p-2">
                        {JSON.stringify(selectedAdapter.defaults, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              )}
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="target-base-url">Base URL</Label>
                <Input
                  id="target-base-url"
                  value={draft.base_url}
                  onChange={(event) => {
                    update("base_url", event.target.value);
                  }}
                  placeholder="https://target.example"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="target-model">Model</Label>
                <Input
                  id="target-model"
                  value={draft.model}
                  onChange={(event) => {
                    update("model", event.target.value);
                  }}
                  placeholder="Optional adapter model"
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="target-auth-type">Auth type</Label>
                <Input
                  id="target-auth-type"
                  value={draft.auth_type}
                  onChange={(event) => {
                    update("auth_type", event.target.value);
                  }}
                  placeholder="bearer, api_key, ..."
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="target-api-header">API key header</Label>
                <Input
                  id="target-api-header"
                  value={draft.api_key_header}
                  onChange={(event) => {
                    update("api_key_header", event.target.value);
                  }}
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="target-bearer">Bearer token (write-only)</Label>
                <Input
                  id="target-bearer"
                  type="password"
                  value={draft.bearer_token}
                  onChange={(event) => {
                    update("bearer_token", event.target.value);
                  }}
                  placeholder="Leave blank to preserve existing secret"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="target-key">API key (write-only)</Label>
                <Input
                  id="target-key"
                  type="password"
                  value={draft.api_key}
                  onChange={(event) => {
                    update("api_key", event.target.value);
                  }}
                  placeholder="Leave blank to preserve existing secret"
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="target-parameters">Parameters (JSON)</Label>
                <Textarea
                  id="target-parameters"
                  value={draft.parameters_json}
                  onChange={(event) => {
                    update("parameters_json", event.target.value);
                  }}
                  rows={4}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="target-overrides">Overrides (JSON)</Label>
                <Textarea
                  id="target-overrides"
                  value={draft.overrides_json}
                  onChange={(event) => {
                    update("overrides_json", event.target.value);
                  }}
                  rows={4}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="target-protocol">Protocol (JSON, Level 3)</Label>
              <Textarea
                id="target-protocol"
                value={draft.protocol_json}
                onChange={(event) => {
                  update("protocol_json", event.target.value);
                }}
                rows={5}
              />
            </div>
          </div>
        )}
        {mode === "yaml" && (
          <div className="space-y-3">
            <Label htmlFor="target-yaml">Sanitized target.yaml</Label>
            <Textarea
              id="target-yaml"
              value={yaml}
              onChange={(event) => {
                setYaml(event.target.value);
              }}
              rows={16}
              className="font-mono text-xs"
            />
            <label className="text-sm text-text-secondary">
              Or upload YAML
              <input
                type="file"
                accept=".yaml,.yml"
                className="mt-2 block text-sm"
                onChange={(event) => {
                  setYamlFile(event.target.files?.[0] ?? null);
                }}
              />
            </label>
          </div>
        )}
        {mode === "python" && (
          <div className="space-y-3">
            <p className="text-sm text-text-tertiary">
              Level 4 adapters are trusted Python files. The backend validates syntax
              and the TargetAdapter interface before execution.
            </p>
            <input
              type="file"
              accept=".py"
              className="block text-sm text-text-secondary"
              onChange={(event) => {
                setPythonFile(event.target.files?.[0] ?? null);
              }}
            />
            {target?.adapter_type === "uploaded_python" && (
              <p className="text-xs text-text-tertiary">
                Upload a replacement file to create a new configuration version.
              </p>
            )}
          </div>
        )}
      </section>
      <div className="flex items-center gap-3 border-t border-border-default pt-6">
        <Button type="submit" disabled={isSubmitting || !name.trim()}>
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
