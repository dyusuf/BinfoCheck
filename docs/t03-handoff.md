# T03 implementation handoff — decision and generation adapters

Task / assignee / status: T03 / Codex / offline implementation complete; final check
results below. Live integration is blocked pending explicit authorization; T03 is
not accepted. Branch: `codex/t03-model-adapters`, based on merged main `87808d1`.

## Scope and authorization

The user approved the T03 planning handoff and the pinned providers, authorized
implementation, commit/push and a draft PR, and explicitly prohibited live calls.
Their corrections require semantic generated JSON to be separate from the raw
provider response and all outputs to remain out of input lineage. Both are
implemented. No T04 extraction, business prompts/rubrics, comparisons, fallback,
worker orchestration, new storage service, deployment or T00 wire changes.

Read AGENTS.md, MVP/exclusions, task conventions/T03, Architecture Sections 3/7/8,
model/storage contracts, T11A implementation, contract fixtures and existing receipt
conventions. T00/T11A are present. D04 implementation choices are recorded in
Architecture; live authorization remains unresolved. D07 remains downstream.

The initial interrupted sync fast-forwarded the branch to merged main; continuing
confirmed and completed the push. No branch switch occurred. This assignment
explicitly authorizes the final implementation commit/push and draft PR, not merging.

## Files and versions

- `src/binfocheck/models/decision.py`: `JevDecisionModel`, strict choice normalization.
- `generation.py`: `OpenAIGenerationModel`, strict Responses structured-output normalization.
- `persistence.py`: preparation/resource snapshots, canonical work IDs, T11A writes,
  failed-record handling, partial-write recovery and usage estimates.
- `receipt.py`: versioned prepared/receipt artifact contents and deterministic role IDs.
- `replay.py`: credential-free/network-free recovery and exact normalization checks.
- `transport.py`: guarded synchronous direct HTTPS, one attempt, no redirects/retries.
- `config.py`: provider pins, shared Budget limits, secrets loading and authorization binding.
- `resources.py`: explicit resource registry, supported schema preflight and jsonschema validation.
- `json.py`, `errors.py`, `__init__.py`: strict/canonical JSON, sanitized errors and exports.
- `live_check.py`: offline smoke preparation by default; separately guarded explicit execution.
- `models/README.md`: full usage/configuration/receipt/limitation documentation.
- `tests/models/`: helpers and adapter, transport, resource, failure/recovery and smoke/replay tests.
- `tests/fixtures/models/`: synthetic provider responses, context/resource files, frozen
  domain requests and exact outbound smoke bytes; origin README.
- `.env.example`: empty `OPENAI_API_KEY` added; existing TypeSafe entry preserved.
- `pyproject.toml`, `uv.lock`: jsonschema moved from development to runtime; no package
  version churn. `types-jsonschema` stays development-only.
- `docs/architecture.md`: approved D04 implementation and explicitly unresolved live budget.
- `docs/implementation-plan.md`: T03 offline status and this handoff link.

Exact versions: Python 3.13.7; Pydantic 2.13.5; python-dotenv 1.2.3; jsonschema 4.26.0.
Configuration VersionRef `t03-model-adapters/1`; preparation, normalization and receipt
versions `1`; pricing basis `2026-09-19`. Domain schema `1`, contract validation `1.1`,
T11A storage/codec `1` unchanged. No TypeSafe/OpenAI SDK installed for this task.

Approved models/endpoints:

| Provider | Model | Endpoint | Credential |
|---|---|---|---|
| TypeSafe AI | `jev-1.13.0` | POST `https://api.typesafe.ai/v1/systemone` | `TYPESAFE_API_KEY` |
| OpenAI | `gpt-4.1-mini-2025-04-14` | POST `https://api.openai.com/v1/responses` | `OPENAI_API_KEY` |

Direct HTTPS uses standard-library http.client and normal TLS verification. Default
limits: request 1, retry 0, concurrency 1, timeout target 60 seconds, cost USD 0.01,
request bytes 4096, response bytes 2 MiB, generation maximum output tokens 512.
These settings are not live authorization. Provider/model/body/work-key mismatches,
missing authorization or credentials stop before the network connection.

## Behavior and persistence

Both public protocols are unchanged. Preparation resolves one explicit input artifact
and caller-owned versioned resources, preserves German/Unicode text, and freezes exact
outbound JSON and resource bytes. No page/schema URL or provider probe is fetched.

Jev validates labels, question/type, confidence and probabilities: complete requested
coverage, finite values in [0,1], sum tolerance 1e-6 without normalization, chosen
maximum including ties. Optional missing/partial distributions retain availability.
Missing usage is unknown; explicit reported zero remains zero. Actual returned identity
must exactly equal the pin; mismatch is a saved failure carrying the returned identity.

