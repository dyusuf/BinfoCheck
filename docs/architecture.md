# BinfoCheck — Architecture

**Version:** 1.4 · 18 September 2026  
**Status:** Initial design for the [MVP](mvp.md); model quality remains unvalidated.

This document owns component responsibilities, data contracts and decision rules.
The [implementation plan](implementation-plan.md) owns tasks and acceptance checks.
[Beyond MVP](beyond-mvp.md) owns later benchmarking and features. Paths below are
planned deliverables, not evidence of existing code.

## 1. System structure and boundaries

Two inputs meet in evidence analysis: AI-search answers and versioned diabinfo pages.

```text
AI-search capture → Claim processing → Citation routing
                                            │
                      ┌─────────────────────┼─────────────────────┐
                      ↓                     ↓                     ↓
                 Diabinfo cited       Citation unclear       Not cited
                      ↓                     ↓                     ↓
                Citation finding     Unresolved finding    Evidence analysis
                                                                  ↑
Diabinfo pages → Corpus ingestion → Versioned passages/indexes ────┘

Every stage → Shared store: originals, intermediate results and reviews
                                      ↕
                                     API
                                      ↕
                                  Dashboard
                                      ↕
                                    Editor
```

Use **one application codebase**, not microservices. Run processing outside
interactive page requests. A worker may be a process in that codebase; its mechanism
is still open. The dashboard reads saved results/progress and writes reviews through
the API, never directly to providers or storage.

Route citations per claim. Clearly cited claims skip matching; unclear claims are
not definitely uncited. Claims citing other sites but not diabinfo are uncited for
this purpose. Category 1's retained label, **“Cited diabinfo match,” means citation
presence only**. No category or model score proves where an answer came from.

## 2. Implementation map

**Code** means explicit rules rather than model judgments. Keep tool integrations
behind the named interfaces. Record exact models, packages and settings before use;
do not silently change vendors or allow library defaults to make extra model calls.

| Component | Initial implementation |
|---|---|
| `ObservationProvider` | Python HTTP adapter → DataForSEO Google AI Mode SERP API [1] |
| `AnswerIndexer`, `ContextBuilder` | Python; spaCy German tokenizer + rule-based Sentencizer proposed [5] |
| `ClaimExtractor` | Claimify-inspired stages: Jev decisions + local Qwen generation through vLLM [3] |
| `CitationMapper` | Code using citation metadata and versioned mapping rules |
| `CorpusIngestor` | Code for fetching/parsing/versioning; LlamaIndex ingestion [4] |
| `ClaimRetriever` | LlamaIndex vector retrieval, local Harrier embeddings, direct German-configured bm25s (D05/D06) |
| Rank fusion, `ContextExpander` | Code merges ranks and attaches saved source context |
| `CandidateVerifier`, `CorrespondenceJudge` | Jev through `DecisionModel` [2] |
| `AlternativeSourceAnalyzer` | Code selects captured excerpts; Jev compares them |
| `EvidenceClassifier` | Jev combines evidence; code enforces routing and evidence requirements |
| Storage, execution, API, dashboard | Application code; concrete stack remains open |

Jev's fixed-choice outputs and probabilities do not establish accuracy on this data.
Sentence splitting prepares context; it does not define claim boundaries.

## 3. Shared data contracts

### 3.1. Schemas and records

T00 creates typed records/interfaces in `src/binfocheck/domain/` and examples in
`tests/fixtures/contracts/v1/`. Export schemas from those types; do not maintain
separate handwritten versions. Each boundary returns a typed result or failure.

Require valid, invalid-with-expected-error, and unavailable-data examples where
applicable, plus one linked observation-to-review example. Model only MVP fields.
An **artifact** is a saved payload/file; a **manifest** records the inputs and versions
used together.

| Records | Required data and rules |
|---|---|
| `ArtifactRef`, `TextRecord`, `SpanRef` | Artifact ID/storage key, hash, media type; immutable text ID; exact quote and start/end offsets identifying one saved text. |
| `CaptureRequest`, `Observation` | Request/query ID, product/provider, requested/reported settings, timestamps, capture outcome, raw artifact, answer text ID, source references and metadata availability. Replay retains observation identity. |
| `SourceReference`, `TextUnit` | URL, original metadata location, citation/reference/search-result kind and available excerpt; unit order, parent/heading IDs and spans. Do not copy neighboring text into each unit. |
| `Claim`, `ExtractionIssue` | Claim, observation and run IDs; normalized German claim, original span, context-unit IDs and decisions. Invalid, unlocatable or unresolved outputs are issues, not accepted claims. |
| `CitationAssociation` | Claim/run IDs, reference IDs, yes/no/unclear status, rule version and mapping evidence. A nearby domain is not enough. |
| `ArticleVersion`, `Passage`, `CorpusManifest` | URL, raw/cleaned text IDs, title/headings, fetch time, hash, parser version and spans. Pin article/passage versions in the manifest. |
| `RetrievalBatch`, `CandidatePair` | Claim/run/corpus/index IDs, completion status, passage IDs, each path's ranks/scores, fused rank and context references. Deduplication preserves all ranks. |
| `DecisionRecord` | ID/task type, input IDs/artifacts, requested/returned model IDs, prompt/rubric/config versions, label/probabilities, usage, timing and errors. Missing usage/output is not zero. |
| `AlternativeInspection` | Source/excerpt IDs, correspondence decision, inspected/unassessed state, coverage reason and known duplicate group. URL-only sources are not inspected text. |
| `Finding` | Claim/run ID, status, nullable category, pair/decision IDs, provisional scores and reason codes. One selected finding per claim/run. |
| `RunManifest`, `StepAttempt`, `Review` | Input/version references, capture settings, diagnostic/monitoring purpose, model/prompt/rubric versions and budgets; step attempts/outcomes; reviewer, finding ID, decision, note and time. Never overwrite earlier results. |

