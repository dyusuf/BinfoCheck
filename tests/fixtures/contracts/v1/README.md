# Synthetic contract fixtures — schema version 1

Every example here is synthetic and shareable. No provider response, captured
article, real model output, patient information or credential is included. URLs
are labels only and are never fetched.

- `records.json`: coverage for all 20 record variants, with invalid error type and
  message fragment, plus missing-data examples or an explicit applicability reason.
- `boundaries.json`: coverage for all 21 component/storage operations. Each has a
  valid request/result, invalid request/result with expected errors, and a typed
  unavailable-input failure. Unknown fields are deliberately invalid.
- `linked.json`: resolves the complete observation → claim → finding → review
  chain and additional corpus/retrieval/model records. Retrieval records are
  independent contract examples, not evidence that cited claims trigger retrieval.

The answer repeats `Äpfel 🍎 sind rot.`. The claim points to the second occurrence
(`26:35`, `unit-2`), not the first (`8:17`, `unit-1`). Article and excerpt text IDs
are separate, even though their synthetic content is identical. The artifact's
hash covers the UTF-8 text without a trailing newline. The generation artifact
contains `{}`. These are not realistic DataForSEO payload fixtures.

The corpus is explicitly incomplete: this one-page example does not satisfy
five-page pilot readiness. All model/version identities are synthetic placeholders.
Missing usage remains unknown; a separate test distinguishes known zero usage.
`review-2` corrects `review-1` without removing either or changing `finding-1`.

The invalid fixtures test local validation. Cross-record mutations, history
conflicts and quote mismatches are exercised by `tests/contracts/test_links.py`.
