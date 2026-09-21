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

### Fresh v3 gate on the original first target — 20 September 2026

The user authorized one fresh v3-bound run on the existing **[0,63)** target only:
at most five Jev calls and one local Qwen generation, concurrency one, 60-second
timeouts, zero retries, no external paid generation, and immediate stopping on a
non-required label, malformed output, uncertain dispatch, location/budget problem
or validation failure. Existing cost caps were retained: USD 0.01 per Jev request,
USD 0.05 for this gate. Current Jev pricing was checked again against the official
model documentation. No prompt, rubric, threshold, state-selection or B/F/H/T05
logic changed during execution.

Execution used code `e89fa5493aef77bec911347215815c58902c1337`, immutable bundle v3
(`8d34d05c57578b2eed05e383102420df97aacb512069c541854cc337fb36168d`), and the
same pinned Qwen/vLLM runtime. Authentication, model-file hashes and server version
passed read-only checks without generation. The source was a copy of the **first**
historical gate store; both original historical stores remained unchanged.
Every dispatched request's exact prepared bytes and approval hash were saved before
dispatch and bound to the new run/configuration. A one-shot marker prevents re-entry.

Private evidence: `/mnt/workspace/BinfoCheck-data/t04-qwen-v3-first-20260920/`.

- Run: `t04-local-qwen-v3-first-gate-74cd3db88bdefc6122af0d17f49dfd7cd34670f52d1601f77e7209d098d35255`.
- Index: `text-index-1c29edeaa1a5a96bf8d2315b192211941e356678bce2a6f8eccccf220032d6d4`.
- Final audit: `extraction-final-d03c1cd22b43a160345b4b1015ee9bf8fa95dc31afa5151c87be7ed9b489d1e4`.
- B: **factual (0.97)**; D v3: **clear (1.0)**. These are reported model scores,
  not measured accuracy. Historical v1 unresolved outcomes were not reinterpreted.
- F: one local request, complete HTTP 200, normal stop; adapter normalization failed
  with **`schema_validation_failed`**. The JSON omitted `status` and
  `normalized_claim`, used an unexpected `text` key, and supplied strings where
  `anchor` and `required_support` entries require objects. Raw response, exact
  schema, receipt and schema-error inspection are preserved; no output repair or
  additional generation was attempted.
- F record: `model-generation-f00fd00955fd7b4b4ee93010df58702e97da7520535b2324c5e3f58c0ab51389`.
- Terminal result: **zero Claims, one `F.model_failed` issue**. G/H were not reached.
  The extraction boundary completed terminal accounting; this is not live acceptance.
- Calls: **two Jev, one local Qwen**, zero retries, zero uncertain dispatches.
  Jev reported 2,045 input / 98 output tokens; estimated USD **0.00008589**.
  Local Qwen reported 577 input / 92 output tokens; external provider cost zero,
  infrastructure cost unknown. Session totals: six Jev calls, one local generation,
  4,964 Jev input / 300 output tokens, estimated Jev cost **USD 0.000208488**.
  Billed cost is unknown; estimates are separate from provider billing.
- Replay passed twice after close/reopen with sockets/DNS/model operations blocked,
  reproducing the two successful decisions, failed F record and identical extraction
  output. Linked records, original records, complete target accounting and source
  fingerprints passed. Both historical stores retained hashes, mtimes and modes.
- T05 saved-pair diagnostic: **not run**, because no genuine accepted Claim exists.
  No T05 code changed. This gate is terminal; remaining numeric allowance is not
  permission to retry or dispatch H after failed F.

Pre-dispatch problems made zero model calls and are retained in private logs:
automatic approval review rejected an initial source-copy choice that included both
historical runs; using the first store directly and proving the exact target resolved
that concern. A runner-only assertion incorrectly expected a hash on the adapter's
version reference; it was replaced with canonical adapter-version and run-binding
checks. A saved fingerprint needed JSON-list-to-tuple restoration before comparison.
Both checks were corrected before any request dispatch, with the same run and frozen
resources. They are not model retries; original scripts and failure logs remain saved.

