from unittest.mock import patch

import pytest
from pydantic import JsonValue

from binfocheck.claims.artifacts import FinalAudit
from binfocheck.claims.context import prepare_inputs
from binfocheck.claims.errors import ExtractionError
from binfocheck.claims.extractor import validate_accounting
from binfocheck.claims.persistence import identity, load
from binfocheck.domain.common import Outcome
from binfocheck.domain.decisions import DecisionRecord
from binfocheck.domain.interfaces import DecisionRequest
from binfocheck.domain.storage import ArtifactPayload, IdRequest
from binfocheck.domain.text import ArtifactRef
from binfocheck.storage import MemoryStore
from tests.claims.helpers import anchor, candidate, candidates, positive, seed_extraction
from tests.storage.helpers import success

TEXT = "Der Ball ist rot. Das Tor ist offen."
FIRST = "Der Ball ist rot."


@pytest.mark.parametrize("outcome", ["accepted", "rejected", "failed", "unlocated", "duplicate"])
def test_candidate_cannot_account_for_an_unrepresented_sibling(outcome: str) -> None:
    store = MemoryStore()

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if stage == "F":
            first = candidate(store, state, FIRST)
            if outcome == "unlocated":
                anchor = first["anchor"]
                assert isinstance(anchor, dict)
                anchor["quote"] = "Erfundenes Zitat."
            if outcome == "duplicate":
                implicit = candidate(store, state, FIRST)
                anchor = implicit["anchor"]
                assert isinstance(anchor, dict)
                anchor["start"], anchor["end"] = None, None
                return candidates(first, implicit)
            return candidates(first)
        if stage == "H.faithfulness":
            if outcome == "rejected":
                return "unfaithful"
        return positive(stage)

    request, extractor, double = seed_extraction(store, TEXT, reply, target_kind="sentence")
    original_decide = double.decide

    def fail_validation(request: DecisionRequest) -> Outcome[DecisionRecord]:
        if request.task_type == "t04.H.faithfulness":
            double.failure = "synthetic_failure"
        return original_decide(request)

    inputs = prepare_inputs(store, store, request)
    assert len(inputs.groups) == 1
    a, b = inputs.groups[0].target_ids
    with patch.object(
        double, "decide", fail_validation if outcome == "failed" else original_decide
    ):
        result = extractor.extract_claims(request)
    extracted = success(result)
    final_id = identity("extraction-final", inputs.work_key)
    raw = load(store, final_id)
    assert raw is not None
    audit = FinalAudit.model_validate_json(raw)
    account_a, account_b = audit.target_accounting
    by_id = {issue.id: issue for issue in extracted.issues}

    assert account_b.terminal_claim_ids == ()
    assert len(account_b.terminal_issue_ids) == 1
    missing_b = by_id[account_b.terminal_issue_ids[0]]
    assert missing_b.reason == "target_not_represented." + b
    assert audit.issue_target_ids[missing_b.id] == (b,)
    assert missing_b.id not in account_a.terminal_issue_ids

    candidate_issues = [i for i in extracted.issues if i.reason.startswith(("G.", "H."))]
    for issue in candidate_issues:
        # The original broad provenance is preserved, but is not terminal scope.
        assert a in issue.context_unit_ids and b in issue.context_unit_ids
        assert issue.id not in account_b.terminal_issue_ids
        assert audit.issue_target_ids[issue.id] == (() if outcome == "unlocated" else (a,))
    if outcome == "unlocated":
        assert by_id[account_a.terminal_issue_ids[0]].reason == "target_not_represented." + a
    elif outcome in {"accepted", "duplicate"}:
        assert account_a.terminal_claim_ids == (extracted.claims[0].id,)
    else:
        assert not extracted.claims
        assert set(account_a.terminal_issue_ids) == {i.id for i in candidate_issues}
    assert audit.assessment_state == ("partial_failure" if outcome == "failed" else "complete")
    assert result.reason == ("partial_extraction" if outcome == "failed" else None)

    if candidate_issues and outcome != "unlocated":
        wrong_b = account_b.model_copy(update={"terminal_issue_ids": (candidate_issues[0].id,)})
        with pytest.raises(ExtractionError, match="accounting_issue_mismatch"):
            validate_accounting(inputs, extracted, (account_a, wrong_b), audit.issue_target_ids)

    calls = len(double.calls)
    assert extractor.extract_claims(request) == result
    assert load(store, final_id) == raw
    assert len(double.calls) == calls


