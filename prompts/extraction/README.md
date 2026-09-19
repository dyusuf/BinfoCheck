# Extraction resources (T04 / D07)

Version 1 implements the approved extraction-only policy. The manifest in `v1/`
pins exact prompt, output-schema and rubric bytes by SHA-256; resource loading fails
on a mismatch. All examples and test responses are synthetic. None are evidence of
accuracy or reproduction of Claimify performance.

Generation prompts cover mixed-content rewriting, reference clarification and atomic
German decomposition. They prohibit external facts, question-premise injection and
instructions embedded in source text. Original support is exact and minimal;
`required_support` can extend an anchor to include an indispensable qualifier.

The output schemas describe untrusted stage proposals, not shared Claim/ExtractionIssue
contracts. They were generated from the T04 payload types in `claims/artifacts.py`
with the redundant `minLength` keyword removed from ID strings for T03's supported
schema subset. Pattern validation remains. Business cross-field validation is separate.

Do not change bytes under a released version. Freeze a new version and update the
manifest, policy/configuration and consumer fixtures when behavior changes. No T05,
T08, T09 or T10 resource is selected here. No live authorization is supplied.
