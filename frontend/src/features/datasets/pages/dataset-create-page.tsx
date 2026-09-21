/** Standalone benchmark creation route kept for deep links. */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { toast } from "@/lib/toast";
import { useCreateBenchmark, useCreateBenchmarkFromFiles } from "../use-datasets";
import type { BenchmarkFileCreate, BenchmarkInfo } from "../dataset-types";

export function DatasetCreatePage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [cases, setCases] = useState<File[]>([]);
  const [documents, setDocuments] = useState<File[]>([]);
  const onSuccess = (benchmark: BenchmarkInfo) => {
    toast.success(`Benchmark created: ${benchmark.name}`);
    navigate(`/benchmarks/${benchmark.benchmark_id}`);
  };
  const create = useCreateBenchmark({ onSuccess });
  const createFromFiles = useCreateBenchmarkFromFiles({ onSuccess });
  const submit = () => {
    if (!name.trim()) return;
    if (cases.length === 0 && documents.length === 0)
      create.mutate({ name: name.trim() });
    else
      createFromFiles.mutate({
        name: name.trim(),
        cases,
        documents,
      } satisfies BenchmarkFileCreate);
  };
  const error = create.error ?? createFromFiles.error;
  return (
    <Page>
      <Page.Header
        title="New Benchmark"
        description="Create a benchmark and optionally import its files."
        breadcrumbs={[{ label: "Benchmarks", href: "/benchmarks" }]}
      />
      <Page.Content>
        <div className="mx-auto max-w-2xl space-y-6">
          {error && (
            <Alert variant="error">
              <AlertDescription>{error.message}</AlertDescription>
            </Alert>
          )}
          <div className="space-y-4">
            <div>
              <Label htmlFor="benchmark-name">Name *</Label>
              <Input
                id="benchmark-name"
                value={name}
                onChange={(event) => {
                  setName(event.target.value);
                }}
              />
            </div>
            <div>
              <Label htmlFor="benchmark-cases">Case files</Label>
              <Input
                id="benchmark-cases"
                type="file"
                accept=".json,.jsonl,application/json"
                multiple
                onChange={(event) => {
                  setCases(Array.from(event.target.files ?? []));
                }}
              />
            </div>
            <div>
              <Label htmlFor="benchmark-documents">Document files</Label>
              <Input
                id="benchmark-documents"
                type="file"
                multiple
                onChange={(event) => {
                  setDocuments(Array.from(event.target.files ?? []));
                }}
              />
            </div>
          </div>
          <div className="border-border flex items-center gap-4 border-t pt-6">
            <Button
              onClick={submit}
              disabled={!name.trim() || create.isPending || createFromFiles.isPending}
            >
              {create.isPending || createFromFiles.isPending
                ? "Creating..."
                : "Create Benchmark"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                navigate("/benchmarks");
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      </Page.Content>
    </Page>
  );
}