The current integration blocker is local F schema compliance. Any follow-up diagnosis
or execution must be separately scoped; the failed output must not be promoted to a
Claim or used to bypass the T05 genuine-evidence prerequisite.

Post-gate offline verification: 250 focused model/Claim tests passed;
`scripts/verify.sh` passed all 1,029 tests plus lint, formatting, Pyright, schema
and whitespace checks. No further live call occurred during verification.

### Offline F runtime correction — 20 September 2026

The retained prepared request rebuilt byte-identically, and the strict F JSON schema
reached the saved outbound body unchanged. Installed vLLM 0.10.2 protocol parsing
converted it to `guided_decoding.json`; the historical V0 engine installed no guided
logits processors. The configured xgrammar compiler accepted the exact schema and
rejected the failed content. The private diagnosis is preserved in the sibling
`t04-qwen-v3-first-20260920-f-review/` directory; original evidence is unchanged.

The authorized implementation introduces local configuration v2 (V1 with
XFORMERS_VLLM_V1) and rejects legacy V0 calls before dispatch. Both adapter and
transport validate the bound runtime manifest's relevant settings. Old configuration
preparation and network/model-disabled replay remain supported. No F schema/prompt,
Jev rubric, threshold, extraction methodology or T05 logic changed.

The installed-environment offline regression uses the exact saved request and local
tokenizer: V1 attaches a compiled grammar, masks invalid tokens, rejects a synthetic
malformed shape, and accepts a schema-conforming unresolved control. No engine,
weights or generation are initialized. xgrammar emits its existing non-ASCII
negative-character-class warning; adapter schema validation remains mandatory.
This demonstrates wiring/enforcement, not exhaustive JSON Schema fidelity or GPU
serving acceptance. The old server and manifest remain untouched; corrected GPU
startup and any newly authorized live gate are still outstanding.

Both historical unresolved runs and the failed v3 run replayed after close/reopen
with network/model access disabled. The exact failed F request still rebuilds
identically; the entire failed gate retains its hashes, mtimes and modes.
New Jev/Qwen calls and incremental provider cost: zero. T04 remains unaccepted and
T05 remains blocked by the absence of a genuine accepted Claim.

### V1 GPU startup attempt — 20 September 2026

The GET-only runtime assignment authorized one corrected startup, with no Jev,
generation, gate or T05 execution. Evidence is in the separate private directory
`/mnt/workspace/BinfoCheck-data/t04-local-runtime-v2-20260920/`.
The exact historical listener PID 4147705 was terminated with SIGKILL to avoid
appending shutdown output to its historical log. Its V0 worker PID 4147811 remained
in that session, holding 21,290 MiB; identifying only the listener before startup
was insufficient. Ollama and other GPU processes were not stopped.

New API PID 31499 / V1 engine PID 31861 used the documented vLLM 0.10.2, pinned
snapshot, FP16, XFORMERS_VLLM_V1, xgrammar/no-fallback and offline-loading settings.
The logs confirm V1 initialization and `trust_remote_code=False`, but startup
failed before readiness: 9.72 GiB free of 31.73 GiB was below the configured 0.65
allocation (20.63 GiB). A preceding FlashAttention2 capability warning is retained;
it does not establish an additional fatal cause. No settings or versions were
changed and no restart was attempted after failure.

There were zero HTTP requests, including zero chat-completion requests. `/version`,
models/authentication checks and a verified running-runtime manifest are blocked.
The separately named failed-startup manifest is evidence, not dispatch eligibility.
The offline structured-output script passed with the exact saved F body/local
tokenizer; 27 focused adapter/extraction tests passed. No genuine Claim or T05
result was produced. The next runtime attempt must explicitly account for the
remaining identified V0 worker while preserving historical files and unrelated
processes; this failed attempt is not authorization to retry.

### V1 GPU runtime accepted after orphan cleanup — 20 September 2026

The user subsequently authorized the identified fix. PID 4147811 was reconfirmed as
the orphaned worker of the historical V0 runtime and the only BinfoCheck process using
GPU memory (21,290 MiB); it was terminated without affecting Ollama. Free GPU memory
rose to 31,615 MiB. The resource tracker then appended a 242-byte leaked-semaphore
warning to the historical log. Its original 10,350-byte prefix matched the retained
SHA-256 exactly, so only that append was removed and the recorded timestamp restored.
A complete rehash confirms the historical runtime's bytes, paths, modes, mtimes and
symlinks again match its pre-attempt fingerprint.

