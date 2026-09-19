# T01 live-acceptance handoff — 19 September 2026

Task: T01 only / Codex / live and offline acceptance passed.
Branch: `codex/t01-acquisition`. Draft PR #4 remains unmerged.
The one-call authorization is consumed; no further provider request is authorized.

## Scope and changed files

This live-acceptance turn changes only `docs/t01-handoff.md`,
`docs/implementation-plan.md` (T01 status), and `docs/architecture.md` (D03 result).
No runtime code, T00 wire schemas, storage implementation or dependencies changed.
No extraction, claim routing, source fetching, browser automation, API/UI or T02+ work.

Existing implementation lives in `src/binfocheck/acquisition/`: config, transport,
normalizer, receipt, persistence, replay, provider and gated live-check command.
Tests are under `tests/acquisition/`; synthetic provider fixtures remain under
`tests/fixtures/acquisition/dataforseo/`. Real payloads are not test fixtures.

Key prior commits: `774a953` implementation, `42d6d86` initial handoff,
`fbdef0c` correlation/budget fixes, `dae91d3` review verification,
`c41120f` empty environment template. Remote credential-loading/test fixes and
`4c464b3` one-call D03 authorization were synchronized before this live check.

## Preflight and authorization

Local branch was clean and identical to origin at `4c464b3`. Locked sync passed.
`Credentials.from_environment()` loaded the ignored local `.env`; only
`credentials_loaded=true` was printed. Existing environment variables retain
precedence. Credential values and Basic Authorization were never printed.

Official pages checked immediately before dispatch (19 September 2026, about
06:59 UTC):

