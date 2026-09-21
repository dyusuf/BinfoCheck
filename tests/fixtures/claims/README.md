# T04 regression fixtures

`v1/spans.json` contains invented German sentences with independently specified
Unicode-code-point offsets, including a combining mark and emoji. No patient data,
real provider capture, credentials or fetched website content is included.

`tests/claims/helpers.py` supplies exact-preparation scripted model records;
`test_adapters.py` supplies frozen response shapes through a network-free transport
using the real T03 adapters. Test callbacks select synthetic labels and wording to
exercise branches; they do not establish actual Jev or generation accuracy.

The extraction resource manifest pins all business prompt/schema/rubric bytes used
by these fixtures. These tests make zero provider/model calls.

`v2/ambiguity.json` is a human-labeled Stage-D specification. Its first two texts
are the exact, narrowly authorized retained gate excerpts at [0,63) and
[2155,2338), respectively, from the private T01/T02 evidence. Remaining texts are
invented. No full capture or actual provider response is copied into fixtures.
Expected labels describe the corrected rubric; they are not new Jev observations.
Synthetic storage IDs and scripted decisions test exact v2 preparation, E/F/H
routing, unresolved stopping and historical version separation. A generic synthetic
question, when selected by existing context logic, supplies no missing antecedent.

The Jev skill review corrects the second regression input to include its actual
heading, `### 3. Besonderheiten bei schwerer Unterzuckerung`. Test IDs/offsets remain
synthetic; exact historical state reconstruction is verified separately against the
private prepared request. Cases run with both v2 and v3. The internal-pronoun case
omits unrelated “hier”; additional headings distinguish unique from irrelevant
context. Neither expected labels nor synthetic responses replace saved decisions.