The unchanged documented V1 configuration then started successfully on the V100.
API PID 38126 and engine PID 38272 use vLLM 0.10.2, FP16,
XFORMERS_VLLM_V1, xgrammar with fallback disabled, eager execution, context 4096,
one sequence and prefix caching disabled. Logs explicitly report the V1 engine,
XFormers backend, `trust_remote_code=False`, local snapshot path and completed API
startup. The V100's expected FlashAttention2 capability warning is retained; XFormers
was selected successfully. No silent guided-decoding fallback appears.

Exactly three HTTP requests were made, all GETs: `/version` returned vLLM 0.10.2;
authenticated `/v1/models` returned exactly the pinned Qwen alias; unauthenticated
`/v1/models` returned 401. No POST or `/v1/chat/completions` request occurred. The
separate offline structured-output probe passed against the pinned tokenizer and
exact saved historical F request, with sockets blocked and zero model calls.

The new immutable manifest is
`/mnt/workspace/BinfoCheck-data/t04-local-runtime-v2-20260920-attempt2/runtime-manifest.json`,
SHA-256 `9d3b58c2caa263806cee5f52b70cdcc8e30abba0182123db74b7e9fd1734e5e4`.
It records the actual command, selected environment, process session, GPU/driver,
NVML hash, package versions, GET results and model-file hashes. A
`LocalGenerationConfig` v2 bound to that hash passes `require_structured_runtime`.
The isolated new Hugging Face cache contains no files, establishing that startup did
not download model content. New Jev calls, Qwen generations, T04 gates and T05 runs:
zero. This resolves the runtime blocker only; a genuine accepted Claim still requires
separate live-call authorization.

### Fresh D v3 / local v2 gate — 21 September 2026

The user authorized the proposed first-target gate with at most five Jev calls and
one local generation; the previous USD 0.05 ceiling, concurrency one, 60-second
timeouts and zero retries were retained. A fresh process/model-hash and GET preflight
passed against the accepted manifest. All stage resources remained unchanged.

Run `t04-local-qwen-v3-v1-first-gate-f55aab1f6f9a526da3974560a410f012dd87ae51092c3c704086be2ff0a6a4b3`
targets only the retained `[0,63)` sentence. Each exact request and single-use
authorization was saved before dispatch. B returned factual (0.97), D v3 returned
clear (1.0), then the only F request returned complete HTTP 500,
`provider_unavailable`. Dispatch was known, not uncertain. No retries or H calls
occurred; G was not reached. The pipeline persisted zero Claims and one
`F.model_failed` issue.

The server traceback identifies `NotImplementedError` in XFormers
`memory_efficient_attention_forward` with
`PagedBlockDiagonalCausalWithOffsetPaddedKeysMask`: FA2 and Triton candidates reject
compute capability 7.0 (Triton also rejects page-size 16 against block-size 64), and
the CUTLASS candidate rejects the mask type. The V1 engine and API server exited.
This reveals inference incompatibility that successful startup, GETs and offline
grammar tests did not exercise. No corrective settings or model changes were made.

Evidence is in `/mnt/workspace/BinfoCheck-data/t04-qwen-v3-v1-first-20260921/`:
prepared requests, authorizations, raw bodies/responses, receipts, exact server log,
bound manifest, final audit and replay/usage reports. Final audit:
`extraction-final-8aa83fafba83795286962fcb29e4f1774ee4eafcaf914ddb1e0d3b15bc8d2be7`.
F record: `model-generation-3c89d6764cbc0994b069473f765a813c37d7a323b8b7b6ecdbbd5bc3741f9d37`.
Same-run T02 index:
`text-index-6f6b8149eb96db6a181395a6241d32808e9fcef3c2ffe5ccae17fc8a689bd1d1`.

