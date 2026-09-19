# T01 implementation handoff — 19 September 2026

Task: T01 only / Codex / offline implementation complete; live acceptance blocked.
Branch: `codex/t01-acquisition`. No merge authorized. No live provider call made.

## Scope and files

Architecture acquisition/shared contracts/storage/D03; domain wire schema v1 and
validation v1.1 unchanged, storage schema v1 unchanged. T00/T11A build dependencies
are present. `python-dotenv` is added solely to load an optional local `.env`; real
environment variables retain precedence (`override=false`). No extraction, source fetching, claim routing,
browser automation, other AI-search product, scheduling, API/UI or T02+ behavior.

- `src/binfocheck/acquisition/{__init__,config,errors,transport,receipt,normalize,
  persistence,replay,dataforseo,live_check}.py`: injectable single-attempt provider,
  exact decoded raw artifacts, conservative normalization, receipt and offline replay.
- `src/binfocheck/acquisition/README.md`: rules, limits, gated future live-check usage.
- `tests/acquisition/{__init__,conftest,helpers,test_normalize,test_capture_replay,
  test_transport,test_review_fixes}.py`: offline fixtures, no-network guard and acceptance tests.
- `tests/fixtures/acquisition/dataforseo/{success.json,README.md}`: labeled synthetic
  provider-shaped payload, not a saved real capture or clinical content.
- `docs/architecture.md`, `docs/implementation-plan.md`, this handoff: minimal D03
  implementation/status notes, without expanding architecture.

## Contract behavior

CaptureRequest is validated and saved before dispatch through T11A protocols.
The fixed Google AI Mode endpoint receives one task, with no silent product/language
fallback. Basic-auth secrets stay in transport memory/environment, not stored settings.
One attempt/zero retries applies even to uncertain dispatch. Existing request IDs
refuse re-dispatch; new authorized captures need new IDs. No provider idempotency
or cross-process exactly-once guarantee is claimed.

Pre-live review fixes: successful normalization now requires object-valued `task.data`
and an exact returned deterministic request tag. Missing/mismatched tags fail with
`response_correlation_failed`; provider-added/canonicalized unrelated fields are
allowed. Outbound and validation paths share the tag helper. The synthetic fixture
contains the expected tag; tests of distinct captures use their own matching tags.

Raw response bytes are saved after normal HTTP transfer/content decoding and before
JSON parsing/reformatting. Allowlisted HTTP metadata lives separately in a versioned
restricted receipt artifact. Replay consumes the stored bytes, original timestamp
and version; normalized IDs derive from request ID, role and source location.

Only aggregate `ai_overview.markdown` supplies the answer, preserving exact Unicode,
CRLF and whitespace. Missing/blank aggregate answers fail; child text is not a fallback.
References retain exact JSON pointers and captured excerpts. Ordinary provider refs
and Markdown links remain references. Only supported explicit `[[number]](URL)`
markers with an exact captured URL create separate citation records at exact answer
spans. Positive capture stays incomplete; empty requires an assessable representation;
missing metadata is unavailable. Code/HTML/escaped/ambiguous markup never creates
citations. Unknown fields remain in raw data; fan-out is unavailable, not empty.

Both provider envelope and task status are evaluated, alongside HTTP status. Auth,
access/billing, rate limit, provider errors, malformed/incomplete bodies, absent answers
and uncertain dispatch return typed failures, not successful empty observations.
Error bodies are retained when delivered completely by transport. Task/HTTP request
IDs, reported cost and provider time are retained; missing cost is null, zero remains
zero, envelope/task costs are not added, and token counts are unknown.

Budget verification now uses both receipt costs, not preferential `usage.cost`.
Neither known fails; one known is compared to the ceiling; both known must agree
within absolute `1e-9 USD` (zero relative tolerance). The maximum must not exceed
the ceiling, with no ceiling tolerance. Disagreement or unknown/over-ceiling cost
returns CLI exit 2 and `budget_verified=false`. Both raw reported values remain
unchanged in the receipt and are included in the CLI report. No wire schema changes.

## Fixture coverage and local verification

