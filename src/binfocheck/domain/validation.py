"""Explicit graph validation; call after loading a complete set of linked records.

This checks contract integrity, not whether model/evidence judgments are correct.
External identities (query, reviewer, model, version, group, provider request, storage
key and work key) are opaque labels, not references to a missing local record type.
"""

from collections.abc import Iterable
from typing import cast

from .claims import CitationAssociation, Claim, ExtractionIssue
from .common import Contract, DerivedRecord
from .corpus import ArticleVersion, CorpusManifest, Passage
from .decisions import DecisionRecord, GenerationResult
from .evidence import AlternativeInspection, Finding
from .observations import CaptureRequest, Observation, SourceReference, TextUnit
from .records import Record, RecordSet
from .retrieval import CandidatePair, RetrievalBatch
from .runs import Review, RunManifest, StepAttempt
from .text import ArtifactRef, SpanRef, TextRecord


class LinkError(ValueError):
    def __init__(self, code: str, record_id: str, detail: str) -> None:
        self.code = code
        self.record_id = record_id
        super().__init__(f"{code}: {record_id}: {detail}")


def spans_in(value: object) -> Iterable[SpanRef]:
    if isinstance(value, SpanRef):
        yield value
    elif isinstance(value, Contract):
        for name in type(value).model_fields:
            yield from spans_in(getattr(value, name))
    elif isinstance(value, tuple):
        for item in cast(tuple[object, ...], value):
            yield from spans_in(item)


