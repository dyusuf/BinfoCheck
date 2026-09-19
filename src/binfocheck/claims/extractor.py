"""Bounded A–I ClaimExtractor. Provider details are confined to composition."""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import JsonValue, ValidationError

from binfocheck.domain.claims import Claim, ExtractionIssue
from binfocheck.domain.common import ErrorDetail, Outcome
from binfocheck.domain.decisions import DecisionRecord, DecisionResult, GenerationResult
from binfocheck.domain.interfaces import ExtractionRequest, ExtractionResult
from binfocheck.domain.observations import TextUnit
from binfocheck.domain.storage import ArtifactStore, IdRequest, RecordStore
from binfocheck.domain.text import SpanRef
from binfocheck.text.errors import TextError

from .artifacts import Accounting, Binding, Candidate, Clarified, Decomposed, FinalAudit, Mixed
from .context import Group, Inputs, prepare_inputs
from .errors import ExtractionError, check, require
from .locating import locate, supporting_span
from .persistence import canonical, closure, identity, load, save
from .policy import GENERATIONS, LABELS, VALIDATIONS
from .stages import StageModels, StageResult, reference_context, validation_state, working_state

IssueKind = Literal["invalid", "unlocatable", "ambiguous", "unresolved", "excluded", "failed"]


@dataclass
class Work:
    group: Group
    records: list[DecisionRecord] = field(default_factory=lambda: list[DecisionRecord]())
    units: set[str] = field(default_factory=lambda: set[str]())
    question_used: bool = False


class StoredClaimExtractor:
    def __init__(self, records: RecordStore, artifacts: ArtifactStore, models: StageModels) -> None:
        self.records, self.artifacts, self.models = records, artifacts, models

    def extract_claims(self, request: ExtractionRequest) -> Outcome[ExtractionResult]:
        try:
            inputs = prepare_inputs(self.records, self.artifacts, request)
            self.models.validate_run(inputs.run)
            check(
                inputs.settings.policy_version == self.models.policy_version
                and inputs.settings.resource_bundle_version == self.models.resource_version,
                "extraction_resource_mismatch",
            )
            return Session(self.records, self.artifacts, self.models, inputs).execute()
        except ExtractionError as error:
            return Outcome(status="failed", value=None, error=error.detail)
        except (ValidationError, TextError, ValueError, KeyError):
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(
                    code="invalid_extraction_input", message="Invalid extraction input"
                ),
            )


