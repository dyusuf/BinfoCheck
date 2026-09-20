# T05 citation mapping

`StoredCitationMapper(records, artifacts).map_citations(ClaimRequest)` implements
T00's unchanged `CitationMapper` boundary using T11A stores. It returns a persisted
`CitationAssociation` or typed failure. Mapping is deterministic; it neither calls
models/retrieval nor fetches sources. Category 1 establishes citation presence only,
not source support, medical truth or AI provenance.

## Inputs and configuration

Use `CitationSettings(index_artifact_id=...).envelope()` as the request settings.
Supply the exact completed T02 index from the Claim's run. The mapper validates the
entire cohort, original spans, claim context membership, linked records and artifact
bytes. `Claim.original_span` is authoritative, not normalized wording. Unknown IDs,
corrupt artifacts, invalid spans, foreign runs/cohorts and bad settings are failures,
not missing citation evidence. The original span must contain non-whitespace text.

`rules_v1.json` and `config.VERSION` pin `t05-citation-mapping/1`. Its SHA-256 covers
canonical JSON rules, scope/host/audit versions, wire schema 1 and contract validation
1.1. Config changes require a versioned approved decision when they change policy;
request settings cannot override the allowlist or silently select different rules.
There are no new dependencies or shared schemas.

## Captured evidence and scope

Only citation-kind records in the observation's captured citation list can establish
presence. Current supported semantics are `dataforseo-ai-mode-normalizer/1`: exact
`[[number]](URL)` spans in saved aggregate Markdown, backed by exact captured reference
URLs and raw JSON pointers. Pointers and artifact bytes are checked locally. A marker
span is not a provider-declared claim scope. References, excerpts, ordinary links,
search results and proximity alone never become citations. Unknown normalizers or
optional missing marker locations retain uncertainty. Invalid declared metadata/spans
fail. Image/nested marker contexts are not established T01 citation syntax.

Inference uses stored T02 sentences and paragraph/bullet parents:

- One terminal citation group in a supported non-final sentence attaches to that
  sentence. A group in a single-sentence block also attaches to that sentence.
- A terminal group at the end of a multi-sentence paragraph/bullet is ambiguous
  across that block, including its last sentence. It is never assigned to every claim.
- Leading/internal/multiple separated groups, opaque or unsupported markup retain
  uncertain scope. Unlocated evidence can affect any claim; ambiguity demonstrably
  restricted to another block does not affect this claim.
- Consecutive markers form a group only across SPACE, TAB or NBSP. After a terminal
  group, only whitespace and `. ! ? … " ' ” ’ » “` are permitted. Semicolons, colons,
  bracket closers and arbitrary punctuation are not treated as terminal suffixes.
- After excluding captured marker spans, `[ ] < >` backticks, backslashes, `|`, `*`
  and `_` make a sentence unsupported. Thus even emphasis markup is conservatively
  unclear in v1. T02's single conservative sentence for malformed markup is not
  evidence of supported citation scope. Original text is never stripped or rewritten.

Association uses interval containment. A claim inside a clearly cited sentence
inherits its sentence-level citation. Different claims sharing a span keep separate
results. Every non-whitespace code point of a multi-sentence original span must be
covered by clear target-cited scopes for `yes`; partial coverage is `unclear`.
Context neighbors/headings cannot expand citation scope. These mechanical rules are
not a citation-quality benchmark or proof of semantic support.

## Status precedence and routes

After integrity validation:

1. Clear full target-citation coverage -> `yes`, even with incomplete global capture.
2. Otherwise incomplete/unavailable citation capture -> `unclear`.
3. Otherwise uncertain relevant scope/hostname, unsupported claim scope or partial
   target coverage -> `unclear`.
4. Otherwise assessable complete capture -> `no`.

`scope_assessable` is true for yes/no and false for unclear. Source-list or excerpt
availability never substitutes for citation completeness. Current T01 captures with
markers are incomplete: other-source-only evidence in those captures is still unclear.
Supported complete-empty and assessable complete other-source-only fixtures return no.

