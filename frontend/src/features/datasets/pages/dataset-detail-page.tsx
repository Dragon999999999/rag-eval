/** Benchmark detail page backed by dedicated content resource endpoints. */
import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import { EmptyState } from "@/components/ui/empty-state";
import { Spinner } from "@/components/ui/spinner";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Database, Eye, Pencil, Trash2, Upload } from "lucide-react";
import { toast } from "@/lib/toast";
import {
  useBenchmark,
  useBenchmarkCase,
  useBenchmarkCases,
  useBenchmarkChunk,
  useBenchmarkChunks,
  useBenchmarkDocuments,
  useChangeCorpusMode,
  useCreateBenchmarkCase,
  useCreateBenchmarkChunk,
  useDeleteBenchmark,
  useDeleteBenchmarkCase,
  useDeleteBenchmarkChunk,
  useDeleteBenchmarkDocument,
  useImportBenchmarkCases,
  useImportBenchmarkChunks,
  useUpdateBenchmarkCase,
  useUploadBenchmarkDocuments,
} from "../use-datasets";
import type {
  BenchmarkCase,
  BenchmarkChunk,
  BenchmarkDocument,
  BenchmarkInfo,
  CorpusMode,
} from "../dataset-types";
import {
  formatAnswerability,
  getAnswerabilityVariant,
  truncateQuery,
} from "../dataset-formatters";
import { getConflictMessage, getStatusMessage } from "../dataset-errors";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const notifyError = (error: Error) => {
  toast.error(error.message);
};

export function DatasetDetailPage() {
  const { benchmarkId, datasetId } = useParams<{
    benchmarkId?: string;
    datasetId?: string;
  }>();
  const id = benchmarkId ?? datasetId ?? "";
  const benchmarkQuery = useBenchmark(id);
  const casesQuery = useBenchmarkCases(id);
  const documentsQuery = useBenchmarkDocuments(id);
  const chunksQuery = useBenchmarkChunks(id);
  const caseInput = useRef<HTMLInputElement>(null);
  const documentInput = useRef<HTMLInputElement>(null);
  const chunkInput = useRef<HTMLInputElement>(null);
  const [uploadConflict, setUploadConflict] = useState<string | null>(null);
  const [caseDialog, setCaseDialog] = useState<"create" | "edit" | null>(null);
  const [selectedCase, setSelectedCase] = useState<BenchmarkCase | null>(null);
  const [selectedChunk, setSelectedChunk] = useState<BenchmarkChunk | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const handleUploadError = (subject: string) => (error: Error) => {
    const conflict = getConflictMessage(error, subject);
    if (conflict) {
      setUploadConflict(conflict);
      toast.error(conflict);
      return;
    }
    notifyError(error);
  };
  const importCases = useImportBenchmarkCases(id, {
    onSuccess: () => {
      setUploadConflict(null);
      toast.success("Cases imported");
    },
    onError: handleUploadError("Case import"),
  });
  const uploadDocuments = useUploadBenchmarkDocuments(id, {
    onSuccess: () => {
      setUploadConflict(null);
      toast.success("Documents uploaded");
    },
    onError: handleUploadError("Document upload"),
  });
  const importChunks = useImportBenchmarkChunks(id, {
    onSuccess: () => {
      setUploadConflict(null);
      toast.success("Chunks imported");
    },
    onError: handleUploadError("Chunk import"),
  });
  const error =
    benchmarkQuery.error ??
    casesQuery.error ??
    documentsQuery.error ??
    chunksQuery.error;
  if (benchmarkQuery.isLoading)
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
  if (error || !benchmarkQuery.data)
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
  const benchmark = benchmarkQuery.data;
  const cases = casesQuery.data ?? [];
  const documents = documentsQuery.data ?? [];
  const chunks = chunksQuery.data ?? [];
  const corpusItems =
    benchmark.corpus_mode === "CHUNKS" ? chunks.length : documents.length;
  const description =
    benchmark.corpus_mode +
    " · " +
    String(cases.length) +
    " cases · " +
    String(corpusItems) +
    " " +
    (benchmark.corpus_mode === "CHUNKS" ? "chunks" : "documents");
  return (
    <Page>
      <Page.Header
        title={benchmark.name}
        description={description}
        breadcrumbs={[{ label: "Benchmarks", href: "/benchmarks" }]}
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setDeleteOpen(true);
            }}
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        }
      />
      <Page.Content>
        <div className="space-y-6">
          {uploadConflict && (
            <Alert variant="error">
              <AlertTitle>Upload conflict</AlertTitle>
              <AlertDescription className="flex items-center justify-between gap-4">
                <span>{uploadConflict}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setUploadConflict(null);
                  }}
                >
                  Dismiss
                </Button>
              </AlertDescription>
            </Alert>
          )}
          <BenchmarkSummary benchmark={benchmark} id={id} />
          <CaseSection
            id={id}
            cases={cases}
            inputRef={caseInput}
            onCreate={() => {
              setCaseDialog("create");
            }}
            onView={setSelectedCase}
            onEdit={(item) => {
              setSelectedCase(item);
              setCaseDialog("edit");
            }}
          />
          {benchmark.corpus_mode === "CHUNKS" ? (
            <ChunkSection
              id={id}
              chunks={chunks}
              inputRef={chunkInput}
              onView={setSelectedChunk}
            />
          ) : (
            <DocumentSection id={id} documents={documents} inputRef={documentInput} />
          )}
        </div>
      </Page.Content>
      <input
        ref={caseInput}
        className="hidden"
        type="file"
        accept=".json,.jsonl,application/json"
        multiple
        onChange={(event) => {
          if (event.target.files?.length)
            importCases.mutate(Array.from(event.target.files));
          event.target.value = "";
        }}
      />
      <input
        ref={documentInput}
        className="hidden"
        type="file"
        multiple
        onChange={(event) => {
          if (event.target.files?.length)
            uploadDocuments.mutate(Array.from(event.target.files));
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
          if (event.target.files?.length)
            importChunks.mutate(Array.from(event.target.files));
          event.target.value = "";
        }}
      />
      <CaseDialog
        id={id}
        mode={caseDialog}
        item={selectedCase}
        onClose={() => {
          setCaseDialog(null);
          setSelectedCase(null);
        }}
      />
      <CaseViewDialog
        id={id}
        item={selectedCase}
        open={caseDialog === null && selectedCase !== null}
        onClose={() => {
          setSelectedCase(null);
        }}
      />
      <ChunkViewDialog
        id={id}
        item={selectedChunk}
        onClose={() => {
          setSelectedChunk(null);
        }}
      />
      <DeleteBenchmarkDialog
        id={id}
        open={deleteOpen}
        onClose={() => {
          setDeleteOpen(false);
        }}
      />
    </Page>
  );
}

