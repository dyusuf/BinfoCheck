# T06 corpus ingestion

Offline implementation only. **No diabinfo page or robots.txt has been fetched.**
The five URLs in `config.URLS` are fixed. T06 live acceptance remains outstanding;
synthetic readiness proves wiring and extraction invariants, not real-page usability.

## Interfaces and usage

`StoredCorpusIngestor` implements the shared `CorpusIngestor` interface using
`RecordStore` and `ArtifactStore`. `ingest` only replays saved snapshots; it cannot
fetch. Supply `IngestionRequest(urls=URLS, settings=ReplaySettings(
batch_artifact_id=...).envelope())`. Optional parser configuration and predecessor
IDs are frozen in these settings. `load(manifest_id)` verifies completion and all
saved dependencies, reconstructs text/structure/passages offline and checks links.

`SnapshotCapture` is separate and takes an injected transport. Offline tests use a
synthetic transport and fake clock. `HttpsTransport()` denies live requests by
default. A later explicit operator authorization must supply a batch-bound
`LiveAuthorization` with the explicit approval reference, batch ID and required
`policy_sha256`. The digest is SHA-256 of canonical JSON containing format
`t06-live-authorization/1`, the robots URL, the ordered five page URLs and every
`FetchPolicy` field. Copy the digest recorded in the explicit approval; do not
recompute it to refresh an old authorization. Capture checks it before writing the
start marker, and HTTPS checks it before each dispatch or request-counter increment.
Mismatch returns `live_policy_not_authorized`. The offline `proposed-policy`
command prints this digest with `authorized: false`; it grants no permission.
This implementation instruction supplies no live authorization.
Capture saves a start marker before dispatch and refuses a second invocation for
that batch ID, including after an uncertain interruption. Replay never refetches.
The API is intended for one capture caller, not concurrent capture workers.

Offline CLI (does not expose a capture command):

```sh
uv run --offline --locked python -m binfocheck.corpus proposed-policy
uv run --offline --locked python -m binfocheck.corpus replay --store /private/store --request /private/request.json
uv run --offline --locked python -m binfocheck.corpus inspect --store /private/store --manifest CORPUS_ID
```

The request file is a serialized shared `IngestionRequest`. Inspection prints
status/provenance/counts, not executable HTML. Nonready corpora and failures exit 1.
The configured store must meet T11A private directory permissions. Do not put real
snapshots into Git. All saved artifacts use restricted access; the authored fixture
files in `tests/fixtures/corpus/v1` are shareable synthetic material.

## Frozen proposal for later live authorization

`FetchPolicy` is fixed: one robots GET plus five article GETs, maximum six dispatches,
zero redirects/retries, concurrency one, two seconds minimum request spacing,
longer applicable robots delay/rate respected. Connect timeout 10 s, read timeout
20 s, request deadline 30 s, batch deadline 900 s. The connection watchdog also
interrupts a slow response at the request deadline. System DNS resolution occurs
inside the standard-library connection operation and is subject to OS resolver
behavior; Python's socket timeout cannot forcibly interrupt that resolver. No
hard real-time OS/DNS guarantee is claimed.

Only the exact HTTPS URLs and robots.txt on `www.diabinfo.de` are permitted.
User-Agent `BinfoCheck-T06/1.0`, German Accept-Language, identity Accept-Encoding;
no cookies, credentials, browser, assets, independent searches or link following.
Bounds: 512 KiB robots; 5 MiB each for received and content-decoded page bodies;
1,000,000 cleaned code points; 20,000 blocks; 100,000 DOM elements; depth 80.
All request attempts consume budget. No paid calls or models; provider cost ceiling
USD 0. This configuration is a **proposal, not authorization**.

Robots 404/410 permits the batch; an unavailable/unassessable policy blocks it.
Unsupported delay/rate syntax fails closed instead of silently ignoring a limit.
Robots disallow skips the affected page. 429/503 stops the remaining host requests.
Redirects are recorded but never followed. Missing bytes, unsupported encodings,
truncation and bounds have explicit failure states. There is no automatic retry
or recovery fetch; save/replay what arrived, then seek a separately bounded retry
instruction if needed. T11B execution is not part of this module.

## Bytes, charset and provenance

`ArticleVersion.raw_artifact_id` identifies the **complete HTTP content-decoded
HTML body bytes before charset decoding**, and `content_sha256` hashes those exact
bytes. `http.client` already removes transfer framing. Encoded gzip/deflate bytes,
when present, have a separate receipt artifact; partial bytes also have a separate
artifact and never become the article's raw artifact. Every artifact has its own
SHA-256, checked by T11A and replay. These are body snapshots, not packet captures.

Transport receipts record URL, ordinal, batch, UTC start/end, dispatched flag,
status, safe response headers, omitted header names, byte counts, body/encoded/
partial artifact IDs, completeness and errors. Header values outside the allowlist
are not saved. Input bodies are immutable and treated as untrusted.

Charset policy: BOM, explicit HTTP declaration, HTML meta declaration within the
first 4096 bytes, then strict UTF-8 fallback. Conflicting or unsupported declarations
and invalid bytes are rejected, never replaced. Supported codecs: UTF-8, UTF-16,
explicit UTF-16 endian variants, Latin-1 and Windows-1252. This is a documented
bounded decoder, not the browser's full encoding-sniffing specification. Raw text
preserves its decoded characters/line endings; a UTF-8 BOM remains U+FEFF and a
UTF-16 BOM is consumed by the codec.

Raw `TextRecord` directly references the raw artifact with no transformation.
Cleaned text has a separate UTF-8 artifact and descends from the raw text through
the hashed parser configuration. Every span uses shared Unicode-code-point,
half-open `SpanRef` values. `source_unit_id=None`: observation TextUnit and
SourceReference contracts are not reused for articles. No T00 schemas changed.

