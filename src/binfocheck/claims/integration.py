"""Only composition layer knows T03 preparation, configuration and resource mechanics."""

from pydantic import JsonValue

from binfocheck.domain.common import ErrorDetail, Outcome, Settings, VersionRef
from binfocheck.domain.decisions import DecisionRecord, DecisionResult, GenerationResult
from binfocheck.domain.interfaces import (
    DecisionModel,
    DecisionRequest,
    GenerationModel,
    GenerationRequest,
)
from binfocheck.domain.runs import RunManifest
from binfocheck.domain.storage import ArtifactStore, IdRequest, RecordStore
from binfocheck.models.config import MODELS, ModelAdapterConfig, config_version
from binfocheck.models.errors import ModelError
from binfocheck.models.persistence import prepare
from binfocheck.models.receipt import ModelReceipt, role_id
from binfocheck.models.resources import schema_resource, validate_output

from .artifacts import StageEvidence
from .errors import ExtractionError, check, require
from .persistence import canonical, digest, identity, json_object, load, save
from .policy import GENERATIONS, LABELS, RUBRICS
from .resources import ExtractionResources
from .stages import StageResult


class T03Models:
    def __init__(
        self,
        records: RecordStore,
        artifacts: ArtifactStore,
        decisions: DecisionModel,
        generation: GenerationModel,
        resources: ExtractionResources,
        decision_config: ModelAdapterConfig,
        generation_config: ModelAdapterConfig,
    ) -> None:
        check(
            decision_config.provider == "jev" and generation_config.provider in ("openai", "vllm")
        )
        self.records, self.artifacts = records, artifacts
        self.decisions, self.generation, self.resources = decisions, generation, resources
        self.decision_config, self.generation_config = decision_config, generation_config
        self.resource_version, self.policy_version = resources.version, resources.policy
        self.configuration = VersionRef(
            name="t04-claim-extraction",
            version="1",
            sha256=digest(
                canonical(
                    {
                        "resources": resources.version.model_dump(mode="json"),
                        "policy": resources.policy.model_dump(mode="json"),
                        "decision": decision_config.model_dump(mode="json"),
                        "generation": generation_config.model_dump(mode="json"),
                        "preparation": "1",
                        "location": "1",
                        "assembly": "2",
                        "contract_validation": "1.1",
                    }
                )
            ),
        )

    @property
    def prompts(self) -> tuple[VersionRef, ...]:
        return tuple(self.resources.ref(name) for name in GENERATIONS.values())

    def reservation(self, stage: str) -> float:
        config = self.generation_config if stage in GENERATIONS else self.decision_config
        return config.budget.cost_limit

    def reserve(self, run: RunManifest, operation_id: str, cost: float) -> str | None:
        """Single-owner immutable allowance slots, shared across scopes in this run.

        These are conservative reservations, not reported usage. No evidence lookup,
        worker lease, mutable counter or automatic retry is involved.
        """
        reserved = 0.0
        for index in range(run.budget.request_limit):
            id = identity("extraction-reservation", run.id, index)
            raw = load(self.artifacts, id)
            if raw is None:
                if reserved + cost > run.budget.cost_limit + 1e-12:
                    return None
                save(
                    self.artifacts,
                    id,
                    {
                        "version": "1",
                        "run_id": run.id,
                        "operation_id": operation_id,
                        "reserved_cost_usd": cost,
                    },
                )
                return id
            slot = json_object(raw)
            amount = slot.get("reserved_cost_usd")
            check(
                slot.get("version") == "1"
                and slot.get("run_id") == run.id
                and type(amount) in (int, float),
                "invalid_budget_reservation",
            )
            assert isinstance(amount, (int, float))
            check(amount >= 0, "invalid_budget_reservation")
            if slot.get("operation_id") == operation_id:
                check(amount == cost, "reservation_configuration_mismatch")
                return id
            reserved += amount
        return None

    @property
    def rubrics(self) -> tuple[VersionRef, ...]:
        return tuple(self.resources.ref(name) for name in RUBRICS.values())

    def validate_run(self, run: RunManifest) -> None:
        check(run.configuration == self.configuration, "run_configuration_mismatch")
        check(
            set(run.model_ids)
            == {MODELS[self.decision_config.provider], MODELS[self.generation_config.provider]},
            "run_models_mismatch",
        )
        check(
            set(run.prompt_versions) == set(self.prompts)
            and set(run.rubric_versions) == set(self.rubrics),
            "run_resources_mismatch",
        )
        check(
            run.budget.retry_limit == 0
            and run.budget.concurrency == 1
            and run.budget.currency == "USD"
            and run.budget.request_limit <= 340,
            "invalid_run_budget",
        )
        check(
            all(
                c.budget.timeout_seconds <= run.budget.timeout_seconds
                for c in (self.decision_config, self.generation_config)
            ),
            "run_timeout_mismatch",
        )
        try:
            for name in GENERATIONS.values():
                schema_resource(self.resources.resolve(self.resources.ref(name + "-output")))
        except ModelError:
            raise ExtractionError("invalid_output_schema_resource") from None
        for ref in (*self.prompts, *self.rubrics):
            self.resources.resolve(ref)

    def call(
        self,
        run: RunManifest,
        stage: str,
        state: dict[str, JsonValue],
        input_ids: tuple[str, ...],
        scope: str,
        upstream: tuple[DecisionRecord, ...],
    ) -> StageResult:
        state_id = identity("extraction-state", scope, stage, state)
        save(self.artifacts, state_id, state)
        generated = stage in GENERATIONS
        config = self.generation_config if generated else self.decision_config
        consumed = tuple(r for r in upstream if isinstance(r.result, GenerationResult))
        artifact_ids = (
            state_id,
            *(
                r.result.output_artifact_id
                for r in consumed
                if isinstance(r.result, GenerationResult)
            ),
        )
        values = dict(
            analysis_run_id=run.id,
            task_type="t04." + stage,
            input_ids=tuple(dict.fromkeys((*input_ids, *(r.id for r in upstream)))),
            input_artifact_ids=tuple(dict.fromkeys(artifact_ids)),
            requested_model_id=MODELS[config.provider],
            settings=Settings(
                version=config_version(config), values={"state_artifact_id": state_id}
            ),
        )
        if generated:
            name = GENERATIONS[stage]
            request = GenerationRequest.model_validate(
                {
                    **values,
                    "prompt_version": self.resources.ref(name),
                    "rubric_version": None,
                    "output_schema": self.resources.ref(name + "-output"),
                }
            )
        else:
            request = DecisionRequest.model_validate(
                {
                    **values,
                    "prompt_version": None,
                    "rubric_version": self.resources.ref(RUBRICS[stage]),
                    "allowed_labels": LABELS[stage],
                    "probabilities_required": True,
                }
            )
        stage_key = identity("extraction-stage", scope, stage, request.model_dump(mode="json"))
        evidence_id = identity("extraction-evidence", stage_key)
        try:
            prepared = prepare(request, config, self.resources, self.artifacts)
        except (ModelError, ValueError) as caught:
            if isinstance(caught, ModelError) and "storage" in caught.detail.code:
                raise ExtractionError("model_persistence_failed") from None
            error = ErrorDetail(code="model_preparation_failed", message="Model preparation failed")
            evidence = StageEvidence(
                stage_key=stage_key,
                stage=stage,
                state_artifact_id=state_id,
                prepared_record_id=None,
                model_work_key=None,
                outbound_sha256=None,
                decision_ids=(),
                error=error,
            )
            save(self.artifacts, evidence_id, evidence.model_dump(mode="json"))
            return StageResult(evidence_id, None, error)
        binding = {
            "record_id": prepared.record_id,
            "work_key": prepared.work_key,
            "outbound_sha256": digest(canonical(prepared.body)),
            "outbound_bytes": len(canonical(prepared.body)),
            "request": request.model_dump(mode="json"),
        }
        save(self.artifacts, identity("extraction-binding", stage_key), binding)
        existing = load(self.artifacts, evidence_id)
        if existing is not None:
            evidence = StageEvidence.model_validate_json(existing)
            check(
                evidence.prepared_record_id == prepared.record_id
                and evidence.model_work_key == prepared.work_key
                and evidence.outbound_sha256 == binding["outbound_sha256"]
                and evidence.stage_key == stage_key
                and evidence.stage == stage
                and evidence.state_artifact_id == state_id
                and evidence.decision_ids in ((), (prepared.record_id,))
                and (bool(evidence.decision_ids) or evidence.error is not None),
                "stage_identity_mismatch",
            )
            record = None
            if evidence.reservation_id is not None:
                reservation = load(self.artifacts, evidence.reservation_id)
                check(reservation is not None, "missing_budget_reservation")
                assert reservation is not None
                slot = json_object(reservation)
                check(
                    slot.get("run_id") == run.id
                    and slot.get("operation_id") == prepared.record_id
                    and slot.get("reserved_cost_usd") == config.budget.cost_limit,
                    "invalid_budget_reservation",
                )
            if evidence.decision_ids:
                saved_record = require(self.records.get_record(IdRequest(id=prepared.record_id)))
                check(isinstance(saved_record, DecisionRecord), "wrong_model_record")
                assert isinstance(saved_record, DecisionRecord)
                record = saved_record
                self.validate_record(record, request, prepared.record_id)
                check(
                    (record.status == "failed") == (evidence.error is not None),
                    "cached_model_outcome_mismatch",
                )
            return StageResult(evidence_id, record, evidence.error, evidence.halt)
        # No secrets/transport creation: only injected shared model interfaces execute.
        reservation_id = self.reserve(run, prepared.record_id, config.budget.cost_limit)
        try:
            if reservation_id is None:
                outcome = Outcome[DecisionRecord](
                    status="failed",
                    value=None,
                    error=ErrorDetail(
                        code="run_budget_exhausted", message="Run allowance exhausted"
                    ),
                )
            else:
                outcome = (
                    self.generation.generate(request)
                    if isinstance(request, GenerationRequest)
                    else self.decisions.decide(request)
                )
        except OSError:
            outcome = Outcome[DecisionRecord](
                status="failed",
                value=None,
                error=ErrorDetail(
                    code="dispatch_outcome_uncertain", message="Model outcome unknown"
                ),
            )
        error = outcome.error
        record: DecisionRecord | None = None
        if outcome.status == "succeeded":
            check(outcome.value is not None, "missing_model_record")
            record = outcome.value
            assert record is not None
            self.validate_record(record, request, prepared.record_id)
            check(record.status == "succeeded", "model_outcome_mismatch")
            stored = require(self.records.get_record(IdRequest(id=prepared.record_id)))
            check(stored == record, "model_record_not_persisted")
        else:
            if error is None:
                error = ErrorDetail(code="model_skipped", message="Model operation did not succeed")
            found = self.records.get_record(IdRequest(id=prepared.record_id))
            if not (found.error and found.error.code == "not_found"):
                value = require(found)
                check(isinstance(value, DecisionRecord), "wrong_model_record")
                assert isinstance(value, DecisionRecord)
                self.validate_record(value, request, prepared.record_id)
                check(value.status == "failed", "model_outcome_mismatch")
                record = value
            if "storage" in error.code or "persistence" in error.code:
                # Do not freeze a transient global write failure into a terminal audit.
                # Reinvocation lets T03 finish its exact saved receipt locally.
                raise ExtractionError("model_persistence_failed")
        halt = False
        receipt_raw = load(self.artifacts, role_id(prepared.record_id, "receipt"))
        if receipt_raw is not None:
            receipt = ModelReceipt.model_validate_json(receipt_raw)
            check(receipt.record_id == prepared.record_id, "receipt_identity_mismatch")
            halt = receipt.outcome_uncertain
        evidence = StageEvidence(
            stage_key=stage_key,
            stage=stage,
            state_artifact_id=state_id,
            prepared_record_id=prepared.record_id,
            model_work_key=prepared.work_key,
            outbound_sha256=digest(canonical(prepared.body)),
            decision_ids=(record.id,) if record else (),
            error=error,
            halt=halt,
            reservation_id=reservation_id,
        )
        save(self.artifacts, evidence_id, evidence.model_dump(mode="json"))
        return StageResult(evidence_id, record, error, halt)

    def validate_record(
        self, record: DecisionRecord, request: DecisionRequest | GenerationRequest, expected_id: str
    ) -> None:
        record = DecisionRecord.model_validate_json(record.model_dump_json())
        check(
            record.id == expected_id
            and record.analysis_run_id == request.analysis_run_id
            and record.task_type == request.task_type
            and record.input_ids == request.input_ids
            and record.input_artifact_ids == request.input_artifact_ids
            and record.requested_model_id == request.requested_model_id
            and record.config_version == request.settings.version
            and record.prompt_version == request.prompt_version
            and record.rubric_version == request.rubric_version,
            "model_identity_mismatch",
        )
        if record.status == "failed":
            return
        check(
            record.returned_model_id.data == request.requested_model_id, "returned_model_mismatch"
        )
        if isinstance(request, DecisionRequest):
            result = record.result
            check(isinstance(result, DecisionResult), "wrong_model_result")
            assert isinstance(result, DecisionResult)
            check(
                result.allowed_labels == request.allowed_labels
                and result.probabilities.availability == "available"
                and result.probabilities.data is not None,
                "invalid_probabilities",
            )
            assert result.probabilities.data is not None
            check(
                result.probabilities.data[result.label] == max(result.probabilities.data.values()),
                "invalid_probabilities",
            )
        else:
            result = record.result
            check(isinstance(result, GenerationResult), "wrong_model_result")
            assert isinstance(result, GenerationResult)
            check(result.output_schema == request.output_schema, "output_schema_mismatch")
            data = load(self.artifacts, result.output_artifact_id)
            check(data == canonical(result.structured_output), "semantic_output_mismatch")
            try:
                validate_output(
                    schema_resource(self.resources.resolve(request.output_schema)),
                    result.structured_output,
                )
            except ModelError:
                raise ExtractionError("invalid_model_output") from None