Two Jev calls reported 2,043 input and 98 output tokens: estimated USD 0.000085806
at the verified input-only rate. Local request usage and infrastructure cost are
unknown; external generation cost is zero. Session totals are eight Jev calls,
two local generation requests, 7,007 Jev input / 398 output tokens and estimated
Jev USD 0.000294294; billed cost remains unknown.

Network/model-disabled replay passed twice after close/reopen, reproducing all three
records and identical terminal output; links and target accounting passed. Both
historical v1 stores and the entire previous v3 failed-gate directory retain their
fingerprints. T05 was not run because no genuine accepted Claim exists. The initial
automatic approval rejection made zero calls; read-only inspection established the
generic retained payload and its authorized destination, after which review allowed
the same bounded dispatch. This gate is terminal and cannot be resumed or retried
under its consumed authorization.

Post-gate verification passed: 257 focused model/Claim tests and `scripts/verify.sh`
with all 1,036 tests, lint, formatting, types, schema and whitespace checks.

### V3 runtime implementation — 21 September 2026

The post-reboot F-only diagnostic again returned HTTP 500 on the V100 under
vLLM 0.10.2 V1/XFormers, now with matching NVIDIA 580.178.04 libraries. It used
direct HTTP and supplies terminal runtime evidence, not manifest-bound T03
adapter acceptance. Historical gate stores and failed output remain unchanged.

The authorized correction adds local configuration v3 for vLLM 0.19.0 V1,
explicit `--attention-backend TRITON_ATTN` and explicit xgrammar. The old attention
environment variable is not a supported 0.19 selector. A separate lock provisions
`/mnt/workspace/BinfoCheck-data/t04-runtime-v3-env`; shared runtime environments
were not changed. The dependency consistency check passed. Legacy configurations
and saved replay remain supported; only v3 may make new calls.

The installed-runtime verifier passed for both 0.10.2 and the durable 0.19.0
runtime using the exact saved F request and local tokenizer with sockets blocked.
The new path verifies CLI parsing, schema preservation, V1 grammar attachment,
invalid-token masking, malformed-shape rejection, and unsupported-schema/compiler
failure without fallback. xgrammar retains its non-ASCII negative-character-class
warning; strict adapter schema validation remains mandatory. These checks do not
prove exhaustive schema fidelity or GPU decoding compatibility.

Implementation evidence is separate at
`/mnt/workspace/BinfoCheck-data/t04-runtime-v3-implementation-20260921/`.
This assignment makes zero generation/Jev calls and performs no gate/T05 run.
A new actual-process manifest and bounded F-only test through T03, followed by
close/reopen offline replay, remain prerequisites to a fresh authorized Jev gate.
T04 has no accepted Claim; T05 remains blocked.


### V3 runtime F-only diagnostic — 21 September 2026

The user authorized one local F call to test the implemented runtime fix, with
USD 0 external provider cost, a 60-second timeout, concurrency one, zero retries
and zero Jev calls. No extraction gate or T05 was executed. The first startup
passed GET-only checks but a private diagnostic helper supplied a string instead
of the required `ProcessingStatus` enum when constructing its run. That local
preflight failure dispatched nothing. The helper was corrected and its complete
preparation checked offline before a fresh startup used the still-unused call.
Both startup inventories remain separate; neither replaces historical evidence.

The fresh actual-process manifest is
`/mnt/workspace/BinfoCheck-data/t04-f-runtime-v3-20260921T090626Z/runtime-manifest.json`,
SHA-256 `77c1ad4f8a03f8c0676dd9db9487d63d8c2735da66a9e8948389c2e4cab85b95`.
PID 39676 served the pinned Qwen revision on V100 with NVIDIA 580.178.04,
vLLM 0.19.0 V1, FP16, TRITON_ATTN and explicit xgrammar. Actual process arguments,
selected environment, mapped NVML identity/hash, package inventory, verified
snapshot hashes, logs and authenticated/unauthenticated GET checks are retained.
The manifest passed the unmodified v3 live guard. No model downloads or remote
code loading were used. The task-local server was stopped afterward; both shared
BinfoNet services were restored and passed GET `/v1/models`. Ollama remained
running with the same service and GPU process identities; port 8004 is free.