## Bounded extraction and passages

Pins: Beautiful Soup **4.15.0**, explicit **html5lib 1.1**, and
**llama-index-core 0.14.24**. Runtime/replay checks reject version drift. Exact
transitive dependencies are in `uv.lock`.

The default root is a unique `article` element. Multiple explicit, nonoverlapping
roots can be configured and are traversed in DOM order. Actual site selectors are
**unverified** until the later authorized five-page capture. There is no body-wide,
longest-text, readability, relevance or generic crawler fallback.

Supported blocks are h1–h6, paragraphs/captions, ordered/unordered nested lists,
preformatted text, explicitly configured FAQ headings and details/summary. Layout
wrappers are bounded and collapsed HTML FAQ answers remain included. A unique h1
and nonempty body are required; declared non-German language and known error-page
titles are unusable. Missing language metadata remains unknown. This is not a
complete challenge/soft-404 detector: inspect every saved page before live acceptance.

Versioned selectors remove navigation, scripts/styles, forms, consent, breadcrumbs,
share tools, local TOC and related-page widgets. Reference/source/footnote/meta/advice
blocks are protected against overlapping removal. Article footer/aside elements
are not blanket exclusions. Unrecognized essential structures (including tables,
definition lists or media in this profile) and unwrapped content produce an
explicit unusable result, never silent omission. Extend only for a required saved
pilot structure with a versioned rule and fixture; do not build a general web parser.

HTML layout whitespace collapses outside preformatted text; explicit breaks remain
line breaks. Entities decode, meaningful NBSP/Unicode/qualifiers are retained, and
inline tags do not split words. No language normalization or rewriting occurs.
Synthetic list markers preserve explicit start/value numbering and nesting; unusual
numbering styles/reversed lists are currently rejected. Original DOM locators are
cached before removals. Anchors retain exact cleaned spans, original href and a
page-relative resolved target. A foreign HTML base is recorded but not trusted;
unsafe/malformed targets remain inert metadata. Nothing follows article links.

Each natural paragraph/list/pre block is a passage; an immediately preceding
colon-ended paragraph is grouped with its list in the same section. No sentence
or token windows, overlap, arbitrary chunking, or copied heading prefixes.
Headings/section ancestry are span references; nested lists remain whole.
Parent passage pointers are null because sections live in the structure companion.

Structure artifact `<article-id>.structure.v1` records shared spans, block kinds,
heading levels/parents/section ends, list depth/markers, links, roots, original DOM
locators, excluded subtrees, language availability, charset and parser provenance.
It supplements domain records using T11A; it is not a duplicate domain schema or
new record kind. Exact spans refer to cleaned article text, not raw HTML bytes.

## Identity, storage and outcomes

Canonical sorted UTF-8 JSON/SHA-256 and record-kind prefixes identify derived
records. Capture batch identity/times are frozen before dispatch; replay timestamps
come from receipts. Article IDs pin immutable receipt ID, parser/config hash and
explicit predecessor. Text and body artifacts are content addressed. Passage IDs
pin article/construction version/order/offsets. Manifest IDs pin the batch and exact
ordered members/construction/status. Equal replay is idempotent; fresh captures
have new receipt/article identities even for identical bytes. Old versions are
never updated. Changed parser configuration makes a new derivation; explicit prior
IDs keep same-URL, acyclic history. Segmentation version is separately pinned.

Write artifacts/text/articles/structure/passages first, validate/read back the
closed dependency graph, publish `<manifest-id>.completion.v1`, then write the
manifest last. Completion records settings and member hashes/artifact IDs. Loading
checks both publications and every member, including raw bytes/cleaned text and
reconstructed structure. A partial write cannot load as ready. T11A has no multi-
record transaction; orphan immutable artifacts are possible. Retry offline replay
with the same inputs, never refetch. No deletion, garbage collector or crash/power-
loss guarantee is introduced.

`ready` requires one usable article and passages for each of the exact five URLs.
`incomplete` means 1–4 usable pages; `failed` means none. Per-page `failed` denotes
acquisition failure; `unusable` denotes saved HTML that cannot be completely
interpreted under the profile. These never become negative overlap findings.
`Outcome.succeeded` can contain a nonready manifest: recording the page outcomes
succeeded. Configuration/storage failures return failed Outcome without a partial
value, retaining already saved artifacts for audit/replay.

The LlamaIndex adapter uses one explicit mechanical transform producing TextNodes
from exact precomputed spans. It verifies ID/text/offset/source round-trip and
embedding=None, with no vector store/docstore/cache, default transformations,
model extractors, indexes or model settings. Core brings transitive NLTK/tiktoken/
SQLAlchemy packages; T06 invokes none of their model/resource/indexing functions,
downloads no linguistic resources and creates no SQLAlchemy database.

## Verification and next live gate

Run the repository checks and `pytest tests/corpus`. Tests are synthetic with
network blocked, covering parser expected output, Unicode and repeated locations,
transport policy, byte/charset handling, exact identities, failure states,
publication interruptions, SQLite reopen, offline replay and model-free adapter.
Mocks are not live integration proof.

Before later T06 acceptance: obtain the frozen bounded public-fetch authorization;
capture robots and all five pages into the private T11A store once; inspect saved
HTML offline to select/verify the bounded site profile; replay without requests;
inspect full text/headings/lists/references for each page; validate every slice,
reopen and replay with sockets blocked; report all actual snapshot IDs/hashes,
times/statuses/request counts and any missing pages. Do not label T06 accepted
until all five are usable. T07 remains outside scope.
