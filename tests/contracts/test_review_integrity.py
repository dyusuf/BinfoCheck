"""T00 review regressions: captured citations, text provenance and probabilities."""

import hashlib
import json

import pytest
from pydantic import JsonValue, ValidationError

from binfocheck.domain.common import VersionRef
from binfocheck.domain.decisions import DecisionResult
from binfocheck.domain.records import RecordSet
from binfocheck.domain.text import ArtifactRef, TextRecord
from binfocheck.domain.validation import LinkError, validate_links

from .helpers import linked, replace_record


def citation_bundle(
    availability: str, status: str, references: list[JsonValue], captured: list[JsonValue] | None
) -> RecordSet:
    bundle = replace_record(
        linked(),
        "obs-1",
        citation_reference_ids={
            "availability": availability,
            "data": captured,
            "reason": None if availability == "available" else "Synthetic missing capture",
        },
    )
    bundle = replace_record(
        bundle,
        "citation-1",
        status=status,
        reference_ids=references,
        scope_assessable=status != "unclear",
    )
    return replace_record(bundle, "finding-1", status="pending", category=None)


@pytest.mark.parametrize("kind", ["reference", "search_result"])
def test_positive_association_rejects_non_citation_reference(kind: str) -> None:
    bundle = citation_bundle("available", "yes", ["ref-2"], ["ref-1"])
    bundle = replace_record(bundle, "ref-2", reference_kind=kind)
    with pytest.raises(LinkError, match="not_a_citation_reference") as error:
        validate_links(bundle)
    assert error.value.record_id == "citation-1"


@pytest.mark.parametrize("status", ["yes", "no", "unclear"])
@pytest.mark.parametrize("availability", ["available", "incomplete", "unavailable"])
def test_associated_citation_must_be_in_captured_list(status: str, availability: str) -> None:
    bundle = citation_bundle(
        availability,
        status,
        ["ref-1"],
        None if availability == "unavailable" else [],
    )
    code = (
        "citation_no_requires_complete_capture"
        if status == "no" and availability != "available"
        else "citation_not_captured"
    )
    with pytest.raises(LinkError, match=code) as error:
        validate_links(bundle)
    assert error.value.record_id == "citation-1"


@pytest.mark.parametrize("availability", ["incomplete", "unavailable"])
def test_incomplete_capture_cannot_establish_no_citation(availability: str) -> None:
    bundle = citation_bundle(
        availability,
        "no",
        [],
        None if availability == "unavailable" else [],
    )
    with pytest.raises(LinkError, match="citation_no_requires_complete_capture"):
        validate_links(bundle)
    validate_links(replace_record(bundle, "citation-1", status="unclear", scope_assessable=False))


def test_captured_positive_survives_incomplete_capture() -> None:
    validate_links(citation_bundle("incomplete", "yes", ["ref-1"], ["ref-1"]))


def test_available_empty_citations_allow_assessable_no() -> None:
    validate_links(citation_bundle("available", "no", [], []))


def capture_bundle() -> RecordSet:
    bundle = replace_record(
        linked(),
        "obs-1",
        source_reference_ids={"availability": "available", "data": []},
        citation_reference_ids={"availability": "available", "data": []},
    )
    ids = {"artifact-1", "artifact-generation", "text-answer", "request-1", "obs-1"}
    return RecordSet(records=tuple(record for record in bundle.records if record.id in ids))


def article_bundle() -> RecordSet:
    ids = {"artifact-1", "artifact-generation", "text-article", "article-1"}
    return RecordSet(records=tuple(record for record in linked().records if record.id in ids))


def add_representation(bundle: RecordSet, id: str, source: str | None) -> RecordSet:
    text = "Synthetisch transformierter Text."
    artifact = ArtifactRef(
        id=f"artifact-{id}",
        storage_key=f"synthetic/{id}.txt",
        sha256=hashlib.sha256(text.encode()).hexdigest(),
        media_type="text/plain",
        access="shareable_fixture",
    )
    record = TextRecord(
        id=id,
        text=text,
        artifact_id=artifact.id,
        source_text_id=source,
        transformation=VersionRef(name="synthetic-transform", version="1") if source else None,
    )
    return RecordSet(records=(*bundle.records, artifact, record))


def test_answer_rejects_unrelated_artifact() -> None:
    bundle = replace_record(capture_bundle(), "text-answer", artifact_id="artifact-generation")
    with pytest.raises(LinkError, match="answer_artifact_provenance_mismatch"):
        validate_links(bundle)


def test_answer_accepts_direct_and_transformed_capture_provenance() -> None:
    bundle = capture_bundle()
    validate_links(bundle)
    bundle = add_representation(bundle, "intermediate-answer", "text-answer")
    bundle = add_representation(bundle, "derived-answer", "intermediate-answer")
    bundle = replace_record(bundle, "obs-1", answer_text_id="derived-answer")
    validate_links(bundle)
    restored = RecordSet.model_validate_json(bundle.model_dump_json())
    assert restored == bundle
    validate_links(restored)
    bundle = replace_record(bundle, "text-answer", artifact_id="artifact-generation")
    with pytest.raises(LinkError, match="answer_artifact_provenance_mismatch"):
        validate_links(bundle)


@pytest.mark.parametrize("text", ["", " \n\t"])
def test_successful_capture_rejects_empty_answer(text: str) -> None:
    bundle = replace_record(capture_bundle(), "text-answer", text=text)
    with pytest.raises(LinkError, match="successful_answer_empty") as error:
        validate_links(bundle)
    assert error.value.record_id == "obs-1"


