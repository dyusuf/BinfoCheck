"""Deterministic citation presence; no model, retrieval or support assessment."""

import re
from typing import Literal

from pydantic import JsonValue

from binfocheck.acquisition.errors import AcquisitionError
from binfocheck.acquisition.normalize import parse
from binfocheck.domain.claims import CitationAssociation, Claim
from binfocheck.domain.common import CitationStatus, Outcome, VersionRef
from binfocheck.domain.interfaces import ClaimRequest
from binfocheck.domain.observations import SourceReference
from binfocheck.domain.storage import ArtifactStore, RecordStore
from binfocheck.domain.text import ArtifactRef, SpanRef
from binfocheck.domain.validation import LinkError
from binfocheck.text.errors import TextError
from binfocheck.text.persistence import load_index, load_inputs

from .config import CONFIGURATION, RULES, VERSION, CitationSettings, identity
from .errors import CitationError, check
from .hosts import classify_host
from .persistence import Audit, Store, closure
from .scope import covers, infer_scope, intersects, supported

MARKER = re.compile(r"\[\[[0-9]+\]\]\((https?://[^\s()]+)\)")


def citation_route(status: CitationStatus) -> Literal["category_1", "matching", "citation_unclear"]:
    if status == CitationStatus.YES:
        return "category_1"
    if status == CitationStatus.NO:
        return "matching"
    return "citation_unclear"


def pointer(document: JsonValue, location: str) -> JsonValue:
    check(location.startswith("/"), "invalid_metadata_location")
    current = document
    for part in location[1:].split("/"):
        check(re.search(r"~(?![01])", part) is None, "invalid_metadata_location")
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif (
            isinstance(current, list)
            and re.fullmatch(r"0|[1-9][0-9]*", part)
            and int(part) < len(current)
        ):
            current = current[int(part)]
        else:
            raise CitationError("invalid_metadata_location")
    return current


def evidence_reasons(
    source_refs: tuple[SourceReference, ...],
    citations: tuple[SourceReference, ...],
    document: JsonValue,
    answer: str,
) -> dict[str, str | None]:
    """Ground T01 recorded markers to raw Markdown and captured reference URLs."""
    urls: set[str] = set()
    for ref in source_refs:
        if ref.reference_kind == "reference":
            value = pointer(document, ref.metadata_location)
            check(
                isinstance(value, dict) and value.get("url") == ref.url, "source_metadata_mismatch"
            )
            urls.add(ref.url)
    reasons: dict[str, str | None] = {}
    for ref in citations:
        value = pointer(document, ref.metadata_location)
        if ref.citation_span is None:
            reasons[ref.id] = "missing_marker_location"
            continue
        check(value == answer, "citation_metadata_mismatch")
        match = MARKER.fullmatch(ref.citation_span.exact_text)
        check(match is not None and match.group(1) == ref.url, "citation_marker_mismatch")
        start = ref.citation_span.start
        # T01 excludes image/nested marker contexts; an arbitrary span is not enough.
        unsafe = (start > 0 and answer[start - 1] in "![") or answer[:start].count("[") != answer[
            :start
        ].count("]")
        reasons[ref.id] = (
            "unestablished_marker_syntax"
            if unsafe
            else None
            if ref.url in urls
            else "unestablished_reference_metadata"
        )
    return reasons