class LinkedRecords:
    def __init__(self, bundle: RecordSet) -> None:
        self.records: dict[str, Record] = {}
        for record in bundle.records:
            if record.id in self.records:
                raise LinkError("duplicate_id", record.id, "IDs must be unique")
            self.records[record.id] = record

    def require[T: Record](self, id: str, expected: type[T], owner: str) -> T:
        target = self.records.get(id)
        if target is None:
            raise LinkError("missing_id", owner, id)
        if not isinstance(target, expected):
            raise LinkError("wrong_record_kind", owner, f"{id}: expected {expected.__name__}")
        return target

    def any_id(self, id: str, owner: str) -> Record:
        if id not in self.records:
            raise LinkError("missing_id", owner, id)
        return self.records[id]

    def check(self, condition: bool, code: str, owner: str, detail: str = "") -> None:
        if not condition:
            raise LinkError(code, owner, detail)

    def same_run(self, source: DerivedRecord, target: DerivedRecord) -> None:
        self.check(
            source.analysis_run_id == target.analysis_run_id,
            "run_mismatch",
            source.id,
            target.id,
        )

    def span(self, span: SpanRef, owner: str) -> None:
        text = self.require(span.text_id, TextRecord, owner)
        self.check(span.end <= len(text.text), "span_out_of_bounds", owner)
        self.check(text.text[span.start : span.end] == span.exact_text, "quote_mismatch", owner)
        if span.source_unit_id is not None:
            unit = self.require(span.source_unit_id, TextUnit, owner)
            self.check(
                unit.span.text_id == span.text_id
                and unit.span.start <= span.start < span.end <= unit.span.end,
                "source_unit_mismatch",
                owner,
            )

    def observation(
        self,
        record: TextUnit
        | Claim
        | ExtractionIssue
        | CitationAssociation
        | AlternativeInspection
        | Finding,
    ) -> Observation:
        observation = self.require(record.observation_id, Observation, record.id)
        run = self.require(record.analysis_run_id, RunManifest, record.id)
        self.check(observation.id in run.observation_ids, "observation_run_mismatch", record.id)
        return observation

    def claim(
        self,
        record: CitationAssociation
        | RetrievalBatch
        | CandidatePair
        | AlternativeInspection
        | Finding,
    ) -> Claim:
        claim = self.require(record.claim_id, Claim, record.id)
        self.same_run(record, claim)
        if isinstance(record, (CitationAssociation, AlternativeInspection, Finding)):
            self.check(
                record.observation_id == claim.observation_id, "observation_mismatch", record.id
            )
        return claim

    def decisions(self, record: DerivedRecord, ids: Iterable[str]) -> None:
        for id in ids:
            decision = self.require(id, DecisionRecord, record.id)
            self.same_run(record, decision)

    def text_lineage(self, text: TextRecord, owner: str) -> tuple[TextRecord, ...]:
        """Resolve representations back to their original text without altering them."""
        lineage: list[TextRecord] = []
        seen: set[str] = set()
        while True:
            self.check(text.id not in seen, "text_lineage_cycle", owner, text.id)
            seen.add(text.id)
            lineage.append(text)
            if text.source_text_id is None:
                return tuple(lineage)
            text = self.require(text.source_text_id, TextRecord, owner)

    def validate(self) -> None:
        for record in self.records.values():
            self.validate_record(record)
        self.validate_history()

    def validate_record(self, r: Record) -> None:
        for span in spans_in(r):
            self.span(span, r.id)
        if isinstance(r, DerivedRecord):
            run = self.require(r.analysis_run_id, RunManifest, r.id)
            for id in r.input_ids:
                target = self.any_id(id, r.id)
                if isinstance(target, DerivedRecord):
                    self.same_run(r, target)
                elif isinstance(target, Observation):
                    self.check(target.id in run.observation_ids, "observation_run_mismatch", r.id)
        if isinstance(
            r,
            (TextUnit, Claim, ExtractionIssue, CitationAssociation, AlternativeInspection, Finding),
        ):
            self.observation(r)
        if isinstance(
            r, (CitationAssociation, RetrievalBatch, CandidatePair, AlternativeInspection, Finding)
        ):
            self.claim(r)

        if isinstance(r, TextRecord):
            self.require(r.artifact_id, ArtifactRef, r.id)
            self.text_lineage(r, r.id)
        elif isinstance(r, Observation):
            request = self.require(r.request_id, CaptureRequest, r.id)
            self.check(
                (r.query_id, r.product, r.provider, r.requested_settings)
                == (
                    request.query_id,
                    request.product,
                    request.provider,
                    request.requested_settings,
                ),
                "capture_request_mismatch",
                r.id,
            )
            if r.raw_artifact_id:
                self.require(r.raw_artifact_id, ArtifactRef, r.id)
            if r.answer_text_id:
                answer = self.require(r.answer_text_id, TextRecord, r.id)
                lineage = self.text_lineage(answer, r.id)
                self.check(
                    lineage[-1].artifact_id == r.raw_artifact_id,
                    "answer_artifact_provenance_mismatch",
                    r.id,
                )
                if r.status == "succeeded":
                    self.check(bool(answer.text.strip()), "successful_answer_empty", r.id)
            for id in (r.source_reference_ids.data or ()) + (r.citation_reference_ids.data or ()):
                ref = self.require(id, SourceReference, r.id)
                self.check(ref.observation_id == r.id, "reference_observation_mismatch", r.id)
            for id in r.citation_reference_ids.data or ():
                ref = self.require(id, SourceReference, r.id)
                self.check(ref.reference_kind == "citation", "not_a_citation_reference", r.id)
        elif isinstance(r, SourceReference):
            observation = self.require(r.observation_id, Observation, r.id)
            self.require(r.metadata_artifact_id, ArtifactRef, r.id)
            self.check(
                r.metadata_artifact_id == observation.raw_artifact_id,
                "source_metadata_artifact_mismatch",
                r.id,
            )
            if r.citation_span:
                self.check(
                    r.citation_span.text_id == observation.answer_text_id,
                    "citation_text_mismatch",
                    r.id,
                )
        elif isinstance(r, TextUnit):
            observation = self.require(r.observation_id, Observation, r.id)
            self.check(r.span.text_id == observation.answer_text_id, "unit_text_mismatch", r.id)
            for id in (r.parent_unit_id, r.heading_unit_id):
                if id:
                    unit = self.require(id, TextUnit, r.id)
                    self.same_run(r, unit)
                    self.check(
                        unit.observation_id == r.observation_id and unit.id != r.id,
                        "unit_relationship_mismatch",
                        r.id,
                    )
            if r.parent_unit_id:
                parent = self.require(r.parent_unit_id, TextUnit, r.id)
                self.check(
                    parent.span.start <= r.span.start and r.span.end <= parent.span.end,
                    "unit_outside_parent",
                    r.id,
                )
            if r.heading_unit_id:
                heading = self.require(r.heading_unit_id, TextUnit, r.id)
                self.check(heading.unit_kind == "heading", "not_a_heading", r.id)
        elif isinstance(r, (Claim, ExtractionIssue)):
            observation = self.require(r.observation_id, Observation, r.id)
            if r.original_span:
                self.check(
                    r.original_span.text_id == observation.answer_text_id,
                    "claim_text_mismatch",
                    r.id,
                )
                if r.original_span.source_unit_id:
                    self.check(
                        r.original_span.source_unit_id in r.context_unit_ids,
                        "source_unit_not_in_context",
                        r.id,
                    )
            for id in r.context_unit_ids:
                unit = self.require(id, TextUnit, r.id)
                self.same_run(r, unit)
                self.check(
                    unit.observation_id == r.observation_id, "context_observation_mismatch", r.id
                )
            self.decisions(r, r.decision_ids)
        elif isinstance(r, CitationAssociation):
            observation = self.require(r.observation_id, Observation, r.id)
            captured = observation.citation_reference_ids
            if r.status == "no":
                self.check(
                    captured.availability == "available",
                    "citation_no_requires_complete_capture",
                    r.id,
                )
            for id in r.reference_ids:
                ref = self.require(id, SourceReference, r.id)
                self.check(
                    ref.observation_id == r.observation_id, "reference_observation_mismatch", r.id
                )
                if r.status == "yes":
                    self.check(ref.reference_kind == "citation", "not_a_citation_reference", r.id)
                if ref.reference_kind == "citation":
                    self.check(id in (captured.data or ()), "citation_not_captured", r.id, id)
            for span in r.evidence_spans:
                self.check(
                    span.text_id == observation.answer_text_id, "citation_text_mismatch", r.id
                )
        elif isinstance(r, ArticleVersion):
            if r.raw_artifact_id:
                self.require(r.raw_artifact_id, ArtifactRef, r.id)
            if r.raw_text_id:
                raw = self.require(r.raw_text_id, TextRecord, r.id)
                self.check(
                    raw.artifact_id == r.raw_artifact_id and raw.source_text_id is None,
                    "article_raw_provenance_mismatch",
                    r.id,
                )
            if r.cleaned_text_id:
                cleaned = self.require(r.cleaned_text_id, TextRecord, r.id)
                lineage = self.text_lineage(cleaned, r.id)
                self.check(
                    lineage[-1].id == r.raw_text_id,
                    "article_cleaned_lineage_mismatch",
                    r.id,
                )
            for span in r.heading_spans:
                self.check(span.text_id == r.cleaned_text_id, "article_heading_text_mismatch", r.id)
            if r.previous_version_id:
                old = self.require(r.previous_version_id, ArticleVersion, r.id)
                self.check(old.url == r.url and old.id != r.id, "article_version_mismatch", r.id)
        elif isinstance(r, Passage):
            article = self.require(r.article_version_id, ArticleVersion, r.id)
            self.check(
                article.status == "usable" and r.span.text_id == article.cleaned_text_id,
                "passage_article_mismatch",
                r.id,
            )
            for span in r.heading_spans:
                self.check(
                    span.text_id == article.cleaned_text_id, "passage_heading_text_mismatch", r.id
                )
            if r.parent_passage_id:
                parent = self.require(r.parent_passage_id, Passage, r.id)
                self.check(
                    parent.article_version_id == r.article_version_id and parent.id != r.id,
                    "passage_parent_mismatch",
                    r.id,
                )
        elif isinstance(r, CorpusManifest):
            for id in r.article_version_ids:
                article = self.require(id, ArticleVersion, r.id)
                if r.status == "ready":
                    self.check(article.status == "usable", "corpus_contains_unusable_article", r.id)
            for id in r.passage_ids:
                passage = self.require(id, Passage, r.id)
                self.check(
                    passage.article_version_id in r.article_version_ids,
                    "corpus_passage_mismatch",
                    r.id,
                )
        elif isinstance(r, RetrievalBatch):
            self.require(r.corpus_manifest_id, CorpusManifest, r.id)
            seen: set[str] = set()
            for id in r.candidate_pair_ids:
                pair = self.require(id, CandidatePair, r.id)
                self.check(pair.retrieval_batch_id == r.id, "pair_batch_mismatch", r.id)
                self.check(pair.passage_id not in seen, "duplicate_candidate_passage", r.id)
                seen.add(pair.passage_id)
        elif isinstance(r, CandidatePair):
            batch = self.require(r.retrieval_batch_id, RetrievalBatch, r.id)
            corpus = self.require(r.corpus_manifest_id, CorpusManifest, r.id)
            self.same_run(r, batch)
            self.check(
                r.claim_id == batch.claim_id
                and r.corpus_manifest_id == batch.corpus_manifest_id
                and r.index_id == batch.index.id
                and r.id in batch.candidate_pair_ids,
                "pair_batch_mismatch",
                r.id,
            )
            for id in (r.passage_id, *r.context_passage_ids):
                self.require(id, Passage, r.id)
                self.check(id in corpus.passage_ids, "pair_passage_outside_corpus", r.id)
            self.decisions(
                r, (id for id in (r.verification_decision_id, r.correspondence_decision_id) if id)
            )
        elif isinstance(r, DecisionRecord):
            for id in r.input_artifact_ids:
                self.require(id, ArtifactRef, r.id)
            if isinstance(r.result, GenerationResult):
                self.require(r.result.output_artifact_id, ArtifactRef, r.id)
        elif isinstance(r, AlternativeInspection):
            ref = self.require(r.source_reference_id, SourceReference, r.id)
            self.check(
                ref.observation_id == r.observation_id, "alternative_observation_mismatch", r.id
            )
            self.check(ref.duplicate_group == r.duplicate_group, "duplicate_group_mismatch", r.id)
            if r.excerpt_text_id:
                self.require(r.excerpt_text_id, TextRecord, r.id)
                self.check(
                    ref.excerpt.data is not None and ref.excerpt.data.text_id == r.excerpt_text_id,
                    "alternative_excerpt_mismatch",
                    r.id,
                )
            if r.decision_id:
                self.decisions(r, (r.decision_id,))
        elif isinstance(r, Finding):
            citation = self.require(r.citation_association_id, CitationAssociation, r.id)
            self.same_run(r, citation)
            self.check(citation.claim_id == r.claim_id, "finding_citation_mismatch", r.id)
            # Validate consistency of supplied states, never calculate a category.
            if r.category == 1:
                self.check(citation.status == "yes", "category_one_requires_citation", r.id)
            if r.category in (2, 3, 4) or r.status == "no_match_found":
                self.check(citation.status == "no", "uncited_finding_requires_no_citation", r.id)
            if r.status == "citation_unclear":
                self.check(
                    citation.status == "unclear", "unclear_finding_requires_unclear_citation", r.id
                )
            for id in r.candidate_pair_ids:
                pair = self.require(id, CandidatePair, r.id)
                self.same_run(r, pair)
                self.check(pair.claim_id == r.claim_id, "finding_pair_claim_mismatch", r.id)
            for id in r.alternative_inspection_ids.data or ():
                alternative = self.require(id, AlternativeInspection, r.id)
                self.same_run(r, alternative)
                self.check(alternative.claim_id == r.claim_id, "finding_alternative_mismatch", r.id)
            self.decisions(r, r.decision_ids)
        elif isinstance(r, RunManifest):
            for id in r.input_ids:
                self.any_id(id, r.id)
            for id in r.observation_ids:
                self.require(id, Observation, r.id)
            if r.corpus_manifest_id:
                self.require(r.corpus_manifest_id, CorpusManifest, r.id)
        elif isinstance(r, StepAttempt):
            for id in r.output_ids:
                output = self.any_id(id, r.id)
                if isinstance(output, DerivedRecord):
                    self.same_run(r, output)
        elif isinstance(r, Review):
            finding = self.require(r.finding_id, Finding, r.id)
            self.same_run(r, finding)

    def validate_history(self) -> None:
        successors: dict[str, str] = {}
        findings: dict[tuple[str, str], list[Finding]] = {}
        for r in self.records.values():
            previous: str | None = None
            if isinstance(r, Finding):
                findings.setdefault((r.analysis_run_id, r.claim_id), []).append(r)
                previous = r.supersedes_finding_id
                if previous:
                    old = self.require(previous, Finding, r.id)
                    self.same_run(r, old)
                    self.check(r.claim_id == old.claim_id, "finding_history_claim_mismatch", r.id)
                    self.check(r.created_at >= old.created_at, "history_time_reversed", r.id)
            elif isinstance(r, Review):
                previous = r.supersedes_review_id
                if previous:
                    old_review = self.require(previous, Review, r.id)
                    self.same_run(r, old_review)
                    self.check(
                        r.finding_id == old_review.finding_id,
                        "review_history_finding_mismatch",
                        r.id,
                    )
                    self.check(r.created_at >= old_review.created_at, "history_time_reversed", r.id)
            if previous:
                self.check(previous not in successors, "branched_history", r.id)
                successors[previous] = r.id
        for id in successors:
            visited: set[str] = set()
            cursor = id
            while cursor in successors:
                self.check(cursor not in visited, "history_cycle", id)
                visited.add(cursor)
                cursor = successors[cursor]
        for group in findings.values():
            self.check(
                sum(r.id not in successors for r in group) == 1,
                "multiple_selected_findings",
                group[0].id,
            )


def validate_links(bundle: RecordSet) -> None:
    LinkedRecords(bundle).validate()
