# T03 synthetic adapter fixtures

All bodies, IDs, usage counts and instructions here are synthetic and shareable.
No Jev/OpenAI response was captured. Error variants are derived in `tests/models/`
from these fixtures; they are not model accuracy or calibration examples.

`resources/` contains only a German apple-text transport smoke case. The output
schema is exported from `SmokeOutput` in `tests/models/test_resources.py` and its
equality is checked. It is not a copy of a domain schema or a T04 business prompt.

Each provider directory contains a synthetic `success.json`, an existing T00
request instance in `smoke-domain-request.json`, and the exact frozen outbound
UTF-8 bytes in `smoke-request.json` (no trailing newline). The instruction resource
has a final newline, preserved in the OpenAI request. Tests check frozen payload
hashes; changing them requires new review before live use.

Documentation inspected on 19 September 2026:

- [TypeSafe HTTP API](https://docs.typesafe.ai/api)
- [TypeSafe models and prices](https://docs.typesafe.ai/models)
- [TypeSafe response metadata](https://docs.typesafe.ai/sdk/python/api/types/responses)
- [OpenAI structured output](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI model snapshot](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
- [OpenAI Responses reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)

Fresh live artifacts, if later explicitly authorized, go into a restricted T11A
store. They must not overwrite or be mislabeled as these synthetic fixtures.
