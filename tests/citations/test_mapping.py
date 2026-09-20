import pytest

from binfocheck.citations import StoredCitationMapper, citation_route
from binfocheck.domain.claims import Claim
from binfocheck.domain.common import Availability, CitationStatus
from binfocheck.domain.interfaces import CitationMapper
from binfocheck.domain.records import RecordSet
from binfocheck.domain.storage import IdRequest
from binfocheck.domain.validation import validate_links
from tests.storage.helpers import Store, all_records, success

from .helpers import CITE, seed_pair


@pytest.mark.parametrize("availability", list(Availability))
@pytest.mark.parametrize("positive", [True, False])
def test_capture_precedence(store: Store, availability: Availability, positive: bool) -> None:
    # Unavailable cannot legally contain captured references: no marker for that case.
    captured = positive and availability != Availability.UNAVAILABLE
    request = seed_pair(
        store, "Äpfel sind rot." + (" " + CITE if captured else ""), availability=availability
    )
    mapper: CitationMapper = StoredCitationMapper(store, store)
    result = success(mapper.map_citations(request))
    expected = "yes" if captured else "no" if availability == Availability.AVAILABLE else "unclear"
    assert result.status == expected
    assert result.scope_assessable == (expected != "unclear")
    assert result.analysis_run_id == request.analysis_run_id
    validate_links(RecordSet(records=all_records(store)))


@pytest.mark.parametrize(
    "host,expected",
    [("example.org", "no"), ("sub.diabinfo.de", "unclear"), ("www.diabinfo.de", "yes")],
)
def test_host_routing(store: Store, host: str, expected: str) -> None:
    request = seed_pair(store, f"Äpfel sind rot. [[1]](https://{host}/)")
    result = success(StoredCitationMapper(store, store).map_citations(request))
    assert result.status == expected
    assert (
        citation_route(result.status)
        == {"yes": "category_1", "no": "matching", "unclear": "citation_unclear"}[expected]
    )


def test_citation_elsewhere_does_not_exempt_claim(store: Store) -> None:
    request = seed_pair(
        store, "Äpfel sind rot. " + CITE + " Birnen sind grün.", quote="Birnen sind grün."
    )
    result = success(StoredCitationMapper(store, store).map_citations(request))
    assert result.status == CitationStatus.NO
    assert not result.reference_ids


def test_shared_span_does_not_merge_claims(store: Store) -> None:
    request = seed_pair(store)
    original = success(store.get_record(IdRequest(id=request.claim_id)))
    assert isinstance(original, Claim)
    second = original.model_copy(update={"id": "second-claim"})
    success(store.put_record(second))
    mapper = StoredCitationMapper(store, store)
    one = success(mapper.map_citations(request))
    two = success(mapper.map_citations(request.model_copy(update={"claim_id": second.id})))
    assert one.status == two.status == "yes"
    assert one.id != two.id
    assert one.reference_ids == two.reference_ids


@pytest.mark.parametrize(
    "normalizer,unlocated", [("unknown", False), ("dataforseo-ai-mode-normalizer", True)]
)
def test_unestablished_semantics(store: Store, normalizer: str, unlocated: bool) -> None:
    request = seed_pair(store, normalizer=normalizer, unlocated=unlocated)
    assert success(StoredCitationMapper(store, store).map_citations(request)).status == "unclear"


def test_mixed_target_group(store: Store) -> None:
    request = seed_pair(store, "Äpfel sind rot. [[2]](https://example.org/) " + CITE)
    result = success(StoredCitationMapper(store, store).map_citations(request))
    assert result.status == "yes"
    assert result.reference_ids == ("a-citation-1",)


@pytest.mark.parametrize("syntax", ["!{cite}", "[{cite}](https://example.org/)"])
def test_image_or_nested_marker_never_positive(store: Store, syntax: str) -> None:
    request = seed_pair(store, "Äpfel sind rot. " + syntax.replace("{cite}", CITE))
    assert success(StoredCitationMapper(store, store).map_citations(request)).status == "unclear"


def test_other_source_with_incomplete_capture_is_not_uncited(store: Store) -> None:
    request = seed_pair(
        store, "Äpfel sind rot. [[1]](https://example.org/)", availability=Availability.INCOMPLETE
    )
    assert success(StoredCitationMapper(store, store).map_citations(request)).status == "unclear"


def test_plain_domain_without_marker_is_not_citation(store: Store) -> None:
    request = seed_pair(store, "Äpfel sind rot. Die Adresse lautet diabinfo.de.")
    assert success(StoredCitationMapper(store, store).map_citations(request)).status == "no"


@pytest.mark.parametrize("target", [True, False])
def test_saved_t01_provider_fixture_integration(store: Store, target: bool) -> None:
    """Real T01/T02 code on an existing synthetic capture; Claim remains synthetic."""
    from binfocheck.acquisition.persistence import persist_response
    from binfocheck.citations import CitationSettings
    from binfocheck.domain.interfaces import ClaimRequest, IndexRequest
    from binfocheck.domain.runs import RunManifest
    from binfocheck.domain.text import SpanRef, TextRecord
    from binfocheck.text import IndexSettings, StoredAnswerIndexer, index_reference_id
    from tests.acquisition.helpers import AT, response
    from tests.acquisition.helpers import request as capture_request
    from tests.text.helpers import seed

    template, _ = seed(store, "Template.")
    run = success(store.get_record(IdRequest(id=template.analysis_run_id)))
    assert isinstance(run, RunManifest)
    capture = capture_request()
    success(store.put_record(capture))
    http_response = response()
    assert http_response.payload is not None
    if target:
        from dataclasses import replace

        http_response = replace(
            http_response,
            payload=http_response.payload.replace(
                b"https://example.org/a", b"https://www.diabinfo.de/example"
            ),
        )
    observation = persist_response(store, store, capture, http_response, AT)
    assert observation.answer_text_id
    answer = success(store.get_record(IdRequest(id=observation.answer_text_id)))
    assert isinstance(answer, TextRecord)
    run = run.model_copy(
        update={
            "id": "provider-fixture-run",
            "observation_ids": (observation.id,),
            "input_ids": (observation.id, answer.id),
        }
    )
    success(store.put_record(run))
    index = IndexRequest(
        analysis_run_id=run.id,
        observation_id=observation.id,
        answer_text_id=answer.id,
        settings=IndexSettings().envelope(),
    )
    units = success(StoredAnswerIndexer(store, store).index_answer(index))
    quote = "Äpfel 🍎 sind rot."
    claim = Claim(
        id="provider-fixture-claim",
        created_at=AT,
        analysis_run_id=run.id,
        observation_id=observation.id,
        input_ids=(answer.id, observation.id),
        normalized_claim=quote,
        original_span=SpanRef(text_id=answer.id, start=0, end=len(quote), exact_text=quote),
        context_unit_ids=tuple(u.id for u in units if u.span.start == 0),
        decision_ids=(),
        claim_group_id="synthetic-provider-group",
    )
    success(store.put_record(claim))
    originals = all_records(store)
    request = ClaimRequest(
        analysis_run_id=run.id,
        claim_id=claim.id,
        settings=CitationSettings(index_artifact_id=index_reference_id(index, answer)).envelope(),
    )
    result = success(StoredCitationMapper(store, store).map_citations(request))
    assert observation.citation_reference_ids.availability == "incomplete"
    assert result.status == ("yes" if target else "unclear")
    for original in originals:
        assert success(store.get_record(IdRequest(id=original.id))) == original
