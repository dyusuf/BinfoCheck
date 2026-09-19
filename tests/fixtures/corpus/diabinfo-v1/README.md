Authored synthetic markup only; no copied live HTML or medical source paragraphs.
The tiny article and FAQ fragment reproduce the observed four-root TYPO3 layout,
TOC, nested lists, credits, stock-image gallery, audio-only promotion, news/sidebar,
references and button/h2/ARIA-linked collapsed FAQ answers. Text is invented.

Tests also synthesize an informational-image variant: it must stay unusable, not
be stripped as a stock photo. The hidden mail marker and scoped callout headings
are covered without loading any real captured body.

`decorative.html` and `podcast.html` are minimal hand-authored pattern fixtures.
Their exact reviewed public metadata matches the positive signature registry; they
contain no captured page body or actual image/audio bytes. The earlier article
fixture intentionally retains its fake media for historical parser-3 regressions.
New-profile tests remove those fake media and insert these explicit cases.
