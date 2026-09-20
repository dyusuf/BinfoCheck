# T04 bounded live-acceptance proposal

Historical frozen proposal prepared offline from retained T01/T02 evidence.
The continuation below supersedes its model/access and approval policy for the current assignment.
The original proposal and private bundle remain unchanged.
This gate is a proposal for one saved target, not a benchmark, medical truth check,
new capture, or permission to spend. The theoretical 340-call bound does not apply.

## Retained evidence and exact scope

The retained T01 store and T02 indexed copy were found at their documented private
locations. Preparation copied the complete quiescent T02 store before opening it
with T11A. Source fingerprints (hashes, mtimes and modes) remained unchanged.

- Observation: `capture-observation-1c8c8d29e92c00f7f5473716291a185cde1a5f21babfe89841b6aa6c9b857179`.
- Answer: `capture-answer-630b1fb95dde23947d0c4df392fdd6897fddcb7701d7ca41f900087159e08119`.
- Answer SHA-256: `e6fc250c93791578463a5cc5fe62858536507c9b40ece6cf20dda5a1e64854ba`.
- Retained T02 run: `t02-verification-5aea204b9001411aadc28de02f88ffcf`.
- Retained index: `text-index-1b247e432d4388c0b58076ba5acc58cf29e7018f25b3191414707fd65dbb7dfc`.
- Retained target: `text-unit-dea9579d7031b11b562649b75b0d1626b75dbca6bb438a3a0ac38c6ef639ad70`.
- Selected scope: the first sentence only, exact Unicode-code-point offsets **[0, 63)**
  in the immutable answer, including original Markdown and qualification. It is the
  shortest affirmative sentence suitable for this basic extraction-path check.

The existing T02 run has a zero model budget and a T02 configuration. It cannot be
rewritten into a T04 run. Offline preparation created a separate diagnostic/reanalysis
run in the private copy, retaining the same observation and answer, and used unchanged
T02 code to index that answer in the new run. Old records were preserved exactly.

- Proposed T04 run: `t04-live-gate-605d1a57b4e43d81496618266a420c21cf3f395b5d66b28e3677fe51b0361e27`.
- Same-run T02 index: `text-index-39e33d7eb6dba168b25452fcd560b72e747c083aaa58aaded6b1875b8eb40dfc`.
- Exact target ID: `text-unit-55704a8a09a35cd93bcf4e3dcdf7aeb595581d176cf873123cc1041dd5e15cb7`.
- ExtractionRequest SHA-256: `2ae69a1314afa661cc3f57f18383ed77a9ece3291855f7384d628610fa0ca7eb`.
- Configuration SHA-256: `57a888727d47b0bd3cf501a401e06a9c759126cafbb8fe0037e1231ded4e57b9`.

The request caps groups/candidates at 1/1, decisions at 5, generations at 1, and all
model operations at 6. Context uses before=0, after=1 and recorded headings. The
neighbor remains stored referential context, not another extraction target. B/D/F
states contain only the selected source; the question and neighbor are not sent.
H uses only the actual candidate, its exact original span and property-needed context
selected by existing T04 code. No wording or claim is preselected as a model result.

## Frozen private proposal

Durable private directory: `/mnt/workspace/BinfoCheck-data/t04-live-gate/`.
The private parent and every bundle directory are mode 0700; all files are mode 0600.
The original `/tmp/binfocheck-t04-live-gate-5cCOzYFR/` remains unchanged.

Preservation verified all 24 files, 10 directories and 293830 file bytes by complete
membership, sizes and SHA-256. The copied SQLite store passed integrity and foreign-key
checks using an immutable read-only connection. The private verification manifests
are beside the bundle at `t04-live-gate-preservation.json` and
`t04-live-gate-revalidation.json`, also mode 0600.

After merging main `579ad7571841394256de5e80d94775ccb3da1492` (T06), offline
reconstruction on a scratch copy reproduced the same observation/answer, target/span,
ExtractionRequest, B/D/F prepared identities/outbound bytes and proposal/policy hashes.
The six-call/USD 0.06 proposal is unchanged. Neither preserved copy was modified.

