"""Pure response normalization. No source fetching, claim routing, or generated text."""

import hashlib
import json
import math
import re
from datetime import datetime
from urllib.parse import urlsplit

from pydantic import JsonValue

from binfocheck.domain.common import (
    Availability,
    Available,
    ErrorDetail,
    ProcessingStatus,
    Settings,
    VersionRef,
)
from binfocheck.domain.decisions import Usage
from binfocheck.domain.observations import CaptureRequest, Observation, SourceReference
from binfocheck.domain.records import Record, RecordSet
from binfocheck.domain.text import ArtifactRef, SpanRef, TextRecord
from binfocheck.domain.validation import validate_links

from .config import NORMALIZATION_VERSION, request_tag
from .errors import AcquisitionError, status_error
from .receipt import JSON_OBJECT, CaptureReceipt, NormalizedCapture, identifier
from .transport import HttpResponse, allowed_headers

VERSION = VersionRef(name="dataforseo-ai-mode-normalizer", version=NORMALIZATION_VERSION)
MARKER = re.compile(r"\[\[[0-9]+\]\]\((https?://[^\s()]+)\)")
KNOWN_ELEMENTS = {
    "ai_overview",
    "ai_overview_element",
    "ai_overview_table_element",
    "ai_overview_expanded_element",
    "ai_overview_expanded_component",
}
KNOWN_ELEMENT_FIELDS = {
    "type",
    "markdown",
    "text",
    "title",
    "items",
    "components",
    "references",
    "links",
    "images",
    "table",
    "position",
    "rank_group",
    "rank_absolute",
    "page",
    "xpath",
    "rectangle",
}


def unknown[T](reason: str, value_type: type[T]) -> Available[T]:
    return Available(availability=Availability.UNAVAILABLE, data=None, reason=reason)


def object_value(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise AcquisitionError("malformed_response")
    return value


def unique_object(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise AcquisitionError("malformed_response")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise AcquisitionError("malformed_response")


def finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise AcquisitionError("malformed_response")
    return number


def parse(payload: bytes) -> dict[str, JsonValue]:
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
            parse_float=finite_float,
        )
        return JSON_OBJECT.validate_python(value, strict=True)
    except (ValueError, TypeError, RecursionError):
        raise AcquisitionError("malformed_response") from None


def integer(value: JsonValue) -> int | None:
    return value if type(value) is int else None


def string(value: JsonValue) -> str | None:
    return value if isinstance(value, str) and value else None


def money(value: JsonValue) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) and number >= 0 else None


def valid_url(value: JsonValue) -> str | None:
    if not isinstance(value, str) or any(c.isspace() for c in value):
        return None
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme in {"http", "https"} and parsed.netloc else None
    except ValueError:
        return None


def raw_reference(request_id: str, payload: bytes) -> ArtifactRef:
    return ArtifactRef(
        id=identifier(request_id, "raw"),
        storage_key="acquisition/raw-response",
        sha256=hashlib.sha256(payload).hexdigest(),
        media_type="application/octet-stream",
        access="restricted",
        redacted_transport_fields=("request.headers.authorization",),
    )


