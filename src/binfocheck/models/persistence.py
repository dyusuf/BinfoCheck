"""Single-operation adapter mechanics through T11A only; no worker orchestration."""

import base64
import math
import time
from dataclasses import replace
from datetime import UTC, datetime
from typing import Protocol

from pydantic import JsonValue

from binfocheck.domain.common import Availability, Available, DerivedRecord, ErrorDetail, Outcome
from binfocheck.domain.decisions import DecisionRecord, GenerationResult, ModelResult, Usage
from binfocheck.domain.interfaces import DecisionRequest, GenerationRequest
from binfocheck.domain.observations import Observation
from binfocheck.domain.records import Record
from binfocheck.domain.runs import RunManifest
from binfocheck.domain.storage import ArtifactPayload, ArtifactStore, IdRequest, RecordStore
from binfocheck.domain.text import ArtifactRef

from .config import MODELS, LocalGenerationConfig, ModelAdapterConfig, config_version
from .errors import ModelError, failure, require
from .json import canonical, digest, object_value, parse, text_value
from .local_runtime import require_structured_runtime
from .receipt import ModelReceipt, PreparedRequest, role_id
from .resources import ModelResources, resolve, schema_resource
from .transport import ALLOWED_HEADERS, HttpResponse, ModelTransport


class Clock(Protocol):
    def now(self) -> datetime: ...
    def monotonic(self) -> float: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()


def artifact_ref(record_id: str, role: str, data: bytes) -> ArtifactRef:
    return ArtifactRef(
        id=role_id(record_id, role),
        storage_key="models/v1/" + role,
        sha256=digest(data),
        media_type="application/octet-stream" if role == "raw" else "application/json",
        access="restricted",
        redacted_transport_fields=("authorization", "cookie", "set-cookie"),
    )


def save(artifacts: ArtifactStore, ref: ArtifactRef, data: bytes) -> None:
    require(
        artifacts.put_artifact(
            ArtifactPayload(
                ref=ref,
                content_base64=base64.b64encode(data).decode("ascii"),
            )
        )
    )


def load(artifacts: ArtifactStore, ref: ArtifactRef) -> bytes:
    payload = require(artifacts.get_artifact(IdRequest(id=ref.id)))
    if payload.ref != ref:
        raise ModelError("replay_artifact_mismatch")
    data = base64.b64decode(payload.content_base64, validate=True)
    if digest(data) != ref.sha256:
        raise ModelError("replay_artifact_mismatch")
    return data


def optional_artifact(artifacts: ArtifactStore, id: str) -> ArtifactPayload | None:
    result = artifacts.get_artifact(IdRequest(id=id))
    if result.error is not None and result.error.code == "not_found":
        return None
    return require(result)


def validate_request_lineage(
    request: DecisionRequest | GenerationRequest, records: RecordStore
) -> None:
    """Reject unpersistable lineage before authorization or any adapter writes."""

    def resolve_record(id: str) -> Record:
        result = records.get_record(IdRequest(id=id))
        if result.error is not None and result.error.code == "not_found":
            raise ModelError("invalid_request_lineage")
        return require(result)

    run = resolve_record(request.analysis_run_id)
    if not isinstance(run, RunManifest):
        raise ModelError("invalid_request_lineage")
    for id in request.input_ids:
        record = resolve_record(id)
        if isinstance(record, DerivedRecord) and record.analysis_run_id != run.id:
            raise ModelError("invalid_request_lineage")
        if isinstance(record, Observation) and record.id not in run.observation_ids:
            raise ModelError("invalid_request_lineage")
    for id in request.input_artifact_ids:
        if not isinstance(resolve_record(id), ArtifactRef):
            raise ModelError("invalid_request_lineage")


