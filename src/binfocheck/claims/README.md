# T04 ClaimExtractor

`StoredClaimExtractor(records, artifacts, models).extract_claims(request)` implements
the unchanged T00 boundary. `records`/`artifacts` are T11A stores; `models` implements
the local `StageModels` composition port. `T03Models` in `integration.py` composes
injected shared `DecisionModel`/`GenerationModel` interfaces with existing offline
T03 preparation. Only that module imports provider-specific adapter facilities.
It does not instantiate a transport, load credentials or grant live authorization.

Load `ExtractionResources(repository_root)` from a trusted checkout containing
`prompts/extraction/v1/manifest.json`. Supply the SAME immutable adapter configs and
resource registry to T03 adapters and `T03Models`; the run must pin the composition's
`configuration`, `prompts`, `rubrics` and model IDs. Use request bytes <=16384, output
<=512 tokens, retries zero and concurrency one as recorded under D07. No dependency,
shared contract or T03 change is required.

Create a diagnostic/reanalysis RunManifest first, then index the saved original in
that same run with T02. `ExtractionSettings` names the complete T02 index, 1–20 ordered
target IDs, exact ContextSettings recipe, resource/policy refs and bounds. Build the
supplied ContextResult through T02. `settings.envelope(models.configuration)` supplies
the ExtractionRequest settings. Whole paragraphs, bullets, sentences and opaque units
are supported; adjacent targeted sibling sentences are grouped. Sentences are not claims.

Preflight revalidates the entire T02 cohort, its completion payload/hashes/order/graph,
all source spans, run/observation/context membership, run/resource configuration and
reachable linked records/artifact bytes. Missing, corrupt or cross-run data fails
before any model operation. Running/succeeded runs are eligible; manifests are never
rewritten. The complete context is available locally; this does not mean it is sent.

A–I follows selection → optional mixed rewriting → ambiguity → optional clarification
→ decomposition → deterministic source location → three independent validation calls
→ assembly. B/C send source only. D/E use a frozen conservative reference-cue rule
and at most the nearest same-heading antecedent or heading. Question is sent only
for a leading unresolved pronoun with no supplied answer antecedent. F sends original
provenance, changed working text and consumed clarification bindings. H sends the
candidate and minimal span; faithfulness adds governing boundary-sentence/heading
context when needed. Question is included only for consumed question-based bindings.
This mechanical selector is deliberately limited; unresolved cases are not negative
factual judgments. No extra model selector, retrieval or context expansion occurs.

Generation is always secondary to original source. Candidate anchors and additional
required support locate unique exact original substrings or explicit code-point
offsets. Code forms the smallest contiguous envelope of located fragments; it does
not pad to a paragraph, normalize text or guess the first repeated match. Semantic
sufficiency/minimality is independently assessed by faithfulness. Code cannot prove
which words are semantically indispensable. Necessary qualifications must remain in
both claim wording and its support. Several claims may share a minimal span; genuinely
multi-sentence assertions may cross units. Noncontiguous Claim spans are not supported.

All three validation decisions must be independently positive with untied complete
probabilities. Rejections, uncertainty, malformed results and unavailable operations
remain separate issues. A mixed rewrite with unlocated exclusions records uncertainty
rather than silently dropping it. Original question premises cannot supply new facts.

## Audit and recovery

Before a model operation, integration saves the exact minimal state, calls existing
T03 `prepare`, and saves its exact record ID/work key/outbound hash. Successful and
failed records are verified only by that exact ID. No evidence scan, latest-record
query or duplicate T03 hash algorithm exists. Missing failed records retain their
actual typed failure without a fabricated decision ID. A storage read error is not
not_found. T03 owns its raw/structured/receipt evidence and original timing/usage.

T04 saves reference-only preparation, exact per-call selection/state, preparation
binding, stage evidence, location result and a final audit through T11A. Current-call
outputs/receipts never enter source inputs. Consumed prior output is linked as derived
evidence, never original source. Claim/issue decision_ids retain the actual decisions.
Records use run creation time and deterministic SHA-256 IDs. The work key includes
immutable inputs, T02 cohort, settings, versions, resources and effective adapter config.

The final audit embeds the shared ExtractionResult and a validated target-accounting
table. Assembly/final-audit version 2 records explicit issue target scopes separately
from context lineage. Group-terminal issues cover the group; located candidate issues
and claims cover only overlapping targets. Unlocated candidate issues cover no target.
Any otherwise unrepresented target gets its own `target_not_represented` issue.
The assembly version participates in the configuration hash, so corrected outputs
cannot overwrite earlier audits; prior manifests require a newly configured run.
Every requested target must have terminal claims/issues. After graph validation,
write the final artifact, output records and completion payload LAST. No complete
marker is published for incomplete accounting. Individual writes are immutable and
idempotent, not a multi-record transaction. Reinvocation reconstructs the same audit
from saved stage evidence; T03 can finish a saved receipt after a record-write failure
without another transport call. Corrupt/missing required evidence never triggers a
blind paid retry. This is single-owner synchronous execution, not worker/restart
orchestration, a multi-process lease or an exactly-once billing guarantee.

Boundary success means COMPLETE DURABLE AUDIT, not successful models or nonempty claims.
Audit states are `complete`, `partial_failure`, `all_targets_failed`; all can have a
successful Outcome. All-model-failed results may contain only failed issues. Invalid
preflight, persistence failure or unaccounted scope returns failed(value=null).
Model failures never become negative factual evidence. The consumer must read issues.

Stage logical bounds are 2+3C decisions and <=3 generations per group (C<=4). The
340-call configuration limit is ONLY a theoretical offline bound, not expected live
usage, recommended live acceptance budget or standing authorization. Effective run
request/cost caps also apply; reserve the adapter's conservative per-call allowance,
including uncertain outcomes. Check the invocation allowance for all three H calls
before validation. Immutable run-wide reservation slots also enforce the aggregate
cap across distinct extraction scopes; each dispatch requires its exact prepared
operation's slot. Exhaustion during H leaves failed issues and cannot accept a claim.
Slots assume one synchronous owner per run, retain uncertain/failed reservations,
and are conservative allowances rather than actual usage reports.
The integration stores exact T03 intents/receipts; no automatic retry or fallback.

## Verification and outstanding integration

Run `uv run --offline --locked pytest tests/claims` and the repository-wide documented
checks. Tests deny network and use synthetic answers/model outputs; both T11A backends
and real T03 adapters with offline transports are exercised. Test outcomes establish
wiring, invariants and audit behavior, not German extraction accuracy.

OpenAI GenerationModel live access is still unavailable and its T03 smoke was skipped.
T04 live acceptance is BLOCKED, not bypassed by doubles or another vendor. Later use
must prepare one retained saved answer and derive a much tighter exact stage/request
bound with explicit cost/request approval. Each adaptive request requires its exact
T03 authorization binding. No such authorization is present. No T05/citation mapping,
retrieval, medical truth checking, benchmark, worker, API or UI work is included.

The [bounded live-gate proposal](../../../docs/t04-live-gate.md) freezes one retained
sentence: at most five Jev calls and one OpenAI call, USD 0.06 total using existing
per-call allowances. Initial B/D/F requests are prepared offline; exact H requests
require the actual F output and a later authorization step. This is not permission
to execute, and does not change extraction policy or the configured adapters.
