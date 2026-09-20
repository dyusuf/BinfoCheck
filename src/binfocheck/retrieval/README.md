# T07 retrieval

`HybridClaimRetriever` implements the shared `ClaimRetriever` and `ContextExpander`
boundaries. `SavedContextExpander` exposes the same saved-context implementation.
The implementation has no dependency on T04 and writes no StepAttempt records.
D05/D06 are recorded in [the architecture](../../../docs/architecture.md);
[the approved plan](../../../docs/t07-plan.md) defines this task.

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

Software pins: SentenceTransformers 5.2.0, Transformers 4.57.3, Torch 2.9.1;
transitive versions and hashes are in `uv.lock`. These are an optional
`local-model` extra, excluded from normal offline verification. Local-model
acceptance is pending; synthetic tests do not validate real inference.

Once separately provisioned, use `LocalHarrier.open(Path(huggingface_hub_cache))`.
The adapter requires the exact existing `models--microsoft--harrier-oss-v1-0.6b/
snapshots/<revision>/` layout and checks required files before importing the model
stack. All loading uses `local_files_only=True`, `trust_remote_code=False`, no token,
CPU float32/eager attention, one Torch thread and deterministic algorithms. No
Ollama, remote API or substitute model is used. Preflight uses the actual tokenizer
with `truncation=False`; inference disables default prompts, sets max sequence
length to the pinned limit and checks the output dimension. Oversized inputs fail
with the offending passage/claim ID; there is no chunking or silent truncation.

This task did not download Harrier. A future setup step must provision the pinned
snapshot and optional software, then perform real-model corpus build/query/reload
acceptance. Offline installation after software has been cached uses
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
index/query explicitly and then close/reopen, `load_index`, `rescore`, and `replay`
with sockets/model calls blocked. Synthetic real-corpus wiring is reported separately
from Harrier acceptance, with no recall or benchmark claims.
