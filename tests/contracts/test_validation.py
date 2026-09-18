import json

import pytest
from pydantic import JsonValue, ValidationError

from binfocheck.domain.decisions import DecisionRecord, DecisionResult, GenerationResult
from binfocheck.domain.evidence import Finding
from binfocheck.domain.observations import Observation
from binfocheck.domain.storage import ArtifactPayload, ListRequest

from .helpers import FIXTURES, read_object


@pytest.mark.parametrize("category", [True, False, 1.0, "1", 0, 5])
def test_category_is_strict_and_bounded(category: JsonValue) -> None:
    data = read_object(FIXTURES / "records/finding.valid.json")
    data["category"] = category
    with pytest.raises(ValidationError):
        Finding.model_validate_json(json.dumps(data))


@pytest.mark.parametrize(
    "status",
    [
        "pending",
        "processing_failed",
        "no_match_found",
        "citation_unclear",
        "not_enough_evidence",
    ],
)
def test_uncategorized_status_cannot_carry_category(status: str) -> None:
    data = read_object(FIXTURES / "records/finding.valid.json")
    data["status"] = status
    with pytest.raises(ValidationError, match="category_requires_categorized_status"):
        Finding.model_validate_json(json.dumps(data))


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-09-18T12:00:00",
        "2026-09-18T12:00:00+02:00",
    ],
)
def test_non_utc_timestamps_rejected(timestamp: str) -> None:
    data = read_object(FIXTURES / "records/observation.valid.json")
    data["created_at"] = timestamp
    with pytest.raises(ValidationError, match="timestamp_must_be_utc"):
        Observation.model_validate_json(json.dumps(data))


def test_decision_and_generation_remain_distinct() -> None:
    decision = DecisionRecord.model_validate_json(
        (FIXTURES / "records/decision_record.valid.json").read_bytes()
    )
    assert isinstance(decision.result, DecisionResult)
    # The generation boundary carries a generation result, not a decision label.
    from tests.doubles.components import Exchange

    exchange = Exchange.model_validate_json(
        (FIXTURES / "boundaries/generate.valid.json").read_bytes()
    )
    generation = DecisionRecord.model_validate_json(json.dumps(exchange.response["value"]))
    assert isinstance(generation.result, GenerationResult)
    restored = DecisionRecord.model_validate_json(generation.model_dump_json())
    assert restored == generation
    assert isinstance(restored.result, GenerationResult)


@pytest.mark.parametrize("limit", [0, 1001, True, 1.5])
def test_listing_is_bounded(limit: JsonValue) -> None:
    with pytest.raises(ValidationError):
        ListRequest.model_validate_json(json.dumps({"limit": limit}))


@pytest.mark.parametrize(
    ("content", "error"),
    [
        ("!invalid!", "invalid_artifact_base64"),
        ("e30=", "artifact_hash_mismatch"),
    ],
)
def test_artifact_content_validation(content: str, error: str) -> None:
    from tests.doubles.components import Exchange

    exchange = Exchange.model_validate_json(
        (FIXTURES / "boundaries/put_artifact.valid.json").read_bytes()
    )
    data = dict(exchange.request)
    data["content_base64"] = content
    with pytest.raises(ValidationError, match=error):
        ArtifactPayload.model_validate_json(json.dumps(data))
