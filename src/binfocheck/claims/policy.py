"""D07 extraction-only labels and mechanical policy. No provider imports."""

LABELS = {
    "B": ("factual", "nonfactual", "mixed", "uncertain"),
    "D": ("clear", "resolvable_from_context", "unresolved"),
    "H.faithfulness": ("faithful", "unfaithful", "uncertain"),
    "H.atomicity": ("atomic", "nonatomic", "uncertain"),
    "H.self_containment": ("self_contained", "context_dependent", "uncertain"),
}
GENERATIONS = {"C": "mixed", "E": "clarify", "F": "decompose"}
RUBRICS = {
    "B": "select-factual",
    "D": "ambiguity",
    "H.faithfulness": "faithfulness",
    "H.atomicity": "atomicity",
    "H.self_containment": "self-containment",
}
VALIDATIONS = ("H.faithfulness", "H.atomicity", "H.self_containment")
POLICY = {
    "version": "1",
    "context": "reference-cues-nearest-sentence-heading/1",
    "source": "exact-smallest-support-envelope/1",
    "ties": "unresolved",
    "accept": ["faithful", "atomic", "self_contained"],
    "boundary": "complete-durable-target-accounting/1",
    "retries": 0,
}
