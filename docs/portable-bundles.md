# Portable `.rzip` bundles

Rag-eval bundles are versioned ZIP archives with a `package.yaml` envelope and
an exact-member `checksums.sha256` file. The current schema version is `1`.

Targets, benchmarks, tests, and evaluation runs are exported as canonical YAML
and JSONL resources. Benchmark source documents are included as bytes and are
re-stored through the artifact service during import. Target secret references
are replaced by `${RAG_EVAL_SECRET:NAME}` placeholders; usable credentials are
never copied into a bundle.

An evaluation run contains the immutable run configuration and raw target
observations. Historical scoring passes are stored below `metric_runs/` and
remain separate from the evaluation. A metric run can therefore be imported or
created again and scored offline without invoking the target.

The additive `metric_runs` migration preserves legacy rows with a NULL
`metric_run_id`. APIs that omit a metric-run selector continue to return those
legacy results, while new scoring passes are isolated by their metric-run ID.
