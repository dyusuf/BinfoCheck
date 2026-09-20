"""Human-labeled D specification and offline routing, never model-quality evidence."""

import json

import pytest
from pydantic import JsonValue, TypeAdapter

from binfocheck.claims.integration import T03Models
from binfocheck.claims.resources import ExtractionResources
from binfocheck.domain.interfaces import DecisionRequest
from binfocheck.models.persistence import prepare
from binfocheck.storage import MemoryStore
from tests.claims.helpers import ROOT, anchor, candidate, candidates, positive, seed_extraction
from tests.storage.helpers import success

CASES = TypeAdapter(list[dict[str, str]]).validate_json(
    (ROOT / "tests/fixtures/claims/v2/ambiguity.json").read_bytes()
)


def test_only_d_changes_and_v1_remains_pinned() -> None:
    old, new = ExtractionResources(ROOT, version="1"), ExtractionResources(ROOT)
    assert old.version.sha256 == "f6b0fc9d2acdd1e96392e29830d57aa96f15c5afd827fd58ba755fbe1d91e281"
    assert (
        old.ref("ambiguity").sha256
        == "d9b9e054db293fea05921637a980fe8be272a664f5074edb38ffccd4298ab620"
    )
    assert old.policy == new.policy
    assert {k for k in old.refs if old.refs[k] != new.refs[k]} == {"t04-ambiguity"}
    assert new.ref("ambiguity").version == "2"
    for key in old.refs.keys() - {"t04-ambiguity"}:
        assert old.resolve(old.refs[key]) == new.resolve(new.refs[key])


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_v2_labeled_cases_prepare_exact_rubric_and_preserve_routing(case: dict[str, str]) -> None:
    store = MemoryStore()
    text, context, expected = case["text"], case["context"], case["expected"]

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if stage == "D":
            supplied = state.get("context", [])
            assert isinstance(supplied, list)
            if context:
                assert any(isinstance(c, dict) and c["text"] == context for c in supplied)
            else:
                assert not supplied
            if "question" in state:
                question = state["question"]
                assert isinstance(question, dict)
                assert question["text"] == "Welche Angaben enthält die Antwort?"
            return expected
        if stage == "E":
            assert expected == "resolvable_from_context"
            supplied = state["context"]
            assert isinstance(supplied, list)
            return {
                "status": "clarified",
                "clarified_text": "Der Ball ist rot.",
                "anchors": [anchor(store, state, text)],
                "bindings": [
                    {
                        "reference": "Er",
                        "resolved_reference": "Der Ball",
                        "answer_context_unit_ids": [
                            c["unit_id"] for c in supplied if isinstance(c, dict)
                        ],
                        "question_reference_used": False,
                    }
                ],
                "reason_code": "none",
            }
        if stage == "F":
            value = candidate(store, state, text, "Der Ball ist rot." if context else text)
            if expected == "resolvable_from_context":
                value["consumed_binding_indices"] = [0]
            return candidates(value)
        return positive(stage)

    request, extractor, double = seed_extraction(
        store,
        context + "\n\n" + text if context else text,
        reply,
        question="Welche Angaben enthält die Antwort?",
        target_orders=(2,) if context else None,
    )
    result = success(extractor.extract_claims(request))
    stages = [stage for stage, _, _ in double.calls]
    if expected == "unresolved":
        assert not result.claims
        assert len(result.issues) == 1 and result.issues[0].issue == "unresolved"
        assert stages == ["B", "D"]
    else:
        assert len(result.claims) == 1 and not result.issues
        assert ("E" in stages) == (expected == "resolvable_from_context")
        assert stages[-4:] == ["F", "H.faithfulness", "H.atomicity", "H.self_containment"]
    d_request = next(req for stage, _, req in double.calls if stage == "D")
    assert isinstance(d_request, DecisionRequest)
    prepared = prepare(d_request, double.dc, double.resources, store)
    rubric = json.loads(double.resources.resolve(double.resources.ref("ambiguity")))
    assert prepared.body["questions"] == {"q0": {"type": "choice", **rubric}}
    assert d_request.rubric_version == double.resources.ref("ambiguity")


def test_v1_replay_and_version_mismatch_fail_before_calls() -> None:
    store = MemoryStore()
    request, extractor, double = seed_extraction(
        store,
        "Er ist rot.",
        lambda stage, _: "unresolved" if stage == "D" else positive(stage),
        question="Welche Angaben enthält die Antwort?",
        resource_version="1",
    )
    old_result = success(extractor.extract_claims(request))
    assert old_result.issues[0].issue == "unresolved"
    d_request = next(req for stage, _, req in double.calls if stage == "D")
    assert isinstance(d_request, DecisionRequest)
    old_prepared = prepare(d_request, double.dc, double.resources, store)
    v2 = ExtractionResources(ROOT)
    v2_request = d_request.model_copy(update={"rubric_version": v2.ref("ambiguity")})
    new_prepared = prepare(v2_request, double.dc, v2, store)
    assert old_prepared.work_key != new_prepared.work_key
    assert old_prepared.record_id != new_prepared.record_id
    double.calls.clear()
    assert success(extractor.extract_claims(request)) == old_result
    assert not double.calls
    old_config = extractor.models.configuration
    extractor.models = T03Models(
        store, store, double, double, ExtractionResources(ROOT), double.dc, double.gc
    )
    assert extractor.models.configuration != old_config
    assert extractor.extract_claims(request).status == "failed"
    assert not double.calls
