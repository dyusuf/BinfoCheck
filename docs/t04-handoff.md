# T04 handoff — Claimify-inspired ClaimExtractor

Task / assignee / status: T04 / Codex / offline implementation and verification
complete. Live integration blocked; not fully accepted.
Branch: `codex/t04-claim-extraction`, worktree `/mnt/workspace/BinfoCheck-t04`, starting
HEAD `80b35c95daaf06bfe9149551068d609e39d4ab58`. No branch switch or merge.

## Authorization and scope

The user approved the revised planning handoff, required T03 preparation to remain
in a composition layer, then instructed implementation under the proposed offline
implementation/tests/commit/push/draft-PR authorization. Live calls remain explicitly
unauthorized. No shared contracts, T03, T02, T11A, dependencies or downstream features
were modified. T05/T08/T09/T10 D07 portions remain open.

The four review revisions are implemented: minimal stage-specific model states;
boundary success based on complete durable audit accounting; exact prepared T03
record identity without scans; and smallest defensible contiguous original support.
There is no shared Claim/ExtractionIssue contract blocker.

## Files, versions and decisions

- `src/binfocheck/claims/`: extractor/state transitions, strict settings, T02 preflight,
  source location, policy, resource loading, T11A persistence/audit envelopes and errors.
- `claims/stages.py`: provider-independent execution port and minimal state selection.
  `claims/integration.py` alone imports T03 configuration/preparation/receipt machinery
  and invokes the shared DecisionModel/GenerationModel interfaces. It creates no live
  transport and loads no credentials.
- `prompts/extraction/v1/`: three German instructions and structured output schemas;
  manifest pins exact bytes of all 11 prompt/schema/rubric resources.
- `rubrics/extraction/v1/`: selection, ambiguity, faithfulness, atomicity and
  self-containment rubrics. Their decisions remain independent.
- `tests/claims/`: synthetic scripted interface tests, real T03 adapters with synthetic
  transports, preflight/failure/recovery, exact payload, minimal span and scope tests.
- `tests/fixtures/claims/v1/spans.json`: explicit German Unicode/emoji/combining-mark
  and multi-sentence offsets. Fixture origin and resource READMEs included.
- `docs/architecture.md`: extraction-only D07 selection; `implementation-plan.md`:
  T04 status; this handoff. No other task ownership expanded.

Domain schema `1`, validation `1.1`, T02 index/context `1`, T03 adapter/receipt `1`,
T11A storage/codec `1` remain unchanged. T04 settings/configuration, resource bundle,
policy and artifact envelopes start at version `1`. Exact effective configuration
hash includes resource/policy versions, both adapter configurations and mechanical
versions. Resource manifest SHA-256:
`f6b0fc9d2acdd1e96392e29830d57aa96f15c5afd827fd58ba755fbe1d91e281`.
Selected existing models are `jev-1.13.0` and `gpt-4.1-mini-2025-04-14`, with no fallback.

D07 authorization is the approved T04 plan and subsequent implementation instruction.
The frozen labels, tie policy, generation schemas, stage limits and failure semantics
are recorded in Architecture Section 8 and the component README. No rubric threshold,
evidence-category change or model-quality claim is introduced.

## Behavior and evidence

Preflight checks the correct RunManifest/configuration/resources, observation membership,
CaptureRequest and answer lineage, complete T02 manifest payload, all cohort unit hashes,
relationships, exact code-point spans and exact reconstructed ContextResult. Corrupt,
incomplete or cross-run context fails before model operations. The complete graph is
resolved by explicit IDs using shared linked validation, never record scanning.

Selection/mixed rewriting receive source only. Ambiguity/clarification use relevant
stored reference context selected by the frozen conservative cue rule. Question use
is exceptional/reference-only and recorded exactly. Decomposition consumes original
provenance, derived wording and relevant bindings; it does not receive the question
by default. H states contain the candidate and authoritative minimal span, with only
property-relevant context. Every exact state is saved and bound by T03 preparation.

Code locates exact unique original fragments and forms their minimal contiguous
envelope. It retains required qualifiers and repeated-location evidence. The model
proposes which support is necessary; independent faithfulness validates sufficiency
and minimality against original context. Code does not prove semantic minimality,
medical truth or extraction accuracy. Several claims may share one source span;
multiple sentences are allowed when needed. No whole-group fallback or first-match
quote attribution exists.

All three H decisions must be independently positive with untied complete probabilities.
Uncertainty, exclusion, invalidity and failures remain separate ExtractionIssues.
Model decisions retain exact evidence IDs, versions and T03-reported timing/usage.
Current-call outputs/receipts never become source inputs. Consumed prior generated
content is explicitly derived evidence, not original answer text.