class Session:
    def __init__(
        self, records: RecordStore, artifacts: ArtifactStore, models: StageModels, inputs: Inputs
    ) -> None:
        self.records, self.artifacts, self.models, self.inputs = records, artifacts, models, inputs
        self.claims: list[Claim] = []
        self.issues: list[ExtractionIssue] = []
        self.issue_target_ids: dict[str, tuple[str, ...]] = {}
        self.stages: list[str] = []
        self.calls = self.decisions = self.generations = 0
        self.reserved = 0.0
        self.stopped = False
        self.accounting: list[Accounting] = []
        self.located: set[str] = set()

    def ids(self, work: Work) -> tuple[str, ...]:
        ids = [self.inputs.observation.id, self.inputs.answer.id]
        if work.question_used:
            ids.append(self.inputs.capture.id)
        ids.extend(self.unit_ids(work))
        return tuple(ids)

    def unit_ids(self, work: Work) -> tuple[str, ...]:
        return tuple(u.id for u in self.inputs.units if u.id in work.units)

    def issue(
        self,
        work: Work,
        code: str,
        kind: IssueKind,
        proposed: str | None = None,
        span: SpanRef | None = None,
        candidate: str | None = None,
        *,
        target_ids: tuple[str, ...] | None = None,
    ) -> None:
        # Evidence context can be wider than terminal coverage. An unlocated
        # candidate accounts for no target; only whole-group outcomes default
        # to the group's complete target scope.
        if target_ids is None:
            target_ids = (
                tuple(
                    u.id
                    for u in self.inputs.units
                    if u.id in work.group.target_ids
                    and u.span.start < span.end
                    and span.start < u.span.end
                )
                if span is not None
                else ()
                if candidate is not None
                else work.group.target_ids
            )
        if span is not None and span.source_unit_id:
            work.units.add(span.source_unit_id)
        self.issues.append(
            ExtractionIssue(
                id=identity(
                    "extraction-issue", self.inputs.work_key, work.group.id, candidate, kind, code
                ),
                created_at=self.inputs.run.created_at,
                analysis_run_id=self.inputs.run.id,
                input_ids=self.ids(work),
                observation_id=self.inputs.observation.id,
                issue=kind,
                reason=code,
                proposed_claim=proposed,
                original_span=span,
                context_unit_ids=self.unit_ids(work),
                decision_ids=tuple(r.id for r in work.records),
            )
        )
        self.issue_target_ids[self.issues[-1].id] = target_ids

    def call(
        self,
        work: Work,
        stage: str,
        state: dict[str, JsonValue],
        context: tuple[TextUnit, ...] = (),
        candidate: str | None = None,
        consumed: tuple[DecisionRecord, ...] = (),
    ) -> StageResult:
        is_generation = stage in GENERATIONS
        limits = self.inputs.settings.limits
        reservation = self.models.reservation(stage)
        exceeded = (
            self.stopped
            or self.calls >= limits.max_model_calls
            or self.calls >= self.inputs.run.budget.request_limit
            or self.reserved + reservation > self.inputs.run.budget.cost_limit + 1e-12
            or (is_generation and self.generations >= limits.max_generation_calls)
            or (not is_generation and self.decisions >= limits.max_decision_calls)
        )
        # Exact exposure lineage per call, separately from transitive work lineage.
        if "source" in state:
            exposed = {u.id for u in work.group.units}
        else:
            raw_span = state["original_span"]
            span = SpanRef.model_validate_json(canonical(raw_span))
            exposed = {
                u.id
                for u in work.group.units
                if u.span.start < span.end and span.start < u.span.end
            }
        exposed.update(u.id for u in context)
        direct = [self.inputs.observation.id, self.inputs.answer.id]
        if "question" in state:
            direct.append(self.inputs.capture.id)
            work.question_used = True
        direct.extend(u.id for u in self.inputs.units if u.id in exposed)
        work.units.update(exposed)
        scope = identity(
            "extraction-operation", self.inputs.work_key, work.group.id, candidate, stage
        )
        selection_id = identity("extraction-selection", scope)
        save(
            self.artifacts,
            selection_id,
            {
                "version": "1",
                "scope": scope,
                "supplied_unit_ids": [u.id for u in self.inputs.units if u.id in exposed],
                "context_unit_ids": [u.id for u in context],
                "question_supplied": "question" in state,
                "question_capture_request_id": self.inputs.capture.id
                if "question" in state
                else None,
                "reason": (
                    "qualification_scope" if stage == "H.faithfulness" else "reference_antecedent"
                )
                if context
                else None,
                "policy_version": self.inputs.settings.policy_version.model_dump(mode="json"),
            },
        )
        self.stages.append(selection_id)
        if exceeded:
            self.stopped = True
            error = ErrorDetail(
                code="budget_or_execution_stopped", message="No further model dispatch allowed"
            )
            artifact_id = identity("extraction-stopped", scope)
            save(
                self.artifacts,
                artifact_id,
                {"scope": scope, "error": error.model_dump(mode="json")},
            )
            self.stages.append(artifact_id)
            return StageResult(artifact_id, None, error)
        self.calls += 1
        self.generations += int(is_generation)
        self.decisions += int(not is_generation)
        self.reserved += reservation
        result = self.models.call(self.inputs.run, stage, state, tuple(direct), scope, consumed)
        self.stages.append(result.artifact_id)
        if result.record:
            work.records.append(result.record)
        if result.halt or (
            result.error
            and any(
                s in result.error.code
                for s in ("auth", "credential", "uncertain", "budget", "limit_exhausted")
            )
        ):
            self.stopped = True
        return result

    def label(self, result: StageResult) -> str | None:
        if result.error or not result.record:
            return None
        value = result.record.result
        check(isinstance(value, DecisionResult), "invalid_decision_result")
        assert isinstance(value, DecisionResult)
        probabilities = value.probabilities.data
        check(probabilities is not None, "missing_probabilities")
        assert probabilities is not None
        if sum(p == max(probabilities.values()) for p in probabilities.values()) > 1:
            return "uncertain"
        return value.label

    def generated(self, result: StageResult) -> bytes | None:
        if result.error or not result.record:
            return None
        value = result.record.result
        check(isinstance(value, GenerationResult), "invalid_generation_result")
        assert isinstance(value, GenerationResult)
        return canonical(value.structured_output)

    def process(self, work: Work) -> None:
        group = work.group
        working = self.inputs.answer.text[group.start : group.end]
        original_state = working_state(self.inputs, group, working)
        selected = self.call(work, "B", original_state)
        label = self.label(selected)
        if label in {None, "nonfactual", "uncertain"}:
            self.issue(
                work,
                "B." + (label or "model_failed"),
                "failed"
                if label is None
                else "excluded"
                if label == "nonfactual"
                else "unresolved",
            )
            return
        rewrite: DecisionRecord | None = None
        if label == "mixed":
            result = self.call(work, "C", original_state)
            raw = self.generated(result)
            if raw is None:
                self.issue(work, "C.model_failed", "failed")
                return
            mixed = Mixed.model_validate_json(raw)
            if mixed.status == "unresolved":
                self.issue(work, "C.cannot_separate", "unresolved")
                return
            for anchor in mixed.anchors:
                locate(anchor, self.inputs, group)
            if not mixed.excluded_quotes:
                self.issue(work, "C.exclusion_unlocated", "unresolved", target_ids=())
            for anchor in mixed.excluded_quotes:
                self.issue(
                    work,
                    "C.nonfactual." + identity("fragment", anchor.model_dump(mode="json")),
                    "excluded",
                    span=locate(anchor, self.inputs, group),
                )
            assert mixed.factual_text is not None
            working, rewrite = mixed.factual_text, result.record
        context, use_question = reference_context(self.inputs, group, working)
        ambiguity = self.call(
            work,
            "D",
            working_state(self.inputs, group, working, context, use_question),
            context,
            consumed=(rewrite,) if rewrite else (),
        )
        label = self.label(ambiguity)
        if label in {None, "unresolved", "uncertain"}:
            self.issue(
                work, "D." + (label or "model_failed"), "failed" if label is None else "unresolved"
            )
            return
        bindings: tuple[Binding, ...] = ()
        if label == "resolvable_from_context":
            clarified = self.call(
                work,
                "E",
                working_state(self.inputs, group, working, context, use_question),
                context,
                consumed=(rewrite,) if rewrite else (),
            )
            raw = self.generated(clarified)
            if raw is None:
                self.issue(work, "E.model_failed", "failed")
                return
            value = Clarified.model_validate_json(raw)
            if value.status == "unresolved":
                self.issue(work, "E.insufficient_context", "unresolved")
                return
            for anchor in value.anchors:
                locate(anchor, self.inputs, group)
            for b in value.bindings:
                check(
                    set(b.answer_context_unit_ids).issubset(u.id for u in (*group.units, *context))
                    and (not b.question_reference_used or use_question)
                    and (bool(b.answer_context_unit_ids) or b.question_reference_used),
                    "invalid_binding",
                )
            assert value.clarified_text is not None
            working, bindings, rewrite = value.clarified_text, value.bindings, clarified.record
        state = working_state(self.inputs, group, working)
        if bindings:
            state["clarification_bindings"] = [b.model_dump(mode="json") for b in bindings]
        decomposed = self.call(work, "F", state, consumed=(rewrite,) if rewrite else ())
        raw = self.generated(decomposed)
        if raw is None:
            self.issue(work, "F.model_failed", "failed")
            return
        value = Decomposed.model_validate_json(raw)
        if value.status == "unresolved":
            self.issue(work, "F." + value.reason_code, "unresolved")
            return
        if len(value.candidates) > self.inputs.settings.limits.max_candidates_per_group:
            self.issue(work, "F.candidate_limit", "unresolved")
            return
        seen: set[str] = set()
        base_records, base_units = list(work.records), set(work.units)
        for candidate in value.candidates:
            key = identity("candidate", group.id, candidate.model_dump(mode="json"))
            if key in seen:
                continue
            seen.add(key)
            candidate_work = Work(group, list(base_records), set(base_units), work.question_used)
            self.candidate(candidate_work, candidate, key, bindings, decomposed.record)

    def candidate(
        self,
        work: Work,
        candidate: Candidate,
        key: str,
        bindings: tuple[Binding, ...],
        decomposition: DecisionRecord | None,
    ) -> None:
        try:
            check(
                len(set(candidate.consumed_binding_indices))
                == len(candidate.consumed_binding_indices)
                and all(0 <= i < len(bindings) for i in candidate.consumed_binding_indices),
                "invalid_binding_indices",
            )
            consumed_bindings = tuple(bindings[i] for i in candidate.consumed_binding_indices)
            span = supporting_span(candidate, self.inputs, work.group)
        except ExtractionError as error:
            code = error.detail.code
            kind: IssueKind = (
                "unlocatable"
                if code == "quote_missing"
                else "ambiguous"
                if code == "location_ambiguous"
                else "invalid"
            )
            self.issue(work, "G." + code, kind, candidate.normalized_claim, candidate=key)
            return
        location_id = identity("extraction-location", key)
        save(
            self.artifacts,
            location_id,
            {"candidate": candidate.model_dump(mode="json"), "span": span.model_dump(mode="json")},
        )
        self.stages.append(location_id)
        located_id = identity(
            "located-candidate",
            work.group.id,
            candidate.normalized_claim,
            span.model_dump(mode="json"),
        )
        if located_id in self.located:
            self.issue(
                work, "G.duplicate_candidate", "excluded", candidate.normalized_claim, span, key
            )
            return
        self.located.add(located_id)
        limits = self.inputs.settings.limits
        if (
            self.calls + 3 > min(limits.max_model_calls, self.inputs.run.budget.request_limit)
            or self.decisions + 3 > limits.max_decision_calls
            or self.reserved + sum(self.models.reservation(s) for s in VALIDATIONS)
            > self.inputs.run.budget.cost_limit + 1e-12
        ):
            self.stopped = True
        # Independent H decisions: no other H result is passed to a property.
        results: list[tuple[str, str | None]] = []
        for stage in VALIDATIONS:
            state, context = validation_state(
                self.inputs, stage, candidate.normalized_claim, span, consumed_bindings
            )
            result = self.call(
                work, stage, state, context, key, consumed=(decomposition,) if decomposition else ()
            )
            results.append((stage, self.label(result)))
        invalid = False
        for stage, label in results:
            if label != LABELS[stage][0]:
                invalid = True
                self.issue(
                    work,
                    stage + "." + (label or "model_failed"),
                    "failed"
                    if label is None
                    else "unresolved"
                    if label == "uncertain"
                    else "invalid",
                    candidate.normalized_claim,
                    span,
                    key,
                )
        if invalid:
            return
        if span.source_unit_id:
            work.units.add(span.source_unit_id)
        self.claims.append(
            Claim(
                id=identity(
                    "claim",
                    self.inputs.work_key,
                    work.group.id,
                    span.model_dump(mode="json"),
                    candidate.normalized_claim,
                    self.unit_ids(work),
                ),
                created_at=self.inputs.run.created_at,
                analysis_run_id=self.inputs.run.id,
                input_ids=self.ids(work),
                observation_id=self.inputs.observation.id,
                normalized_claim=candidate.normalized_claim,
                original_span=span,
                context_unit_ids=self.unit_ids(work),
                decision_ids=tuple(r.id for r in work.records),
                claim_group_id=work.group.id,
            )
        )

    def execute(self) -> Outcome[ExtractionResult]:
        save(
            self.artifacts,
            identity("extraction-prepared", self.inputs.work_key),
            {
                "version": "1",
                "request": self.inputs.request.model_dump(mode="json"),
                "groups": [
                    {
                        "id": g.id,
                        "target_ids": g.target_ids,
                        "unit_ids": [u.id for u in g.units],
                        "start": g.start,
                        "end": g.end,
                    }
                    for g in self.inputs.groups
                ],
            },
        )
        for group in self.inputs.groups:
            before_claims, before_issues = len(self.claims), len(self.issues)
            work = Work(group, units={u.id for u in group.units})
            try:
                self.process(work)
            except ValidationError:
                self.issue(work, "generation.invalid_output", "failed")
            except ExtractionError as error:
                if error.detail.code in {
                    "quote_missing",
                    "location_ambiguous",
                    "invalid_source_units",
                    "invalid_offsets",
                    "invalid_binding",
                    "invalid_source_order",
                    "incomplete_source_units",
                }:
                    self.issue(work, "generation." + error.detail.code, "invalid")
                else:
                    raise
            for target_id in group.target_ids:
                target = next(u for u in self.inputs.units if u.id == target_id)
                claims = [
                    c
                    for c in self.claims[before_claims:]
                    if c.original_span.start < target.span.end
                    and target.span.start < c.original_span.end
                ]
                issues = [
                    i
                    for i in self.issues[before_issues:]
                    if target_id in self.issue_target_ids[i.id]
                ]
                if not claims and not issues:
                    self.issue(
                        work,
                        "target_not_represented." + target_id,
                        "unresolved",
                        target_ids=(target_id,),
                    )
                    issues = [self.issues[-1]]
                self.accounting.append(
                    Accounting(
                        target_unit_id=target_id,
                        group_ids=(group.id,),
                        terminal_claim_ids=tuple(c.id for c in claims),
                        terminal_issue_ids=tuple(i.id for i in issues),
                    )
                )
        result = ExtractionResult(claims=tuple(self.claims), issues=tuple(self.issues))
        validate_accounting(self.inputs, result, tuple(self.accounting), self.issue_target_ids)
        closure(self.records, self.artifacts, (*result.claims, *result.issues, self.inputs.run))
        failed = {i.id for i in result.issues if i.issue == "failed"}
        all_failed = all(
            not a.terminal_claim_ids
            and bool(a.terminal_issue_ids)
            and set(a.terminal_issue_ids).issubset(failed)
            for a in self.accounting
        )
        state = "all_targets_failed" if all_failed else "partial_failure" if failed else "complete"
        audit = FinalAudit(
            work_key=self.inputs.work_key,
            extraction_result=result,
            target_accounting=tuple(self.accounting),
            issue_target_ids=self.issue_target_ids,
            stage_artifact_ids=tuple(self.stages),
            assessment_state=state,
        )
        final_id = identity("extraction-final", self.inputs.work_key)
        ref = save(self.artifacts, final_id, audit.model_dump(mode="json"))
        for record in (*result.claims, *result.issues):
            require(self.records.put_record(record))
            check(
                require(self.records.get_record(IdRequest(id=record.id))) == record,
                "record_write_mismatch",
            )
        for id in self.stages:
            check(load(self.artifacts, id) is not None, "stage_evidence_missing")
        save(
            self.artifacts,
            identity("extraction-complete", self.inputs.work_key),
            {
                "version": "1",
                "work_key": self.inputs.work_key,
                "final_output_artifact_id": final_id,
                "final_output_sha256": ref.sha256,
                "status": "complete",
            },
        )
        return Outcome(
            status="succeeded",
            value=result,
            error=None,
            reason=None
            if state == "complete"
            else "partial_extraction"
            if state == "partial_failure"
            else "all_targets_failed",
        )