New diagnostic run: `t04-f-runtime-v3-20260921T090626Z`.
F record: `model-generation-8eb1b49a1ec765d48793ab86717df125eb321bea15fc9fe798f8534701b19b9c`.
The adapter-prepared outbound bytes match the historical F body exactly:
SHA-256 `5d37cc8f80521929036d17ce165aa154644c86f8f5e92ebfbdbe855cebfb5590`.
The new request links the immutable historical unit through its original run and
unchanged state artifact; its unit is not reassigned to the diagnostic run.
T03 preserved authorization, intent, exact outbound/raw bytes, receipt, runtime,
usage and result in a new SQLiteStore. Close/reopen replay with socket connections
and model transport blocked reproduced the identical adapter result.

The single call returned HTTP 200 in 10.46684 seconds, with `finish_reason=stop`,
576 prompt tokens and 240 completion tokens (816 total). External provider cost
is USD 0; infrastructure cost remains unknown. GPU decoding and adapter JSON-schema
validation passed, but the unchanged T04 `Decomposed` contract rejects the actual
output with `invalid_unresolved_output`: it combines `status=unresolved`,
`reason_code=none` and a nonempty candidate list. The generated claim is `S` and
quote is `J`, with offsets `[0,18)`. No output was repaired, no G/H/I ran and no
Claim was accepted. T05 remains blocked.

Additional **synthetic offline** controls used the exact F schema and installed
vLLM/xgrammar path with sockets blocked and no engine/weights/generation. All four
controls pass independent JSON Schema validation. The grammar accepts single
characters (`S` / `J`) but rejects a multi-character claim (`Rot.`), a
multi-character quote (`Ja`), and a complete sentence. This demonstrates a grammar
compatibility defect for the schema's nonblank-string patterns; the prior
unresolved-only positive control did not test useful claim/quote strings.
It supports a grammar explanation for the short generated strings, without
claiming to explain the model's inconsistent status choice. Preserve the exact
schema and investigate its compilation before another live call; do not loosen
validation, repair this output or treat runtime success as T04 acceptance.

All new private evidence is in the directory above; the zero-dispatch preflight
inventory is in `/mnt/workspace/BinfoCheck-data/t04-f-runtime-v3-20260921T090302Z/`.
Original gate fingerprints are unchanged. The one generation allowance is now
consumed. The remaining blocker is usable, contract-valid F output; no further
live generation or Jev call is authorized by this diagnostic.

### Offline xgrammar compatibility fix — 21 September 2026

No generation, Jev, server startup, gate or T05 call was authorized or performed.
The saved F evidence remains unchanged. Direct compiler controls in the pinned
vLLM 0.19.0 / xgrammar 0.2.3 environment reproduce the defect: canonical
`pattern: "\\S"` accepts an empty string, accepts a one-character string, and
rejects realistic multi-character text. This is xgrammar behavior; independent
Draft 2020-12 validation applies the intended unanchored non-whitespace rule.

Local configuration v4 applies the smallest deterministic provider-only fix. After
the canonical schema has passed the repository's conservative schema validation,
the adapter deep-copies it for guidance and replaces only exact string
`pattern: "\\S"` constraints with `minLength: 1`. The response-format schema sent
to xgrammar is therefore structurally constraining and permits normal text. The
canonical schema bytes remain stored in `PreparedRequest.resource_bytes_base64`
and normalization uses those exact bytes for mandatory post-generation validation.
Whitespace-only values that the weaker guidance may admit consequently remain
invalid, with no repair or coercion.

The installed-runtime verifier, with sockets blocked and without engine/model
initialization, now proves that the actual vLLM protocol carries the compatibility
schema into explicit xgrammar; the grammar accepts a single-character control,
multi-character German claims/quotes and a complete German sentence. It rejects an
empty constrained string and a structurally malformed object. Separate canonical
checks accept the realistic values and reject empty/whitespace-only strings.
Repository adapter tests also prove that a whitespace-only guided value fails
canonical normalization. V1–v3 request construction/replay remains versioned and
unchanged; only v4 can dispatch after a future fresh manifest binding. T04 retains
zero accepted Claims and T05 remains blocked until a separately authorized live
gate succeeds.