@pytest.mark.parametrize(
    "terminal",
    [
        "B.nonfactual",
        "B.uncertain",
        "B.model_failed",
        "D.unresolved",
        "E.insufficient_context",
        "F.candidate_limit",
        "F.cannot_extract",
    ],
)
def test_group_terminal_issue_accounts_for_both_targets(terminal: str) -> None:
    store = MemoryStore()

    def reply(stage: str, _state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if terminal.startswith(stage + "."):
            reason = terminal.split(".", 1)[1]
            if stage == "F":
                return {"status": "unresolved", "candidates": [], "reason_code": reason}
            if stage == "E":
                return {
                    "status": "unresolved",
                    "clarified_text": None,
                    "anchors": [],
                    "bindings": [],
                    "reason_code": reason,
                }
            return reason
        if stage == "D" and terminal.startswith("E."):
            return "resolvable_from_context"
        return positive(stage)

    request, extractor, double = seed_extraction(store, TEXT, reply, target_kind="sentence")
    if terminal == "B.model_failed":
        double.failure = "synthetic_failure"
    inputs = prepare_inputs(store, store, request)
    assert len(inputs.groups) == 1 and len(inputs.groups[0].target_ids) == 2
    result = extractor.extract_claims(request)
    extracted = success(result)
    assert not extracted.claims and len(extracted.issues) == 1
    issue = extracted.issues[0]
    assert issue.reason == terminal
    raw = load(store, identity("extraction-final", inputs.work_key))
    assert raw is not None
    audit = FinalAudit.model_validate_json(raw)
    assert audit.issue_target_ids[issue.id] == inputs.groups[0].target_ids
    assert all(a.terminal_issue_ids == (issue.id,) for a in audit.target_accounting)
    assert audit.assessment_state == (
        "all_targets_failed" if terminal == "B.model_failed" else "complete"
    )
    calls = len(double.calls)
    assert extractor.extract_claims(request) == result
    assert load(store, identity("extraction-final", inputs.work_key)) == raw
    assert len(double.calls) == calls


def test_accounting_survives_final_write_failure_and_retry() -> None:
    store = MemoryStore()

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if stage == "F":
            return candidates(candidate(store, state, FIRST))
        return "unfaithful" if stage == "H.faithfulness" else positive(stage)

    request, extractor, double = seed_extraction(store, TEXT, reply, target_kind="sentence")
    original = store.put_artifact
    attempted: list[ArtifactPayload] = []

    def fail_final(payload: ArtifactPayload) -> Outcome[ArtifactRef]:
        if payload.ref.id.startswith("extraction-final-"):
            attempted.append(payload)
            raise ExtractionError("synthetic_storage_failure")
        return original(payload)

    with patch.object(store, "put_artifact", fail_final):
        assert extractor.extract_claims(request).status == "failed"
    assert len(attempted) == 1 and len(double.calls) == 6
    result = extractor.extract_claims(request)
    success(result)
    assert success(store.get_artifact(IdRequest(id=attempted[0].ref.id))) == attempted[0]
    assert extractor.extract_claims(request) == result and len(double.calls) == 6


def test_located_multisentence_support_accounts_for_both_targets() -> None:
    store = MemoryStore()
    first = "Die Prüfung beginnt um 9 Uhr."
    second = "Sie dauert 30 Minuten."

    def reply(stage: str, state: dict[str, JsonValue]) -> str | dict[str, JsonValue]:
        if stage == "F":
            item = candidate(store, state, second, "Die Prüfung dauert 30 Minuten.")
            item["required_support"] = [anchor(store, state, first)]
            return candidates(item)
        return "uncertain" if stage == "H.faithfulness" else positive(stage)

    request, extractor, _ = seed_extraction(
        store, first + " " + second, reply, target_kind="sentence"
    )
    inputs = prepare_inputs(store, store, request)
    result = success(extractor.extract_claims(request))
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.original_span is not None
    assert issue.original_span.exact_text == first + " " + second
    raw = load(store, identity("extraction-final", inputs.work_key))
    assert raw is not None
    audit = FinalAudit.model_validate_json(raw)
    assert audit.issue_target_ids[issue.id] == inputs.groups[0].target_ids
    assert all(a.terminal_issue_ids == (issue.id,) for a in audit.target_accounting)
