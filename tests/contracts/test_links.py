import json

import pytest
from pydantic import JsonValue, ValidationError

from binfocheck.domain.records import RECORD_ADAPTER, RecordSet
from binfocheck.domain.text import SpanRef
from binfocheck.domain.validation import LinkError, validate_links

from .helpers import JSON_OBJECT, linked, replace_record


@pytest.mark.parametrize(
    ("id", "changes", "code"),
    [
        ("claim-1", {"analysis_run_id": "missing-run"}, "missing_id"),
        ("claim-1", {"observation_id": "request-1"}, "wrong_record_kind"),
        ("run-1", {"observation_ids": []}, "observation_run_mismatch"),
        (
            "claim-1",
            {
                "original_span": {
                    "text_id": "text-answer",
                    "start": 26,
                    "end": 35,
                    "exact_text": "sind blau",
                    "source_unit_id": "unit-2",
                }
            },
            "quote_mismatch",
        ),
        (
            "claim-1",
            {
                "original_span": {
                    "text_id": "text-answer",
                    "start": 40,
                    "end": 49,
                    "exact_text": "sind rot.",
                    "source_unit_id": None,
                }
            },
            "span_out_of_bounds",
        ),
        (
            "claim-1",
            {
                "original_span": {
                    "text_id": "text-answer",
                    "start": 26,
                    "end": 35,
                    "exact_text": "sind rot.",
                    "source_unit_id": "unit-1",
                }
            },
            "source_unit_mismatch",
        ),
        (
            "claim-1",
            {
                "original_span": {
                    "text_id": "text-article",
                    "start": 8,
                    "end": 17,
                    "exact_text": "sind rot.",
                    "source_unit_id": None,
                }
            },
            "claim_text_mismatch",
        ),
        ("citation-1", {"reference_ids": ["missing-ref"]}, "missing_id"),
        (
            "passage-1",
            {
                "span": {
                    "text_id": "text-answer",
                    "start": 8,
                    "end": 17,
                    "exact_text": "sind rot.",
                    "source_unit_id": None,
                }
            },
            "passage_article_mismatch",
        ),
        ("corpus-1", {"passage_ids": []}, "pair_passage_outside_corpus"),
        ("batch-1", {"candidate_pair_ids": ["pair-1", "pair-1"]}, "duplicate_candidate_passage"),
        ("pair-1", {"index_id": "another-index"}, "pair_batch_mismatch"),
        ("alternative-1", {"source_reference_id": "ref-1"}, "alternative_excerpt_mismatch"),
        ("citation-1", {"status": "no"}, "category_one_requires_citation"),
        ("review-2", {"supersedes_review_id": "missing-review"}, "missing_id"),
    ],
)
def test_invalid_links(id: str, changes: dict[str, JsonValue], code: str) -> None:
    bundle = replace_record(linked(), id, **changes)
    with pytest.raises(LinkError) as error:
        validate_links(bundle)
    assert error.value.code == code


def test_cross_run_and_observation_context_rejected() -> None:
    original = linked()
    run = next(record for record in original.records if record.id == "run-1")
    extra_run = RECORD_ADAPTER.validate_json(run.model_dump_json().replace('"run-1"', '"run-2"'))
    bundle = RecordSet(records=(*original.records, extra_run))
    bundle = replace_record(bundle, "unit-2", analysis_run_id="run-2")
    with pytest.raises(LinkError, match="run_mismatch"):
        validate_links(bundle)

    observation = next(record for record in original.records if record.id == "obs-1")
    data = JSON_OBJECT.validate_json(observation.model_dump_json())
    data.update(
        id="obs-2",
        source_reference_ids={"availability": "available", "data": []},
        citation_reference_ids={"availability": "available", "data": []},
    )
    extra_observation = RECORD_ADAPTER.validate_json(json.dumps(data))
    bundle = RecordSet(records=(*original.records, extra_observation))
    bundle = replace_record(bundle, "run-1", observation_ids=["obs-1", "obs-2"])
    bundle = replace_record(bundle, "unit-2", observation_id="obs-2")
    with pytest.raises(LinkError, match="context_observation_mismatch"):
        validate_links(bundle)


def test_unicode_and_repeated_locations() -> None:
    assert "Äpfel 🍎 sind rot."[8:17] == "sind rot."
    bundle = linked()
    validate_links(bundle)
    records = {record.id: record for record in bundle.records}
    text = records["text-answer"]
    assert text.kind == "text"
    claim = records["claim-1"]
    assert claim.kind == "claim"
    assert text.text[8:17] == text.text[26:35] == "sind rot."
    assert claim.original_span.start == 26
    assert claim.original_span.source_unit_id == "unit-2"
    assert (
        text.text[claim.original_span.start : claim.original_span.end]
        == claim.original_span.exact_text
    )


@pytest.mark.parametrize(
    ("start", "end", "text"),
    [
        (-1, 8, "sind rot."),
        (8, 8, "sind rot."),
        (9, 8, "sind rot."),
        (8, 16, "sind rot."),
    ],
)
def test_malformed_spans(start: int, end: int, text: str) -> None:
    with pytest.raises(ValidationError):
        SpanRef(text_id="text-answer", start=start, end=end, exact_text=text)


def test_history_preserves_prior_findings_and_reviews() -> None:
    original = linked()
    finding = next(record for record in original.records if record.id == "finding-1")
    data = JSON_OBJECT.validate_json(finding.model_dump_json())
    data.update(
        id="finding-2", supersedes_finding_id="finding-1", created_at="2026-09-18T12:02:00Z"
    )
    successor = RECORD_ADAPTER.validate_json(json.dumps(data))
    bundle = RecordSet(records=(*original.records, successor))
    validate_links(bundle)
    assert original.records == bundle.records[:-1]
    with pytest.raises(LinkError, match="multiple_selected_findings"):
        validate_links(replace_record(bundle, "finding-2", supersedes_finding_id=None))
    with pytest.raises(LinkError, match="history_cycle"):
        validate_links(
            replace_record(
                original,
                "review-1",
                supersedes_review_id="review-2",
                created_at="2026-09-18T12:01:00Z",
            )
        )


def test_duplicate_record_ids_rejected() -> None:
    bundle = linked()
    with pytest.raises(LinkError, match="duplicate_id"):
        validate_links(RecordSet(records=(*bundle.records, bundle.records[0])))