def sources(
    request: CaptureRequest,
    raw: ArtifactRef,
    answer: TextRecord,
    overview: dict[str, JsonValue],
    location: str,
    at: datetime,
    partial: bool,
) -> tuple[list[Record], Available[tuple[str, ...]], Available[tuple[str, ...]], tuple[str, ...]]:
    records: list[Record] = []
    refs: list[str] = []
    urls: set[str] = set()
    diagnostics: set[str] = set()
    assessed = False
    incomplete = partial

    def walk(node: dict[str, JsonValue], path: str) -> None:
        nonlocal assessed, incomplete
        if string(node.get("type")) not in KNOWN_ELEMENTS:
            incomplete = True
            diagnostics.add("unsupported_source_structure")
        if set(node) - KNOWN_ELEMENT_FIELDS or node.get("images") not in (None, []):
            incomplete = True
            diagnostics.add("unsupported_source_fields")
        fragment = node.get("markdown")
        if path != location and isinstance(fragment, str) and fragment not in answer.text:
            incomplete = True
            diagnostics.add("fragment_not_in_aggregate_answer")
        for key in ("references", "links"):
            if key not in node:
                if key == "references":
                    incomplete = True
                continue
            entries = node[key]
            if entries is None:
                if key == "references":
                    incomplete = True
                continue
            if not isinstance(entries, list):
                incomplete = True
                diagnostics.add("malformed_reference_collection")
                continue
            if key == "references":
                assessed = True
            for index, entry in enumerate(entries):
                pointer = f"{path}/{key}/{index}"
                if not isinstance(entry, dict) or (url := valid_url(entry.get("url"))) is None:
                    incomplete = True
                    diagnostics.add("malformed_reference")
                    continue
                if string(entry.get("type")) not in {"ai_overview_reference", "link_element"}:
                    incomplete = True
                    diagnostics.add("unsupported_reference_type")
                ref_id = identifier(request.id, "source", pointer)
                excerpt: Available[SpanRef] = unknown("excerpt_not_captured", SpanRef)
                excerpt_value = entry.get("text") if key == "references" else None
                if isinstance(excerpt_value, str) and excerpt_value:
                    excerpt_text = TextRecord(
                        id=identifier(request.id, "excerpt", pointer),
                        text=excerpt_value,
                        artifact_id=raw.id,
                    )
                    records.append(excerpt_text)
                    excerpt = Available(
                        availability=Availability.AVAILABLE,
                        data=SpanRef(
                            text_id=excerpt_text.id,
                            start=0,
                            end=len(excerpt_value),
                            exact_text=excerpt_value,
                        ),
                    )
                elif excerpt_value == "":
                    excerpt = unknown("empty_excerpt_has_no_nonempty_span", SpanRef)
                elif excerpt_value is not None:
                    incomplete = True
                    diagnostics.add("malformed_excerpt")
                records.append(
                    SourceReference(
                        id=ref_id,
                        created_at=at,
                        observation_id=identifier(request.id, "observation"),
                        url=url,
                        metadata_artifact_id=raw.id,
                        metadata_location=pointer,
                        reference_kind="reference",
                        excerpt=excerpt,
                    )
                )
                refs.append(ref_id)
                urls.add(url)
        for key in ("items", "components"):
            if key not in node:
                continue
            children = node[key]
            if not isinstance(children, list):
                incomplete = True
                diagnostics.add("unsupported_source_structure")
                continue
            for index, child in enumerate(children):
                if isinstance(child, dict):
                    walk(child, f"{path}/{key}/{index}")
                else:
                    incomplete = True
                    diagnostics.add("malformed_source_element")

    walk(overview, location)
    citations: list[str] = []
    # Intentionally narrow: code/HTML/escaped Markdown is not citation-assessable.
    unsafe_markup = any(character in answer.text for character in ("`", "<", ">", "\\")) or any(
        line.startswith(("    ", "\t")) for line in answer.text.splitlines()
    )
    if not unsafe_markup:
        for match in MARKER.finditer(answer.text):
            # Numbered provider marker AND an exact captured reference URL, not an ordinary link.
            if (
                match.group(1) not in urls
                or (match.start() and answer.text[match.start() - 1] in "![")
                or answer.text[: match.start()].count("[")
                != answer.text[: match.start()].count("]")
            ):
                continue
            citation_id = identifier(request.id, "citation", str(match.start()))
            records.append(
                SourceReference(
                    id=citation_id,
                    created_at=at,
                    observation_id=identifier(request.id, "observation"),
                    url=match.group(1),
                    metadata_artifact_id=raw.id,
                    metadata_location=location + "/markdown",
                    reference_kind="citation",
                    excerpt=unknown("citation_marker_is_not_an_excerpt", SpanRef),
                    citation_span=SpanRef(
                        text_id=answer.id,
                        start=match.start(),
                        end=match.end(),
                        exact_text=match.group(),
                    ),
                )
            )
            citations.append(citation_id)
    ref_state = Availability.INCOMPLETE if incomplete else Availability.AVAILABLE
    source_ids = (
        Available[tuple[str, ...]](
            availability=ref_state,
            data=tuple(refs + citations),
            reason="source_capture_incomplete" if incomplete else None,
        )
        if assessed or refs
        else unknown("source_metadata_unavailable", tuple[str, ...])
    )
    # Empty is assessable only for a fully supported, explicitly empty source structure
    # and a simple answer with no potential link/marker/HTML/code syntax.
    if (
        not refs
        and assessed
        and not incomplete
        and not unsafe_markup
        and not any(c in answer.text for c in "[]<>`\\")
    ):
        citation_ids = Available[tuple[str, ...]](availability=Availability.AVAILABLE, data=())
    elif citations or assessed or refs:
        citation_ids = Available[tuple[str, ...]](
            availability=Availability.INCOMPLETE,
            data=tuple(citations),
            reason="visible_citation_capture_not_proven_complete",
        )
    else:
        citation_ids = unknown("visible_citation_mapping_unavailable", tuple[str, ...])
    if unsafe_markup:
        diagnostics.add("unsupported_citation_markup")
    return records, source_ids, citation_ids, tuple(sorted(diagnostics))


