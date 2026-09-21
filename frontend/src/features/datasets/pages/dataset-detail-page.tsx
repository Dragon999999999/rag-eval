/** Benchmark detail page with case and corpus attachment controls. */
import { Children, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import { EmptyState } from "@/components/ui/empty-state";
import { Spinner } from "@/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/ui/status-badge";
import { Badge } from "@/components/ui/badge";
import { Database, Upload } from "lucide-react";
import { toast } from "@/lib/toast";
import {
  useAddBenchmarkCases,
  useAddBenchmarkChunks,
  useAddBenchmarkDocuments,
  useBenchmark,
} from "../use-datasets";
import type {
  BenchmarkCase,
  BenchmarkChunk,
  BenchmarkDocument,
} from "../dataset-types";
import {
  formatAnswerability,
  getAnswerabilityVariant,
  truncateQuery,
} from "../dataset-formatters";

export function DatasetDetailPage() {
  const { benchmarkId, datasetId } = useParams<{
    benchmarkId?: string;
    datasetId?: string;
  }>();
  const id = benchmarkId ?? datasetId ?? "";
  const { data: benchmark, isLoading, error } = useBenchmark(id);
  const caseInput = useRef<HTMLInputElement>(null);
  const documentInput = useRef<HTMLInputElement>(null);
  const chunkInput = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const onUploadSuccess = () => {
    setUploadError(null);
    toast.success("Benchmark updated");
  };
  const onUploadError = (uploadErrorValue: Error) => {
    setUploadError(uploadErrorValue.message);
  };
  const addCases = useAddBenchmarkCases(id, {
    onSuccess: onUploadSuccess,
    onError: onUploadError,
  });
  const addDocuments = useAddBenchmarkDocuments(id, {
    onSuccess: onUploadSuccess,
    onError: onUploadError,
  });
  const addChunks = useAddBenchmarkChunks(id, {
    onSuccess: onUploadSuccess,
    onError: onUploadError,
  });

  const upload = (
    files: FileList | null,
    mutation: { mutate: (files: File[]) => void }
  ) => {
    if (!files || files.length === 0) return;
    mutation.mutate(Array.from(files));
  };

  if (isLoading) {
    return (
      <Page>
        <Page.Header
          title="Loading benchmark..."
          description="Loading benchmark metadata and records."
        />
        <Page.Content>
          <Spinner />
        </Page.Content>
      </Page>
    );
  }
  if (error || !benchmark) {
    return (
      <Page>
        <Page.Header
          title="Benchmark not found"
          description="The requested benchmark does not exist."
          actions={
            <Button variant="secondary" asChild>
              <Link to="/benchmarks">Back to Benchmarks</Link>
            </Button>
          }
        />
        <Page.Content>
          <EmptyState
            icon={<Database className="h-8 w-8" />}
            title="Benchmark not found"
            description="This benchmark may have been deleted."
            action={
              <Button asChild>
                <Link to="/benchmarks">Browse Benchmarks</Link>
              </Button>
            }
          />
        </Page.Content>
      </Page>
    );
  }

  const corpusLabel = benchmark.corpus_mode === "CHUNKS" ? "Chunks" : "Documents";
  const corpusCount =
    benchmark.corpus_mode === "CHUNKS"
      ? benchmark.chunk_count
      : benchmark.document_count;
  const busy = addCases.isPending || addDocuments.isPending || addChunks.isPending;

  return (
    <Page>
      <Page.Header
        title={benchmark.name}
        description={`${benchmark.corpus_mode} · ${String(benchmark.case_count)} cases · ${String(corpusCount)} ${corpusLabel.toLowerCase()}`}
        breadcrumbs={[{ label: "Benchmarks", href: "/benchmarks" }]}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => caseInput.current?.click()}
              disabled={busy}
            >
              <Upload className="h-4 w-4" />
              Add Cases
            </Button>
            {benchmark.corpus_mode === "CHUNKS" ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => chunkInput.current?.click()}
                disabled={busy}
              >
                <Upload className="h-4 w-4" />
                Add Chunks
              </Button>
            ) : (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => documentInput.current?.click()}
                disabled={busy}
              >
                <Upload className="h-4 w-4" />
                Add Documents
              </Button>
            )}
          </div>
        }
      />
      <input
        ref={caseInput}
        className="hidden"
        type="file"
        accept=".json,.jsonl,application/json"
        multiple
        onChange={(event) => {
          upload(event.target.files, addCases);
          event.target.value = "";
        }}
      />
      <input
        ref={documentInput}
        className="hidden"
        type="file"
        multiple
        onChange={(event) => {
          upload(event.target.files, addDocuments);
          event.target.value = "";
        }}
      />
      <input
        ref={chunkInput}
        className="hidden"
        type="file"
        accept=".json,.jsonl,application/json"
        multiple
        onChange={(event) => {
          upload(event.target.files, addChunks);
          event.target.value = "";
        }}
      />

      <Page.Content>
        <div className="space-y-6">
          <Surface className="p-6">
            <h3 className="text-base font-medium text-text-primary">
              Benchmark Information
            </h3>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <InfoRow label="Name" value={benchmark.name} />
              <InfoRow label="Corpus mode" value={benchmark.corpus_mode} />
              <InfoRow label="Cases" value={String(benchmark.case_count)} />
              <InfoRow label={corpusLabel} value={String(corpusCount)} />
              <InfoRow label="Version" value={benchmark.version} />
              <InfoRow label="Schema" value={benchmark.schema_version ?? "—"} />
              <InfoRow
                label="Created"
                value={
                  benchmark.created_at
                    ? new Date(benchmark.created_at).toLocaleDateString()
                    : "—"
                }
              />
              <InfoRow
                label="Status"
                value={benchmark.is_complete ? "Complete" : "Incomplete"}
              />
            </div>
            {uploadError && <p className="mt-4 text-sm text-error">{uploadError}</p>}
          </Surface>

          <CaseTable cases={benchmark.cases} onAdd={() => caseInput.current?.click()} />
          {benchmark.corpus_mode === "CHUNKS" ? (
            <ChunkTable
              chunks={benchmark.chunks}
              onAdd={() => chunkInput.current?.click()}
            />
          ) : (
            <DocumentTable
              documents={benchmark.documents}
              onAdd={() => documentInput.current?.click()}
            />
          )}
        </div>
      </Page.Content>
    </Page>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-sm text-text-tertiary">{label}</p>
      <p className="mt-1 font-medium text-text-primary">{value}</p>
    </div>
  );
}