function BenchmarkSummary({ benchmark, id }: { benchmark: BenchmarkInfo; id: string }) {
  const [modeError, setModeError] = useState<string | null>(null);
  const mode = useChangeCorpusMode(id, {
    onSuccess: () => {
      setModeError(null);
      toast.success("Corpus mode updated");
    },
    onError: (error) => {
      const message = getStatusMessage(error, 422, "Corpus mode conversion rejected");
      if (message) {
        setModeError(message);
        return;
      }
      notifyError(error);
    },
  });
  return (
    <Surface className="p-6">
      {modeError && (
        <Alert variant="error" className="mb-4">
          <AlertTitle>Cannot change corpus mode</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>{modeError}</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setModeError(null);
              }}
            >
              Dismiss
            </Button>
          </AlertDescription>
        </Alert>
      )}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-medium text-text-primary">
            Benchmark Information
          </h3>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <InfoRow label="Name" value={benchmark.name} />
            <InfoRow label="Corpus mode" value={benchmark.corpus_mode} />
            <InfoRow label="Cases" value={String(benchmark.case_count)} />
            <InfoRow label="Documents" value={String(benchmark.document_count)} />
            <InfoRow label="Chunks" value={String(benchmark.chunk_count)} />
            <InfoRow label="Version" value={benchmark.version} />
          </div>
        </div>
        <div className="min-w-48">
          <Label htmlFor="corpus-mode">Corpus mode</Label>
          <Select
            value={benchmark.corpus_mode}
            onValueChange={(value) => {
              if (value !== "EXTERNAL") mode.mutate(value as CorpusMode);
            }}
            disabled={mode.isPending}
          >
            <SelectTrigger id="corpus-mode">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="DOCUMENTS">DOCUMENTS</SelectItem>
              <SelectItem value="CHUNKS">CHUNKS</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
    </Surface>
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
function SectionHeader({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 p-4">
      <h3 className="text-base font-medium text-text-primary">{title}</h3>
      <div className="flex gap-2">{children}</div>
    </div>
  );
}