OpenAI sends strict JSON Schema Structured Outputs, tools disabled, temperature 0,
standard tier, no conversation, streaming/background disabled and `store=false`.
Successful outputs require completed status, one completed assistant text message,
strict JSON parsing and exact schema validation. Refusal, incomplete, multiple/tool
outputs, malformed JSON, duplicate keys, nonfinite numbers and schema violations
are typed failures, without repair calls.

Generation saves canonical validated structured JSON as the artifact referenced by
`GenerationResult.output_artifact_id`. Exact raw response entity bytes are saved
separately and restricted. The deterministic receipt links both. Input IDs/artifact
IDs are copied as true input lineage; no response/receipt/output is appended to them.

Work/record IDs hash the complete canonical request, effective config, resource bytes
and input hashes. Artifact IDs derive from record ID plus role; SHA-256 covers each
artifact's actual bytes. Roles: prepared, outbound, intent, raw, structured, receipt.
The raw artifact is saved before parsing. T11A handles immutable/idempotent writes.

Receipts capture timing, headers/request IDs, raw usage, validation/transport failures,
uncertain dispatch and estimates. Intent artifacts capture the exact authorization
and reserve the allowance before a possible dispatch. Missing/incomplete usage and
unknown billed charges remain distinct from local dispatch state. `Usage.cost`,
`currency` and `requests` are null for these response schemas. Computed price estimates
are separate and explicitly labeled; cached/reasoning details are not double counted.

Failures return `Outcome(failed, value=null)` and persist failed DecisionRecords where
storage permits. A surviving receipt can complete a failed record write locally.
A failed receipt write can leave an inspectable failed record but incomplete replay.
An abandoned intent becomes an uncertain failure and never sends another request.
Repeated invocations reuse saved outcomes. Fresh analysis IDs preserve prior history.

Offline replay needs stores and record ID only, verifies original inputs and all
required artifact hashes/versions/links/bytes, reproduces normalized output/usage/errors
with original timestamps and appends only identical record content. Missing/corrupt
artifacts produce replay failure; credentials and transport cannot be supplied.

## Verification

All user-required checks passed on the final implementation:

| Command | Result |
|---|---|
| `uv sync --locked --dev` | Passed; 60 locked packages resolved, 59 installed packages audited. |
| `uv run --offline --locked pytest tests/models` | 105 passed. |
| `uv run --offline --locked pytest` | 571 passed in 88.02 seconds. |
| `uv run --offline --locked ruff check .` | Passed. |
| `uv run --offline --locked ruff format --check .` | Passed; 117 files formatted. |
| `uv run --offline --locked pyright` | Zero errors/warnings. |
| `uv run --offline --locked python -m binfocheck.domain.export_schemas --check` | Schemas match; no wire-schema drift. |
| `git diff --check` | Passed. |

`uv lock --offline` updated dependency metadata before these checks. The initial
sandboxed lock command could not write the existing uv cache; the same repository
toolchain succeeded with approved cache access. Ruff format/fix and intermediate
test/type-check runs were also performed. Offline status: passed. Hosted PR checks
are reported separately in the delivery handoff; no hosted result is inferred here.

All tests are offline under the repository's network-denial fixture. No real credentials
are required. Development iterations corrected strict typing and tested recovery paths;
no shared test or requirement was weakened.

Coverage includes exact serialization and independent raw/semantic artifacts; linked
RunManifest/input/result validation; SQLite close/reopen and replay; required/optional
probabilities, rounding/ties; malformed JSON and wrong model identity; missing/partial
usage; refusals and incomplete generation; status errors and zero retries; authorization
mismatch; decreasing read deadlines/prefix preservation; failed writes before/after
dispatch; intent-only recovery; missing replay artifacts; schema no-network resolution;
secret-safe failures; frozen smoke hashes and no-credential smoke preparation.

The two offline smoke commands print `live_authorized=false` and succeeded:

```bash
uv run --offline --locked python -m binfocheck.models.live_check --provider jev
uv run --offline --locked python -m binfocheck.models.live_check --provider openai
```

Live: not run, explicitly unauthorized. Deployed: not applicable/not run. No actual
Jev/OpenAI requests or provider spend: request count 0, cost USD 0 for this assignment.
Synthetic usage numbers in fixtures are invented and never reported as actual usage.
Mocks prove wiring/validation, not access, live compatibility or accuracy.

## Frozen live-smoke proposals — NOT AUTHORIZED