Commands actually run successfully:

```text
uv sync --locked --dev
uv run --offline --locked pytest tests/acquisition         126 passed
uv run --offline --locked pytest                          392 passed
uv run --offline --locked ruff check .                     passed
uv run --offline --locked ruff format --check .             passed
uv run --offline --locked pyright                          0 errors/warnings
uv run --offline --locked python -m binfocheck.domain.export_schemas --check
                                                          schemas match
git diff --check                                          passed
```

Full pytest includes the unchanged 266 T00/T11A tests (90 storage). Synthetic cases
cover exact payload and answer replay; SQLite close/reopen; repeated markers at
different Unicode offsets; excerpts/pointers; distinct availability states; missing,
blank, malformed and inconsistent bodies; HTTP/envelope/task errors; task IDs and
missing/zero/positive usage; gzip/deflate and transfer-decoded payload handling;
authorization/hash/attempt guards; uncertain dispatch with no retries; saved request
before dispatch and saved raw before parse; immutable idempotent replay; and repair
of partial text/reference/observation writes without another provider call.

Review regression coverage adds matching/missing/wrong/non-object task tags, extra
task data fields, typed failure replay, and 13 mocked-transport CLI budget cases:
equal costs, envelope-only, task-only, both missing, disagreements in both directions,
over-ceiling values, tolerance boundaries (without relaxing the ceiling), and zero.
These tests close/reopen SQLite and verify preservation of both receipt costs.

Transport tests replace HTTPS connections, and acquisition tests block socket
connections. Initial transport assertions needed a test-only correction to match
sanitized error messages; the final checks above all pass. CI uses the existing
offline quality workflow; final remote run/commit details belong in the draft PR
and delivery handoff. No live or deployed checks were run.

Pre-live review fix commit `fbdef0c` passed the complete GitHub Actions offline
quality workflow: [CI run 35426404505](https://github.com/dyusuf/BinfoCheck/actions/runs/35426404505).
Local review rerun: 126 acquisition tests passed in 21.16s and 392 total tests in
48.40s. Initial review checks found a test-double type annotation and import spacing
issue; both were corrected, and final Ruff, Pyright, schema and whitespace checks
passed. The subsequent handoff-only commit's final CI status is recorded in draft
PR #4 and `/tmp/handoff.txt`. No live API request or merge was performed.

## Limits and remaining D03 requirements

- T01 is not accepted until one separately authorized Google AI Mode live capture
  is persisted through T11A and successfully replayed. Actual provider calls: **0**;
  actual provider spend from this work: **none**. Fixture costs are synthetic.
- Confirm credentials/account access, exact non-patient question, location,
  language `de`, desktop/windows, timeout, one-request/zero-retry policy and explicit
  USD cost ceiling after verifying current price. The German documentation
  discrepancy remains for live verification; there is no English fallback.
- The live-check command requires request, policy and request-hash-bound approval
  files plus environment credentials. It makes at most one POST, closes/reopens
  storage, replays and checks reported billing; unknown/conflicting/over-ceiling cost is not a
  verified budget success. Credentials alone are not spending permission.
- The endpoint does not establish exhaustive visible-citation capture or fan-out
  completeness. Unsupported fields are raw-only, never inferred.
- T11A has no multi-artifact transaction. Once raw and receipt are saved, partial
  normalized writes are recoverable by offline replay. Failure before that envelope
  is saved returns typed missing-data/storage errors; an externally retained response
  is needed to finish persistence, not a repeated POST. No crash-durability or
  concurrent exactly-once orchestration is introduced.
- T00 has no observation usage field; the adapter receipt artifact retains usage
  without adding a duplicate domain record or modifying authoritative schemas.

Stop before downstream work. Draft review only; do not merge.


## Local credential loading update

T01 now depends on `python-dotenv>=1.2,<2`. `Credentials.from_environment()` loads an
optional `.env` from the process current working directory before reading
`DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD`, with `override=false` so existing
server/shell environment variables win. `.env` remains git-ignored and the committed
`.env.example` contains empty placeholders only. No credential values are committed.
