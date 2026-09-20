# Model adapters — T03, version 1

`JevDecisionModel.decide` and `OpenAIGenerationModel.generate` implement the unchanged
T00 protocols. Construct with `(records, artifacts, resources, config, transport,
clock=None)`. The stores implement T11A protocols; `ResourceRegistry` explicitly maps
`(name, version)` to immutable bytes. Transport and clock are injectable for offline
tests. Runtime `jsonschema` is locked at 4.26.0.

The approved direct endpoints and pins are:

| Adapter | Endpoint | Model | Credential |
|---|---|---|---|
| Jev | `https://api.typesafe.ai/v1/systemone` | `jev-1.13.0` | `TYPESAFE_API_KEY` |
| Generation | `https://api.openai.com/v1/responses` | `gpt-4.1-mini-2025-04-14` | `OPENAI_API_KEY` |

`FixedHttpsTransport` uses `http.client` with TLS certificate/hostname checks. It
sends one synchronous POST, does not follow redirects, and has no retry, gateway,
model fallback or SDK default calls. Credentials load only for explicit execution,
from process environment or explicit `.env`, without override/interpolation. No
credential is part of a request body, settings, record, receipt or log.

## Inputs and configuration

Requests use `settings.version={name: "t03-model-adapters", version: "1"}` with
`sha256=null`. The only `settings.values` entry is `state_artifact_id`, which must
identify an actual artifact in `input_artifact_ids`. UTF-8 text or JSON object/array
state is accepted; no URLs are fetched. `input_ids` and `input_artifact_ids` remain
unchanged in the DecisionRecord. Run and input records must already exist.

The caller supplies a versioned Jev rubric resource containing `instructions` and
`criteria`, or an OpenAI UTF-8 instruction resource and output schema. Versions
with hashes are verified; exact bytes are snapshotted regardless. Jev requests
have no generation prompt; generation requests have no decision rubric. No business
resource is selected or supplied by these adapters. Preparation, including validation,
is available through `persistence.prepare` without credentials or network.

`ModelAdapterConfig` pins adapter version 1, provider, maximum request bytes (4096
default, at most 65536), response bytes (2 MiB), output tokens (512 maximum), and
the existing shared Budget. T03 supports request limit 0/1, retry limit 0,
concurrency 1, USD, and at most 60 seconds. The complete effective config enters
the work-key hash and prepared artifact; the DecisionRecord keeps the caller's
configuration VersionRef. Configurations and credentials do not authorize spending.

## Validation

Jev accepts only the exact label set and question `q0`; known label, type and
confidence are required. Required probabilities must cover every label, be finite
numbers in [0,1], sum to one within absolute tolerance 1e-6 and agree with the
selected maximum (ties allowed). No renormalization or confidence substitution.
Optional missing/partial probabilities remain unavailable/incomplete. Invalid
complete distributions still fail. No business thresholds are applied.

Generation requests use strict JSON Schema in Responses `text.format`, with tools
disabled, temperature 0, standard service tier, no streaming/background/conversation
and `store=false`. The exact returned model must match the pin. Require a completed
response and exactly one completed assistant message with one `output_text` item;
refusal, tool calls, ambiguous multiple outputs and incomplete responses fail.
JSON rejects duplicate keys, nonfinite values and malformed UTF-8; there is no
fence stripping, repair, field coercion, rewriting or second model call.

The caller's exact schema is checked and validated by jsonschema. Version 1 supports
a conservative subset: object roots, closed objects with all properties required,
scalars, arrays, enums/const, nested anyOf and acyclic local `#/$defs/name` references;
allowed numeric/array bounds and patterns are listed in `resources.py`. Remote
references, `$id`, recursive schemas and unsupported keywords are rejected before
dispatch, never fetched or silently removed. Downstream schemas may need an explicit
adapter extension later; no T00 schema is changed or duplicated here.

## Artifacts, IDs and replay

SHA-256 covers canonical request/config/resource snapshots and actual input hashes.
It determines the work key and `model-decision-<hash>` / `model-generation-<hash>`
record ID. `role_id(record_id, role)` determines artifact IDs. Clock values, secrets
and provider response IDs never determine work identity. An intentional new call
requires a new analysis run and, for live work, fresh authorization.

Artifacts use T11A exclusively and are immutable. Roles are `prepared`, `outbound`,
`intent`, `raw`, `structured` and `receipt`. Prepared content includes the actual
T00 request and exact base64 resource bytes, not duplicate domain schemas.
`raw` preserves response entity bytes before JSON parsing, including malformed and
error bodies. HTTP transfer framing is removed by http.client; content coding is
requested as identity. Unexpected coded bytes/prefixes remain stored as failed,
incomplete artifacts. Allowlisted headers are separate; credentials/cookies are omitted.