Synthetic state: `Äpfel 🍎 sind rot.` No patient data or pilot monitoring query.
Choice asks which color the text names; generation asks to return the input unchanged
in `text`. These are transport smoke resources, not downstream business policies.
The exact bodies are committed in the fixture files, without trailing newlines.

| Field | Jev | OpenAI |
|---|---|---|
| Run | `t03-run-jev` | `t03-run-openai` |
| Task | `t03_choice_smoke` | `t03_generation_smoke` |
| Body bytes | 258 | 554 |
| Payload SHA-256 | `5075288ed5570c9fb31cf4cc11faad43756a7c8939022317691b58bcb67202dd` | `b339839d1641defee14f9ed486562795dafb6144bb9884c448a59f1602ded02c` |
| Work key | `4961ad5958656c3a53d5c2719550bc9d35131fd01f0c5e8b78422e93f653e810` | `57506f690a3fa57e71901f57df4c93a2fcc89183b067bcec117fe6c9a802e813` |
| Proposed cost ceiling | USD 0.01 | USD 0.01 |

The DecisionRecord IDs prefix these keys with `model-decision-` and `model-generation-`.
Request/resource/config instances are in each `smoke-domain-request.json`; exact
resource hashes are included there. The schema version is `t03-smoke-output/1`, prompt
`t03-smoke-prompt/1`, rubric `t03-smoke-rubric/1`.

Each proposal is exactly one POST, zero retries, concurrency one, timeout 60 seconds;
no additional model-list, token-count, billing or credential-probe provider requests.
There is no transfer between the two USD 0.01 allowances. Review exact payload hashes
and model identity, current public pricing, private store and a defensible input-token
upper allowance before obtaining explicit user authorization. Do not run `--execute`
or create an authorization file from this proposal alone.

Illustrative estimates at 2,000 input tokens: Jev USD 0.000084; OpenAI plus 512 output
at most USD 0.0016192 at listed standard uncached rates. An 8,192-token allowance plus
512 output yields USD 0.004096 for OpenAI. These allowances are estimates to substantiate
at live preflight, not measured token counts or a provider-enforced dollar limit.
Expected billed charge is unknown until reported. Any uncertainty/error consumes the
single allowance; a second request needs new user authorization.

After authorization, execute through the single-owner guarded transport, save one
contract-valid result from each adapter, close/reopen SQLite, verify returned pins,
raw/structured artifacts, actual usage where available and offline replay. Only then
can the required T03 live acceptance pass. Invalid/missing access cannot be replaced
by another model. Record provider request IDs, actual token counts, unreported cost
and separate estimates; no accuracy/calibration claim follows from these two calls.

## Limitations and remaining dependencies

- No T00 schema blocker remains with the receipt convention. Failure Outcomes cannot
  carry records, so failures are fetched by deterministic ID. Detailed usage/provider
  metadata belongs in receipts, not invented domain fields.
- Conservative schema subset rejects recursive/external references and unsupported
  keywords. It does not silently simplify schemas. The generation adapter expects
  one text document; additional provider output items are rejected.
- Execution is one process/owner per work key. No cross-process lease, exactly-once
  billing guarantee, orchestration or worker restart service is implemented; T11B owns it.
- T11A artifact and record writes are not one transaction. Bytes lost before storage
  cannot be reconstructed; missing receipts prevent full replay. Stored failed records
  remain inspectable; they do not erase prior results. No power-loss guarantee.
- Timeouts decrease at I/O boundaries, but DNS/internal header/TLS blocking may exceed
  the target; no hard process deadline is claimed. Recovery elapsed network time is unknown.
- Raw response is HTTP entity bytes after transfer framing, preserving content coding
  as received. Unsupported coding/oversize/interrupted payloads are failed/incomplete;
  never claim a saved prefix is the complete response.
- Authenticating an API and actually observing response/pricing compatibility remains
  a live dependency. Neither model has been called. D04 live authorization stays open.
- No business prompt/rubric, claim extraction, model benchmark, provenance inference,
  medical advice or other downstream feature was added.

## Official references

- [TypeSafe API](https://docs.typesafe.ai/api), [models/pricing](https://docs.typesafe.ai/models),
  [response/request-ID metadata](https://docs.typesafe.ai/sdk/python/api/types/responses).
- [OpenAI model snapshot/pricing](https://developers.openai.com/api/docs/models/gpt-4.1-mini),
  [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
  [Responses reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create),
  [authentication and request IDs](https://developers.openai.com/api/reference/overview).

Verified during the T03 planning/implementation session on 19 September 2026. No
third-party model gateway documentation is used as authority.
