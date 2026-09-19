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