def prepare(
    request: DecisionRequest | GenerationRequest,
    config: ModelAdapterConfig,
    resources: ModelResources,
    artifacts: ArtifactStore,
) -> PreparedRequest:
    if request.requested_model_id != MODELS[config.provider]:
        raise ModelError("requested_model_mismatch")
    if request.settings.version != config_version(config):
        raise ModelError("unsupported_config_version")
    settings = request.settings.values
    if set(settings) != {"state_artifact_id"}:
        raise ModelError("unsupported_settings")
    state_id = settings["state_artifact_id"]
    if not isinstance(state_id, str) or state_id not in request.input_artifact_ids:
        raise ModelError("invalid_input_binding")
    input_hashes: dict[str, str] = {}
    state: JsonValue = None
    for id in request.input_artifact_ids:
        payload = require(artifacts.get_artifact(IdRequest(id=id)))
        raw = load(artifacts, payload.ref)
        input_hashes[id] = digest(raw)
        if id == state_id:
            if payload.ref.media_type in ("text/plain", "text/plain; charset=utf-8"):
                try:
                    state = raw.decode("utf-8")
                except UnicodeError:
                    raise ModelError("invalid_input_encoding") from None
            elif payload.ref.media_type == "application/json":
                state = parse(raw)
                if not isinstance(state, (dict, list)):
                    raise ModelError("invalid_input_binding")
            else:
                raise ModelError("unsupported_input_media")
    resolved: dict[str, str] = {}

    def resource(name: str, raw: bytes) -> bytes:
        resolved[name] = base64.b64encode(raw).decode("ascii")
        return raw

    body: dict[str, JsonValue]
    if isinstance(request, DecisionRequest):
        if config.provider != "jev" or request.prompt_version is not None:
            raise ModelError("unsupported_request")
        labels = request.allowed_labels
        if len(set(labels)) != len(labels) or any(not label.strip() for label in labels):
            raise ModelError("invalid_allowed_labels")
        rubric = object_value(parse(resource("rubric", resolve(resources, request.rubric_version))))
        if set(rubric) != {"instructions", "criteria"}:
            raise ModelError("invalid_rubric_resource")
        instructions = text_value(rubric["instructions"])
        criteria = object_value(rubric["criteria"])
        if set(criteria) != set(labels) or any(
            value is not None and not isinstance(value, str) for value in criteria.values()
        ):
            raise ModelError("invalid_rubric_resource")
        body = {
            "model": request.requested_model_id,
            "state": state,
            "questions": {
                "q0": {"type": "choice", "instructions": instructions, "criteria": criteria},
            },
        }
    else:
        if config.provider not in ("openai", "vllm") or request.rubric_version is not None:
            raise ModelError("unsupported_request")
        prompt = resource("prompt", resolve(resources, request.prompt_version))
        try:
            instructions = prompt.decode("utf-8")
        except UnicodeError:
            raise ModelError("invalid_prompt_resource") from None
        if not instructions.strip():
            raise ModelError("invalid_prompt_resource")
        schema = schema_resource(resource("schema", resolve(resources, request.output_schema)))
        body = {
            "model": request.requested_model_id,
            "instructions": instructions,
            "input": state if isinstance(state, str) else canonical(state).decode("utf-8"),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "t03_" + digest(canonical(schema))[:32],
                    "strict": True,
                    "schema": schema,
                }
            },
            "stream": False,
            "background": False,
            "store": False,
            "tools": [],
            "tool_choice": "none",
            "service_tier": "default",
            "temperature": 0,
            "max_output_tokens": config.max_output_tokens,
        }
        if isinstance(config, LocalGenerationConfig):
            body = {
                "model": request.requested_model_id,
                "messages": [
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": body["input"]},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "t04_" + digest(canonical(schema))[:32],
                        "strict": True,
                        "schema": schema,
                    },
                },
                "temperature": 0,
                "top_p": 1,
                "seed": 0,
                "max_tokens": config.max_output_tokens,
                "n": 1,
                "stream": False,
                "tools": [],
                "tool_choice": "none",
            }
    if len(canonical(body)) > config.max_request_bytes:
        raise ModelError("request_too_large")
    return PreparedRequest(
        request=request,
        config=config,
        body=body,
        resource_bytes_base64=resolved,
        input_hashes=input_hashes,
    )


def count(value: JsonValue) -> int | None:
    # Provider count overflow is malformed metadata, never a float conversion crash.
    return value if type(value) is int and 0 <= value <= 2**63 - 1 else None


