import json

import pytest
from pydantic import JsonValue

from binfocheck.acquisition.normalize import normalize
from binfocheck.acquisition.transport import HttpResponse
from binfocheck.domain.observations import SourceReference
from binfocheck.domain.records import RecordSet
from binfocheck.domain.text import TextRecord
from binfocheck.domain.validation import validate_links

from .helpers import AT, fixture, overview, request, response, result, task


def test_exact_answer_repeated_markers_excerpts_and_locations() -> None:
    data = fixture()
    capture = normalize(request(), response(data), AT)
    assert capture.observation.status == "succeeded"
    assert capture.observation.product == "google_ai_mode"
    answer = next(
        r
        for r in capture.records
        if isinstance(r, TextRecord) and r.id == capture.observation.answer_text_id
    )
    assert answer.text == overview(data)["markdown"]
    assert answer.text[8:17] == "sind rot."
    refs = [r for r in capture.records if isinstance(r, SourceReference)]
    references = [r for r in refs if r.reference_kind == "reference"]
    citations = [r for r in refs if r.reference_kind == "citation"]
    assert len(references) == 2
    assert references[0].metadata_location == "/tasks/0/result/0/items/0/references/0"
    assert references[0].excerpt.data is not None
    assert references[0].excerpt.data.exact_text == "Äpfel 🍎 sind rot.\n"
    assert references[1].excerpt.availability == "unavailable"
    assert len(citations) == 2
    spans = [r.citation_span for r in citations]
    assert spans[0] is not None and spans[1] is not None
    assert spans[0].start != spans[1].start
    assert spans[0].exact_text == spans[1].exact_text
    for span in spans:
        assert span is not None
        assert answer.text[span.start : span.end] == span.exact_text
    assert capture.observation.citation_reference_ids.availability == "incomplete"
    assert capture.observation.fanout_queries.availability == "unavailable"
    validate_links(RecordSet(records=capture.records))
    assert normalize(request(), response(data), AT) == capture


def test_nonfinite_json_is_malformed() -> None:
    capture = normalize(request(), HttpResponse(b'{"cost":1e999}', 200), AT)
    assert capture.observation.error is not None
    assert capture.observation.error.code == "malformed_response"


def test_indented_representation_is_not_assessable_empty() -> None:
    data = fixture()
    item = overview(data)
    item.clear()
    item.update({"type": "ai_overview", "markdown": "    code", "references": []})
    capture = normalize(request(), response(data), AT)
    assert capture.observation.citation_reference_ids.availability == "incomplete"


@pytest.mark.parametrize(
    "markdown",
    [
        "Äpfel 🍎 sind rot.",
        "[Quelle](https://example.org/a)",
        "[1](https://example.org/a)",
        "https://example.org/a",
        "`[[1]](https://example.org/a)`",
        "\\[[1]](https://example.org/a)",
        "    [[1]](https://example.org/a)",
        "![[1]](https://example.org/a)",
        "[outer [[1]](https://example.org/a)](https://example.org/b)",
        "[[1]](https://not-captured.example/a)",
    ],
)
def test_no_citation_inference(markdown: str) -> None:
    data = fixture()
    overview(data)["markdown"] = markdown
    capture = normalize(request(), response(data), AT)
    refs = [r for r in capture.records if isinstance(r, SourceReference)]
    assert all(r.reference_kind == "reference" and r.citation_span is None for r in refs)
    assert capture.observation.citation_reference_ids.availability == "incomplete"
    assert capture.observation.citation_reference_ids.data == ()


@pytest.mark.parametrize(
    "variant,expected",
    [
        ("empty", "available"),
        ("missing", "unavailable"),
        ("null", "unavailable"),
        ("incomplete", "incomplete"),
        ("unknown", "incomplete"),
    ],
)
def test_distinct_citation_availability(variant: str, expected: str) -> None:
    data = fixture()
    item = overview(data)
    item.clear()
    item.update({"type": "ai_overview", "markdown": "Äpfel 🍎 sind rot.", "items": []})
    if variant == "empty":
        item["references"] = []
    elif variant == "null":
        item["references"] = None
    elif variant == "incomplete":
        item["references"] = [None]
    elif variant == "unknown":
        item["references"] = []
        item["unrecognized_citations"] = []
    capture = normalize(request(), response(data), AT)
    state = capture.observation.citation_reference_ids
    assert state.availability == expected
    assert state.data == (None if expected == "unavailable" else ())
    if expected != "available":
        assert state.reason


@pytest.mark.parametrize("missing", [True, False])
@pytest.mark.parametrize("value", [None, "", " \t\r\n"])
def test_absent_aggregate_does_not_fabricate_answer(missing: bool, value: JsonValue) -> None:
    data = fixture()
    if missing:
        overview(data).pop("markdown")
    else:
        overview(data)["markdown"] = value
    # Child text remains present; it is not assembled into a replacement answer.
    capture = normalize(request(), response(data), AT)
    assert capture.observation.error is not None
    assert capture.observation.error.code == "answer_absent"
    assert capture.observation.answer_text_id is None
    assert capture.observation.raw_artifact_id is not None
    assert capture.observation.status == "failed"
    validate_links(RecordSet(records=capture.records))