`citation_route(status)` returns `category_1`, `matching` or `citation_unclear` without
executing another component. No Finding/classifier, metrics or pipeline is implemented.
Unclear never enters definitely-uncited counts. Processing failures remain failures.

Associations retain exact claim/marker/scope spans, establishing or relevant reference
IDs, a stable reason code and rule version. The audit retains all considered citation
assessments, including host and scope exclusion reasons. Ordinary references remain
in immutable input lineage. Repeated marker occurrences are not deduplicated by URL.

## Hostnames

Only exact `diabinfo.de` and `www.diabinfo.de` are allowed; no wildcard subdomains.
Parse HTTP(S) authority, lowercase ASCII hosts, remove one trailing ASCII dot, validate
explicit numeric ports in 1..65535 and compare hostname independently of port.
The original URL remains unchanged.

Userinfo, controls/whitespace, backslashes, percent-escaped authority, malformed ports,
empty labels, bracketed authorities, non-ASCII hostname/U-labels and invalid IDNA are
unassessable. Checks precede parser cleanup. ASCII A-labels must roundtrip through the
stdlib IDNA codec, but are compared literally; decoded Unicode never enters the
allowlist. No Unicode compatibility folding is used to trust a hostname. Unlisted
true diabinfo.de subdomains are unclear pending an explicit configuration decision.
Lookalike prefixes/suffixes and diabinfo text in another host's path/query are non-target.
No DNS resolution or redirects occur.

## Persistence and replay

The work identity hashes the exact request (including config digest), same-run claim,
observation/answer, captured metadata/availability, complete T02 cohort and all reachable
input record/artifact hashes. References are ordered by marker position then ID.
Result timestamps use the immutable run creation time. Configuration and input-manifest
artifacts are restricted and pinned in association input IDs.

After graph validation, publication writes audit metadata, association, then audit
completion payload LAST. The audit embeds the shared result plus request, input hashes
and per-reference assessments. Exact-ID replay verifies original inputs, completion,
result identity/configuration and linked artifact bytes, then returns the saved result
without running scope inference. It does not select a latest record. Identical offline
retries complete partial writes; missing completion bytes are not success. Corrupt data
and immutable conflicts fail without overwriting originals. T11A is not a multi-record
transaction, worker lease or crash/exactly-once guarantee.

The association uses the existing Claim analysis run. The mapper does not rewrite the
run manifest or require its top-level configuration to equal the T05 component config.
A new analysis run requires coherent upstream claims in that run; T05 neither clones
nor re-extracts claims. Rule changes cannot bypass the shared same-run boundary.

## Verification and real-pair dependency

```sh
uv run --offline --locked pytest tests/citations
uv run --offline --locked pytest tests/contracts tests/acquisition tests/text tests/claims tests/storage
scripts/verify.sh
```

Fixtures are synthetic; tests deny network, cover both T11A backends and never satisfy
the genuine observation/claim gate. No real T04 Claim exists in the inspected durable
T04 live-gate store. T05 real-pair acceptance is BLOCKED; no T04 call is authorized here.

Once genuine saved completed T04 output exists, use:

```sh
uv run --offline --locked python -m binfocheck.citations.verify_saved_pair \
  --source-store /private/quiescent-store \
  --claim-id ACTUAL_CLAIM_ID \
  --index-artifact-id ACTUAL_SAME_RUN_T02_INDEX \
  --extraction-audit-id ACTUAL_T04_FINAL_AUDIT
```

The diagnostic copies the complete private quiescent store before SQLiteStore access.
It requires claim membership/accounting in a completed T04 FinalAudit, saved generation
and positive validation evidence, T03 dispatch receipts and byte-only replay, and T01
saved-capture replay. It never runs extraction or invokes an adapter/model. Origin must
be genuine retained evidence; structural checks cannot authenticate an invented store.
Then it maps in the existing run, validates links, closes/reopens, checks replay and
unchanged originals, and verifies source fingerprints. Sockets and DNS are blocked.
The private copy remains in /tmp for inspection; preserve it durably if used as evidence.
A missing claim is an explicit blocker, never replaced by a synthetic claim on real text.
No live/deployed check, accuracy result or durable real integration is claimed.