**GenerationResult.output_artifact_id points to canonical validated structured JSON.**
It never points to the provider envelope. The receipt separately links the raw
response and semantic output; both are restricted. Neither is added to input lineage.
Receipt/preparation/normalization versions are 1. The receipt captures UTC timing,
elapsed time, dispatch uncertainty, headers, response ID, errors, raw usage and
explicitly labeled cost estimates. The prepared configuration identifies provider
and endpoint mapping. The intent records authorization and reserves the allowance.

`replay_decision` / `replay_generation` accept stores and a record ID, with no
credentials or transport. They verify artifact hashes, versions, IDs, original
inputs, outbound bytes, normalized values, output JSON and usage, then append the
identical record using original timestamps. No existing record is overwritten.

Failures return `Outcome(failed, value=null)` and save failed DecisionRecords where
storage works. They do not become successful Outcomes or negative labels. Normal
provider/validation failures have replayable receipts. If the receipt survived a
record-write failure, replay can finish local persistence. Missing/corrupt required
artifacts fail replay; they never cause a new provider request. If receipt storage
failed but record storage worked, the failed record remains inspectable, repeated
invocation returns it, and full replay remains unavailable. Raw/output write failures
are explicit failures, not successful results with missing artifacts.

## Usage, authorization and limits

Missing usage is unavailable; partial/invalid counters remain unknown. Explicit
reported zero is preserved. Usage.cost/currency/requests remain null because neither
selected response schema supplies a billed cost or request count. Dispatch state
is separate receipt metadata. Jev/OpenAI detailed token metadata remains in raw
responses/receipts. Estimates use the 2026-09-19 public model prices: Jev input
$0.042/M, OpenAI input/cached/output $0.40/$0.10/$1.60 per million. Missing cache
breakdown, unexpected service tier or cache-write usage makes the OpenAI estimate
unknown. Estimates are not reported charges or proof of billing.

Live authorization is unresolved. The real transport requires a reviewed
`LiveAuthorization` bound to provider, endpoint, model, work key, body digest,
approval/pricing references and a verified upper cost within the ceiling. Keys alone
cannot dispatch. The standalone smoke entry point defaults to **offline preparation**:

```bash
uv run --offline --locked python -m binfocheck.models.live_check --provider jev
uv run --offline --locked python -m binfocheck.models.live_check --provider openai
```

These print frozen fixture payloads/hashes and use MemoryStore only. Future execution
requires explicit user approval plus `--execute --store <private-root>
--authorization <reviewed-file>`. Do not create an authorization file from this
README or infer consent from the command's availability. Review current pricing and
the request's upper cost first; there is no provider-enforced dollar limit.

One possible dispatch consumes the allowance even on timeout. Repeated calls reuse
the receipt/failed record, and abandoned intents become uncertain failures without
resending. Their elapsed network duration is unknown. Clock/size bounds apply to
network reads; socket deadlines decrease rather than resetting per body chunk.
DNS resolution and internal blocking header/TLS operations can exceed a wall-clock
target on some platforms: this is not a process-kill or exactly-60-second guarantee.

The supported execution mode is one process/one owner per work key. T11A has no
atomic cross-process dispatch lease; do not launch the smoke runner concurrently.
No exactly-once external billing, distributed transaction, recovery of bytes lost
before persistence, power-loss durability or multi-worker orchestration is claimed.
T11B owns coordination. Real access/API compatibility remains unverified; offline
tests prove wiring/validation, not German model accuracy or provenance.

## MVP local generation — D04 continuation

`LocalVllmGenerationModel.generate` implements the same GenerationModel protocol.
Use `LocalGenerationConfig`, `LocalVllmTransport` and the same ExtractionResources
as T04. The selected model is `Qwen/Qwen3-4B-Instruct-2507`, revision
`cdbee75f17c01a7cc42f958dc650907174af0554`; the served/requested/returned model ID
is the repository name followed by `@` and that revision. Local request settings
use `t04-vllm-generation/2`; legacy Jev/OpenAI configuration and artifact identities
remain unchanged. No shared schema changed and OpenAI is not a fallback.

The local configuration includes the private runtime manifest SHA-256 and fixed
vLLM/version/device settings. Before execution, inspect and hash the actual model
snapshot, tokenizer files, installed package inventory, launch arguments and selected
(non-secret) environment. Verify `/version` is 0.10.2, authenticated `/v1/models`
returns only the selected alias and unauthenticated `/v1/models` fails. These GETs
make no generation calls. The manifest records that a model alias alone is not proof
of weights; retain the independently provisioned snapshot/launch evidence.

Construct `LocalAuthorization` from an actual approved request's work key, outbound
hash and runtime-manifest hash, then inject it with the loopback server key and
manifest bytes into `LocalVllmTransport`. Keys are never serialized. The transport
has no environment credential loading, redirects, proxies or external endpoint
configuration. One request, 60 seconds, concurrency one, zero retries, at most 16384
request bytes for T04, 2 MiB response bytes and 512 output tokens. Local external
provider allowance is zero; infrastructure cost remains unmeasured. Missing token
usage remains unknown. Actual vLLM `prompt_tokens` / `completion_tokens` are retained;
estimates never replace billed-usage fields.

