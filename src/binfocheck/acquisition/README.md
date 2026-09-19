# T01 acquisition

`DataForSEOObservationProvider` implements the T00 `ObservationProvider` boundary
with injected `RecordStore`, `ArtifactStore`, `Transport`, policy and clock.
`replay_capture` takes only stores and a saved request ID; it cannot dispatch HTTP.
No source URL is fetched and no claim/citation association is computed here.

## Request and spending boundary

The fixed endpoint is `POST https://api.dataforseo.com/v3/serp/google/ai_mode/live/advanced`.
The body is a one-element JSON array with `keyword`, `location_name`,
`language_code="de"`, `device="desktop"`, `os="windows"`,
`calculate_rectangles=false` and a deterministic correlation `tag`.
Literal percent and plus characters are escaped for the documented provider decoding.
The tag is **not** a provider idempotency key. Settings reject unknown options.
German support still needs the separately authorized live check; there is no fallback.

Production transport uses stdlib HTTPS with Basic authentication from
`DATAFORSEO_LOGIN`/`DATAFORSEO_PASSWORD`. Credentials are secret-valued, never put
in records, headers receipts, fixtures or logs. HTTPS host/path are not configurable.
Redirects are not followed. The initial policy is one attempt, zero retries,
60-second timeout and a 16 MiB payload limit (configurable within bounded limits).
An explicit `LiveAuthorization` must bind approval and a verified price/cost ceiling
to the SHA-256 of the exact `request_body(request)` bytes. Credentials alone do not
authorize dispatch. The price is operator-verified, not a provider billing guarantee.
An uncertain POST consumes the attempt and is never automatically repeated.

## Raw data and normalization v1

Raw means the exact bytes delivered by HTTP transport after transfer framing and
gzip/deflate content decoding, **before** JSON parsing, normalization or reserialization.
These bytes are saved as a restricted T11A artifact before parsing, including error
and malformed JSON bodies. Truncated/oversized/undecodable transport responses fail;
they are not reported as complete captured raw payloads. The receipt separately
allowlists content-type, content-encoding, date, retry-after and x-request-id headers.
Other headers and outbound Authorization are not retained. Restricted is metadata,
not a user authorization system.

Both HTTP and envelope/task status codes are checked. Exactly one task/result and
the expected endpoint/product are required. Aggregate `ai_overview.markdown` alone
is canonical, verbatim, including Unicode, CRLF, trailing spaces and links. Child
text is never assembled as a substitute. Missing/blank answers are typed failures.

Captured references and link elements remain `reference` records with exact JSON
pointers. Captured reference `text` is preserved as an excerpt TextRecord and span.
An empty excerpt remains in raw data but has no nonempty SpanRef. Unsupported fields,
images, retrieval metadata and fan-out data stay in raw; fan-out is explicitly
unavailable and unsupported source structures make source capture incomplete.

Only a literal numbered provider marker `[[number]](URL)` in aggregate Markdown,
with the identical URL present in captured references, is recognized as an explicit
visible citation signal. Each occurrence gets its own exact answer span and record;
original reference records stay references. Ordinary links (including `[1](URL)`),
URL proximity, code/HTML/escaped markup, nested links and unmatched URLs do not
become citations. This is capture of visible markers, not routing citations to claims.
Positive citation capture remains incomplete because completeness is not established.
Available-empty requires an explicit empty supported reference structure and simple,
assessable answer representation. Missing source metadata is unavailable; ambiguous
or partial capture is incomplete. Unknown never becomes an asserted absence.

Provider task IDs, allowlisted HTTP request ID, envelope/task status, reported cost
and provider time are retained in the versioned receipt artifact. Top-level cost
and task cost are retained separately and not added together. Missing cost is null,
not zero; token usage is unavailable. Reported settings are an explicitly incomplete
provider-reported subset, not independently verified settings. No T00 schema changes.

## Persistence and replay limits

CaptureRequest is saved before dispatch. Existing request IDs refuse redispatch,
even in a new adapter instance. IDs derive from request ID, record role and exact
source location; replay uses the saved receive timestamp and normalization version.
Raw artifact and receipt precede normalized records. Offline replay checks the
recomputed receipt, fills partial normalized writes and preserves immutable IDs.
Failed captures also persist a failed Observation, while their Outcome has no value.

T11A does not offer a multi-artifact transaction or atomic dispatch claim. This is
a single-operator boundary, not an exactly-once concurrent scheduler. Recovery of
normalized writes is supported once raw and receipt are saved. If storage fails
before that recovery envelope is complete, replay returns a typed missing-data
failure; retain the response/receipt externally and complete persistence offline,
never silently issue another POST. No process-kill/power-loss guarantee is claimed.

## Separately authorized live check

Do not run until D03 spending authorization and final settings are recorded:

```bash
uv run --offline --locked python -m binfocheck.acquisition.live_check \
  --request /secure/capture-request.json \
  --authorization /secure/authorization.json \
  --policy /secure/capture-policy.json \
  --store /secure/capture-store
```

Inputs are the corresponding Pydantic JSON contracts. No approval/credential files
are committed. The command performs at most one POST, closes/reopens SQLite, replays
and checks observation equality, then reports IDs and usage. Exit 2 means the
capture succeeded but reported billing was unknown or above the approved ceiling.
There are no automatic retries in either the CLI or provider. Ordinary pytest
fixtures are synthetic, block sockets, and never run this live command.

Documentation inspected: [endpoint and response](https://docs.dataforseo.com/v3/serp/google/ai_mode/live/advanced/),
[status codes](https://docs.dataforseo.com/v3/appendix/errors/),
[languages](https://docs.dataforseo.com/v3/serp/google/ai_mode/languages/),
[AI response parsing](https://dataforseo.com/help-center/parse-google-ai-overviews-ai-mode).
