/** Benchmark list page and benchmark creation dialog. */
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "@/lib/toast";
import {
  useBenchmarkList,
  useCreateBenchmark,
  useCreateBenchmarkFromFiles,
} from "../use-datasets";
import { formatCaseCount, formatRelativeTime } from "../dataset-formatters";
import type { BenchmarkFileCreate, BenchmarkInfo } from "../dataset-types";

export function DatasetsPage() {
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const { data: benchmarks, isLoading, error, refetch } = useBenchmarkList();

  const openCreate = () => {
    setShowCreateDialog(true);
  };
  const header = (description: string) => (
    <Page.Header
      title="Benchmarks"
      description={description}
      actions={<Button onClick={openCreate}>New Benchmark</Button>}
    />
  );

  if (isLoading) {
    return (
      <Page>
        {header("Manage benchmark cases and evaluation corpora.")}
        <Page.Content>
          <BenchmarkListSkeleton />
        </Page.Content>
      </Page>
    );
  }

  if (error) {
    return (
      <Page>
        {header("Manage benchmark cases and evaluation corpora.")}
        <Page.Content>
          <EmptyState
            title="Unable to load benchmarks"
            description="An error occurred while fetching benchmarks."
            action={
              <Button variant="secondary" onClick={() => void refetch()}>
                Retry
              </Button>
            }
          />
        </Page.Content>
        <BenchmarkCreateDialog
          open={showCreateDialog}
          onOpenChange={setShowCreateDialog}
        />
      </Page>
    );
  }

  return (
    <Page>
      {header("Create and manage reusable evaluation benchmarks.")}
      <Page.Content>
        {!benchmarks || benchmarks.length === 0 ? (
          <EmptyState
            title="Create your first benchmark"
            description="Benchmarks contain evaluation cases and the documents or chunks used by the corpus."
            action={<Button onClick={openCreate}>Create Benchmark</Button>}
          />
        ) : (
          <Surface>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Corpus mode</TableHead>
                  <TableHead>Cases</TableHead>
                  <TableHead>Documents / chunks</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {benchmarks.map((benchmark) => (
                  <BenchmarkRow key={benchmark.benchmark_id} benchmark={benchmark} />
                ))}
              </TableBody>
            </Table>
          </Surface>
        )}
      </Page.Content>
      <BenchmarkCreateDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
      />
    </Page>
  );
}

interface BenchmarkRowProps {
  benchmark: BenchmarkInfo;
}