- [Live Advanced endpoint](https://docs.dataforseo.com/v3/serp/google/ai_mode/live/advanced/):
  `POST https://api.dataforseo.com/v3/serp/google/ai_mode/live/advanced`.
- [AI Mode languages](https://docs.dataforseo.com/v3/serp/google/ai_mode/languages/):
  German `de` is listed.
- [Official AI Mode pricing](https://dataforseo.com/pricing/serp/google-ai-mode-serp-api):
  Live Mode USD **0.004** per SERP, below the approved USD **0.01** ceiling.
  Rectangles are disabled; no extra paid option was requested.

User authorization: `user-approved-t01-live-2026-09-19`.
Exact query: **Darf ich mit Diabetes Auto fahren?**

```text
location_name=Germany
language_code=de
device=desktop
os=windows
calculate_rectangles=false
timeout_seconds=60
request_limit=1
retry_limit=0
absolute_cost_ceiling_usd=0.01
verified_request_price_usd=0.004
```

CaptureRequest, LiveAuthorization and CapturePolicy were generated with repository
Pydantic contracts, not approximate handwritten schemas. Exact outbound bytes came
from `request_body(request)`; approval was bound to their SHA-256.

## Live result

| Field | Recorded value |
|---|---|
| Request ID | `t01-live-4073ed92129b4688bcc7fc3eb12983aa` |
| Created UTC | `2026-09-19T06:59:50.507753+00:00` |
| Received UTC | `2026-09-19T07:00:17.139442+00:00` |
| Request SHA-256 | `9a4a111fb86d50246d4816d662c50dadd12188556082b0b166dd8be01cfffda8` |
| Provider task/request ID | `09190700-2568-0139-0000-71062a999c01` |
| Observation ID | `capture-observation-1c8c8d29e92c00f7f5473716291a185cde1a5f21babfe89841b6aa6c9b857179` |
| Raw artifact ID | `capture-raw-84283f0831ef3021961aa4c936e37383a4db4ef7a0538c71d4776e28ceb1f1bf` |
| Raw SHA-256 | `6c76227409ba9f125b413520e0b16dca776af8168f7b5ecc74cedcc7934c756e` |
| Envelope cost / task cost | USD `0.004` / USD `0.004` |
| Budget verified | `true`; costs agree and are below USD `0.01` |
| Live command exit | `0` |
| Provider POSTs / retries | **1 / 0** |
| Raw decoded payload / answer | **15,935 bytes / 3,094 Unicode code points** |
| Saved records | **39** |
| Sources / citations | **23 source records, including 10 citation records** |
| Source / citation availability | `incomplete` / `incomplete` |
| Fan-out availability | `unavailable` |
| Reported language | `de`; no fallback |

One invocation of the existing live-check command was executed from repository root:

```bash
uv run --offline --locked python -m binfocheck.acquisition.live_check \
  --request /tmp/binfocheck-t01-live-NezU38O1/request.json \
  --authorization /tmp/binfocheck-t01-live-NezU38O1/authorization.json \
  --policy /tmp/binfocheck-t01-live-NezU38O1/policy.json \
  --store /tmp/binfocheck-t01-live-NezU38O1/store
```

Exactly one POST is evidenced by this single invocation, the fixed transport's
single request path with no redirect/retry mechanism, one response task and receipt
request count 1. No second provider command, task-status poll or provider GET was
issued. This is not a claim about provider-internal processing or exactly-once billing.

## Acceptance verification

All checks below passed using already-persisted local evidence:

1. CaptureRequest is the first stored record; capture code persists it before
   entering the transport (also covered by offline ordering tests).
2. T11A stored raw bytes after HTTP transfer/content decoding, before JSON parsing;
   artifact SHA-256 verifies. JSON reserialization was not used to store raw content.
3. Returned `task.data.tag` exactly matches the deterministic outbound tag.
4. Nonempty saved answer equals aggregate `ai_overview.markdown` character-for-character.
5. Explicit citation markers have exact answer spans; ordinary references stay
   references. Availability is conservative, not falsely asserted complete/empty.
6. Provider ID and both reported costs survive persistence; budget verification is
   true, with no summing or preference for a lower cost.
7. SQLite closes and reopens; offline replay returns the identical observation,
   answer and entire record set without duplicate records.
8. Replay verification blocks socket connections; no network request occurs.
9. `validate_links` passes on all 39 records.
10. An in-memory credential/Basic-token scan of local artifacts, store files,
    tracked repository files and Git diffs passed without printing secret values.
    Terminal output was limited to approved request metadata, IDs, counts, costs
    and boolean/status verification. No secrets or live raw payload are committed.

The audit script and machine-readable safe result are outside the repository:
`/tmp/binfocheck-t01-live-NezU38O1/verify_offline.py` and `verification.json`.
All request/authorization/policy/store files are in that private temporary directory.
The audit ran with:
`uv run --offline --locked python /tmp/binfocheck-t01-live-NezU38O1/verify_offline.py`
and exited 0.

## Repository verification

```text
uv sync --locked --dev                                    passed
uv run --offline --locked pytest tests/acquisition         128 passed
uv run --offline --locked pytest                          394 passed
uv run --offline --locked ruff check .                     passed
uv run --offline --locked ruff format --check .             passed
uv run --offline --locked pyright                          0 errors/warnings
uv run --offline --locked python -m binfocheck.domain.export_schemas --check
                                                          schemas match
git diff --check                                          passed
```

The full suite includes all 266 T00/T11A tests. Acquisition coverage includes raw
preservation, Unicode/exact spans, conservative citation states, missing answers,
HTTP/envelope/task errors, tag correlation, dotenv precedence, uncertain dispatch,
single-attempt guards, costs/tolerance/ceiling cases, restart and partial-write replay.
Ordinary tests use synthetic fixtures and blocked sockets, not the live capture.
Final remote CI commit/run links are recorded in draft PR #4 and the complete
`/tmp/handoff.txt` delivery record. No deployed check was required or run.

## Preserved normalization and limits

Aggregate Markdown remains canonical and unmodified. References retain exact JSON
locations and captured excerpts. Only supported explicit numbered markers grounded
to the answer create citations; there is no claim mapping or citation-fidelity claim.
Unsupported fields remain in raw. The live capture's source/citation coverage remains
incomplete and fan-out unavailable; token usage is unknown, not zero.
Normalizer diagnostics were empty; that does not imply exhaustive provider coverage.

Missing/mismatched tags fail with `response_correlation_failed`; unrelated task
data fields may be canonicalized/added. Budget verification uses both raw cost
fields, requires agreement within absolute `1e-9 USD` with zero relative tolerance,
and compares the maximum to the ceiling without a ceiling tolerance. Missing or
conflicting cost is not successful budget verification.

T11A has no multi-artifact transaction or concurrent atomic dispatch claim. Replay
repairs normalized writes once raw and receipt are saved; earlier storage failure
needs retained local evidence, never an automatic new POST. The live store is in
ephemeral `/tmp`; preserve it separately if long-term retention is needed. It must
not be committed. Restricted access metadata is not an application authorization layer.

D03 is resolved and exercised for this exact T01 capture only. No remaining T01
acceptance blocker was found. Future requests require fresh explicit authorization.
This verifies acquisition/persistence/replay, not medical accuracy, citation fidelity,
proven AI provenance, deployed behavior or any downstream task. Keep PR draft;
do not merge or start T02+.