Preparation maps the existing instruction and exact state to system/user messages,
with strict JSON Schema, temperature 0, top_p 1, seed 0, n=1, no tools or streaming.
The schema guides generation but adapter validation is still mandatory. Only a
single assistant choice with finish_reason `stop` and the exact model ID is accepted.
Truncation, refusal/tool output, malformed JSON, duplicate keys and schema violations
fail without repair, coercion or another request. Raw vLLM chat envelopes are stored
unchanged, separately from canonical validated JSON. T03 also snapshots a restricted
`runtime` artifact and verifies its configured hash during offline replay. No
server/GPU/model import is needed for replay.

### Isolated vLLM server on the V100

This serving dependency has a separate environment because vLLM 0.10.2 requires
Torch 2.8.0, whereas T07's optional local-model environment pins Torch 2.9.1. It is
not part of the repository test toolchain. Exact installed server dependencies are
in [vllm-runtime.lock](vllm-runtime.lock); use Python 3.12 and `uv pip install --python
<server-env>/bin/python -r src/binfocheck/models/vllm-runtime.lock`. Ordinary tests
remain offline and require no serving environment.

Provision the selected Hugging Face snapshot explicitly before serving; never let
inference download models or remote code. Set `VLLM_USE_V1=1`,
`VLLM_ATTENTION_BACKEND=XFORMERS_VLLM_V1`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`,
`HF_HUB_DISABLE_TELEMETRY=1`, `VLLM_NO_USAGE_STATS=1`, `DO_NOT_TRACK=1` and
`OMP_NUM_THREADS=4`. Inject a private random server key through `VLLM_API_KEY`.
The launch arguments are:

```text
vllm serve <verified-snapshot-directory>
  --served-model-name Qwen/Qwen3-4B-Instruct-2507@cdbee75f17c01a7cc42f958dc650907174af0554
  --host 127.0.0.1 --port 8004 --dtype float16 --max-model-len 4096
  --max-num-seqs 1 --gpu-memory-utilization 0.65 --enforce-eager
  --generation-config vllm --disable-log-requests --no-enable-prefix-caching
  --guided-decoding-backend xgrammar --guided-decoding-disable-fallback
```

Context overflow is rejected, never silently truncated. Prefix caching, speculative
models and quantization are disabled; the selected model is not benchmarked against
alternatives. The V100 lacks BF16 support, so FP16 remains explicit. V1/XFORMERS_VLLM_V1 is the selected correction;
GPU startup with these settings has not yet been verified.
Do not substitute a newer vLLM release that dropped the V100's execution path.
See [vLLM 0.10.2 CUDA requirements](https://github.com/vllm-project/vllm/blob/v0.10.2/requirements/cuda.txt)
and [CUDA platform implementation](https://github.com/vllm-project/vllm/blob/v0.10.2/vllm/platforms/cuda.py).

The acceptance host had a loaded NVIDIA driver 580.173.02 but NVML 580.178.04.
A checksum-verified NVIDIA 580.173.02 redistribution library loaded through the
server process's `LD_LIBRARY_PATH` repairs NVML without changing system packages or
rebooting. Keep this path scoped to the task and record its hash in the runtime
manifest. Model/runtime evidence and the repair are preserved privately; details
and remaining integration limits are in `docs/t04-live-gate.md`.

### Structured-output runtime guard

The saved F failure exposed that vLLM 0.10.2's V0 path accepted the JSON-schema
request but installed no guided-decoding enforcement. Configuration version 2
requires V1 with XFORMERS_VLLM_V1. Before dispatch, both the adapter and transport
check the bound runtime manifest's engine/attention environment, server version,
model alias, dtype, context limit, xgrammar backend and disabled fallback.
A manifest hash alone is insufficient. Preserve the old inventory and create a
new manifest from the actual corrected launch before authorizing new requests.
The manifest is an auditable declaration, not independent server attestation.

Explicit version 1/V0/XFORMERS configurations remain readable for exact preparation
and replay, but cannot make new calls. Cached receipts remain replayable. New
configuration identities differ even though the F prompt, response schema and
HTTP generation body are unchanged. External adapter configuration remains v1.

Run the optional offline runtime regression using the existing serving environment:

```sh
<server-env>/bin/python scripts/verify-vllm-structured-output.py --snapshot <verified-snapshot-directory>
```

An optional `--request <saved-outbound.json>` checks the exact saved request against
the repository schema. This uses installed vLLM protocol, V1 request/grammar wiring,
xgrammar compilation and token masking with the local tokenizer. Sockets are
blocked; no engine, weights or generation are created. It is not GPU/server
acceptance. Repository tests cover rejection before dispatch and legacy replay.