Frozen policy SHA-256: `648f18cbd76e0f454160104bf6bdfd42627c5a29c9696244bc407411a9d67aa8`.
Proposal SHA-256: `b1779ca46e3d1d29679c1b2c4f755bdd211fa03ae41af07e255df43fddda58cb`.

- `extraction-request.json`, `run.json`: exact proposed inputs.
- `decision-config.json`, `generation-config.json`: existing T03 configuration types.
- `proposal.json`: exact source text/span, lineage, prepared IDs/hashes and bounds.
- `policy.json`: scope, stop conditions, stages and two-step authorization policy.
- `B/D/F.request.json`, `B/D/F.prepared.json`, `B/D/F.outbound.json`: one file per
  stage, with actual T03 PreparedRequest identities and exact canonical outbound bytes.
- `store/`: private T11A copy; retained evidence, new run/index and source-state artifacts.
- `prepare_gate.py`: private offline preparation/recheck script; sockets are blocked
  and preparation stops before any adapter invocation. No credentials are loaded.
  Its original paths are preserved as historical preparation code. Rechecking the
  relocated bundle uses a scratch copy and overrides working paths in memory; never
  run it against the preserved store or silently rewrite the frozen proposal.

No real answer text, raw provider payload, private store or credential is committed.
The durable copy preserves the formerly ephemeral bundle. Missing bundle/evidence
blocks execution; do not recreate it by fetching or by fabricating a model response.

## Conditional stage and cost bound

Expected path: A → B(factual) → D(clear) → F(one candidate) → G(exact location) →
H.faithfulness + H.atomicity + H.self_containment → I.

| Operations | Maximum calls | Existing per-call allowance | Subtotal |
|---|---:|---:|---:|
| Jev B, D and three independent H checks | 5 | USD 0.01 | USD 0.05 |
| OpenAI F decomposition | 1 | USD 0.01 | USD 0.01 |
| Total | **6** | | **USD 0.06** |

This is a configuration-derived maximum allowance, not a token-price estimate or a
provider-enforced dollar cap. Before live authorization, verify the upper cost of
each exact request against the T03 authorization requirements. Missing pricing/token
evidence blocks that request. Actual usage/cost may be lower or unreported; preserve
that distinction in DecisionRecords/receipts. No pricing/web request was made here.

Both adapters retain request_limit=1, retries=0, concurrency=1, timeout=60 seconds,
max_request_bytes=16384, max_response_bytes=2097152. Generation output is capped at
512 tokens. Models remain Jev `jev-1.13.0` and OpenAI Responses
`gpt-4.1-mini-2025-04-14`; only existing T03 adapters may execute.

Frozen initial requests (D/F are conditional on actual preceding decisions):

| Stage | T03 work key | Outbound SHA-256 | Bytes |
|---|---|---|---:|
| B | `2f0bca403863d87f769b7a4ab069cb5826297ed9523ced421d93131450c213ef` | `257f6931e11d254fe0ca336a61fcff64a1990b840cd090f49256c373f1206525` | 1143 |
| D | `edb5a0202c2d9cffd9dd6d5ec7ff03e103aa9d464c7c05578d4fb1ecdfeb5dca` | `40da1ec740e8696882f2a34c3efb8577a068cca349409880845ce44b6675b7ff` | 1057 |
| F | `23ecdd37475b8cc404f74694825788e03f79ad10f694cac1b588853933ae9f45` | `66939ec2a6b33e7bf11018bc253ce866f0d20686c9e288efd0c9b4452334fe84` | 3627 |

## Later execution policy — still unauthorized

1. Verify bundle hashes, retained lineage, configuration and generation access before
   requesting approval or spending on Jev. Credentials alone are never authorization.
