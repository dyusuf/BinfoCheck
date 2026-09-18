"""Each assignment is also a strict static conformance check against its Protocol."""

import json

import pytest

from binfocheck.domain import interfaces as api
from binfocheck.domain import storage
from binfocheck.domain.catalog import BOUNDARIES
from binfocheck.domain.decisions import DecisionRecord
from binfocheck.domain.observations import CaptureRequest
from binfocheck.domain.records import RECORD_ADAPTER
from binfocheck.domain.runs import Review
from tests.contracts.helpers import FIXTURES
from tests.doubles.components import ComponentDouble, StorageDouble


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_capture_interface(variant: str) -> None:
    double = ComponentDouble("capture", FIXTURES / "boundaries" / f"capture.{variant}.json")
    component: api.ObservationProvider = double
    request = CaptureRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.capture(request)
    expected = BOUNDARIES["capture"].response.validate_json(json.dumps(double.exchange.response))
    assert result == expected
    assert double.calls == ["capture"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_index_answer_interface(variant: str) -> None:
    double = ComponentDouble(
        "index_answer", FIXTURES / "boundaries" / f"index_answer.{variant}.json"
    )
    component: api.AnswerIndexer = double
    request = api.IndexRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.index_answer(request)
    expected = BOUNDARIES["index_answer"].response.validate_json(
        json.dumps(double.exchange.response)
    )
    assert result == expected
    assert double.calls == ["index_answer"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_build_context_interface(variant: str) -> None:
    double = ComponentDouble(
        "build_context", FIXTURES / "boundaries" / f"build_context.{variant}.json"
    )
    component: api.ContextBuilder = double
    request = api.ContextRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.build_context(request)
    expected = BOUNDARIES["build_context"].response.validate_json(
        json.dumps(double.exchange.response)
    )
    assert result == expected
    assert double.calls == ["build_context"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_extract_claims_interface(variant: str) -> None:
    double = ComponentDouble(
        "extract_claims", FIXTURES / "boundaries" / f"extract_claims.{variant}.json"
    )
    component: api.ClaimExtractor = double
    request = api.ExtractionRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.extract_claims(request)
    expected = BOUNDARIES["extract_claims"].response.validate_json(
        json.dumps(double.exchange.response)
    )
    assert result == expected
    assert double.calls == ["extract_claims"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_map_citations_interface(variant: str) -> None:
    double = ComponentDouble(
        "map_citations", FIXTURES / "boundaries" / f"map_citations.{variant}.json"
    )
    component: api.CitationMapper = double
    request = api.ClaimRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.map_citations(request)
    expected = BOUNDARIES["map_citations"].response.validate_json(
        json.dumps(double.exchange.response)
    )
    assert result == expected
    assert double.calls == ["map_citations"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_ingest_interface(variant: str) -> None:
    double = ComponentDouble("ingest", FIXTURES / "boundaries" / f"ingest.{variant}.json")
    component: api.CorpusIngestor = double
    request = api.IngestionRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.ingest(request)
    expected = BOUNDARIES["ingest"].response.validate_json(json.dumps(double.exchange.response))
    assert result == expected
    assert double.calls == ["ingest"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_retrieve_interface(variant: str) -> None:
    double = ComponentDouble("retrieve", FIXTURES / "boundaries" / f"retrieve.{variant}.json")
    component: api.ClaimRetriever = double
    request = api.RetrievalRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.retrieve(request)
    expected = BOUNDARIES["retrieve"].response.validate_json(json.dumps(double.exchange.response))
    assert result == expected
    assert double.calls == ["retrieve"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_expand_context_interface(variant: str) -> None:
    double = ComponentDouble(
        "expand_context", FIXTURES / "boundaries" / f"expand_context.{variant}.json"
    )
    component: api.ContextExpander = double
    request = api.PairRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.expand_context(request)
    expected = BOUNDARIES["expand_context"].response.validate_json(
        json.dumps(double.exchange.response)
    )
    assert result == expected
    assert double.calls == ["expand_context"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_decide_interface(variant: str) -> None:
    double = ComponentDouble("decide", FIXTURES / "boundaries" / f"decide.{variant}.json")
    component: api.DecisionModel = double
    request = api.DecisionRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.decide(request)
    expected = BOUNDARIES["decide"].response.validate_json(json.dumps(double.exchange.response))
    assert result == expected
    assert double.calls == ["decide"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_generate_interface(variant: str) -> None:
    double = ComponentDouble("generate", FIXTURES / "boundaries" / f"generate.{variant}.json")
    component: api.GenerationModel = double
    request = api.GenerationRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.generate(request)
    expected = BOUNDARIES["generate"].response.validate_json(json.dumps(double.exchange.response))
    assert result == expected
    assert double.calls == ["generate"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_verify_candidate_interface(variant: str) -> None:
    double = ComponentDouble(
        "verify_candidate", FIXTURES / "boundaries" / f"verify_candidate.{variant}.json"
    )
    component: api.CandidateVerifier = double
    request = api.PairRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.verify_candidate(request)
    expected = BOUNDARIES["verify_candidate"].response.validate_json(
        json.dumps(double.exchange.response)
    )
    assert result == expected
    assert double.calls == ["verify_candidate"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_judge_correspondence_interface(variant: str) -> None:
    double = ComponentDouble(
        "judge_correspondence", FIXTURES / "boundaries" / f"judge_correspondence.{variant}.json"
    )
    component: api.CorrespondenceJudge = double
    request = api.PairRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.judge_correspondence(request)
    expected = BOUNDARIES["judge_correspondence"].response.validate_json(
        json.dumps(double.exchange.response)
    )
    assert result == expected
    assert double.calls == ["judge_correspondence"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_inspect_alternatives_interface(variant: str) -> None:
    double = ComponentDouble(
        "inspect_alternatives", FIXTURES / "boundaries" / f"inspect_alternatives.{variant}.json"
    )
    component: api.AlternativeSourceAnalyzer = double
    request = api.ClaimRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.inspect_alternatives(request)
    expected = BOUNDARIES["inspect_alternatives"].response.validate_json(
        json.dumps(double.exchange.response)
    )
    assert result == expected
    assert double.calls == ["inspect_alternatives"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_classify_interface(variant: str) -> None:
    double = ComponentDouble("classify", FIXTURES / "boundaries" / f"classify.{variant}.json")
    component: api.EvidenceClassifier = double
    request = api.ClassificationRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.classify(request)
    expected = BOUNDARIES["classify"].response.validate_json(json.dumps(double.exchange.response))
    assert result == expected
    assert double.calls == ["classify"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_put_artifact_interface(variant: str) -> None:
    double = StorageDouble("put_artifact", FIXTURES / "boundaries" / f"put_artifact.{variant}.json")
    component: storage.ArtifactStore = double
    request = storage.ArtifactPayload.model_validate_json(json.dumps(double.exchange.request))
    result = component.put_artifact(request)
    expected = BOUNDARIES["put_artifact"].response.validate_json(
        json.dumps(double.exchange.response)
    )
    assert result == expected
    assert double.calls == ["put_artifact"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_get_artifact_interface(variant: str) -> None:
    double = StorageDouble("get_artifact", FIXTURES / "boundaries" / f"get_artifact.{variant}.json")
    component: storage.ArtifactStore = double
    request = storage.IdRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.get_artifact(request)
    expected = BOUNDARIES["get_artifact"].response.validate_json(
        json.dumps(double.exchange.response)
    )
    assert result == expected
    assert double.calls == ["get_artifact"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_put_record_interface(variant: str) -> None:
    double = StorageDouble("put_record", FIXTURES / "boundaries" / f"put_record.{variant}.json")
    component: storage.RecordStore = double
    request = RECORD_ADAPTER.validate_json(json.dumps(double.exchange.request))
    result = component.put_record(request)
    expected = BOUNDARIES["put_record"].response.validate_json(json.dumps(double.exchange.response))
    assert result == expected
    assert double.calls == ["put_record"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_get_record_interface(variant: str) -> None:
    double = StorageDouble("get_record", FIXTURES / "boundaries" / f"get_record.{variant}.json")
    component: storage.RecordStore = double
    request = storage.IdRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.get_record(request)
    expected = BOUNDARIES["get_record"].response.validate_json(json.dumps(double.exchange.response))
    assert result == expected
    assert double.calls == ["get_record"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_list_records_interface(variant: str) -> None:
    double = StorageDouble("list_records", FIXTURES / "boundaries" / f"list_records.{variant}.json")
    component: storage.RecordStore = double
    request = storage.ListRequest.model_validate_json(json.dumps(double.exchange.request))
    result = component.list_records(request)
    expected = BOUNDARIES["list_records"].response.validate_json(
        json.dumps(double.exchange.response)
    )
    assert result == expected
    assert double.calls == ["list_records"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_append_decision_interface(variant: str) -> None:
    double = StorageDouble(
        "append_decision", FIXTURES / "boundaries" / f"append_decision.{variant}.json"
    )
    component: storage.RecordStore = double
    request = DecisionRecord.model_validate_json(json.dumps(double.exchange.request))
    result = component.append_decision(request)
    expected = BOUNDARIES["append_decision"].response.validate_json(
        json.dumps(double.exchange.response)
    )
    assert result == expected
    assert double.calls == ["append_decision"]


@pytest.mark.parametrize("variant", ["valid", "unavailable"])
def test_append_review_interface(variant: str) -> None:
    double = StorageDouble(
        "append_review", FIXTURES / "boundaries" / f"append_review.{variant}.json"
    )
    component: storage.RecordStore = double
    request = Review.model_validate_json(json.dumps(double.exchange.request))
    result = component.append_review(request)
    expected = BOUNDARIES["append_review"].response.validate_json(
        json.dumps(double.exchange.response)
    )
    assert result == expected
    assert double.calls == ["append_review"]