function CaseTable({ cases, onAdd }: { cases: BenchmarkCase[]; onAdd: () => void }) {
  return (
    <Surface>
      <div className="flex items-center justify-between p-4">
        <h3 className="text-base font-medium text-text-primary">Benchmark Cases</h3>
        <Button variant="secondary" size="sm" onClick={onAdd}>
          <Upload className="h-4 w-4" />
          Add Cases
        </Button>
      </div>
      {cases.length === 0 ? (
        <EmptyState
          title="No cases yet"
          description="Upload JSON or JSONL case files to this benchmark."
          action={<Button onClick={onAdd}>Add Cases</Button>}
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Query</TableHead>
              <TableHead>Answerability</TableHead>
              <TableHead>Tags</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {cases.map((item) => (
              <CaseRow key={item.case_id} item={item} />
            ))}
          </TableBody>
        </Table>
      )}
    </Surface>
  );
}

function CaseRow({ item }: { item: BenchmarkCase }) {
  return (
    <TableRow>
      <TableCell>
        <code className="text-xs text-text-secondary">{item.case_id}</code>
      </TableCell>
      <TableCell>
        <div className="max-w-xl truncate text-sm text-text-primary" title={item.query}>
          {truncateQuery(item.query)}
        </div>
      </TableCell>
      <TableCell>
        <StatusBadge status={getAnswerabilityVariant(item.answerability)} showDot>
          {formatAnswerability(item.answerability)}
        </StatusBadge>
      </TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {item.tags.slice(0, 3).map((tag) => (
            <Badge key={tag} variant="default" className="text-xs">
              {tag}
            </Badge>
          ))}
        </div>
      </TableCell>
    </TableRow>
  );
}

function DocumentTable({
  documents,
  onAdd,
}: {
  documents: BenchmarkDocument[];
  onAdd: () => void;
}) {
  return (
    <CorpusTable
      title="Documents"
      emptyDescription="Upload source documents for this DOCUMENTS benchmark."
      onAdd={onAdd}
    >
      {documents.map((document) => (
        <TableRow key={document.document_id}>
          <TableCell>
            <code className="text-xs text-text-secondary">{document.document_id}</code>
          </TableCell>
          <TableCell className="font-medium">
            {document.filename ?? "Unnamed document"}
          </TableCell>
          <TableCell>{document.mime_type ?? "—"}</TableCell>
          <TableCell>
            {document.size_bytes == null ? "—" : `${String(document.size_bytes)} bytes`}
          </TableCell>
        </TableRow>
      ))}
    </CorpusTable>
  );
}

function ChunkTable({
  chunks,
  onAdd,
}: {
  chunks: BenchmarkChunk[];
  onAdd: () => void;
}) {
  return (
    <CorpusTable
      title="Chunks"
      emptyDescription="Upload JSON or JSONL chunks for this CHUNKS benchmark."
      onAdd={onAdd}
    >
      {chunks.map((chunk) => (
        <TableRow key={chunk.chunk_id}>
          <TableCell>
            <code className="text-xs text-text-secondary">{chunk.chunk_id}</code>
          </TableCell>
          <TableCell>
            <code className="text-xs text-text-secondary">{chunk.document_id}</code>
          </TableCell>
          <TableCell>
            <div className="max-w-2xl truncate" title={chunk.text}>
              {chunk.text}
            </div>
          </TableCell>
        </TableRow>
      ))}
    </CorpusTable>
  );
}

function CorpusTable({
  title,
  emptyDescription,
  onAdd,
  children,
}: {
  title: string;
  emptyDescription: string;
  onAdd: () => void;
  children: ReactNode;
}) {
  const hasRows = Children.count(children) > 0;
  return (
    <Surface>
      <div className="flex items-center justify-between p-4">
        <h3 className="text-base font-medium text-text-primary">{title}</h3>
        <Button variant="secondary" size="sm" onClick={onAdd}>
          <Upload className="h-4 w-4" />
          Add {title}
        </Button>
      </div>
      {hasRows ? (
        <Table>
          <TableHeader>
            <TableRow>
              {title === "Chunks" ? (
                <>
                  <TableHead>Chunk ID</TableHead>
                  <TableHead>Document ID</TableHead>
                  <TableHead>Text</TableHead>
                </>
              ) : (
                <>
                  <TableHead>Document ID</TableHead>
                  <TableHead>Filename</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Size</TableHead>
                </>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>{children}</TableBody>
        </Table>
      ) : (
        <EmptyState
          title={`No ${title.toLowerCase()} yet`}
          description={emptyDescription}
          action={<Button onClick={onAdd}>Add {title}</Button>}
        />
      )}
    </Surface>
  );
}
