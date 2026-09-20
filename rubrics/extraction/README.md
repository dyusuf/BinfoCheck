# Extraction decision rubrics

Version 1 covers selection, ambiguity and three independent validation properties.
The exact labels and criteria are in the five JSON files. Jev resources have only
`instructions` and `criteria`; hashes are pinned by `prompts/extraction/v1/manifest.json`.

A selected maximum tied with another label remains unresolved; there is no calibrated
threshold. Missing or malformed probabilities are failures. Faithfulness checks
qualifier retention and the smallest defensible original support, not medical truth,
citation fidelity or causal provenance. Atomicity does not license dropping conditions.
Self-containment must hold in the candidate wording itself.

These rubrics are approved implementation settings, not measured model quality.
Live use requires separate exact-request authorization and available generation access.

Version 2 changes only ambiguity (D). Reference means linguistic/anaphoric reference,
not citations. No necessary unresolved reference and generic reader address with
irrelevant identity are clear; missing context alone is not unresolved. Supplied
context must uniquely resolve a necessary referent for `resolvable_from_context`;
meaning-critical unresolved referents alone justify `unresolved`. B and H retain
v1 bytes. The v2 manifest pins the new D rubric and all unchanged v1 resources.
V1 remains available for historical replay. This offline change authorizes no calls.
