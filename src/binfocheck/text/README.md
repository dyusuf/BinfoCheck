# T02 answer indexing

`StoredAnswerIndexer` implements `AnswerIndexer`; `IndexedContextBuilder` implements
`ContextBuilder`. Both use the existing `RecordStore`/`ArtifactStore` protocols and
return typed `Outcome` values. They do not acquire, rewrite, render or classify text.

Pass an existing run, its observation and the observation's original answer ID in
`IndexRequest`, with `IndexSettings().envelope()`. The answer must be nonblank and
the observation successful. Default bounds: 100,000 characters / 10,000 units;
configurable up to 1,000,000 / 50,000. No writes occur for limit/configuration failures.

Index version `t02-text-index/1` pins spaCy **3.8.16**, blank German tokenizer and
rule-based Sentencizer. There is no downloaded model or statistical pipeline.
Offsets are Python Unicode code points in the original text, never token numbers,
bytes, rendered Markdown, normalized whitespace or searched-for quote positions.

## Bounded structure and sentence rules

ATX/Setext headings, paragraphs, flat ordered/unordered list items and indented
continuations are recognized. Structural spans retain original markup and interior
line endings. Sentence spans omit bullet prefixes and edge separator whitespace;
internal whitespace, Unicode, punctuation and attached link markers remain exact.
Blank-line gaps do not create records. Paragraph/bullet sentence parents actually
contain their children. Heading ancestry lives only in the manifest; heading units
have no heading pointer, while nonheadings point to the nearest preceding heading.

The small versioned rule layer protects common German abbreviations, numeric
decimals/dates, selected ordinals, balanced Markdown links (including T01 `[[n]]`
markers), escapes and inline code. It supplements spaCy's sentence candidates for
numeric endings and terminal `usw.`/`etc.`. It is deterministic, not a guarantee of
linguistic correctness for every abbreviation. Unsupported/malformed inline markup
stays one conservative sentence span. Bare URL punctuation is treated conservatively.

Tables, fences, raw HTML regions, block quotes, indented code and ambiguous/nested
lists remain opaque paragraph units without sentence children. This is not CommonMark
and does not infer visible citations. Opaque targets return their own reference;
sentence windows count sentences, not opaque blocks.

## Identity, publication and context

`index_reference_id(request, answer)` identifies a cohort using canonical sorted
JSON/SHA-256 over run, observation, answer ID/hash, configuration and spaCy version.
Unit IDs additionally include kind and absolute start/end. Global order is start,
descending end, kind rank, ID; unit timestamps use the immutable run creation time.
Repeated text at different locations stays distinct; identical re-indexing is idempotent.

The restricted JSON completion artifact records configuration, answer hash, ordered
unit IDs and hashes, heading hierarchy, opaque units and `complete` state. Publish
its metadata first, then all units, then its payload last. Missing payload/units
means incomplete, not a successful partial index. Retry the same offline indexing
operation to finish partial writes. T11A supplies immutability, not a cross-record
transaction. Unit provenance inputs are only observation and original answer IDs;
the output artifact is never a unit input.

Build `ContextRequest` with `ContextSettings(index_artifact_id=...).envelope()`.
Defaults: one sentence before/after, nearest headings included, clipping at heading
boundaries, maximum 200 output IDs. At most 20 targets; neighbor counts 0–10 and
output cap 1–1000. Paragraph/bullet targets expand to their sentence children;
heading targets select that heading plus its first sentence/window. Overlapping
windows deduplicate IDs, never copy neighboring text. Result order follows the exact
manifest cohort, not insertion order. All cohort hashes, spans, relationships and
observation/run membership are checked before returning references. Wrong/foreign
targets, missing data, corrupt graphs and limits are explicit failures.

## Saved-capture verification

`python -m binfocheck.text.verify_saved_capture --source-store PATH --observation-id ID`
first copies the **complete closed private store** to a new private temporary
directory. Only the copy is opened with SQLiteStore. The diagnostic creates a
zero-provider-budget reanalysis run and checks indexing, idempotency, original
records/citations, exact spans, linked validation and close/reopen context recovery.
Socket connections are blocked for the whole verification. The original's file
hashes, modification times and modes are checked before/after. This is not a backup
of a concurrently written store or a crash-recovery test. Keep the source quiescent.
The private copy stays outside Git for review; missing source is a failure, never a
reason to acquire another capture.
