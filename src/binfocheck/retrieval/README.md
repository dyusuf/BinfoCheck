# T07 retrieval

`HybridClaimRetriever` implements the shared `ClaimRetriever` and `ContextExpander`
boundaries. `SavedContextExpander` exposes the same saved-context implementation.
The implementation has no dependency on T04 and writes no StepAttempt records.
D05/D06 are recorded in [the architecture](../../../docs/architecture.md);
[the implementation plan](../../../docs/implementation-plan.md#t07--hybrid-retrieval-and-context)
owns task scope and acceptance status.

## Operations

Pass the existing T11A `RecordStore` and `ArtifactStore` to the constructor.

```python
from binfocheck.retrieval import HybridClaimRetriever, request_settings
from binfocheck.domain.interfaces import RetrievalRequest
from binfocheck.retrieval.errors import require

retriever = HybridClaimRetriever(store, store)
# Explicit preparation: requires an already-open local embedder.
index = require(retriever.prepare_index(corpus_manifest_id, embedder))
query = require(retriever.prepare_query(index, analysis_run_id, claim_id, embedder))
request = RetrievalRequest(
    analysis_run_id=analysis_run_id,
    claim_id=claim_id,
    index=index,
    settings=request_settings(query.id),
)
result = retriever.retrieve(request)
```

`prepare_index` loads the selected corpus through T06's validating loader, including
its completion/media-evidence chain. It preflights every dense document before
calling `encode` once. `prepare_query` separately validates and embeds the versioned
query. Explicit preparation may execute again if invoked again; it is not a worker
or automatic retry mechanism. Prefer saved preparation outputs when available.

`load_index(index)`, `retrieve(request)`, `replay(batch_id)` and `rescore(request)`
never load/download/call a model. `retrieve` returns a saved completed cohort when
present; `rescore` executes both library paths over saved state/vectors and returns
a trace. `replay` verifies and returns the saved result without rescoring.
`expand_context(PairRequest(..., settings=POLICY))` validates and returns saved IDs.
Missing vectors, completions, corrupt bytes and identity mismatches fail closed.

## Pinned local Harrier adapter

The exact model is `microsoft/harrier-oss-v1-0.6b` at revision
`f9b9dc8d367d443f2479d27aa5d8d2850c0774ee`, dimensions 1024, supported input
limit 32768 tokens including special tokens. Public sources inspected:
[model card](https://huggingface.co/microsoft/harrier-oss-v1-0.6b/blob/f9b9dc8d367d443f2479d27aa5d8d2850c0774ee/README.md),
[SentenceTransformers 5.2.0 source](https://github.com/huggingface/sentence-transformers/blob/v5.2.0/sentence_transformers/SentenceTransformer.py).

Software pins checked by the adapter: SentenceTransformers 5.2.0, Transformers
4.57.3, Torch 2.9.1, tokenizers 0.22.2, huggingface-hub 0.36.2 and safetensors 0.8.0;
all transitive versions and hashes are in `uv.lock`. These are an optional
`local-model` extra, excluded from normal offline verification. Real-model
acceptance passed on the saved five-page corpus; synthetic tests remain separate.

Once separately provisioned, use `LocalHarrier.open(Path(huggingface_hub_cache))`.
The adapter requires the exact existing `models--microsoft--harrier-oss-v1-0.6b/
snapshots/<revision>/` layout and checks required files before importing the model
stack. All loading uses `local_files_only=True`, `trust_remote_code=False`, no token,
CPU float32/eager attention, one Torch thread and deterministic algorithms. No
Ollama, remote API or substitute model is used. Preflight uses the actual tokenizer
with `truncation=False`. Inference tokenizes the exact representation with special
tokens and no truncation, then calls SentenceTransformers forward/pooling directly
and normalizes the vector. This bypasses its text wrapper, which strips outer
whitespace from saved passages, and applies no hidden prompt. The private embedding
spec records `encoding=exact-tokenizer-forward/1` in index/query identity. The adapter
checks token counts, the pinned sequence limit and output dimension. Oversized inputs fail
with the offending passage/claim ID; there is no chunking or silent truncation.

Provisioning requires the complete exact snapshot in the cache layout above
(including tokenizer, module/pooling configs and weights), plus the locked
`local-model` extra. These were provisioned under explicit user authorization for
the real-model gate. No download or installation is implicit in ordinary operations.
Offline installation after software has been cached uses
`uv sync --offline --locked --dev --extra local-model`; the standard verify script
uses the base environment, so re-sync the extra before real preparation.

## Representations and scoring

Query text is exactly:

```text
Instruct: Given a German health claim, retrieve passages relevant to evaluating the claim.
Query: {Claim.normalized_claim}
```

Dense documents join `Passage.heading_spans` in saved ancestry order with newline,
then a blank line and `Passage.span.exact_text`; no headings means passage text
alone. There is one vector per authoritative T06 Passage. Retrieval representations
and token counts are saved separately; the original spans never change.

BM25 receives only exact original claim span / exact passage text. Versioned German
blank-spaCy tokenization uses NFC/lower, no stopwords/stemming or transliteration.
The protected scan keeps decimal/grouped number spellings, mg/dl, mmol/l, percent
and comparison operators. Other punctuation is removed; range endpoints, negation,
repeated tokens and single-character tokens remain. `3,5`, `3.5` and `1.000` are
not converted. The bm25s adapter consumes explicit token IDs and a sorted vocabulary;
there is no second library tokenizer. Empty/OOV queries have zero lexical hits.

Both paths score the entire corpus independently, sort descending score then
ascending passage ID, and retain up to 50 hits. Semantic cosine has no threshold;
lexical hits require a positive BM25 score. Direct bm25s 0.2.14 uses Lucene scoring,
k1=1.2, b=0.75, float32, NumPy backend. Dense scoring uses LlamaIndex
SimpleVectorStore with explicit stored vectors/query embedding, no Settings model.

RRF sums `1/(60 + one_based_rank)` for present paths, using exact rational ordering
and passage ID for ties. Every path rank/score is retained. No raw-score averaging
or fused cutoff; up to 100 distinct passage candidates survive. Context is the
target and at most one immediate predecessor/successor with identical saved
heading ancestry in the same article, ordered by source position.

## Artifacts and guards

T11A holds restricted, versioned canonical JSON:

- Index data: source closure hashes, embedding spec/software, passage IDs, dense
  strings, lexical tokens, preflight counts, vectors and native bm25s sparse state.
- Index completion: full IndexRef and payload hash. IndexRef remains embedded;
  no new domain record or storage schema exists.
- Query data: source closure, claim/run/index/spec, semantic/lexical strings, saved
  tokens, length and vector; artifact ID binds its entire content.
- Per-path evidence, combined trace, typed candidates/batch and completion.
  Traces retain requested k, eligible/scored/omitted counts, kth-boundary ties,
  all path hits, RRF denominators and saved contexts.
- Task-specific failure artifacts with operation, input IDs and sanitized error.
  A path failure preserves completed path evidence but publishes no complete batch.
  No negative Finding or successful lexical-only fallback is manufactured.

Index identity binds every payload value, including corpus membership, representations,
model revision and vector bytes. Changing source/config/model/results creates a
new identity. Shared records and exact spans are validated through T00's graph
validator; T06 validates its own full source closure on every load.

The bm25s state codec saves its numeric CSC arrays/vocabulary in JSON and restores
only the pinned implementation's required fields. It validates shape/index ranges;
no pickle or unsafe deserialization is used. LlamaIndex's explicit vector mapping
is reconstructed from saved vectors without embedding. Completion is written last.
Existing writes are immutable; interrupted publication can be completed by the
same explicit request using verified state. T11A is not a multi-record transaction.

Normal top-k omission is policy, recorded in traces; a complete batch means both
bounded paths finished, not an exhaustive relevance search. Batch/candidate creation
timestamps come from an immutable publication artifact created before scoring and
reused if publication is interrupted. Failure artifacts are content-addressed
diagnostics, not T11B time/usage or restart orchestration records.
Bitwise fresh model reproducibility across platforms is not promised. Exact saved
replay does not depend on fresh inference; rescoring uses the pinned numerical stack.

## Verification

`uv run --offline --locked pytest tests/retrieval` exercises actual BM25/vector
libraries with labeled synthetic embeddings and blocks network connections.
`scripts/verify.sh` runs the full repository checks. Tests include independent
routing, German lexical details, hand-calculated fusion, top-50/full union,
identity/dimension/length failures, context clipping and T11A reopen/replay/rescore.

Real-corpus acceptance uses the existing store/manifest in `docs/t06-handoff.md`.
Copy its immutable dependency closure into a private acceptance store; prepare
index/query explicitly using the actual tokenizer for all-input preflight, including
special tokens. Save passage IDs/counts and the traceable diagnostic claim with the
acceptance evidence. Then close/remove model access and reopen the store; exercise
`load_index`, `rescore`, completed-cohort `retrieve` and `replay` with sockets,
tokenization and model loading/encoding blocked. Synthetic real-corpus wiring is
reported separately from Harrier acceptance, with no recall or benchmark claims.

Real Harrier acceptance on 20 September 2026 produced 228 corpus vectors and one
traceable synthetic diagnostic-claim query vector, all finite/non-zero and 1024-D.
Actual preflight counts include the tokenizer's one special token; the largest
passage representation was 784 tokens, and the query was 32. Inference token IDs
matched full representations exactly. A controlled oversized representation failed
before embedding with its passage ID. The independent paths returned 50 hits each,
with 83 union candidates (17 in both paths); exact RRF, path scores and saved context
IDs were checked. A fresh process with model imports, tokenizer calls, model-cache
reads and networking blocked passed load/rescore/completed retrieval/replay.

The durable private T11A acceptance store and reproducible scripts are at
`/mnt/workspace/BinfoCheck-data/t07-harrier-acceptance-20260920/`;
`t07-real-model-report.json` contains IDs, token counts, versions and checks,
`model-provision.json` records snapshot file hashes. The original T06 store is unchanged.
The successful gate encoded 229 inputs locally; earlier failed local attempts did
not publish a completed index and total local inference usage was not metered.
No paid provider calls or provider cost occurred. These counts establish integration,
not recall or retrieval quality.

Transformers 4.57.3 emitted a Mistral-regex warning for this Qwen3 snapshot's 4.57.6
configuration metadata. Its local detection branch was inspected; the exact pinned
tokenizer was retained, with no Mistral rewrite. NVML and deprecated `torch_dtype`
warnings did not prevent CPU acceptance.