2. Obtain exact T03 LiveAuthorization bindings for B, conditional D and conditional F:
   at most 3 calls / USD 0.03. Execute individually through existing adapters, persisting
   the real DecisionRecords and receipts. Allow D only after B=factual, F only after
   D=clear. Stop on any other label, tie, failure or uncertain dispatch. C/E are excluded;
   no alternate target, prompt revision, provider fallback, retry or scope expansion.
3. Require exactly one real F candidate and locate its exact minimal supporting span
   with existing T04 code. More than one candidate, uncertainty, or location failure
   stops this acceptance attempt; never truncate candidates or invent a success.
4. Prepare the three H requests from the actual F output and its real lineage. Their
   hashes, work keys and exact candidate-dependent contexts cannot be known now.
   Obtain new exact authorizations for at most 3 Jev calls / USD 0.03, within the same
   aggregate six-call/USD 0.06 ceiling. Do not pre-authorize unknown H request bodies.
5. Only after the required exact authorizations are available, compose the unchanged
   ClaimExtractor with the existing adapters and single-use, request-bound transports.
   B/D/F reuse their exact persisted real evidence without redispatch. H decisions
   remain independent. Never call the full extractor with intentionally missing H
   authorization as a pause mechanism: that would persist terminal failures. This
   proposal adds no executor or restart/worker orchestration.
6. Enforce the stage allowlist and aggregate allowances during composition. T04 numeric
   limits alone do not exclude C/E; exact T03 work/body authorization also gates calls.
   An uncertain dispatch consumes its allowance. A malformed/failed call stops further
   paid dispatch; preserve its failure evidence. No new capture, search, page fetch or
   other web request is part of this live gate.
7. Acceptance requires real OpenAI generation, all three H checks, at least one accepted
   claim with faithful qualification/minimal exact provenance, complete target audit,
   linked-record validation, close/reopen and network-disabled replay. Manually inspect
   the extraction and report errors/usage. A succeeded Outcome with only issues is an
   auditable result, but does not satisfy this live acceptance gate.

Generation credentials/API access remain unavailable from the recorded T03 status and
were not probed. No live authorization exists; actual calls and spend here are zero.
The conditional B/D/F bindings are prepared, while H bindings require a later real F
result. T04 business logic, shared contracts, resources and downstream scope are unchanged.

## Local Qwen/vLLM continuation — 20 September 2026

The user selected local Qwen3-4B-Instruct-2507 and vLLM, then explicitly authorized
at most five Jev calls, USD 0.05 total, 60-second timeout, concurrency one, zero
retries. D04 records the pinned runtime and unchanged extraction constraints.
Create a new diagnostic run/index on a complete private copy of this bundle; do not
reuse or rewrite the frozen OpenAI run/configuration. Prepare each exact request
from real upstream output and bind its authorization before dispatch. The scope
remains [0,63), one candidate, B/D/F/three H stages, no C/E. One local F request has
zero external-provider cost. No other paid call, fallback, extra target or benchmark.

The runtime is provisioned privately at
`/mnt/workspace/BinfoCheck-data/t04-local-runtime/`. Its hash-bound manifest captures
model-file hashes, exact package versions, launch arguments, selected environment,
GPU/driver, and authenticated server model/version checks. The task-local NVML fix
uses NVIDIA's official 580.173.02 redistribution archive matching the loaded kernel
module; system NVML is not replaced.

