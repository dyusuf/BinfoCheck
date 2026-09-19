# Synthetic T06 fixtures

Authored for offline extraction/provenance testing. These are not captured diabinfo
articles and contain no clinical findings. `article.html` and its hand-authored
`article.txt` expected representation test German Unicode, references, nested lists,
collapsed FAQ content and page chrome. The expected file's terminal newline is file
formatting, not part of the cleaned article. Additional failure/layout variants in
`tests/corpus` are synthetic strings. URLs identify pilot slots only; tests never
fetch them. No parser selector is claimed to be verified against the live site.