Interfaces cover acquisition, indexing/context, extraction, citation mapping,
corpus ingestion, retrieval, decision/generation, evidence analysis and storage.

### 3.2. IDs, source locations and missing data

Records have stable IDs and schema versions. Derived results carry input IDs and
`analysis_run_id`. Use UTC timestamps and versioned or hashed configurations/prompts.

Offsets count **Unicode code points**, start-inclusive/end-exclusive, in an identified
immutable text—not bytes, tokens or JavaScript UTF-16 indexes. The dashboard needs
a tested conversion or code-point-aware slicing helper. [7]

Illustrative location fragment, not a complete record:

```json
{
  "text_id": "answer_fixture_01",
  "text": "Äpfel 🍎 sind rot.",
  "source_span": {
    "text_id": "answer_fixture_01",
    "start": 8,
    "end": 17,
    "exact_text": "sind rot."
  }
}
```

Slicing must recover the exact quote. Never normalize text after assigning offsets;
save a new representation with transformation metadata. Repeated quotes require a
unique source-unit reference or an ambiguity error, not the first substring match.

Optional collections carry **available / incomplete / unavailable**. Available plus
empty means none captured; unavailable means unknown. A nonempty reference list does
not prove complete citation capture.

### 3.3. Separate statuses

| Dimension | Values |
|---|---|
| Processing | `pending`, `running`, `succeeded`, `failed`, `skipped`; run summaries may show partial failure |
| Diabinfo citation | `yes`, `no`, `unclear` |
| Correspondence | `match`, `partial_match`, `no_match`, `uncertain`, `not_assessed` |
| Finding | `categorized`, `no_match_found`, `citation_unclear`, `not_enough_evidence`, `pending`, `processing_failed`; category null unless categorized |
| Review view | `unreviewed`, `confirmed`, `rejected`, `corrected`, derived from separate review events |

A failed call is not a negative result. Successful extraction with no factual claims
is not capture failure. Unresolved claims do not establish absence.

## 4. Observation, extraction and citation routing

### Capture and context

Use DataForSEO's **Google AI Mode endpoint**, not direct model generation. Preserve
the raw response, immutable answer and normalization version. Save requested and
reported settings separately. This is a controlled capture, not the user's personal
logged-in experience.

A payload item named `ai_overview` does not change the product identity to AI
Overview. References are not a complete retrieval history; fan-out data may be
absent. [1] Keep citation-data availability separate from claim-scope assessability.

Index headings, paragraphs, bullets and sentences against the saved answer. Build
context from their IDs when needed. Record the question and context actually sent
to each decision.

### ClaimExtractor stages

This adapts Claimify's method; it does not reproduce its published results. [3]

| Stage | Tool and required behaviour |
|---|---|
| Prepare context | Code selects target, neighbors and headings; context may span sentences. |
| Select factual content | Jev: factual / nonfactual / mixed / uncertain; retain exclusions and issues. |
| Handle mixed text | Local GenerationModel retains factual content in derived wording; adds no facts. |
| Assess ambiguity | Jev: clear / resolvable from supplied context / unresolved. |
| Clarify | Local GenerationModel resolves references from that context, not external knowledge. |
| Decompose | Local GenerationModel returns standalone German claims with original quotes/source-unit references. |
| Locate sources | Code validates exact locations; rejects invented or ambiguous quotes. |
| Validate extraction | Jev separately checks faithfulness, atomicity and self-containment; uncertainty allowed. |
| Assemble | Code saves accepted claims and separate issues with decision/version IDs. |

Validate against the original answer and recorded context, not just a rewrite. The
question may resolve a reference but cannot supply a new assertion. Do not discard
facts as off-topic. Several claims may share a span; one span may cover several
sentences. Checking extraction accuracy is in scope; checking the cited website's
support or medical truth is not.

### Citation routing

| Evidence | Route |
|---|---|
| Clear diabinfo association | Category 1, without retrieval or source-support checking |
| Assessable absence of diabinfo attribution | Overlap analysis, including other-source-only claims |
| Incomplete capture or unclear scope | `citation_unclear`; exclude from definitely-uncited counts |

Use provider mappings when their meaning is established; record rules/evidence for
inferred mappings. Do not apply a paragraph-end citation to every claim automatically.
Parse hostnames; reject lookalikes such as `diabinfo.de.example.org`.

For answer-level statistics, an observed citation establishes presence. Absence
requires assessable citation coverage.

## 5. Corpus and retrieval