function BenchmarkRow({ benchmark }: BenchmarkRowProps) {
  const corpusCount =
    benchmark.corpus_mode === "CHUNKS"
      ? `${String(benchmark.chunk_count)} chunks`
      : `${String(benchmark.document_count)} documents`;
  return (
    <TableRow>
      <TableCell>
        <div className="font-medium text-text-primary">{benchmark.name}</div>
        {benchmark.version && (
          <div className="text-xs text-text-tertiary">v{benchmark.version}</div>
        )}
      </TableCell>
      <TableCell>
        <Badge variant="default">{benchmark.corpus_mode}</Badge>
      </TableCell>
      <TableCell>{formatCaseCount(benchmark.case_count)}</TableCell>
      <TableCell>{corpusCount}</TableCell>
      <TableCell className="text-sm text-text-tertiary">
        {benchmark.updated_at ? formatRelativeTime(benchmark.updated_at) : "—"}
      </TableCell>
      <TableCell className="text-right">
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/benchmarks/${benchmark.benchmark_id}`}>Open</Link>
        </Button>
      </TableCell>
    </TableRow>
  );
}

function BenchmarkListSkeleton() {
  return (
    <Surface>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Corpus mode</TableHead>
            <TableHead>Cases</TableHead>
            <TableHead>Documents / chunks</TableHead>
            <TableHead>Updated</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {Array.from({ length: 5 }).map((_, index) => (
            <TableRow key={index}>
              <TableCell>
                <Skeleton className="h-4 w-40" />
              </TableCell>
              <TableCell>
                <Skeleton className="h-4 w-20" />
              </TableCell>
              <TableCell>
                <Skeleton className="h-4 w-20" />
              </TableCell>
              <TableCell>
                <Skeleton className="h-4 w-24" />
              </TableCell>
              <TableCell>
                <Skeleton className="h-4 w-16" />
              </TableCell>
              <TableCell>
                <Skeleton className="ml-auto h-7 w-14" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Surface>
  );
}

interface BenchmarkCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function BenchmarkCreateDialog({ open, onOpenChange }: BenchmarkCreateDialogProps) {
  const [name, setName] = useState("");
  const [caseFiles, setCaseFiles] = useState<File[]>([]);
  const [documentFiles, setDocumentFiles] = useState<File[]>([]);
  const caseInput = useRef<HTMLInputElement>(null);
  const documentInput = useRef<HTMLInputElement>(null);

  const reset = () => {
    setName("");
    setCaseFiles([]);
    setDocumentFiles([]);
    if (caseInput.current) caseInput.current.value = "";
    if (documentInput.current) documentInput.current.value = "";
  };
  const close = () => {
    reset();
    onOpenChange(false);
  };
  const onSuccess = (benchmark: BenchmarkInfo) => {
    toast.success(`Benchmark created: ${benchmark.name}`);
    close();
  };
  const create = useCreateBenchmark({ onSuccess });
  const createFromFiles = useCreateBenchmarkFromFiles({ onSuccess });
  const pending = create.isPending || createFromFiles.isPending;
  const error = create.error ?? createFromFiles.error;

  const submit = () => {
    const trimmedName = name.trim();
    if (!trimmedName) {
      toast.error("Benchmark name is required");
      return;
    }
    if (caseFiles.length === 0 && documentFiles.length === 0) {
      create.mutate({ name: trimmedName });
      return;
    }
    const data: BenchmarkFileCreate = {
      name: trimmedName,
      cases: caseFiles,
      documents: documentFiles,
    };
    createFromFiles.mutate(data);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) close();
        else onOpenChange(true);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Benchmark</DialogTitle>
          <DialogDescription>
            Create an empty benchmark or import cases and corpus files.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-5 py-2">
          <div className="space-y-2">
            <Label htmlFor="benchmark-name">Name *</Label>
            <Input
              id="benchmark-name"
              value={name}
              onChange={(event) => {
                setName(event.target.value);
              }}
              placeholder="e.g. QKD Grounding Benchmark"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="benchmark-cases">Case files</Label>
            <Input
              ref={caseInput}
              id="benchmark-cases"
              type="file"
              accept=".json,.jsonl,application/json"
              multiple
              onChange={(event) => {
                setCaseFiles(Array.from(event.target.files ?? []));
              }}
            />
            <FileNames files={caseFiles} />
            <p className="text-xs text-text-tertiary">
              Optional JSON or JSONL files. Multiple files are supported.
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="benchmark-documents">Document files</Label>
            <Input
              ref={documentInput}
              id="benchmark-documents"
              type="file"
              multiple
              onChange={(event) => {
                setDocumentFiles(Array.from(event.target.files ?? []));
              }}
            />
            <FileNames files={documentFiles} />
            <p className="text-xs text-text-tertiary">
              Optional source documents. Multiple files are supported.
            </p>
          </div>
          {error && <p className="text-sm text-error">{error.message}</p>}
        </div>
        <DialogFooter>
          <Button type="button" variant="secondary" onClick={close}>
            Cancel
          </Button>
          <Button type="button" onClick={submit} disabled={pending}>
            {pending ? "Creating..." : "Create Benchmark"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function FileNames({ files }: { files: File[] }) {
  if (files.length === 0) return null;
  return (
    <p className="text-xs text-text-secondary">
      {files.map((file) => file.name).join(", ")}
    </p>
  );
}