def normalize(
    request: CaptureRequest,
    response: HttpResponse | None,
    received_at: datetime,
    transport_error: ErrorDetail | None = None,
) -> NormalizedCapture:
    request = CaptureRequest.model_validate_json(request.model_dump_json())
    raw = raw_reference(request.id, response.payload) if response is not None else None
    headers = allowed_headers(response.headers) if response is not None else {}
    envelope: dict[str, JsonValue] = {}
    task: dict[str, JsonValue] = {}
    failure: ErrorDetail | None = transport_error
    diagnostics: tuple[str, ...] = ()
    answer_location: str | None = None
    records: list[Record] = [request]
    if raw is not None:
        records.append(raw)
    reported: Available[Settings] = unknown("reported_settings_unavailable", Settings)
    source_ids: Available[tuple[str, ...]] = unknown("source_metadata_unavailable", tuple[str, ...])
    citation_ids: Available[tuple[str, ...]] = unknown(
        "visible_citation_mapping_unavailable", tuple[str, ...]
    )
    answer_id: str | None = None
    provider_id = headers.get("x-request-id")
    try:
        if transport_error is not None:
            raise AcquisitionError(transport_error.code, transport_error.provider_request_id)
        if response is None:
            raise AcquisitionError("malformed_response")
        http_error = status_error(response.status, http=True)
        try:
            envelope = parse(response.payload)
        except AcquisitionError:
            raise AcquisitionError(http_error or "malformed_response", provider_id) from None
        tasks = envelope.get("tasks")
        if isinstance(tasks, list) and len(tasks) == 1 and isinstance(tasks[0], dict):
            task = tasks[0]
            provider_id = string(task.get("id")) or provider_id
        if http_error:
            raise AcquisitionError(http_error, provider_id)
        envelope_status = integer(envelope.get("status_code"))
        if envelope_status is None:
            raise AcquisitionError("malformed_response", provider_id)
        if code := status_error(envelope_status):
            raise AcquisitionError(code, provider_id)
        if not task or integer(envelope.get("tasks_count")) != 1:
            raise AcquisitionError("malformed_response", provider_id)
        task_status = integer(task.get("status_code"))
        if task_status is None:
            raise AcquisitionError("malformed_response", provider_id)
        if code := status_error(task_status):
            raise AcquisitionError(code, provider_id)
        if integer(envelope.get("tasks_error")) != 0 or integer(task.get("result_count")) != 1:
            raise AcquisitionError("malformed_response", provider_id)
        task_data = task.get("data")
        if not isinstance(task_data, dict) or task_data.get("tag") != request_tag(request):
            raise AcquisitionError("response_correlation_failed", provider_id)
        expected_path = ["v3", "serp", "google", "ai_mode", "live", "advanced"]
        if task.get("path") != expected_path:
            raise AcquisitionError("unexpected_provider_endpoint", provider_id)
        results = task.get("result")
        if not isinstance(results, list) or len(results) != 1:
            raise AcquisitionError("malformed_response", provider_id)
        result = object_value(results[0])
        if result.get("type") != "ai_mode":
            raise AcquisitionError("unexpected_provider_product", provider_id)
        settings = {
            key: result[key]
            for key in ("language_code", "location_code", "se_domain", "datetime")
            if key in result
        }
        if settings:
            reported = Available(
                availability=Availability.INCOMPLETE,
                data=Settings(version=VERSION, values=settings),
                reason="provider_reported_subset_not_independently_verified",
            )
        if result.get("language_code") not in (None, "de"):
            raise AcquisitionError("reported_settings_mismatch", provider_id)
        items = result.get("items")
        if items is None or items == []:
            raise AcquisitionError("answer_absent", provider_id)
        if not isinstance(items, list):
            raise AcquisitionError("malformed_response", provider_id)
        candidates = [
            (index, item)
            for index, item in enumerate(items)
            if isinstance(item, dict) and item.get("type") == "ai_overview"
        ]
        if not candidates:
            raise AcquisitionError("answer_absent", provider_id)
        if len(candidates) != 1:
            raise AcquisitionError("malformed_response", provider_id)
        index, overview = candidates[0]
        answer_value = overview.get("markdown")
        if answer_value is None or isinstance(answer_value, str) and not answer_value.strip():
            raise AcquisitionError("answer_absent", provider_id)
        if not isinstance(answer_value, str):
            raise AcquisitionError("malformed_response", provider_id)
        assert raw is not None
        answer = TextRecord(
            id=identifier(request.id, "answer"), text=answer_value, artifact_id=raw.id
        )
        location = f"/tasks/0/result/0/items/{index}"
        answer_location = location + "/markdown"
        extra, source_ids, citation_ids, diagnostics = sources(
            request, raw, answer, overview, location, received_at, len(items) != 1
        )
        answer_id = answer.id
        records.extend([answer, *extra])
    except AcquisitionError as error:
        failure = AcquisitionError(
            error.detail.code, provider_id or error.detail.provider_request_id
        ).detail
    except (ValueError, TypeError, RecursionError):
        failure = AcquisitionError("malformed_response", provider_id).detail
    observation = Observation(
        id=identifier(request.id, "observation"),
        created_at=received_at,
        request_id=request.id,
        query_id=request.query_id,
        product=request.product,
        provider=request.provider,
        requested_settings=request.requested_settings,
        reported_settings=reported,
        status=ProcessingStatus.FAILED if failure else ProcessingStatus.SUCCEEDED,
        raw_artifact_id=raw.id if raw else None,
        answer_text_id=answer_id,
        source_reference_ids=source_ids,
        citation_reference_ids=citation_ids,
        fanout_queries=unknown("fanout_not_supported_by_endpoint", tuple[str, ...]),
        normalization_version=VERSION,
        provider_request_id=provider_id,
        error=failure,
    )
    envelope_cost = money(envelope.get("cost"))
    task_cost = money(task.get("cost"))
    cost = envelope_cost if envelope_cost is not None else task_cost
    receipt = CaptureReceipt(
        request_id=request.id,
        observation_id=observation.id,
        received_at=received_at,
        raw_artifact=raw,
        http_status=response.status if response else None,
        response_headers=headers,
        provider_request_id=provider_id,
        envelope_status=integer(envelope.get("status_code")),
        task_status=integer(task.get("status_code")),
        envelope_cost_usd=envelope_cost,
        task_cost_usd=task_cost,
        provider_time=string(task.get("time")) or string(envelope.get("time")),
        usage=Available(
            availability=Availability.INCOMPLETE,
            data=Usage(
                input_tokens=None,
                output_tokens=None,
                requests=0
                if transport_error
                and transport_error.code
                in {
                    "live_not_authorized",
                    "live_request_not_authorized",
                    "request_limit_exhausted",
                    "credentials_missing",
                }
                else 1,
                cost=cost,
                currency="USD" if cost is not None else None,
            ),
            reason="provider_token_usage_unavailable"
            if cost is not None
            else "provider_cost_unavailable",
        ),
        transport_error=transport_error,
        normalization_error=failure,
        answer_location=answer_location,
        diagnostics=diagnostics,
    )
    records.append(observation)
    validate_links(RecordSet(records=tuple(records)))
    return NormalizedCapture(receipt=receipt, observation=observation, records=tuple(records))
