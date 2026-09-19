"""Real T03 adapter paths with synthetic network-free transport; no credentials."""

import pytest
from pydantic import JsonValue

from binfocheck.claims.integration import T03Models
from binfocheck.claims.persistence import canonical, json_object
from binfocheck.domain.common import ErrorDetail, Outcome
from binfocheck.domain.decisions import DecisionRecord
from binfocheck.models.config import ModelAdapterConfig
from binfocheck.models.decision import JevDecisionModel
from binfocheck.models.generation import OpenAIGenerationModel
from binfocheck.models.transport import HttpResponse
from binfocheck.storage import MemoryStore
from tests.claims.helpers import candidate, candidates, seed_extraction
from tests.models.helpers import Clock
from tests.storage.helpers import success


class OfflineTransport:
    def __init__(self, store: MemoryStore, fault: str | None = None) -> None:
        self.store, self.fault = store, fault
        self.calls: list[dict[str, JsonValue]] = []

    def check(self, config: ModelAdapterConfig, body: bytes, work_key: str) -> None:
        pass

    def post(self, config: ModelAdapterConfig, body: bytes, work_key: str) -> HttpResponse:
        request = json_object(body)
        self.calls.append(request)
        if config.provider == "jev":
            if self.fault == "uncertain_receipt":
                return HttpResponse(
                    None,
                    None,
                    complete=False,
                    outcome_uncertain=True,
                    error=ErrorDetail(code="read_interrupted", message="Synthetic interruption"),
                )
            if self.fault == "jev_malformed":
                return HttpResponse(b"not-json", 200)
            if self.fault == "jev_failed":
                return HttpResponse(b"{}", 503)
            questions = request["questions"]
            assert isinstance(questions, dict) and isinstance(questions["q0"], dict)
            criteria = questions["q0"]["criteria"]
            assert isinstance(criteria, dict)
            positive = next(
                k
                for k in ("factual", "clear", "faithful", "atomic", "self_contained")
                if k in criteria
            )
            choice = "other" if self.fault == "unknown_label" else positive
            probabilities: JsonValue = {k: float(k == positive) for k in criteria}
            if self.fault == "missing_probabilities":
                probabilities = None
            if self.fault == "tie":
                probabilities = {k: 1 / len(criteria) for k in criteria}
            return HttpResponse(
                canonical(
                    {
                        "model": config.provider == "jev" and "jev-1.13.0",
                        "answers": {
                            "q0": {
                                "type": "choice",
                                "choice": choice,
                                "confidence": 1.0,
                                "probabilities": probabilities,
                            }
                        },
                    }
                ),
                200,
            )
        if self.fault == "generation_failed":
            return HttpResponse(b"{}", 503)
        raw = request["input"]
        assert isinstance(raw, str)
        state = json_object(raw.encode())
        output = candidates(candidate(self.store, state, "Rot."))
        text = canonical(output).decode()
        if self.fault == "generation_malformed":
            text = '{"candidates":'
        if self.fault == "generation_schema":
            text = '{"wrong":true}'
        if self.fault == "generation_semantic":
            text = '{"status":"candidates","candidates":[],"reason_code":"none"}'
        return HttpResponse(
            canonical(
                {
                    "model": "gpt-4.1-mini-2025-04-14",
                    "status": "completed",
                    "error": None,
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "status": "completed",
                            "content": [{"type": "output_text", "text": text}],
                        }
                    ],
                }
            ),
            200,
        )


def wired(fault: str | None = None):
    store = MemoryStore()
    req, ext, double = seed_extraction(store, "Rot.", lambda _stage, _state: "factual")
    transport = OfflineTransport(store, fault)
    decisions = JevDecisionModel(store, store, double.resources, double.dc, transport, Clock())
    generation = OpenAIGenerationModel(
        store, store, double.resources, double.gc, transport, Clock()
    )
    ext.models = T03Models(
        store, store, decisions, generation, double.resources, double.dc, double.gc
    )
    return store, req, ext, transport


def test_real_adapters_offline_replay() -> None:
    store, req, ext, transport = wired()
    outcome = ext.extract_claims(req)
    result = success(outcome)
    assert len(result.claims) == 1 and len(transport.calls) == 6
    first_state = transport.calls[0]["state"]
    assert isinstance(first_state, dict) and set(first_state) == {"source"}
    assert ext.extract_claims(req) == outcome and len(transport.calls) == 6
    for call in transport.calls:
        if "input" in call:
            raw = call["input"]
            assert isinstance(raw, str)
            assert "question" not in json_object(raw.encode())
    store.close()


@pytest.mark.parametrize(
    "fault",
    [
        "jev_malformed",
        "jev_failed",
        "unknown_label",
        "missing_probabilities",
        "generation_malformed",
        "generation_failed",
        "generation_schema",
        "generation_semantic",
        "tie",
    ],
)
def test_adapter_failures_are_auditable_not_negative(fault: str) -> None:
    _, req, ext, transport = wired(fault)
    outcome = ext.extract_claims(req)
    result = success(outcome)
    assert not result.claims
    assert result.issues and result.issues[-1].issue in {"failed", "unresolved"}
    calls = len(transport.calls)
    assert ext.extract_claims(req) == outcome and len(transport.calls) == calls


def test_receipt_survives_failed_decision_write() -> None:
    from unittest.mock import patch

    store, req, ext, transport = wired()
    original = store.append_decision
    failed = False

    def append(record: DecisionRecord) -> Outcome[DecisionRecord]:
        nonlocal failed
        if not failed:
            failed = True
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="storage_io_error", message="synthetic"),
            )
        return original(record)

    with patch.object(store, "append_decision", append):
        assert ext.extract_claims(req).status == "failed"
    assert len(transport.calls) == 1
    result = success(ext.extract_claims(req))
    assert len(result.claims) == 1 and len(transport.calls) == 6


def test_uncertain_receipt_stops_other_groups_without_error_name_heuristic() -> None:
    store = MemoryStore()
    req, ext, double = seed_extraction(store, "Rot.\n\nBlau.", lambda _stage, _state: "factual")
    transport = OfflineTransport(store, "uncertain_receipt")
    decision = JevDecisionModel(store, store, double.resources, double.dc, transport, Clock())
    generation = OpenAIGenerationModel(
        store, store, double.resources, double.gc, transport, Clock()
    )
    ext.models = T03Models(
        store, store, decision, generation, double.resources, double.dc, double.gc
    )
    outcome = ext.extract_claims(req)
    result = success(outcome)
    assert len(result.issues) == 2 and outcome.reason == "all_targets_failed"
    assert len(transport.calls) == 1
    assert ext.extract_claims(req) == outcome and len(transport.calls) == 1
