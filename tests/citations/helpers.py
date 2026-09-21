"""Explicitly synthetic T01-shaped metadata and accepted Claim fixtures, never live."""

from binfocheck.citations import CitationSettings
from binfocheck.citations.config import canonical
from binfocheck.citations.mapper import MARKER
from binfocheck.domain.claims import Claim
from binfocheck.domain.common import Availability, Available, VersionRef
from binfocheck.domain.interfaces import ClaimRequest
from binfocheck.domain.observations import Observation, SourceReference
from binfocheck.domain.text import ArtifactRef, SpanRef
from binfocheck.storage import MemoryStore
from binfocheck.text import StoredAnswerIndexer, index_reference_id
from tests.storage.helpers import Store, all_records, payload, success
from tests.text.helpers import AT, seed

URL = "https://www.diabinfo.de/example"
CITE = f"[[1]]({URL})"


def seed_pair(
    store: Store,
    text: str = "Äpfel sind rot. " + CITE,
    quote: str = "Äpfel sind rot.",
    availability: Availability = Availability.AVAILABLE,
    *,
    prefix: str = "a",
    start: int | None = None,
    normalizer: str = "dataforseo-ai-mode-normalizer",
    capture_markers: bool = True,
    unlocated: bool = False,
) -> ClaimRequest:
    with MemoryStore() as staging:
        index_request, answer = seed(staging, text, prefix)
        initial = all_records(staging)
    matches = list(MARKER.finditer(text)) if capture_markers else []
    entries = [{"url": m.group(1)} for m in matches]
    raw = payload(prefix + "-raw", canonical({"markdown": text, "references": entries}))
    refs: list[SourceReference] = []
    citation_ids: list[str] = []
    for i, match in enumerate(matches):
        refs.append(
            SourceReference(
                id=f"{prefix}-source-{i}",
                metadata_location=f"/references/{i}",
                reference_kind="reference",
                created_at=AT,
                observation_id=prefix + "-obs",
                url=match.group(1),
                metadata_artifact_id=raw.ref.id,
                excerpt=Available[SpanRef](
                    availability=Availability.UNAVAILABLE, data=None, reason="synthetic"
                ),
            )
        )
        ref = SourceReference(
            id=f"{prefix}-citation-{i}",
            metadata_location="/markdown",
            reference_kind="citation",
            citation_span=None
            if unlocated
            else SpanRef(
                text_id=answer.id, start=match.start(), end=match.end(), exact_text=match.group()
            ),
            created_at=AT,
            observation_id=prefix + "-obs",
            url=match.group(1),
            metadata_artifact_id=raw.ref.id,
            excerpt=Available[SpanRef](
                availability=Availability.UNAVAILABLE, data=None, reason="synthetic"
            ),
        )
        refs.append(ref)
        citation_ids.append(ref.id)
    success(store.put_artifact(raw))
    for record in initial:
        if isinstance(record, ArtifactRef):
            continue
        if isinstance(record, Observation):
            record = record.model_copy(
                update={
                    "normalization_version": VersionRef(name=normalizer, version="1"),
                    "source_reference_ids": Available[tuple[str, ...]](
                        availability=Availability.AVAILABLE, data=tuple(r.id for r in refs)
                    ),
                    "citation_reference_ids": Available[tuple[str, ...]](
                        availability=availability,
                        data=None
                        if availability == Availability.UNAVAILABLE
                        else tuple(citation_ids),
                        reason=None
                        if availability == Availability.AVAILABLE
                        else "synthetic coverage limitation",
                    ),
                }
            )
        success(store.put_record(record))
    for ref in refs:
        success(store.put_record(ref))
    units = success(StoredAnswerIndexer(store, store).index_answer(index_request))
    left = text.index(quote) if start is None else start
    contexts = tuple(u.id for u in units if u.span.start < left + len(quote) and left < u.span.end)
    claim = Claim(
        id=prefix + "-claim",
        created_at=AT,
        analysis_run_id=index_request.analysis_run_id,
        observation_id=index_request.observation_id,
        input_ids=(answer.id, index_request.observation_id),
        normalized_claim=quote,
        original_span=SpanRef(
            text_id=answer.id, start=left, end=left + len(quote), exact_text=quote
        ),
        context_unit_ids=contexts,
        decision_ids=(),
        claim_group_id=prefix + "-group",
    )
    success(store.put_record(claim))
    return ClaimRequest(
        analysis_run_id=claim.analysis_run_id,
        claim_id=claim.id,
        settings=CitationSettings(
            index_artifact_id=index_reference_id(index_request, answer)
        ).envelope(),
    )
