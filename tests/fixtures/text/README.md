# Synthetic T02 fixtures

`v1/sentences.json` is hand-authored German boundary gold data, not provider output.
Cases cover repeated emoji text, abbreviations, decimals/ordinals, terminal
abbreviations, LF/CRLF, NBSP/tabs, combining Unicode, ZWJ emoji, Markdown links and
numbered T01 markers, emphasis, quotes, malformed markup and inline code.
Expected sentence content is literal; tests recover it by absolute offsets with
a prefixed Unicode string, without searching for the expected quote.

Structure/context/storage fixtures in `tests/text/` add headings, flat bullets,
opaque complex blocks, cross-observation/cohort rejection, immutable retries,
partial publication, graph corruption and reopen recovery on both T11A backends.
The T01 synthetic acquisition fixture is also normalized and indexed offline, with
its original citation spans checked unchanged. Real T01 data is never a Git fixture.