@pytest.mark.parametrize("level", ["envelope", "task", "http"])
@pytest.mark.parametrize(
    "provider_code,http_code,expected",
    [
        (40100, 401, "authentication_failed"),
        (40202, 429, "rate_limited"),
        (40209, 429, "rate_limited"),
        (40200, 402, "provider_access_denied"),
        (40207, 403, "provider_access_denied"),
        (50000, 500, "provider_failed"),
    ],
)
def test_both_provider_status_levels_and_http(
    level: str, provider_code: int, http_code: int, expected: str
) -> None:
    data = fixture()
    if level == "envelope":
        data["status_code"] = provider_code
    elif level == "task":
        task(data)["status_code"] = provider_code
    capture = normalize(request(), response(data, http_code if level == "http" else 200), AT)
    assert capture.observation.error is not None
    assert capture.observation.error.code == expected
    assert capture.observation.error.provider_request_id == "synthetic-task-1"
    assert capture.receipt.provider_request_id == "synthetic-task-1"
    assert capture.receipt.envelope_cost_usd == 0.004
    assert capture.receipt.task_cost_usd == 0.004


@pytest.mark.parametrize(
    "payload",
    [
        b"not JSON",
        b"[]",
        b"null",
        b"{",
        b"{}",
        b'{"status_code":20000,"status_code":40100}',
        b"\xff",
    ],
)
def test_malformed_payload(payload: bytes) -> None:
    capture = normalize(request(), HttpResponse(payload, 200), AT)
    assert capture.observation.error is not None
    assert capture.observation.error.code == "malformed_response"


def test_http_authentication_error_with_non_json_body() -> None:
    capture = normalize(request(), HttpResponse(b"<error>denied</error>", 401), AT)
    assert capture.observation.error is not None
    assert capture.observation.error.code == "authentication_failed"


@pytest.mark.parametrize(
    "change",
    ["counts", "tasks", "results", "items", "markdown", "duplicate", "endpoint", "language"],
)
def test_inconsistent_response(change: str) -> None:
    data = fixture()
    expected = "malformed_response"
    if change == "counts":
        data["tasks_count"] = 2
    elif change == "tasks":
        data["tasks"] = []
    elif change == "results":
        task(data)["result"] = []
    elif change == "items":
        result(data)["items"] = {}
    elif change == "markdown":
        overview(data)["markdown"] = 42
    elif change == "duplicate":
        result(data)["items"] = [overview(data), overview(data)]
    elif change == "endpoint":
        task(data)["path"] = ["v3", "serp", "google", "organic", "live", "advanced"]
        expected = "unexpected_provider_endpoint"
    else:
        result(data)["language_code"] = "en"
        expected = "reported_settings_mismatch"
    capture = normalize(request(), response(data), AT)
    assert capture.observation.error is not None
    assert capture.observation.error.code == expected


@pytest.mark.parametrize(
    "code,expected", [(40102, "answer_absent"), (40106, "response_incomplete")]
)
def test_no_results_or_provider_partial(code: int, expected: str) -> None:
    data = fixture()
    task(data)["status_code"] = code
    capture = normalize(request(), response(data), AT)
    assert capture.observation.error is not None and capture.observation.error.code == expected


@pytest.mark.parametrize("cost", [None, 0, 0.004])
def test_unknown_zero_and_known_usage_are_distinct(cost: JsonValue) -> None:
    data = fixture()
    data["cost"] = cost
    task(data)["cost"] = cost
    capture = normalize(request(), response(data), AT)
    usage = capture.receipt.usage.data
    assert usage is not None
    assert usage.cost == cost  # No envelope + task double counting.
    assert usage.currency == (None if cost is None else "USD")
    assert usage.input_tokens is None and usage.output_tokens is None
    assert usage.requests == 1
    assert "synthetic-secret-cookie" not in capture.receipt.model_dump_json()


def test_nested_locations_and_unknown_fields_survive() -> None:
    data = fixture()
    overview(data)["items"] = [
        {
            "type": "future_element",
            "components": [
                {
                    "type": "ai_overview_expanded_component",
                    "references": [
                        {
                            "type": "ai_overview_reference",
                            "url": "https://example.org/c",
                            "text": "Genau.",
                        }
                    ],
                }
            ],
        }
    ]
    capture = normalize(request(), response(data), AT)
    nested = next(
        r for r in capture.records if isinstance(r, SourceReference) and r.url.endswith("/c")
    )
    assert nested.metadata_location == "/tasks/0/result/0/items/0/items/0/components/0/references/0"
    assert nested.reference_kind == "reference"
    assert capture.observation.source_reference_ids.availability == "incomplete"
    assert "unsupported_source_structure" in capture.receipt.diagnostics
    assert json.loads(response(data).payload)["tasks"][0]["result"][0]["items"][0][
        "synthetic_unknown_field"
    ]