class StoredCitationMapper:
    def __init__(self, records: RecordStore, artifacts: ArtifactStore) -> None:
        self.store = Store(records, artifacts)

    def map_citations(self, request: ClaimRequest) -> Outcome[CitationAssociation]:
        try:
            result = self._map(ClaimRequest.model_validate_json(request.model_dump_json()))
            return Outcome(status="succeeded", value=result, error=None)
        except (CitationError, TextError) as error:
            return Outcome(status="failed", value=None, error=error.detail)
        except (ValueError, TypeError, RecursionError, LinkError, AcquisitionError):
            return Outcome(
                status="failed", value=None, error=CitationError("invalid_citation_input").detail
            )

    def _map(self, request: ClaimRequest) -> CitationAssociation:
        check(request.settings.version == VERSION, "invalid_citation_settings")
        settings = CitationSettings.model_validate(request.settings.values)
        store = self.store
        claim = store.record(request.claim_id, Claim)
        check(claim.analysis_run_id == request.analysis_run_id, "run_mismatch")
        check(bool(claim.original_span.exact_text.strip()), "empty_original_span")
        run, observation, answer = load_inputs(
            store.records, request.analysis_run_id, claim.observation_id
        )
        manifest, units = load_index(
            store.records, store.artifacts, settings.index_artifact_id, run, observation, answer
        )
        check(set(claim.context_unit_ids).issubset({u.id for u in units}), "claim_cohort_mismatch")
        ref_ids = set(observation.source_reference_ids.data or ()) | set(
            observation.citation_reference_ids.data or ()
        )
        check(len(ref_ids) <= RULES.max_references, "reference_limit")
        references = tuple(store.record(id, SourceReference) for id in sorted(ref_ids))
        captured = set(observation.citation_reference_ids.data or ())
        citations = tuple(
            sorted(
                (r for r in references if r.id in captured),
                key=lambda r: (
                    r.citation_span.start if r.citation_span else len(answer.text),
                    r.id,
                ),
            )
        )
        hashes = closure(
            store,
            (claim, *units, *references, store.record(settings.index_artifact_id, ArtifactRef)),
        )
        work = identity("work", {"request": request.model_dump(mode="json"), "inputs": hashes})
        saved = store.replay(identity("audit", work), request, hashes, work)
        if saved is not None:
            return saved
        known = observation.normalization_version == VersionRef(
            name=RULES.normalizer_name, version=RULES.normalizer_version
        )
        reasons = (
            evidence_reasons(
                references, citations, parse(store.bytes(answer.artifact_id)), answer.text
            )
            if known
            else {r.id: "unknown_normalizer" for r in citations}
        )
        assessments = tuple(
            infer_scope(r, citations, units, manifest, answer, classify_host(r.url), reasons[r.id])
            for r in citations
        )
        relevant = tuple(
            a for a in assessments if a.scope is None or intersects(a.scope, claim.original_span)
        )
        positive = tuple(a for a in relevant if a.clear and a.host.status == "target" and a.scope)
        positive_scopes = tuple(a.scope for a in positive if a.scope is not None)
        supported_scopes = tuple(
            u.span
            for u in units
            if u.unit_kind == "sentence"
            and u.parent_unit_id not in manifest.opaque_unit_ids
            and supported(u, citations)
        )
        scope_ok = known and covers(claim.original_span, supported_scopes, answer)
        if covers(claim.original_span, positive_scopes, answer) and positive:
            status, reason = CitationStatus.YES, "clear_full_citation_coverage"
            selected = positive
        elif observation.citation_reference_ids.availability != "available":
            status, reason, selected = (
                CitationStatus.UNCLEAR,
                "citation_capture_not_complete",
                relevant,
            )
        elif not scope_ok or any(not a.clear or a.host.status == "unclear" for a in relevant):
            status, reason, selected = CitationStatus.UNCLEAR, "citation_scope_unclear", relevant
        elif positive:
            status, reason, selected = CitationStatus.UNCLEAR, "partial_citation_coverage", relevant
        else:
            status, reason, selected = CitationStatus.NO, "assessable_citation_absence", relevant
        config_ref = store.save("configuration", CONFIGURATION)
        input_ref = store.save(
            "inputs", {"request": request.model_dump(mode="json"), "hashes": hashes}
        )
        evidence: list[SpanRef] = [claim.original_span]
        for assessment in relevant:
            for span in (assessment.marker, assessment.scope):
                if span and span not in evidence:
                    evidence.append(span)
        result = CitationAssociation(
            id=identity("association", work),
            created_at=run.created_at,
            analysis_run_id=run.id,
            observation_id=observation.id,
            claim_id=claim.id,
            input_ids=tuple(
                dict.fromkeys(
                    (
                        claim.id,
                        observation.id,
                        answer.id,
                        settings.index_artifact_id,
                        config_ref.id,
                        input_ref.id,
                        *(r.id for r in references),
                    )
                )
            ),
            reference_ids=tuple(a.reference_id for a in selected),
            status=status,
            scope_assessable=status != CitationStatus.UNCLEAR,
            rule_version=VERSION,
            evidence_spans=tuple(evidence),
            reason=reason,
        )
        return store.publish(
            Audit(
                work_key=work,
                request=request,
                input_hashes=hashes,
                assessments=assessments,
                result=result,
            )
        )