function CaseSection({
  id,
  cases,
  inputRef,
  onCreate,
  onView,
  onEdit,
}: {
  id: string;
  cases: BenchmarkCase[];
  inputRef: React.RefObject<HTMLInputElement>;
  onCreate: () => void;
  onView: (item: BenchmarkCase) => void;
  onEdit: (item: BenchmarkCase) => void;
}) {
  const deleteCase = useDeleteBenchmarkCase(id, {
    onSuccess: () => {
      toast.success("Case deleted");
    },
    onError: notifyError,
  });
  return (
    <Surface>
      <SectionHeader title="Benchmark Cases">
        <Button size="sm" onClick={onCreate}>
          Add Case
        </Button>
        <Button variant="secondary" size="sm" onClick={() => inputRef.current?.click()}>
          <Upload className="h-4 w-4" />
          Import Cases
        </Button>
      </SectionHeader>
      {cases.length === 0 ? (
        <EmptyState
          title="No cases yet"
          description="Add a case manually or import JSON/JSONL files."
          action={<Button onClick={onCreate}>Add Case</Button>}
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Query</TableHead>
              <TableHead>Answerability</TableHead>
              <TableHead>Tags</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {cases.map((item) => (
              <TableRow key={item.case_id}>
                <TableCell>
                  <code className="text-xs">{item.case_id}</code>
                </TableCell>
                <TableCell>
                  <div className="max-w-xl truncate" title={item.query}>
                    {truncateQuery(item.query)}
                  </div>
                </TableCell>
                <TableCell>
                  <StatusBadge
                    status={getAnswerabilityVariant(item.answerability)}
                    showDot
                  >
                    {formatAnswerability(item.answerability)}
                  </StatusBadge>
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    {item.tags.slice(0, 2).map((tag) => (
                      <Badge key={tag}>{tag}</Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      onView(item);
                    }}
                  >
                    <Eye className="h-4 w-4" />
                    View
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      onEdit(item);
                    }}
                  >
                    <Pencil className="h-4 w-4" />
                    Edit
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-error"
                    onClick={() => {
                      deleteCase.mutate(item.case_id);
                    }}
                    disabled={deleteCase.isPending}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Surface>
  );
}

function DocumentSection({
  id,
  documents,
  inputRef,
}: {
  id: string;
  documents: BenchmarkDocument[];
  inputRef: React.RefObject<HTMLInputElement>;
}) {
  const deleteDocument = useDeleteBenchmarkDocument(id, {
    onSuccess: () => {
      toast.success("Document deleted");
    },
    onError: notifyError,
  });
  return (
    <Surface>
      <SectionHeader title="Documents">
        <Button size="sm" onClick={() => inputRef.current?.click()}>
          <Upload className="h-4 w-4" />
          Upload Documents
        </Button>
      </SectionHeader>
      {documents.length === 0 ? (
        <EmptyState
          title="No documents yet"
          description="Upload source documents for this benchmark."
          action={
            <Button onClick={() => inputRef.current?.click()}>Upload Documents</Button>
          }
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Filename</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Size</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {documents.map((item) => (
              <TableRow key={item.document_id}>
                <TableCell>
                  <code className="text-xs">{item.document_id}</code>
                </TableCell>
                <TableCell>{item.filename ?? "Unnamed document"}</TableCell>
                <TableCell>{item.mime_type ?? "—"}</TableCell>
                <TableCell>
                  {item.size_bytes == null ? "—" : String(item.size_bytes) + " bytes"}
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-error"
                    onClick={() => {
                      deleteDocument.mutate(item.document_id);
                    }}
                    disabled={deleteDocument.isPending}
                  >
                    <Trash2 className="h-4 w-4" />
                    Delete
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Surface>
  );
}

function ChunkSection({
  id,
  chunks,
  inputRef,
  onView,
}: {
  id: string;
  chunks: BenchmarkChunk[];
  inputRef: React.RefObject<HTMLInputElement>;
  onView: (item: BenchmarkChunk) => void;
}) {
  const [showCreate, setShowCreate] = useState(false);
  const deleteChunk = useDeleteBenchmarkChunk(id, {
    onSuccess: () => {
      toast.success("Chunk deleted");
    },
    onError: notifyError,
  });
  return (
    <>
      <Surface>
        <SectionHeader title="Chunks">
          <Button
            size="sm"
            onClick={() => {
              setShowCreate(true);
            }}
          >
            Add Chunk
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => inputRef.current?.click()}
          >
            <Upload className="h-4 w-4" />
            Import Chunks
          </Button>
        </SectionHeader>
        {chunks.length === 0 ? (
          <EmptyState
            title="No chunks yet"
            description="Add a chunk manually or import JSON/JSONL files."
            action={
              <Button
                onClick={() => {
                  setShowCreate(true);
                }}
              >
                Add Chunk
              </Button>
            }
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Document</TableHead>
                <TableHead>Text</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {chunks.map((item) => (
                <TableRow key={item.chunk_id}>
                  <TableCell>
                    <code className="text-xs">{item.chunk_id}</code>
                  </TableCell>
                  <TableCell>
                    <code className="text-xs">{item.document_id}</code>
                  </TableCell>
                  <TableCell>
                    <div className="max-w-2xl truncate" title={item.text}>
                      {item.text}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        onView(item);
                      }}
                    >
                      <Eye className="h-4 w-4" />
                      View
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-error"
                      onClick={() => {
                        deleteChunk.mutate(item.chunk_id);
                      }}
                      disabled={deleteChunk.isPending}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Surface>
      <ChunkFormDialog
        key={showCreate ? "open" : "closed"}
        id={id}
        open={showCreate}
        onClose={() => {
          setShowCreate(false);
        }}
      />
    </>
  );
}

function CaseDialog({
  id,
  mode,
  item,
  onClose,
}: {
  id: string;
  mode: "create" | "edit" | null;
  item: BenchmarkCase | null;
  onClose: () => void;
}) {
  const create = useCreateBenchmarkCase(id, {
    onSuccess: () => {
      toast.success("Case created");
      onClose();
    },
    onError: notifyError,
  });
  const update = useUpdateBenchmarkCase(id, item?.case_id ?? "", {
    onSuccess: () => {
      toast.success("Case updated");
      onClose();
    },
    onError: notifyError,
  });
  return (
    <Dialog
      open={mode !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{mode === "edit" ? "Edit Case" : "Add Case"}</DialogTitle>
          <DialogDescription>
            {mode === "edit"
              ? "The API client is ready for case updates when backend support is enabled."
              : "Create one benchmark case."}
          </DialogDescription>
        </DialogHeader>
        <CaseForm
          key={`${String(mode)}-${item?.case_id ?? "new"}`}
          item={mode === "edit" ? item : null}
          pending={create.isPending || update.isPending}
          onSubmit={(data) => {
            if (mode === "edit") update.mutate(data);
            else
              create.mutate({
                ...data,
                case_id: data.case_id || "case-" + crypto.randomUUID(),
              } as BenchmarkCase);
          }}
        />
        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
function CaseForm({
  item,
  pending,
  onSubmit,
}: {
  item: BenchmarkCase | null;
  pending: boolean;
  onSubmit: (data: Partial<BenchmarkCase>) => void;
}) {
  const [caseId, setCaseId] = useState(item?.case_id ?? "");
  const [query, setQuery] = useState(item?.query ?? "");
  const [answer, setAnswer] = useState(item?.reference_answer ?? "");
  const [tags, setTags] = useState(item?.tags.join(", ") ?? "");
  return (
    <div className="space-y-4">
      <div>
        <Label htmlFor="case-id">Case ID</Label>
        <Input
          id="case-id"
          value={caseId}
          onChange={(event) => {
            setCaseId(event.target.value);
          }}
          disabled={Boolean(item)}
        />
      </div>
      <Textarea
        label="Query"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
        }}
        rows={3}
      />
      <Textarea
        label="Reference answer"
        value={answer}
        onChange={(event) => {
          setAnswer(event.target.value);
        }}
        rows={3}
      />
      <Input
        label="Tags"
        value={tags}
        onChange={(event) => {
          setTags(event.target.value);
        }}
        placeholder="comma-separated"
      />
      <Button
        onClick={() => {
          onSubmit({
            case_id: caseId,
            query,
            reference_answer: answer || null,
            tags: tags
              .split(",")
              .map((tag) => tag.trim())
              .filter(Boolean),
            history: [],
            gold_evidence: [],
            metadata: {},
          });
        }}
        disabled={pending || !query.trim()}
      >
        {pending ? "Saving..." : item ? "Save Changes" : "Add Case"}
      </Button>
    </div>
  );
}
function ChunkFormDialog({
  id,
  open,
  onClose,
}: {
  id: string;
  open: boolean;
  onClose: () => void;
}) {
  const create = useCreateBenchmarkChunk(id, {
    onSuccess: () => {
      toast.success("Chunk created");
      onClose();
    },
    onError: notifyError,
  });
  const [chunkId, setChunkId] = useState("");
  const [documentId, setDocumentId] = useState("");
  const [text, setText] = useState("");
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Chunk</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <Input
            label="Chunk ID"
            value={chunkId}
            onChange={(event) => {
              setChunkId(event.target.value);
            }}
          />
          <Input
            label="Document ID"
            value={documentId}
            onChange={(event) => {
              setDocumentId(event.target.value);
            }}
          />
          <Textarea
            label="Text"
            value={text}
            onChange={(event) => {
              setText(event.target.value);
            }}
            rows={6}
          />
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              create.mutate({
                chunk_id: chunkId || "chunk-" + crypto.randomUUID(),
                document_id: documentId,
                text,
                metadata: {},
              });
            }}
            disabled={create.isPending || !documentId.trim() || !text.trim()}
          >
            Add Chunk
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
function CaseViewDialog({
  id,
  item,
  open,
  onClose,
}: {
  id: string;
  item: BenchmarkCase | null;
  open: boolean;
  onClose: () => void;
}) {
  const query = useBenchmarkCase(id, item?.case_id ?? "", {
    enabled: open && Boolean(item),
  });
  const value = query.data ?? item;
  return (
    <Dialog
      open={open}
      onOpenChange={(valueOpen) => {
        if (!valueOpen) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Case {value?.case_id}</DialogTitle>
        </DialogHeader>
        {query.isLoading ? (
          <Spinner />
        ) : (
          <pre className="max-h-96 overflow-auto rounded-md bg-surface p-3 text-xs text-text-secondary">
            {value ? JSON.stringify(value, null, 2) : ""}
          </pre>
        )}
      </DialogContent>
    </Dialog>
  );
}
function ChunkViewDialog({
  id,
  item,
  onClose,
}: {
  id: string;
  item: BenchmarkChunk | null;
  onClose: () => void;
}) {
  const query = useBenchmarkChunk(id, item?.chunk_id ?? "", { enabled: Boolean(item) });
  const value = query.data ?? item;
  return (
    <Dialog
      open={item !== null}
      onOpenChange={(valueOpen) => {
        if (!valueOpen) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Chunk {value?.chunk_id}</DialogTitle>
        </DialogHeader>
        {query.isLoading ? (
          <Spinner />
        ) : (
          <pre className="max-h-96 overflow-auto rounded-md bg-surface p-3 text-xs text-text-secondary">
            {value ? JSON.stringify(value, null, 2) : ""}
          </pre>
        )}
      </DialogContent>
    </Dialog>
  );
}
function DeleteBenchmarkDialog({
  id,
  open,
  onClose,
}: {
  id: string;
  open: boolean;
  onClose: () => void;
}) {
  const remove = useDeleteBenchmark({
    onSuccess: () => {
      toast.success("Benchmark deleted");
      window.location.href = "/benchmarks";
    },
    onError: notifyError,
  });
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete benchmark?</DialogTitle>
          <DialogDescription>
            This permanently removes the benchmark and its normalized records.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              remove.mutate(id);
            }}
            disabled={remove.isPending}
          >
            {remove.isPending ? "Deleting..." : "Delete Benchmark"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
