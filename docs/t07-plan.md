# T07 implementation plan

Approved by the user's T07 implementation instruction on 20 September 2026.
Scope and shared rules: docs/implementation-plan.md (T07), AGENTS.md and
docs/development-workflow.md. No shared domain/schema changes are planned.

## Decisions

- Local SentenceTransformers model microsoft/harrier-oss-v1-0.6b, revision
  f9b9dc8d367d443f2479d27aa5d8d2850c0774ee, 1024 dimensions. No Ollama.
- Query representation: `Instruct: {instruction}\nQuery: {normalized_claim}`;
  instruction: "Given a German health claim, retrieve passages relevant to evaluating the claim."
- Dense document: saved heading spans in their ancestry order, joined with newlines,
  then two newlines and the exact passage; if no headings, exact passage alone.
  Each passage remains one index unit and authoritative evidence.
- Preflight all complete representations with the pinned tokenizer, including special
  tokens, before any embedding. Model limit 32768 tokens; fail with passage ID on
  overflow. No truncation, chunking or implicit model loading/downloading in reads.
- Lexical query: exact original claim span; document: exact passage. Direct bm25s,
  Lucene BM25 k1=1.2, b=0.75, deterministic German blank-spaCy tokens, NFC/lower,
  no stemming/stopword removal, preserve negation/numbers/units/operators.
- Independent semantic_k=50 and lexical_k=50. Stable score/ID ordering; passage-ID
  deduplication; equal-weight RRF c=60; retain all union candidates and both ranks/
  scores. No final cutoff. Context: target and eligible immediate same-section neighbors.
- T11A stores index/vector/lexical/representation artifacts, traces, failures and
  completion records. No StepAttempt or restart orchestration (T11B).
- Explicit preparation runs the local model; retrieve/reload/replay use saved vectors.
  Corpus/model/revision/dimension/config/content mismatches fail closed.

## Files and implementation

Create src/binfocheck/retrieval/ with config/errors, representations/tokenization,
local embedding adapter, index serialization/search, corpus loading, persistence,
retriever/context and README. Create tests/retrieval/ with synthetic embeddings.
Update pyproject.toml/uv.lock, D05/D06 in docs/architecture.md, T07 status in
docs/implementation-plan.md and deferred work in docs/beyond-mvp.md.

1. Pin dependencies; verify bm25s and SentenceTransformers APIs and local model availability.
2. Implement versioned representations, preflight, tokenization, fusion and context.
3. Implement T11A index/query-vector preparation, completion and strict reload guards.
4. Implement ClaimRetriever and ContextExpander with saved traces and replay.
5. Test input routing, numeric/negation tokens, hand-calculated RRF, top-50/full union,
   overflow before embedding, identity guards, SQLite reopen/reload/replay and failures.
6. Run `uv run --offline --locked pytest tests/retrieval` and `scripts/verify.sh`.
7. Exercise saved T06 corpus with synthetic embeddings; real-model acceptance remains
   blocked if the pinned model is absent. No model download in this assignment.
8. Sync main, publish the existing branch/draft PR and concise temporary handoff.

## Persistence and replay

Index identity binds corpus closure, passage order, full dense/lexical representations,
model revision/software/settings and vector/lexical state hashes. Retrieval identity
also binds run, claim, saved query-vector hash and retrieval/context policy. Preserve
native lexical state and vectors in T11A artifacts; IndexRef is embedded in an artifact,
not a new record kind. CandidatePair holds per-path ranks/scores and context IDs;
trace holds full path counts, omitted counts, fusion contributions and input provenance.
Completion is published last and verified on load. Saved-result replay returns the
original result; rescoring reloads indexes without tokenization or model execution.
Failed preparation/retrieval saves a task-specific failure artifact, not a negative finding.

## Integration gates and risks

Exact dependency pins and adapter behavior must be verified. The public pinned model
card gives dimension 1024 and limit 32768; local real-model behavior still requires
acceptance. Input-length checks include heading context and the query instruction.
No model comparison, chunking, reranking or tuning in T07. Top-50 and c=60 are fixed
implementation settings, not validated recall guarantees. Numerical recomputation
requires the pinned software stack; exact replay uses saved results.

Public model metadata/card (read without downloading weights):
https://huggingface.co/microsoft/harrier-oss-v1-0.6b/tree/f9b9dc8d367d443f2479d27aa5d8d2850c0774ee