def test_absent_answer_remains_typed_failed_capture() -> None:
    bundle = replace_record(
        capture_bundle(),
        "obs-1",
        status="failed",
        answer_text_id=None,
        error={"code": "answer_absent", "message": "No answer captured"},
    )
    validate_links(bundle)


def test_article_rejects_unrelated_raw_artifact() -> None:
    bundle = replace_record(article_bundle(), "text-article", artifact_id="artifact-generation")
    with pytest.raises(LinkError, match="article_raw_provenance_mismatch"):
        validate_links(bundle)


def test_article_raw_text_cannot_itself_be_a_transformation() -> None:
    bundle = add_representation(article_bundle(), "earlier-text", None)
    bundle = replace_record(
        bundle,
        "text-article",
        source_text_id="earlier-text",
        transformation={"name": "synthetic-transform", "version": "1"},
    )
    with pytest.raises(LinkError, match="article_raw_provenance_mismatch"):
        validate_links(bundle)


@pytest.mark.parametrize("same_artifact", [True, False])
def test_cleaned_text_must_descend_from_article_raw_text(same_artifact: bool) -> None:
    bundle = add_representation(article_bundle(), "unrelated-text", None)
    bundle = add_representation(bundle, "cleaned-text", "unrelated-text")
    if same_artifact:
        bundle = replace_record(bundle, "unrelated-text", artifact_id="artifact-1")
        bundle = replace_record(bundle, "cleaned-text", artifact_id="artifact-1")
    bundle = replace_record(bundle, "article-1", cleaned_text_id="cleaned-text")
    with pytest.raises(LinkError, match="article_cleaned_lineage_mismatch"):
        validate_links(bundle)


def test_distinct_cleaned_text_requires_explicit_transformation() -> None:
    bundle = add_representation(article_bundle(), "cleaned-text", None)
    bundle = replace_record(bundle, "article-1", cleaned_text_id="cleaned-text")
    with pytest.raises(LinkError, match="article_cleaned_lineage_mismatch"):
        validate_links(bundle)


def test_article_accepts_shared_text_and_multistep_cleaned_lineage() -> None:
    bundle = article_bundle()
    validate_links(bundle)
    bundle = add_representation(bundle, "intermediate-text", "text-article")
    bundle = add_representation(bundle, "cleaned-text", "intermediate-text")
    bundle = replace_record(bundle, "article-1", cleaned_text_id="cleaned-text")
    validate_links(bundle)


@pytest.mark.parametrize("field", ["raw_text_id", "raw_artifact_id"])
def test_partial_article_cannot_claim_cleaned_text_without_raw_provenance(field: str) -> None:
    bundle = replace_record(
        article_bundle(),
        "article-1",
        status="unusable",
        reason="Synthetic partial article",
        **{field: None},
    )
    with pytest.raises(LinkError, match="article_(raw_provenance|cleaned_lineage)_mismatch"):
        validate_links(bundle)


def test_lineage_cycles_are_rejected() -> None:
    bundle = add_representation(capture_bundle(), "derived-answer", "text-answer")
    bundle = replace_record(
        bundle,
        "text-answer",
        source_text_id="derived-answer",
        transformation={"name": "synthetic-transform", "version": "1"},
    )
    with pytest.raises(LinkError, match="text_lineage_cycle"):
        validate_links(bundle)


def probability_result(
    availability: str, probabilities: dict[str, JsonValue] | None
) -> DecisionResult:
    return DecisionResult.model_validate_json(
        json.dumps(
            {
                "allowed_labels": ["yes", "no"],
                "label": "yes",
                "probabilities": {
                    "availability": availability,
                    "data": probabilities,
                    "reason": None if availability == "available" else "Synthetic missing output",
                },
            }
        )
    )


@pytest.mark.parametrize(
    "probabilities",
    [
        {"yes": 0.8, "no": 0.2},
        {"yes": 1.0, "no": 0.0},
        {"yes": 0.8, "no": 0.2000005},
        {"yes": 0.8, "no": 0.1999995},
    ],
)
def test_complete_probabilities_sum_to_one_with_rounding_tolerance(
    probabilities: dict[str, JsonValue],
) -> None:
    result = probability_result("available", probabilities)
    assert result.probabilities.data == probabilities  # Do not renormalize.
    assert DecisionResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize(
    "probabilities",
    [
        {"yes": 0.0, "no": 0.0},
        {"yes": 0.8, "no": 0.3},
        {"yes": 0.8, "no": 0.199998},
        {"yes": 0.8, "no": 0.200002},
    ],
)
def test_complete_unnormalized_probabilities_rejected(probabilities: dict[str, JsonValue]) -> None:
    with pytest.raises(ValidationError, match="available_probabilities_must_sum_to_one"):
        probability_result("available", probabilities)


def test_incomplete_and_missing_probabilities_are_not_normalized() -> None:
    result = probability_result("incomplete", {"yes": 0.7})
    assert result.probabilities.data == {"yes": 0.7}
    assert probability_result("unavailable", None).probabilities.data is None
    with pytest.raises(ValidationError, match="available_probabilities_require_all_labels"):
        probability_result("available", {"yes": 1.0})


@pytest.mark.parametrize("probability", [-0.1, 1.1, float("nan"), float("inf")])
def test_probability_values_remain_finite_and_bounded(probability: float) -> None:
    with pytest.raises(ValidationError):
        probability_result("incomplete", {"yes": probability})
