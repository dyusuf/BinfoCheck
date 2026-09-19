# Synthetic T04 fixtures

`v1/spans.json` contains invented German sentences with independently specified
Unicode-code-point offsets, including a combining mark and emoji. No patient data,
real provider capture, credentials or fetched website content is included.

`tests/claims/helpers.py` supplies exact-preparation scripted model records;
`test_adapters.py` supplies frozen response shapes through a network-free transport
using the real T03 adapters. Test callbacks select synthetic labels and wording to
exercise branches; they do not establish actual Jev or generation accuracy.

The extraction resource manifest pins all business prompt/schema/rubric bytes used
by these fixtures. Provider/model calls during T04 implementation: zero.