Before every model invocation, the composition calls existing T03 prepare offline,
saves the exact PreparedRequest record/work/outbound identity, and checks returned or
failed persisted evidence by that exact record ID. No pagination, latest-decision
query, task_type uniqueness assumption or duplicated T03 hash algorithm is used.
A failed operation without a saved record retains its typed failure without inventing
an ID. Storage errors are not missing data. Uncertain-dispatch receipt flags stop
further operations even when the provider error name does not say 'uncertain'.

The final artifact embeds the unchanged ExtractionResult and target accounting.
Records are immutable by deterministic ID; created_at uses the original run timestamp.
Completion payload is published last. Reinvocation reconstructs the identical result
from saved stage evidence without repeat transport calls. A receipt-survived T03 record
write failure can finish on local retry. Failed persistence does not publish success.

Immutable T11A reservation slots enforce aggregate request/cost caps across separate
extraction scopes in the same run. Each slot binds the exact prepared operation;
replay reuses it. Failed/uncertain calls retain their conservative reservation.
Slots are not actual usage, worker leases or concurrency control. This synchronous
component requires a single owner per run. Invocation allowance is checked for all
three H properties before validation; the remaining run-wide cap is enforced at each
dispatch and exhaustion can only yield failed issues, never an accepted claim.

A successful Outcome means complete durable audit accounting. Zero claims with only
failed issues may succeed as `all_targets_failed`; uncertainty/exclusions are not model
failures. Partial failures are explicit. Invalid inputs, corrupt required evidence,
global write failure or unaccounted target scope fail the boundary. Success is not an
assertion that factual content was found or that models succeeded.

## Checks and results

Commands actually run:

- `git fetch origin`, `git status`, `git pull --ff-only origin codex/t04-claim-extraction`
  in order: passed, clean branch, already up to date. Fetch/pull used approved access
  to linked-worktree metadata outside the writable sandbox.
- `uv sync --locked --dev`: passed; existing locked dependencies, no lockfile change.
- `.venv/bin/pytest tests/claims -q`: 63 passed after final budget changes.
- `uv run --offline --locked pytest`: **650 passed in 111.79s**.
- `uv run --offline --locked ruff check .`: passed.
- `uv run --offline --locked ruff format --check .`: passed, 142 files formatted.
- `uv run --offline --locked pyright`: zero errors/warnings.
- `uv run --offline --locked python -m binfocheck.domain.export_schemas --check`:
  schemas match the Python types.
- `git diff --check` and `git diff --cached --check`: passed. Staged scope review
  found no shared-contract/upstream/dependency changes or secrets.
- Development iterations ran targeted tests and formatting/lint fixes. Two manually
  specified fixture end offsets were corrected against literal Unicode source text;
  the required source-slice checks were preserved. No shared test was weakened.

All tests execute under the repository's global network-denial fixture. Acceptance
covers factual/nonfactual/mixed text, shared-span multi-fact and multi-sentence claims,
resolvable/unresolved references, question-premise rejection, qualifiers, invented and
repeated quotes, Unicode offsets, independent uncertainty/rejection, malformed/failed
Jev and generation responses, exact prepared IDs with/without failed records, wrong-ID
rejection, all-target failure success, missing target failure, partial failures, stage
budgets, preflight corruption, source/metadata lineage, SQLite reopen, write failures,
idempotent retries and uncertain-dispatch stopping. Core provider-import and no-evidence-
scan tests enforce the composition boundary. Real T03 adapter tests still use synthetic
transports: they establish wiring, not live access or extraction performance.

## Integration, limits and next dependency

Offline: implementation/tests completed; results above.
Live: BLOCKED / not run. Generation credentials/API access remain unavailable, its
T03 smoke was explicitly skipped, and no new live authorization exists. T03's prior
Jev smoke does not authorize another call. T04 task-card live check remains outstanding.
Deployed: not applicable / not run. T04 is not fully accepted and the MVP is not complete.

Artifact origins: synthetic fixture text and model responses only; no private capture
was copied/opened for this assignment and no fresh live artifact was created.
Actual provider/model requests: **0**. Actual provider/model cost: **USD 0**. Synthetic
usage in tests is not actual usage. Git/dependency operations are separate from model use.

The 340-operation value is only a theoretical offline configuration maximum. It is
neither expected live use, a recommended live acceptance budget nor standing approval.
Later acceptance needs a retained T01 answer, same-run T02 indexing, available generation
access, and a much tighter exact bound derived from prepared stages with explicit
request/cost authorization. Adaptive stages require their exact T03 request hashes.
No substitute provider, new capture, automatic retry, extra web fetch or benchmark.

Limitations: conservative deterministic referent-context selection can leave cases
unresolved; exact locations do not establish semantic support. T03's 512-token output
cap and bounded request bytes can produce explicit failed/incomplete extraction.
T11A has no cross-record transaction/worker lease or power-loss guarantee. Single-owner
local replay is supported; T11B orchestration, API/UI, citation mapping and retrieval
remain outside this task.
