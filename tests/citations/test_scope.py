import json
from pathlib import Path

import pytest

from binfocheck.citations import StoredCitationMapper
from binfocheck.domain.claims import Claim
from binfocheck.domain.storage import IdRequest
from tests.storage.helpers import Store, success

from .helpers import CITE, seed_pair

CASES = json.loads(
    (Path(__file__).parents[1] / "fixtures/citations/v1/mapping_cases.json").read_text()
)


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_scope_cases(store: Store, case: dict[str, str]) -> None:
    text = case["text"].replace("{cite}", CITE)
    quote = text if case.get("span") == "whole" else case["quote"]
    request = seed_pair(store, text, quote=quote)
    result = success(StoredCitationMapper(store, store).map_citations(request))
    assert result.status == case["expected"]
    claim = success(store.get_record(IdRequest(id=request.claim_id)))
    assert isinstance(claim, Claim)
    assert claim.original_span.exact_text == quote
    for span in result.evidence_spans:
        assert text[span.start : span.end] == span.exact_text


def test_repeated_quote_uses_explicit_offset(store: Store) -> None:
    quote = "Äpfel sind rot."
    text = quote + " " + CITE + "\n\n" + quote
    request = seed_pair(store, text, quote=quote, start=text.rindex(quote))
    assert success(StoredCitationMapper(store, store).map_citations(request)).status == "no"