def validate_accounting(
    inputs: Inputs,
    result: ExtractionResult,
    accounting: tuple[Accounting, ...],
    issue_target_ids: dict[str, tuple[str, ...]],
) -> None:
    check(
        tuple(a.target_unit_id for a in accounting) == inputs.settings.target_unit_ids,
        "incomplete_target_accounting",
    )
    claims, issues = {c.id: c for c in result.claims}, {i.id: i for i in result.issues}
    check(
        len(claims) == len(result.claims) and len(issues) == len(result.issues), "duplicate_output"
    )
    check(
        set(issue_target_ids) == set(issues)
        and all(
            len(ids) == len(set(ids)) and set(ids).issubset(inputs.settings.target_unit_ids)
            for ids in issue_target_ids.values()
        ),
        "invalid_issue_target_scope",
    )
    for entry in accounting:
        check(
            bool(entry.terminal_claim_ids or entry.terminal_issue_ids)
            and all(id in claims for id in entry.terminal_claim_ids)
            and all(id in issues for id in entry.terminal_issue_ids),
            "incomplete_target_accounting",
        )
        expected_groups = tuple(g.id for g in inputs.groups if entry.target_unit_id in g.target_ids)
        check(entry.group_ids == expected_groups, "accounting_group_mismatch")
        target = next(u for u in inputs.units if u.id == entry.target_unit_id)
        check(
            all(
                claims[id].claim_group_id in expected_groups
                and claims[id].original_span.start < target.span.end
                and target.span.start < claims[id].original_span.end
                for id in entry.terminal_claim_ids
            ),
            "accounting_claim_mismatch",
        )
        check(
            all(
                entry.target_unit_id in issue_target_ids[issue.id]
                and entry.target_unit_id in issue.context_unit_ids
                and (
                    issue.original_span is None
                    or (
                        issue.original_span.start < target.span.end
                        and target.span.start < issue.original_span.end
                    )
                )
                for issue in (issues[id] for id in entry.terminal_issue_ids)
            ),
            "accounting_issue_mismatch",
        )
