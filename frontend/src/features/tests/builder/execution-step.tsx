/**
 * Step 4: Execution Settings component.
 */
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { UseFormReturn } from "react-hook-form";
import type { TestBuilderValues } from "../test-builder-form";

interface ExecutionStepProps {
  form: UseFormReturn<TestBuilderValues>;
  onPrevious: () => void;
  onNext: () => void;
}

export function ExecutionStep({ form, onPrevious, onNext }: ExecutionStepProps) {
  const executionConfig = form.watch("execution_config");
  const seed = form.watch("seed");
  const tags = form.watch("tags");
  const [tagInput, setTagInput] = useState("");

  const updateConfig = <K extends keyof typeof executionConfig>(
    key: K,
    value: typeof executionConfig[K]
  ) => {
    form.setValue("execution_config", { ...executionConfig, [key]: value }, { shouldValidate: true, shouldDirty: true });
  };

  const setSeed = (value: string) => {
    const num = parseInt(value);
    form.setValue("seed", isNaN(num) ? null : num, { shouldValidate: true, shouldDirty: true });
  };

  const addTag = () => {
    if (tagInput.trim()) {
      form.setValue("tags", [...tags, tagInput.trim()], { shouldValidate: true, shouldDirty: true });
      setTagInput("");
    }
  };

  const removeTag = (index: number) => {
    form.setValue("tags", tags.filter((_, i) => i !== index), { shouldValidate: true, shouldDirty: true });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addTag();
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-text-primary">Execution Settings</h2>
        <p className="text-sm text-text-tertiary">
          Configure concurrency, timeouts, and failure handling.
        </p>
      </div>

      {/* Concurrency */}
      <Surface className="p-4">
        <h3 className="mb-4 text-sm font-medium text-text-primary">Performance</h3>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="concurrency">Concurrency</Label>
            <Input
              id="concurrency"
              type="number"
              min="1"
              max="32"
              value={executionConfig.concurrency}
              onChange={(e) => updateConfig("concurrency", parseInt(e.target.value) || 1)}
            />
            <p className="text-xs text-text-tertiary">
              Number of parallel requests (1-32)
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="timeout">Timeout per Request (seconds)</Label>
            <Input
              id="timeout"
              type="number"
              min="1"
              max="300"
              value={executionConfig.timeout_per_request}
              onChange={(e) => updateConfig("timeout_per_request", parseInt(e.target.value) || 30)}
            />
            <p className="text-xs text-text-tertiary">
              Maximum time to wait for each request
            </p>
          </div>
        </div>
      </Surface>

      {/* Retry and Failure Policy */}
      <Surface className="p-4">
        <h3 className="mb-4 text-sm font-medium text-text-primary">Retry & Failure Handling</h3>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="retries">Retries per Case</Label>
            <Input
              id="retries"
              type="number"
              min="0"
              max="10"
              value={executionConfig.retries}
              onChange={(e) => updateConfig("retries", parseInt(e.target.value) || 0)}
            />
            <p className="text-xs text-text-tertiary">
              Number of retry attempts on failure
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="failure-policy">On Failure</Label>
            <Select
              value={executionConfig.failure_policy}
              onValueChange={(value: "continue" | "abort") => updateConfig("failure_policy", value)}
            >
              <SelectTrigger id="failure-policy">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="continue">Continue</SelectItem>
                <SelectItem value="abort">Abort Run</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-text-tertiary">
              Whether to continue or stop on case failure
            </p>
          </div>
        </div>
      </Surface>

      {/* Storage Options */}
      <Surface className="p-4">
        <h3 className="mb-4 text-sm font-medium text-text-primary">Data Storage</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="store-raw">Store Raw Responses</Label>
              <p className="text-xs text-text-tertiary">
                Save original request/response payloads
              </p>
            </div>
            <Switch
              id="store-raw"
              checked={executionConfig.store_raw_responses}
              onCheckedChange={(checked) => updateConfig("store_raw_responses", checked)}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="store-traces">Store Traces</Label>
              <p className="text-xs text-text-tertiary">
                Save execution traces for debugging
              </p>
            </div>
            <Switch
              id="store-traces"
              checked={executionConfig.store_traces}
              onCheckedChange={(checked) => updateConfig("store_traces", checked)}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="store-usage">Store Usage Data</Label>
              <p className="text-xs text-text-tertiary">
                Save token usage and cost information
              </p>
            </div>
            <Switch
              id="store-usage"
              checked={executionConfig.store_usage}
              onCheckedChange={(checked) => updateConfig("store_usage", checked)}
            />
          </div>
        </div>
      </Surface>

      {/* Advanced Settings */}
      <Surface className="p-4">
        <h3 className="mb-4 text-sm font-medium text-text-primary">Advanced</h3>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="seed">Random Seed (optional)</Label>
            <Input
              id="seed"
              type="number"
              min="0"
              value={seed ?? ""}
              onChange={(e) => setSeed(e.target.value)}
              placeholder="For reproducible sampling"
            />
            <p className="text-xs text-text-tertiary">
              Used for deterministic random sampling
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="tags">Tags</Label>
            <div className="flex gap-2">
              <Input
                id="tags"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Add a tag..."
                className="flex-1"
              />
              <Button type="button" variant="secondary" onClick={addTag}>
                Add
              </Button>
            </div>
            {tags.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {tags.map((tag, index) => (
                  <span
                    key={index}
                    className="inline-flex cursor-pointer items-center rounded-md bg-surface-hover px-2 py-0.5 text-xs font-medium text-text-secondary transition-colors"
                    onClick={() => removeTag(index)}
                  >
                    {tag} ×
                  </span>
                ))}
              </div>
            )}
            <p className="text-xs text-text-tertiary">
              Press Enter or click Add to add tags. Click a tag to remove it.
            </p>
          </div>
        </div>
      </Surface>

      <div className="flex justify-between">
        <Button variant="secondary" onClick={onPrevious}>
          Back
        </Button>
        <Button onClick={onNext}>
          Next: Review
        </Button>
      </div>
    </div>
  );
}