Current Jev pricing was verified from [TypeSafe model documentation](https://docs.typesafe.ai/models):
USD 0.042 per million input tokens, output free. A conservative full 65,536-token
context costs at most USD 0.002752512, below each USD 0.01 reserved allowance.
Actual reported usage and estimates remain separate from unknown billed cost.

### Executed first gate: genuine unresolved result

Private evidence: `/mnt/workspace/BinfoCheck-data/t04-qwen-acceptance-20260920/`.
Original gate source/fingerprints and every copied original record remain unchanged.
A preflight-only enum construction failure made zero calls and is preserved separately
in the sibling `t04-qwen-acceptance-20260920-preflight-error` directory.

- Run: `t04-local-qwen-gate-08196e14576b073dcd35df16d5d329dc15565801daac11136b5778ea42d57856`.
- Same-run index: `text-index-3815c3dd8a32e7158134537b23439d44938837983f437cd5032f787b9e180440`.
- Final audit: `extraction-final-de878643d405b8a9befa8f6cce2f5fb9602cf910e38fd13d6ee7d30621ab95e8`.
- B: factual (0.97); D: unresolved (0.55, versus clear 0.42). These are model scores,
  not accuracy estimates or invented explanations of model reasoning.
- Two Jev calls, zero retries; 1,355 input / 101 output tokens reported. Estimated
  provider cost USD 0.00005691; billed cost unknown. No F/H calls were made.
- Boundary success means completed durable accounting: **zero Claims, one D.unresolved
  issue**. It does not satisfy the nonempty-Claim integration gate or T05 prerequisite.
- Two socket/DNS-blocked close/reopen cycles reproduced every decision and identical
  extraction output without model execution. Linked records, terminal accounting and
  source fingerprints passed; see private `offline-replay.json`.

The original frozen B/D/F preparation bytes and work identities were independently
reconstructed unchanged with the extended adapter code. Historical evidence remains
replayable. No validation label was overridden and no generation was run past D.

### Authorized additional gate — 20 September 2026

The user explicitly approved one additional gate on the retained sentence at
**[2155,2338)**, target
`text-unit-476f64c946df226da997df354a55876a1a7c879c52f906bb6dcce9db54ef77f0`.
This allows at most five further Jev calls, giving a session ceiling of seven calls
and USD 0.07, with 60-second timeouts, concurrency one and zero retries. One local
Qwen F generation, the same prompts/rubrics and all three independent H checks remain
required. There is no further target expansion or retry authorization.

Copy the first completed gate store, preserving its original decisions/issues/audit,
then create a distinct diagnostic run whose identity includes the new target and a
new same-run T02 index. No prior result is rewritten. Private continuation location:
`/mnt/workspace/BinfoCheck-data/t04-qwen-followup-20260920/`.

### Additional gate result: genuine unresolved output

The additional gate executed once through the unchanged T04/T03 implementation.
B selected factual (1.0); D selected unresolved (0.47, versus clear 0.38 and
resolvable_from_context 0.15). The exact source sentence and stored heading were
provided by the existing context-selection code. Inspection confirmed their saved
text/offsets; no model reasoning or explanation for the label is inferred.

- Run: `t04-local-qwen-followup-adf23c2a7856afc86e2042f35782ca92ba91c60a7235efd39ed47107b9267750`.
- Same-run index: `text-index-3db7f0015f3cbc2ab26ab412938dc3dfb198f1d98517f32e9f656bbc9c73ff6c`.
- Final audit: `extraction-final-9dc86c02c76512de2de111213b974027e9e0f0f162611184bf23739dc51646bb`.
- Result: zero Claims and one `D.unresolved` issue with complete target accounting.
  No local F or H operations occurred. There were two additional Jev calls and zero
  retries, reporting 1,564 input / 101 output tokens; estimated cost USD 0.000065688.
- Session total: **four Jev calls**, 2,919 input / 202 output tokens, estimated cost
  **USD 0.000122598**. Billed cost remains unknown. No other paid model call occurred.
- The store includes both runs and their original decisions/issues/audits.
  Network/model-disabled close/reopen replay, linked records, target accounting and
  unchanged predecessor-store fingerprints passed; private `offline-replay.json`
  and `execution.log` preserve the checks.

This consumes the authorized additional-gate attempt. Unused numeric allowance is
not authorization to retry, select another target or override D. T04 remains
**integration_blocked**; Qwen serving is ready but no real F request was reached.
The existing T05 saved-pair diagnostic was not run because there is no genuine
accepted Claim ID to supply. No T05 logic or provenance guard was changed.
