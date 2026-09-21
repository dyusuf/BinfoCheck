# T04 Stage-D Jev review — 20 September 2026

Reviewed HEAD `9b4a5d135228f594e0225fec58776c8062f0c4c4` using the globally installed
TypeSafe skill (`/home/ubuntu/.agents/skills/typesafe-ai/SKILL.md`) and current
[Choice](https://docs.typesafe.ai/primitives/choice),
[state](https://docs.typesafe.ai/concepts/state),
[question](https://docs.typesafe.ai/primitives) and
[confidence](https://docs.typesafe.ai/confidence) documentation. The index/Markdown
endpoints were unavailable; the normal documentation pages were readable.
This is an offline design/code review, not a new Jev judgment or quality measurement.

## Findings and bounded fixes

**The three choices describe one coherent judgment.** For the referents necessary
to understand the target: `clear` needs no resolution beyond the source/working
text; `resolvable_from_context` requires at least one necessary external resolution
and uniquely supplied support for all necessary referents; `unresolved` means at
least one remains missing or ambiguous. These definitions are mutually exclusive
and cover the intended reference-resolution question. Jev's Choice primitive fits
this routing decision. Uncertainty in the model's distribution is separate from
an unresolved referent; existing maximum/tie/failure handling is unchanged.

V2 explicitly excludes citations, URLs and source-support quality from “reference.”
No-reference cases are clear. Formal reader `Sie/Ihnen/Ihr` does not need a named
identity when the assertion is addressed generically to its reader; this is not an
exemption for third-person pronouns or meaning-critical specific identities.
Missing context alone does not imply ambiguity. Irrelevant or ambiguous supplied
context cannot justify `resolvable_from_context`. A partially resolved set of
necessary referents remains unresolved.

**Field targeting was implicit.** The rubric referred to source/working text and
context without identifying the actual JSON fields. Current question guidance
recommends explicit field paths and complete meaning in instructions, independent
of the question ID. D v3 therefore adds a direct question and identifies
`source.text`, optional `working_text`, `context[0].text` and `question.text`.
It distinguishes target references from unrelated references inside extra context,
and provenance IDs/offsets from linguistic evidence. V2's criteria and complete
existing instructions remain unchanged. V1 and v2 resources stay immutable; only
D changes in the v3 manifest. No structured-criteria/API migration is necessary:
string instructions and criteria remain supported.

**The historical regression omitted supplied evidence.** The second fixture now
includes the exact heading, exercising existing heading selection. Its relative
pronouns “die” and “denen” have the source-internal antecedent “Unterzuckerungen”;
“Sie” addresses the reader. The heading supplies topic context, not a necessary
missing person. Under the written rubric this case is expected clear, with or
without that heading. This expectation does not relabel its saved Jev outcome.
The internal-pronoun fixture also contained the unrelated deictic “hier”; it now
uses “Der Ball ist rund und er ist rot.” to isolate the intended test. Separate
unique/irrelevant heading cases exercise the boundary.

## State construction and historical reproduction

`reference_context` remains the frozen mechanical cue selector: it chooses the
nearest preceding sentence in the same heading, otherwise that heading, otherwise
an eligible reference-only question. It is not a complete German pronoun detector
or semantic resolver; its finite cue set does not include every possessive/dative
form. D must judge only what is actually supplied, never infer omitted context.
No selector change or broader context expansion is justified by these two inputs.
`working_state` preserves exact source text, IDs and offsets and includes only
selected context, the eligible question and any changed working text. B/C can
change the text D receives, so this review does not batch D with those stages.

Both exact historical D states were rebuilt through current `prepare_inputs`,
`reference_context` and `working_state` on temporary copies of the retained stores,
then compared with each saved `D.prepared.json` body's state. Both matched exactly.
Network operations were blocked, source-store fingerprints stayed unchanged, and
both historical v1 outcomes also passed model-disabled replay after close/reopen.

The second state contains only `source` and one `context` entry:

- Context `[2104,2153)`: `### 3. Besonderheiten bei schwerer Unterzuckerung`
- Source `[2155,2338)`: “Häufige oder schwere Unterzuckerungen, die unbemerkt auftreten oder bei denen Sie fremde Hilfe benötigen, können die Eignung zum Führen von Kraftfahrzeugen vorübergehend einschränken.”
- No `question` or `working_text` was supplied. Exact historical IDs remain in the
  private prepared request and the reproduced state linked from the handoff.
- Canonical second-state SHA-256:
  `067417d0c7ddbdc356c4b3aa035ff1bddfe7dda1c620679716f7dd4131558798`.

The first state contains only its original source at `[0,63)`; its canonical hash
is `acf326fb7761f27869dbc4f6f9959312190479f8885d2585cd84a31d9367d4fb`.
The two original `unresolved` responses remain evidence, not explanations of why
Jev chose them. No model reasoning is inferred.

## Verification limits

Regression cases exercise both v2 and v3 preparation/routing, including the real
heading with synthetic test IDs. Expected labels are scripted specification values;
they do not test Jev's semantic accuracy. V1/v2 replay and version isolation are
covered separately. No live/model calls were made. German model quality remains
unmeasured, and the docs caution that non-English accuracy is lower than English.
No threshold change, forced label, skipped D, B/F/H/T05 change or relaxed audit,
provenance or target accounting is part of this review. Genuine Claim output and
the T05 saved-pair diagnostic remain blocked pending separately authorized execution.
