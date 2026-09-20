# T07 durable acceptance handoff — 20 September 2026

**Status: accepted.** Offline verification and real local Harrier integration passed.
This records durable engineering evidence, not retrieval quality or recall.
[Architecture D05/D06](architecture.md#8-decision-register) owns the decisions;
[the task card](implementation-plan.md#t07--hybrid-retrieval-and-context) owns status
and required checks; the [retrieval README](../src/binfocheck/retrieval/README.md)
owns implementation, configuration and usage.

## Pinned model and execution

- Model: `microsoft/harrier-oss-v1-0.6b`.
- Revision: `f9b9dc8d367d443f2479d27aa5d8d2850c0774ee`.
- Execution: local SentenceTransformers, CPU float32/eager attention, one Torch
  thread, deterministic algorithms; 1024 dimensions. Snapshot loading passed with
  networking blocked and `local_files_only=True`.
- Exact snapshot path:
  `/home/ubuntu/.cache/huggingface/hub/models--microsoft--harrier-oss-v1-0.6b/snapshots/f9b9dc8d367d443f2479d27aa5d8d2850c0774ee/`.

| Local-model software | Pinned version |
|---|---|
| sentence-transformers | 5.2.0 |
| transformers | 4.57.3 |
| torch | 2.9.1 |
| tokenizers | 0.22.2 |
| huggingface-hub | 0.36.2 |
| safetensors | 0.8.0 |

The locked dependencies and exact snapshot were provisioned under explicit user
authorization. File hashes are preserved in `model-provision.json` below.

Encoding is `exact-tokenizer-forward/1`, included in private index/query identity.
The gate exposed SentenceTransformers' automatic outer-whitespace stripping,
which changed tokenization for 28 saved representations. Exact tokenizer features
now pass through SentenceTransformers forward/pooling and vector normalization,
without its text wrapper or hidden prompts. Authoritative passage text and the
approved retrieval representations remain unchanged; an offline regression covers
outer whitespace, including non-breaking spaces.

## Acceptance inputs and results

The existing ready T06 corpus contained **five pages / 228 passages**. Acceptance
used a private copy of the saved corpus and one traceable synthetic driving claim
(`t07-synthetic-claim`), with real Harrier vectors. The original T06 store was not
modified; source evidence and corpus provenance are described in the
[T06 handoff](t06-handoff.md).

- The actual tokenizer preflighted every complete heading-plus-passage representation
  before embedding. Counts included its one special token. Maximum observed passage
  length: **784 tokens**; the single diagnostic query: **32 tokens**; model limit:
  **32768 tokens**. Inference token IDs matched the full representations exactly,
  with no silent truncation.
- A controlled oversized copy of the last passage representation failed preparation
  before any encoding and identified the offending passage ID. The corpus itself
  was unchanged; the ID and probe outcome are saved in the report.
- **228 corpus vectors + 1 diagnostic query vector** were finite, non-zero and
  exactly **1024-dimensional**. Observed normalized-vector norms ranged from
  `0.999999922140952` to `1.0000001247779187`.
- Semantic query routing used the fixed versioned instruction plus
  `Claim.normalized_claim`; dense documents used saved heading context plus exact
  passage text. BM25 used `Claim.original_span.exact_text` against exact
  `Passage.span.exact_text`. The diagnostic normalized claim differed from its
  original span, allowing the routes to be checked separately.
- Independent retrieval returned **50 semantic / 50 lexical hits**, yielding
  **83 fused candidates**, including **17 shared** by both paths. An independent
  exact-fraction calculation verified equal-weight RRF (`c=60`) ordering and the
  full union. Candidates retained applicable path ranks/scores; passage and saved
  immediate same-section context IDs resolved and matched the expected context.
- T11A persisted the real index, query vector, traces, candidate cohort and completion
  evidence. Close/reopen checks passed. A separate fresh process with model-package
  imports, tokenization, model-cache reads and networking disabled passed
  `load_index`, `rescore`, completed-cohort `retrieve` and `replay` entirely from
  persisted artifacts/vectors.

The successful gate encoded 229 inputs locally in two preparation batches. Earlier
failed local attempts published no completed index; total local inference usage
across those attempts was not metered. **Paid provider calls: 0; provider cost: USD 0.**
Offline acceptance also passed 36 retrieval tests and `scripts/verify.sh` (977 tests,
lint, formatting, types, schema and whitespace checks). No deployed check applies.

## Durable private evidence

Store and evidence directory:
`/mnt/workspace/BinfoCheck-data/t07-harrier-acceptance-20260920/`.
It is outside the task worktree and must be preserved independently of Git.

| File | Evidence |
|---|---|
| `t07-real-model-report.json` | Model/software identity, artifact IDs, per-passage token counts, vector checks, retrieval counts and replay outcomes |
| `model-provision.json` | Exact snapshot revision, downloaded file sizes and SHA-256 hashes |
| `acceptance.py` | Original real-model acceptance harness and diagnostic-claim construction |
| `model-free-replay.py` | Fresh-process saved-artifact verification with model/cache/tokenizer/network access blocked |
| `acceptance.log` | Successful local model gate, token-count progress and result |
| `model-free-replay.log` | Successful isolated replay result |
| `whitespace-failure.log` | Earlier token-mismatch failure that exposed wrapper stripping |
| `store.sqlite3`, `artifacts/` | T11A records and restricted evidence payloads |

Saved cohort identifiers:

- Corpus: `corpus-manifest-cca67f16867a3a37e37252c360e364e597a2cab368ac6cc52ee5d6b693d41e69`.
- Index: `retrieval-index-e3ce0d241daf31d82951d418738ba31aaaed500fecd2c48ebb581c5805a8d346`.
- Query: `retrieval-query-e9fa371b2862f31d4b23aec127b0b38da980fbb0c4e3caf373f9685d780718c1`.
- Retrieval batch: `retrieval-batch-4166180761e9653ac67bfaae23f12c4744b0af0ed0a4c26d5ca005e7aec8a4b5`.

## Warning and limits

Pinned Transformers 4.57.3 emitted a Mistral-regex warning for this Qwen3 snapshot's
4.57.6 configuration metadata. The local detection branch was inspected; the exact
pinned tokenizer was retained unchanged, with no Mistral regex rewrite. NVML and
deprecated `torch_dtype` warnings did not prevent CPU acceptance.

This is integration acceptance, **not a retrieval-quality or recall benchmark**.
The single synthetic diagnostic claim and fixed corpus do not establish accuracy,
optimal retrieval depth or general quality. No model comparison, tuning, chunking,
reranking, query expansion, Jev/T08 or T11B orchestration was performed.