Ingest the [five pilot HTML pages](mvp.md#6-included-scope). Save raw snapshots and
cleaned article text, headings, parent sections, spans and hashes. Exclude navigation
and banners by recorded parser rules; do not rewrite articles. All five pages must
be usable before corpus readiness. Record failures. A page-list change requires
explicit task/user authorization and an update to the MVP.

Start with natural paragraphs/sections. Pin passage construction and German lexical
settings. Source, parser, segmentation or embedding changes create a new corpus/index
version. Semantic and lexical paths use the same passage IDs and corpus version.

```text
Normalized claim → semantic top-k ─┐
Original span    → BM25 top-k ─────┴→ deduplicate → rank fusion
                                    → saved context → verification → correspondence
```

Equal-weight reciprocal-rank fusion is selected under D06, not calibrated. Store
path scores, ranks, fusion parameters and truncation. Never sum raw BM25/vector scores. Pin
embedding model, dimensions and language settings; disable implicit model calls or
query expansion. [4], [6]

Develop retrieval with fixture claims; T04 connects later in T11B.
A verifier cannot recover a passage retrieval missed.

## 6. Decision rubrics and evidence classification

### 6.1. Decision rules

A **rubric** defines a decision's question, input fields, labels, uncertainty handling
and examples. Version these in `rubrics/`; keep generation instructions in `prompts/`.
Implement these rules in the assigned task. Record their versions and authorization
under D07 before live use. Defining rules is not benchmarking them.

| Decision | Labels and use |
|---|---|
| Candidate verification | Could this passage help? `worth_examining` = relevant factual material; `clearly_irrelevant` = cannot help; `uncertain` = possible relevance/inadequate context. Rerank and remove only clearly irrelevant candidates under a recorded provisional policy. Keep uncertain candidates and rejection records. |
| Correspondence | How much of the claim is expressed? `match` = assertion with essential qualifications; `partial_match` = only part; `no_match` = no corresponding assertion; `uncertain` = cannot determine. Topic or numbers alone do not establish a match. |
| Alternative-source correspondence | Captured excerpt corresponds / partly corresponds / does not correspond / unclear. A negative describes the excerpt, not its whole page. |
| Classification | Which category does the evidence support? Allow insufficient evidence; enforce Section 6.2 regardless of model score. |

Candidate verification selects material for closer inspection; correspondence judges
that material. Preserve both decisions. A budget cap that leaves candidates unassessed
must record incomplete work, not a complete negative finding.

### 6.2. Classification rules

Supply the original span/context, normalized claim, matching diabinfo span/context,
alternative excerpts/decisions, citation status, metadata coverage and retrieval
records. Keep claim-group references so decomposition does not erase distinctive
combinations. Scores alone are insufficient.

| Category | Required evidence |
|---|---|
| **1. Cited diabinfo match** | Clear citation association; no model support check. |
| **2. Uncited generic match** | Full diabinfo correspondence plus inspected alternative text expressing the same information. Sharing is established in this set, not across the whole web. |
| **3. Uncited distinctive match** | An identifiable specific detail/combination matches; inspected relevant alternatives still offer plausible competing explanations. |
| **4. Uncited highly distinctive match** | Positive, unusually close wording/examples/details and meaningful comparison with relevant excerpts; limited competing explanation within that set. Missing, irrelevant or truncated alternatives alone are insufficient. |

Categories 3–4 require traceable evidence for the distinctive pattern and an adequately
assessable comparison under the rubric. An excerpt does not exhaust its source page.

**Code-enforced rules:**

- Clear citation → Category 1; unclear citation → `citation_unclear`.
- Completed retrieval/judging with no correspondence → `no_match_found` in this
  corpus. Unfinished candidates or failures cannot produce that finding.
- Partial/uncertain correspondence or inadequate alternatives → `not_enough_evidence`;
  retain partial results. Categories 2–4 require a full match.
- Invalid output/model failure → recorded issue or processing failure, not a negative.
- High model scores do not override missing evidence or establish hidden use.

Jev combines evidence without a handwritten weighted attribution formula. Store its
scores as provisional, not calibrated provenance probabilities. Explain findings
with highlighted evidence and rubric-based templates, not invented model reasoning.

### 6.3. Alternative-source limit

**Analyze captured excerpts only. No additional page fetching or web search.** Even
fetching an already-listed URL requires a separate task explicitly authorizing that
scope change; URL-only sources remain unassessed.

Record excerpt provenance/availability, exact duplicates and known related sources.
Different URLs need not be independent. Fan-out queries and reported retrieval are
leads, not proof of matching content or causal use. Positive excerpts can establish
sharing; missing matches in a small set cannot establish uniqueness.

## 7. Storage, execution and product access

### Persistence

T00 defines storage interfaces; **T11A implements shared persistence before live
integrations**. T11B later connects execution. Do not invent per-branch save formats.

Store original artifacts, typed intermediate records, source/index versions and model
decisions. Exclude credentials from saved payload bodies; record transport-envelope
redactions. Separate restricted real artifacts from shareable fixtures.

A new capture creates an observation; reanalysis creates a run over saved input and
pinned versions. Resume reuses completed outputs. Reviews append events against a
finding/run; corrections supersede without deleting history. Use the RunManifest
fields in Section 3.1. Replay recovers saved artifacts; fresh model/search calls may
differ.

### Execution

Save step attempts, provider request IDs when available, timing, usage and failures.
Set cost/request caps, timeouts, concurrency and retry limits before paid execution.
Use stable work keys to prevent duplicate local work, but do not promise exactly-once
external billing. A paid timeout with unknown outcome must not trigger a blind retry.

Keep browser requests responsive by saving progress outside the request. Restarts
retain completed work, findings and reviews. Show partial failures. No large-scale
scheduler or extra distributed service is required.

### Access and metrics

Choose authentication before T12. Permissions must distinguish:

| Capability | Required access |
|---|---|
| Read normalized evidence/summaries | Authorized pilot reader/editor |
| Confirm/reject/correct | Authenticated reviewer; preserve identity |
| Start paid runs/change limits | Explicitly authorized operator; denied by default |
| Raw payloads/credentials | Restricted operator/admin; never browser secrets |

Roles may share an account in a private pilot, but permissions stay explicit. Do not
build tenant management. Use the question set recorded in the task or pilot manifest,
not patient records. Treat captured text as untrusted; render safely, without executing
embedded content or following arbitrary links. No public raw-artifact access by default.

The API exposes stored observations, claims, evidence, progress and reviews with
stable IDs, requested run versions and errors. Code calculates metrics: count each
answer once for answer-level metrics and each claim once per selected analysis run
for claim-level metrics, not per passage. Show failures, unknowns and exclusions.
Separate diagnostics from monitoring, reviews from automated results, and reanalyses
from new captures. Use the citation coverage rule in Section 4.

## 8. Decision register

**Selected:** initial implementation choice, not validated. **Proposed:** needs a
recorded decision before use. **Open:** blocks the named work, not unrelated development.

A required decision is resolved when its selected value and authorization are
recorded in the assigned task or a repository decision record. Authorization must
come from the assigned task or a direct user instruction; writing a record does not
authorize the choice by itself. Record the value, version/configuration path, date,
affected tasks and authorization reference here or in a linked decision record.

A task may explicitly delegate an implementation choice within its bounds. Record
the selection without asking again. Otherwise, propose unresolved blocking choices
and request direction from the user; stop only dependent work. Routine in-scope
implementation details need no separate approval.

| ID | Decision | Record before |
|---|---|---|
| D01 | Python schema/runtime/test dependencies | T00 acceptance |
| D02 | Shared artifact and record/database backend | T11A backend implementation |
| D03 | Resolved and exercised for the exact T01 German capture: Germany/de/desktop/windows, one POST, zero retries, 60s timeout; USD 0.004 reported against USD 0.01 ceiling, budget verified; see T01 handoff | One-call authorization consumed; any further provider call requires new explicit authorization |
| D04 | Jev `jev-1.13.0`; MVP GenerationModel is local Qwen3-4B-Instruct-2507 served by vLLM, selected below. Historical OpenAI adapter retained for replay | Local T04 integration in progress; bounded Jev authorization recorded below |
| D05 | T07 selected: local pinned Harrier/SentenceTransformers, 1024 dimensions, T11A index artifacts; details below | T07 real-model acceptance passed |
| D06 | T02 resolved: spaCy 3.8.16 blank German tokenizer + rule-based Sentencizer and versioned mechanical rules; T06 textual corpus and audited non-text visual limitation resolved below; T07 direct bm25s and top-50/RRF settings selected below | T07 offline and real-model acceptance passed |
| D07 | T04 extraction policy/resources selected below; T05/T08/T09/T10 portions remain open | Both authorized retained gates returned D.unresolved; accepted Claim output remains blocked. Further execution requires new scope authorization. Category changes require explicit scope authorization. |
| D08 | German question manifest and run limits; five pages fixed | T11B live run and T14; T06 supplies snapshots |
| D09 | Worker, API, frontend, deployment stack; one codebase | Affected T11B/T12/T13/T14 work |
| D10 | Authentication, accounts, artifact handling, deployment access | T12 access checks and T14 deployment |

**D04 local generation selected — 20 September 2026:** the current T04 assignment
explicitly selects `Qwen/Qwen3-4B-Instruct-2507` for MVP generation; subsequent user
instruction selects vLLM serving. Model comparison remains Beyond MVP. The pinned
snapshot is `cdbee75f17c01a7cc42f958dc650907174af0554`. The separate
`t04-vllm-generation/1` adapter configuration in `models/config.py` binds the complete
private runtime manifest hash, revision and serving settings. Historical
`t03-model-adapters/1` Jev/OpenAI prepared bytes and replay identities remain unchanged.
No shared wire schema, extraction prompt, rubric, locating or target-accounting rule
changes. T04 validates the two actually selected model identities in each run.

The V100 uses vLLM 0.10.2, V0 engine, FP16, XFORMERS, eager execution, context limit
4096, one sequence, tensor parallelism one, GPU memory fraction 0.65, no quantization,
no prefix caching and no guided-decoding fallback. Exact server dependencies are in
`models/vllm-runtime.lock`; its isolated Python 3.12 environment uses Torch 2.8.0 and
Transformers 4.57.3. It does not alter T07's locked Torch 2.9.1 environment. A verified
process-local NVML 580.173.02 library matches this host's loaded driver; no system
library replacement, driver unload or reboot is needed for serving.

The authenticated loopback-only endpoint is `http://127.0.0.1:8004/v1/chat/completions`.
Requests bind the exact model/revision alias, unchanged extraction prompt and input,
strict JSON Schema, temperature 0, top_p 1, seed 0, n=1, max_tokens<=512, no tools,
no streaming. Input overflow fails; it is never truncated. Model weights/tokenizer
are pre-provisioned, inference runs with offline Hugging Face settings and usage
telemetry disabled. Exact runtime inventory, launch settings and model-file hashes
are retained privately and snapshotted with T03 model evidence. Actual vLLM raw chat
responses remain separate from validated canonical structured output; finish reasons
other than `stop`, malformed/schema-invalid JSON and identity mismatch fail without
repair. The response model alias alone does not authenticate weights; retained launch
and snapshot evidence establish the local origin. Replay requires no server or GPU.

The user subsequently authorized at most **five Jev calls / USD 0.05 total** for the
retained gate, concurrency one, timeout 60 seconds each, zero retries. Exact request
bindings are prepared from actual stage inputs under this bounded authorization;
B/D selection and three independent H validations remain unchanged. Other paid model
calls are prohibited. One local F operation uses a zero external-provider allowance;
local infrastructure cost is unknown. The original gate bundle is immutable; create
a new same-observation diagnostic run/index/configuration in a private copy. Gate
scope stays first sentence [0,63), B/D/F/H only, no C/E or alternative targets.
This supersedes the old OpenAI-access and separate H-approval proposal for this
assignment only. Outcomes and actual usage must be recorded before acceptance.

**D04/T04 bounded continuation authorization — 20 September 2026:** after the first
gate returned D.unresolved, the user approved exactly the additional retained
sentence [2155,2338) under the [gate policy](t04-live-gate.md). At most five further
Jev calls are allowed (seven calls/USD 0.07 session ceiling), one local Qwen F call,
60-second timeouts, concurrency one and zero retries. All extraction rules remain
unchanged; the original result is preserved and a distinct run/index is required.
This additional gate also returned B=factual and D=unresolved, stopping before F/H.
Four Jev calls total were used; no accepted Claim exists and no further gate is authorized.

**D05/D06 T07 selected — 20 September 2026:** authorized by the user's final
T07 implementation decisions. Dense retrieval uses local SentenceTransformers with
`microsoft/harrier-oss-v1-0.6b` revision
`f9b9dc8d367d443f2479d27aa5d8d2850c0774ee`, 1024 dimensions, no Ollama.
The fixed query instruction is “Given a German health claim, retrieve passages
relevant to evaluating the claim.” The versioned representation uses
`Instruct: {instruction}\nQuery: {Claim.normalized_claim}`. Dense documents prepend
saved heading ancestry (newline-separated, then a blank line) to exact passage text.
One T06 Passage remains one retrieval unit and authoritative evidence. Tokenize
all complete inputs before embedding, including special tokens; reject overflow
beyond 32768 tokens with the passage ID. No silent truncation or sub-passage chunks.

Lexical retrieval uses **bm25s directly**, exact original claim span against exact
passage text, German blank-spaCy tokenization, NFC/lower, no stemming or stopwords,
protected numbers/units/negations, Lucene BM25 k1=1.2 and b=0.75. Paths independently
retain top 50, ties use passage ID; equal-weight RRF c=60 retains the full union
and both paths' ranks/scores. Saved context is target plus eligible immediate
same-section neighbors. T07 owns T11A artifacts, traces, failure and completion
records; T11B owns StepAttempt/restart orchestration. Load/replay never downloads
or invokes models. Shared wire contracts are unchanged. Exact software pins and
configuration live in the lockfile and
[retrieval README](../src/binfocheck/retrieval/README.md).
Real-model acceptance is separate from synthetic offline tests. The subsequent
user instruction authorized provisioning this exact snapshot and locked software
for local acceptance, with no paid provider calls. Inference uses exact tokenizer
features through SentenceTransformers forward/pooling because its text wrapper
strips saved outer whitespace; `encoding=exact-tokenizer-forward/1` participates
in private index/query identity. The model, representations and retrieval policy
remain unchanged.

T07 offline and real-model acceptance passed on the saved five-page corpus.
See the [durable T07 handoff](t07-handoff.md) for detailed integration evidence,
artifact identities and limitations; this is not a retrieval-quality benchmark.

**D07 T04 portion selected — 19 September 2026:** authorized by the user's approval
of the revised T04 plan and subsequent offline implementation instruction. Scope is
extraction only; T05 mapping and T08/T09/T10 rubrics/categories are untouched.
Configuration/policy are under `src/binfocheck/claims/`; exact resource bytes are
pinned by `prompts/extraction/v1/manifest.json` (SHA-256
`f6b0fc9d2acdd1e96392e29830d57aa96f15c5afd827fd58ba755fbe1d91e281`).
The effective `t04-claim-extraction/1` configuration hashes the resource bundle,
policy, adapter configurations and mechanical versions. Shared wire schema 1,
validation 1.1, T02 and T03 remain unchanged.

Selection uses factual/nonfactual/mixed/uncertain; ambiguity uses
clear/resolvable_from_context/unresolved. Faithfulness, atomicity and self-containment
are three independent Jev decisions; all must be positive, with complete untied
probabilities. No confidence threshold or calibration claim. Generation rewrites
mixed content, clarifies supplied references and proposes atomic German claims only.
Each stage receives minimal inputs; B/C have no question or default neighbors.
Question use is referential only and recorded per call. A frozen conservative cue
rule selects stored antecedent context; uncertainty remains auditable.

Code locates unique exact original support and forms the smallest contiguous envelope
of required fragments without padding to groups or stripping qualifiers. Faithfulness
also assesses semantic sufficiency/minimality; code alone cannot prove it. Multiple
claims may share a span. Exact T03 preparation stays in `claims/integration.py`;
model evidence is retrieved by PreparedRequest.record_id, never scanning records.
T11A stores immutable states, decisions, original/output lineage and complete target
accounting. Boundary success means durable complete accounting even when every target
has failed issues and zero claims. Persistence/preflight/incomplete accounting fails.

The theoretical offline hard bounds are <=20 groups, <=4 candidates/group, <=280
decision and <=60 generation operations (340 total). This is not expected live usage,
a live budget recommendation or authorization. Effective run request/cost limits
also apply, with conservative per-call reservation, zero retries, concurrency one
and <=60-second T03 timeout targets; the recorded extraction profile uses <=16384
request bytes and <=512 generation output tokens. Immutable T11A allowance slots keyed
by run and bound to exact prepared operations enforce caps across extraction scopes;
local replay reuses those reservations. Slots assume one synchronous owner per run
and do not represent actual usage or T11B worker coordination. Uncertain dispatch
stops further model calls. Later live acceptance must derive a much tighter exact bound
from a prepared saved answer/stages and obtain request-bound authorization. Generation live
access remains blocked; no live calls are authorized. See the
[component README](../src/binfocheck/claims/README.md) for tests and limitations.

**D04 implementation resolved — 19 September 2026:** authorized by the user's T03
implementation instruction approving the planning handoff with two corrections:
semantic generated output is canonical validated JSON, and outputs never enter input
lineage. TypeSafe AI uses direct synchronous HTTPS POST
`https://api.typesafe.ai/v1/systemone`, model `jev-1.13.0`, `TYPESAFE_API_KEY`.
Generation uses direct OpenAI POST `https://api.openai.com/v1/responses`, snapshot
`gpt-4.1-mini-2025-04-14`, `OPENAI_API_KEY`, strict JSON Schema Structured Outputs.
No SDK, fallback, redirects or automatic retries. Configuration is
`t03-model-adapters/1` in `src/binfocheck/models/config.py`; preparation, normalization
and receipt versions are 1. Runtime jsonschema is locked at 4.26.0 in `uv.lock`.

Adapters resolve explicit `state_artifact_id` and caller-owned versioned resources;
no business prompts/rubrics are supplied. Validate Jev choice coverage/sum (absolute
tolerance 1e-6), returned identities and generation output without repair/coercion.
Unsupported output schemas fail before dispatch. OpenAI has no tools/conversation,
uses standard tier, temperature 0, maximum output 512, streaming/background disabled
and `store=false`. The bounded default request is at most 4096 UTF-8 bytes.

T11A stores immutable prepared/outbound/raw/structured/receipt artifacts with
deterministic work/record/role IDs. `GenerationResult.output_artifact_id` references
canonical validated JSON; the restricted raw response is separate and both are
linked by the deterministic receipt. Input fields remain actual inputs. Failed
DecisionRecords are persisted separately from failed Outcomes. Usage missing from
providers stays unknown; estimates are distinct from unreported billed cost.

Transport policy supports one request, zero retries, concurrency one and a 60-second
deadline target with decreasing socket timeouts; DNS/internal blocking operations
are not a hard process deadline. Abandoned intents/uncertain dispatch never resend.
Single-owner execution is required; T11A has no atomic multi-worker dispatch lease.
Full configuration, schema subset, recovery limits and source references are in the
[adapter README](../src/binfocheck/models/README.md) and [T03 handoff](t03-handoff.md).
No domain wire-schema change or D07 business decision is authorized by this entry.

**D04 live status — 19 September 2026:** the user authorized exactly the frozen
Jev smoke request, USD 0.01 ceiling, zero retries, concurrency one, 60-second timeout,
and explicitly skipped OpenAI. One Jev request passed (HTTP 200, exact returned
`jev-1.13.0`, complete choice probabilities); restricted raw/receipt persistence,
reopen, link validation and network-disabled replay passed. Reported usage was
331 input / 33 output tokens; billed cost is unknown, estimated USD 0.000013902.
Published pricing and a conservative full-context cost bound were verified before
dispatch. This single-request authorization is consumed; no repeat is authorized.
OpenAI live is **blocked — credentials unavailable (no API access)**; no OpenAI
request was made. Offline checks passed; **T03 overall: integration partially
blocked**, not fully live-accepted. OpenAI remains an explicit outstanding
integration dependency. See [live acceptance details](t03-handoff.md#jev-live-acceptance--19-september-2026).
No merge is authorized by this status entry; PR #6 remains draft.

**D06 T02 portion resolved — 19 September 2026:** user explicitly selected
`spacy==3.8.16`, `spacy.blank("de")` and rule-based Sentencizer, without a downloaded
language model, parser, NER, transformer or GPU pipeline. Configuration and the small
German abbreviation/decimal/protected-Markdown rule layer are versioned as
`t02-text-index/1` under `src/binfocheck/text/`; dependencies are pinned in `uv.lock`.
The bounded structure scanner preserves original offsets and opaque unsupported
blocks. Context uses explicit completion cohorts and reference-only windows
(`t02-text-context/1`). See [T02 handoff](t02-handoff.md). This resolves answer
indexing only; corpus parsing, passages, lexical retrieval, BM25 and RRF parameters
remain open for T06/T07.

**D06 T06 offline portion resolved — 19 September 2026:** the user's T06
implementation instruction approves Beautiful Soup with explicit html5lib, core-only
LlamaIndex ingestion, stdlib direct HTTPS and no embeddings/LLM/retrieval. Resolved
compatible pins: `beautifulsoup4==4.15.0`, `html5lib==1.1`,
`llama-index-core==0.14.24`; exact dependencies in `pyproject.toml`/`uv.lock`.
Configuration and versions live in `src/binfocheck/corpus/config.py`: hashed
`t06-corpus-parser/1`, `t06-corpus-passages/1`, `t06-corpus-fetch/1`, and
`t06-corpus-settings/1`. Article raw artifact/hash mean the same complete HTTP
content-decoded HTML bytes before charset decoding; encoded/partial bytes remain
separate receipt artifacts. Structure/completion companions reuse shared spans and
T11A artifacts; wire schema 1 is unchanged. Natural paragraph/list passages retain
exact cleaned-text offsets; replay is immutable and model-free. The bounded
structural profile is synthetic-tested, not verified against live diabinfo HTML.
The six-request public-fetch configuration is frozen for later authorization;
**no diabinfo or robots requests are authorized by this offline instruction**.
The subsequent pre-live review requires a `LiveAuthorization.policy_sha256` binding
under `t06-live-authorization/1`: canonical SHA-256 over the robots URL, ordered
five-page URLs and complete FetchPolicy. Validate before capture-start writes and
every HTTPS dispatch; a changed policy requires a newly recorded approval digest.
The auditability follow-up persists the validated envelope as restricted immutable
`<batch-id>.authorization.v1` before the capture-start marker and any dispatch.
It records batch ID, approval reference, digest, robots URL, ordered URLs and full
policy. CaptureStart links the artifact; completion includes it as a dependency.
Replay/load require and validate this evidence for live batches against the frozen
policy. Synthetic batches carry no authorization. No shared domain schema changes;
CaptureStart gains an optional companion link (required for live captures).
**D06 live-capture gate — 19 September 2026:** the subsequent user authorization
for digest `78de13b54502cf2c8395d9be1301f66c74bbe0d8b8cf5a931f58e71c1aad5d18`
was consumed by one six-GET batch, all HTTP 200. Raw bodies and approval evidence
are saved in T11A. Default replay records five unusable pages: no `article` roots.
A bounded site profile and full cleaned-content inspection remain offline work;
no additional GET is authorized. See [capture report](t06-live-capture.md).
**D06 offline site-profile follow-up:** four explicit title/credit/intro/article roots
and shape-validated exclusions now implement the saved TYPO3 pilot layout.
`diabinfo-pilot/2` uses `t06-corpus-parser/3` and keeps original parser-1 identities
unchanged; the rejected diagnostic profile-1/parser-2 remains replayable history.
FAQ questions use level 3 beneath topic headings; callout/question ancestry ends at
its DOM boundary. Exact source wording and links remain; no broad fallback exists.
That saved-batch replay has four usable articles and 201 passages, but Ramadan
is unusable (`unsupported_informational_media`): an informational SVG is referenced
but its contents were not captured. Acceptance remains blocked, not merge-ready.
The initial diagnostic ready corpus is explicitly rejected in restricted inspection
evidence. Durable private store and exact versions/IDs are in the updated handoff.
No further network call, shared-schema change or T07 work was introduced.
**D06 media-hardening follow-up:** `diabinfo-pilot/3` / `t06-corpus-parser/4`
replaces the copyright/negative-alt heuristic with 16 positive, per-page subtree
signatures in `decorative_media_v1.json` (registry digest participates in identity).
Every unknown/changed media signature fails closed; parser versions 1–3 remain
identity-stable replay history. Saved-batch replay retains four usable pages and
201 unchanged-text passages; Ramadan remains blocked. A separate fixed one-SVG
T11A companion is prepared with an independently bound authorization envelope,
restricted pre-dispatch evidence and one persistent intent. It cannot reuse the
consumed six-GET authorization. Exact proposal and inert XML/provenance procedure
and result are in
[capture report](t06-live-capture.md#one-svg-companion-policy-and-consumed-authorization).
The user subsequently authorized the exact proposal once. One HTTP-200 SVG response
was preserved with its bound authorization and receipts. Offline XML inspection found
no machine-readable text/title/description/accessibility wording, so no asset text or
parser-5 result was manufactured. The single allowance is consumed; the remaining
gate is an explicit product decision on textual-corpus acceptance for the captured
informational visual. No T00 schema change or merge is implied. T06 remains
code_hardening_passed / live_acceptance_blocked at that historical gate.

**D06 final textual-corpus decision — 19 September 2026:** the user explicitly
approved that usable means **all deterministically extractable textual evidence is
represented; captured non-text informational visuals remain explicit audited
limitations**. This permits neither decorative reclassification nor OCR, image
interpretation, SVG path inference or fabricated wording. `diabinfo-pilot/4` /
`t06-corpus-parser/5` implements only the exact saved Ramadan visual case.
Before any derived article writes, replay verifies pinned restricted parent HTML,
batch/authorization/start/receipts, SVG bytes and inspection evidence. The complete
asset chain must validate and the pinned inspection must report
`no_deterministic_text_extractable` with no text/accessibility wording. The frozen
policy and evidence identities participate in the parser hash, preventing an
evidence-dependent failure from publishing a conflicting ArticleVersion.
The restricted `<article-id>.media-evidence.v1` records
`captured_nontext_informational`, exact HTML gallery locator, article/parent/SVG/
inspection links and the visual limitation. Completion requires the companion and
all pinned evidence; loading validates them again and fails closed on missing,
corrupt or mismatched evidence. Unknown media still fails closed under the exact
positive signatures. Parsers 1–4, rejected diagnostics and original captures are
unchanged immutable history; the prior inspection's blocked decision is historical.
Offline replay from parser-4 predecessors yields five usable articles, 228 passages
and a ready manifest, with unchanged text/passages for the four unaffected pages.
Socket-blocked close/reopen replay passed. No new network call, dependency, shared
schema, T07 work or merge is introduced.
See [corpus README](../src/binfocheck/corpus/README.md) and
[T06 final handoff](t06-handoff.md). T07 lexical/BM25/RRF choices were still open
at this handoff; they are now selected in the T07 D05/D06 entry above. T02's
recorded decision is unchanged.

**D03 live authorization — 19 September 2026:** user explicitly authorized exactly one
DataForSEO Google AI Mode Live Advanced request for the query
`Darf ich mit Diabetes Auto fahren?` with `location_name="Germany"`,
`language_code="de"`, `device="desktop"`, `os="windows"`,
`calculate_rectangles=false`, timeout 60 seconds, request limit 1, retry limit 0,
and an absolute cost ceiling of USD 0.01. Credentials are supplied locally through
the ignored `.env`/process environment and must never be committed or printed. Before
dispatch, verify the current endpoint price and current German-language support from
the provider documentation. If the current price exceeds USD 0.01, credentials fail,
settings are unsupported, or preflight checks fail, stop without making a request.
Any second provider request, including a retry after an uncertain outcome, requires
fresh explicit user authorization.

**D03 live result — 19 September 2026:** current official endpoint, German listing
and USD 0.004 Live price were verified before dispatch. The exact authorized query
succeeded with one POST and zero retries; envelope/task costs both USD 0.004 and
budget verified. SQLite reopen, exact-answer replay with network blocked, and linked
validation passed. Provider task ID: `09190700-2568-0139-0000-71062a999c01`.
See [T01 handoff](t01-handoff.md) for official URLs, artifact IDs, checks and limits.
This consumes the one-call authorization; it does not authorize further calls.

**D01 resolved — 18 September 2026:** Python 3.13, uv, Pydantic v2, pytest, Ruff
and Pyright. Authorized by the user's explicit T00 approval in this branch.
Configuration: `pyproject.toml`, `.python-version`; exact dependencies: `uv.lock`.
Affects T00 and consumers of its shared contracts. Development-only jsonschema
and typing stubs support schema checks. Generated exports live in `schemas/v1/`
as directed in the same approval; Python models remain in `src/binfocheck/domain/`.

**T00 contract validation revision 1.1 — 18 September 2026:** authorized by the
user's pre-merge contract review. Recorded in `domain/common.py` as
`CONTRACT_VALIDATION_VERSION`; v1 wire fields/paths remain unchanged. Affects T00
and its future contract consumers. Linked validation now requires captured citation
membership, actual citation kinds for positive associations, complete capture for
definite absence, nonblank successful answers, and acyclic text/artifact lineage.
An observed positive citation may survive incomplete capture; absence may not.
`TextRecord.artifact_id` identifies the artifact backing that representation.
Article raw text directly references its raw artifact and is not a transformation;
distinct cleaned text must descend from that raw text through versioned
transformations. Identical raw/cleaned text IDs are allowed. Answer lineage must
terminate at text backed by the capture artifact. Validation resolves references;
it does not parse artifacts or verify their bytes against text. The [TypeSafe choice API][2]
explicitly defines a distribution summing to one: complete available probabilities
must sum to 1 within absolute tolerance `1e-6`, without renormalization. Incomplete
and unavailable data retain their meanings; incomplete distributions are not
required to sum to one. D04 integration verification remains with T03. This is
structural validation, not a calibration or provenance-probability claim.

**D02 resolved — 19 September 2026:** T11A uses SQLite for persistent typed-record
metadata/indexing and a content-addressed local filesystem for artifact bytes. Keep
both behind the T00 storage protocols so later deployment may replace them without
changing domain contracts. Use the Python standard library (`sqlite3`, `pathlib`) unless
T11A demonstrates a concrete need for another dependency. One configured store root
contains the SQLite database and artifact directory. Record writes are immutable by
ID: byte-for-byte/logically identical retries are idempotent; different serialized
content under the same ID is a conflict. Artifact writes verify the declared SHA-256,
write atomically, and never trust an unrestricted user path. Store artifacts by
content hash and keep their logical `storage_key` as metadata rather than using it as
an arbitrary filesystem path. Decisions and reviews remain append-only records. Use
bounded deterministic listing with opaque cursors. Add a small schema-version/migration
mechanism sufficient for T11A, not an ORM or deployment service. PostgreSQL/object
storage remain future substitutions if D09 deployment or concurrency requirements
justify them.

Live calls also follow [AGENTS.md](../AGENTS.md#safety-and-live-calls). Never count an
undisclosed substitute as live acceptance.

## 9. Engineering handoff and verification

Use the [task cards and handoff](implementation-plan.md). Shared-contract changes must
be authorized and recorded under Section 8, versioned, and tested against affected
consumers. Report offline, live and deployed checks separately: mocks do not prove
compatibility, and live calls do not prove accuracy. Error tests cannot replace
usable captures or a ready corpus.

Basic tests are required; systematic comparisons/calibration remain
[beyond MVP](beyond-mvp.md). This document supplies no implementation or test results.

## 10. Implementation references

Official references for the selected tools; verify actual versions at integration.
They describe capabilities, not BinfoCheck quality.

[1]: https://docs.dataforseo.com/v3/serp/google/ai_mode/live/advanced/ "DataForSEO Google AI Mode"
[2]: https://docs.typesafe.ai/api "TypeSafe decisions and probabilities"
[3]: https://www.microsoft.com/en-us/research/blog/claimify-extracting-high-quality-claims-from-language-model-outputs/ "Microsoft Research: Claimify"
[4]: https://developers.llamaindex.ai/python/framework/module_guides/loading/ingestion_pipeline/ "LlamaIndex ingestion"
[5]: https://spacy.io/api/sentencizer "spaCy Sentencizer"
[6]: https://developers.llamaindex.ai/python/framework-api-reference/retrievers/bm25/ "LlamaIndex BM25Retriever"
[7]: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String "MDN: JavaScript strings"