def usage_metadata(
    provider: str,
    body: dict[str, JsonValue],
) -> tuple[Available[Usage], float | None, str]:
    raw = body.get("usage")
    if not isinstance(raw, dict):
        return (
            Available(
                availability=Availability.UNAVAILABLE,
                data=None,
                reason="Provider usage not reported",
            ),
            None,
            "estimate unavailable",
        )
    inputs = count(raw.get("prompt_tokens" if provider == "vllm" else "input_tokens"))
    outputs = count(raw.get("completion_tokens" if provider == "vllm" else "output_tokens"))
    usage = Available[Usage](
        availability=Availability.INCOMPLETE,
        data=Usage(
            input_tokens=inputs, output_tokens=outputs, requests=None, cost=None, currency=None
        ),
        reason="Only reported token counts; request count and billed cost unknown",
    )
    estimate: float | None = None
    basis = "estimate unavailable"
    if provider == "vllm":
        basis = "Local inference: no external provider charge; infrastructure cost unknown"
        estimate = 0.0
    if provider == "jev" and inputs is not None:
        estimate = inputs * 0.042 / 1_000_000
        basis = "estimate: input tokens * USD 0.042/M; docs.typesafe.ai/models"
    elif provider == "openai" and inputs is not None and outputs is not None:
        details = raw.get("input_tokens_details")
        cached = count(details.get("cached_tokens")) if isinstance(details, dict) else None
        writes = count(details.get("cache_write_tokens", 0)) if isinstance(details, dict) else None
        if (
            cached is not None
            and cached <= inputs
            and writes == 0
            and body.get("service_tier") == "default"
        ):
            estimate = ((inputs - cached) * 0.4 + cached * 0.1 + outputs * 1.6) / 1_000_000
            basis = "estimate: USD/M input 0.40, cached 0.10, output 1.60; OpenAI gpt-4.1-mini"
    if estimate is not None and not math.isfinite(estimate):
        estimate, basis = None, "estimate unavailable"
    return usage, estimate, basis


def normalize(
    prepared: PreparedRequest,
    response: HttpResponse,
    started: datetime,
    finished: datetime,
) -> tuple[DecisionRecord, dict[str, JsonValue] | None, dict[str, JsonValue]]:
    from .decision import decision_result
    from .generation import generation_output, local_generation_output

    request = prepared.request
    body: dict[str, JsonValue] = {}
    structured: dict[str, JsonValue] | None = None
    result: ModelResult | None = None
    error = response.error
    try:
        if response.payload is not None and response.complete:
            body = object_value(parse(response.payload))
    except ModelError as caught:
        if error is None:
            error = caught.detail
    model = body.get("model")
    returned = Available[str](
        availability=Availability.UNAVAILABLE, data=None, reason="Returned model identity missing"
    )
    if isinstance(model, str) and model.strip():
        returned = Available(availability=Availability.AVAILABLE, data=model)
    headers = dict(response.headers)
    request_id = headers.get(
        "x-typesafe-request-id" if prepared.config.provider == "jev" else "x-request-id"
    )
    try:
        if error is not None:
            raise ModelError(error.code)
        if response.status is None or not 200 <= response.status < 300:
            codes = {
                400: "request_rejected",
                422: "request_rejected",
                401: "authentication_failed",
                403: "access_denied",
                404: "model_unavailable",
                429: "rate_limited",
            }
            raise ModelError(codes.get(response.status or 0, "provider_unavailable"))
        if not response.complete:
            raise ModelError("response_incomplete")
        if returned.data is None:
            raise ModelError("model_identity_missing")
        if returned.data != request.requested_model_id:
            raise ModelError("model_mismatch")
        if isinstance(request, DecisionRequest):
            result = decision_result(request, body)
        else:
            schema = schema_resource(base64.b64decode(prepared.resource_bytes_base64["schema"]))
            structured = (
                local_generation_output(schema, body)
                if prepared.config.provider == "vllm"
                else generation_output(schema, body)
            )
            result = GenerationResult(
                output_schema=request.output_schema,
                structured_output=structured,
                output_artifact_id=role_id(prepared.record_id, "structured"),
            )
    except ModelError as caught:
        error = ErrorDetail(
            code=caught.detail.code, message=caught.detail.message, provider_request_id=request_id
        )
    usage, _, _ = usage_metadata(prepared.config.provider, body)
    record = DecisionRecord(
        id=prepared.record_id,
        created_at=finished,
        analysis_run_id=request.analysis_run_id,
        input_ids=request.input_ids,
        input_artifact_ids=request.input_artifact_ids,
        task_type=request.task_type,
        requested_model_id=request.requested_model_id,
        returned_model_id=returned,
        prompt_version=request.prompt_version,
        rubric_version=request.rubric_version,
        config_version=request.settings.version,
        status="failed" if error is not None else "succeeded",
        result=result,
        usage=usage,
        started_at=started,
        finished_at=finished,
        error=error,
        provider_request_id=request_id,
    )
    return record, structured, body


def record_outcome(record: DecisionRecord) -> Outcome[DecisionRecord]:
    if record.error is not None:
        return failure(record.error)
    return Outcome(status="succeeded", value=record, error=None)


class ModelAdapter:
    provider: str = ""

    def __init__(
        self,
        records: RecordStore,
        artifacts: ArtifactStore,
        resources: ModelResources,
        config: ModelAdapterConfig,
        transport: ModelTransport,
        clock: Clock | None = None,
    ) -> None:
        self.records, self.artifacts, self.resources = records, artifacts, resources
        self.config = type(config).model_validate_json(config.model_dump_json())
        if self.provider != self.config.provider:
            raise ModelError("provider_mismatch")
        self.transport, self.clock = transport, clock or SystemClock()

    def execute(self, request: DecisionRequest | GenerationRequest) -> Outcome[DecisionRecord]:
        from .replay import replay

        started = self.clock.now()
        tick = self.clock.monotonic()
        # Snapshot mutable nested input before deriving identity or dispatching.
        try:
            request = type(request).model_validate_json(request.model_dump_json())
        except ValueError:
            return failure(ModelError("invalid_request").detail)
        try:
            validate_request_lineage(request, self.records)
        except ModelError as caught:
            return failure(caught.detail)
        prepared = PreparedRequest(
            request=request, config=self.config, body={}, resource_bytes_base64={}, input_hashes={}
        )
        preflight_error: ErrorDetail | None = None
        response = HttpResponse(None, None, dispatched=False)
        try:
            prepared = prepare(request, self.config, self.resources, self.artifacts)
        except (ModelError, ValueError) as caught:
            preflight_error = (
                caught.detail
                if isinstance(caught, ModelError)
                else ModelError("invalid_request").detail
            )
        try:
            saved = optional_artifact(self.artifacts, role_id(prepared.record_id, "receipt"))
            if saved is not None:
                return replay(self.records, self.artifacts, prepared.record_id)
            existing = self.records.get_record(IdRequest(id=prepared.record_id))
            if existing.status == "succeeded":
                record = existing.value
                if isinstance(record, DecisionRecord) and record.error is not None:
                    return record_outcome(record)
                raise ModelError("receipt_missing")
            if existing.error is None or existing.error.code != "not_found":
                raise ModelError("storage_failure")
            intent_payload = optional_artifact(
                self.artifacts, role_id(prepared.record_id, "intent")
            )
            if intent_payload is not None:
                # An abandoned intent consumes the allowance. Persist a failure, never resend.
                original = object_value(parse(load(self.artifacts, intent_payload.ref)))
                original_start = datetime.fromisoformat(text_value(original.get("started_at")))
                prepared_payload = require(
                    self.artifacts.get_artifact(
                        IdRequest(id=role_id(prepared.record_id, "prepared"))
                    )
                )
                outbound_payload = require(
                    self.artifacts.get_artifact(
                        IdRequest(id=role_id(prepared.record_id, "outbound"))
                    )
                )
                raw_payload = optional_artifact(self.artifacts, role_id(prepared.record_id, "raw"))
                response = HttpResponse(
                    load(self.artifacts, raw_payload.ref) if raw_payload else None,
                    None,
                    complete=False,
                    outcome_uncertain=True,
                    error=ModelError("dispatch_outcome_uncertain").detail,
                )
                return self._persist(
                    prepared,
                    prepared_payload.ref,
                    outbound_payload.ref,
                    response,
                    original_start,
                    max(original_start, self.clock.now()),
                    None,
                )
            prepared_bytes = canonical(prepared.model_dump(mode="json"))
            prepared_ref = artifact_ref(prepared.record_id, "prepared", prepared_bytes)
            outbound = canonical(prepared.body)
            outbound_ref = artifact_ref(prepared.record_id, "outbound", outbound)
            save(self.artifacts, prepared_ref, prepared_bytes)
            save(self.artifacts, outbound_ref, outbound)
            approval = None
            if preflight_error is None:
                try:
                    if self.config.budget.request_limit != 1:
                        raise ModelError("request_limit_exhausted")
                    if isinstance(self.config, LocalGenerationConfig):
                        manifest = getattr(self.transport, "runtime_manifest", None)
                        if (
                            not isinstance(manifest, bytes)
                            or digest(manifest) != self.config.runtime_manifest_sha256
                        ):
                            raise ModelError("local_runtime_manifest_mismatch")
                        require_structured_runtime(self.config, manifest)
                        save(
                            self.artifacts,
                            artifact_ref(prepared.record_id, "runtime", manifest),
                            manifest,
                        )
                    approval = self.transport.check(self.config, outbound, prepared.work_key)
                except ModelError as caught:
                    preflight_error = caught.detail
            response = HttpResponse(None, None, dispatched=False, error=preflight_error)
            if preflight_error is None:
                intent = canonical(
                    {
                        "work_key": prepared.work_key,
                        "started_at": started.isoformat(),
                        "request_sha256": digest(outbound),
                        "reserved_cost_usd": self.config.budget.cost_limit,
                        "authorization": approval.model_dump(mode="json") if approval else None,
                    }
                )
                save(self.artifacts, artifact_ref(prepared.record_id, "intent", intent), intent)
                try:
                    response = self.transport.post(self.config, outbound, prepared.work_key)
                except (ModelError, OSError):
                    response = HttpResponse(
                        None,
                        None,
                        complete=False,
                        outcome_uncertain=True,
                        error=ModelError("dispatch_outcome_uncertain").detail,
                    )
            finished = max(started, self.clock.now())
            elapsed = max(0.0, self.clock.monotonic() - tick)
            return self._persist(
                prepared, prepared_ref, outbound_ref, response, started, finished, elapsed
            )
        except (ModelError, ValueError) as caught:
            detail = (
                caught.detail
                if isinstance(caught, ModelError)
                else ModelError("invalid_adapter_data").detail
            )
            # If a complete receipt exists, later local replay can finish the SAME record.
            # Otherwise preserve a failure even when the artifact store is unusable.
            try:
                terminal = optional_artifact(self.artifacts, role_id(prepared.record_id, "receipt"))
                if terminal is None:
                    failed_response = replace(response, error=detail)
                    record, _, _ = normalize(
                        prepared, failed_response, started, max(started, self.clock.now())
                    )
                    self.records.append_decision(record)
            except (ModelError, ValueError):
                pass  # No success claim when storage cannot save the failure either.
            return failure(detail)

    def _persist(
        self,
        prepared: PreparedRequest,
        prepared_ref: ArtifactRef,
        outbound_ref: ArtifactRef,
        response: HttpResponse,
        started: datetime,
        finished: datetime,
        elapsed: float | None,
    ) -> Outcome[DecisionRecord]:
        raw_ref: ArtifactRef | None = None
        if response.payload is not None:
            raw_ref = artifact_ref(prepared.record_id, "raw", response.payload)
            try:
                save(self.artifacts, raw_ref, response.payload)  # BEFORE parsing, including errors.
            except ModelError:
                raw_ref = None
                response = replace(
                    response,
                    payload=None,
                    complete=False,
                    error=ModelError("raw_persistence_failed").detail,
                    outcome_uncertain=response.dispatched,
                )
        record, structured, body = normalize(prepared, response, started, finished)
        structured_ref: ArtifactRef | None = None
        if structured is not None:
            data = canonical(structured)
            structured_ref = artifact_ref(prepared.record_id, "structured", data)
            try:
                save(self.artifacts, structured_ref, data)
            except ModelError:
                structured_ref = None
                response = replace(response, error=ModelError("output_persistence_failed").detail)
                record, _, body = normalize(prepared, response, started, finished)
        _, estimate, basis = usage_metadata(prepared.config.provider, body)
        response_id = body.get("id")
        receipt = ModelReceipt(
            record_id=record.id,
            prepared_artifact=prepared_ref,
            outbound_artifact=outbound_ref,
            raw_response_artifact=raw_ref,
            structured_output_artifact=structured_ref,
            started_at=started,
            finished_at=finished,
            elapsed_seconds=elapsed,
            http_status=response.status,
            response_headers={
                k.lower(): v for k, v in response.headers if k.lower() in ALLOWED_HEADERS
            },
            complete=response.complete,
            dispatched=response.dispatched,
            outcome_uncertain=response.outcome_uncertain,
            transport_error=response.error,
            normalization_error=record.error,
            provider_response_id=response_id if isinstance(response_id, str) else None,
            raw_usage=body.get("usage"),
            estimated_cost_usd=estimate,
            estimate_basis=basis,
        )
        data = canonical(receipt.model_dump(mode="json"))
        save(self.artifacts, artifact_ref(record.id, "receipt", data), data)
        require(self.records.append_decision(record))
        return record_outcome(record)
