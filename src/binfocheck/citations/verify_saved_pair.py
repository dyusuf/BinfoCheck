"""Offline diagnostic on a private copy; requires already-completed T04 evidence."""

import argparse
import json
import shutil
import socket
import tempfile
from pathlib import Path
from unittest.mock import patch

from pydantic import JsonValue

from binfocheck.acquisition.replay import replay_capture
from binfocheck.claims.artifacts import FinalAudit
from binfocheck.claims.persistence import identity as extraction_identity
from binfocheck.domain.claims import Claim
from binfocheck.domain.decisions import DecisionRecord, DecisionResult, GenerationResult
from binfocheck.domain.interfaces import ClaimRequest
from binfocheck.domain.observations import Observation
from binfocheck.domain.records import RecordSet
from binfocheck.domain.storage import IdRequest
from binfocheck.domain.text import ArtifactRef
from binfocheck.domain.validation import validate_links
from binfocheck.models.receipt import ModelReceipt, PreparedRequest, role_id
from binfocheck.models.replay import replay as replay_saved_model_record
from binfocheck.storage import SQLiteStore, StorageInitializationError
from binfocheck.text.errors import TextError
from binfocheck.text.verify_saved_capture import all_records, fingerprint

from .config import CitationSettings, digest
from .errors import CitationError, check, require
from .mapper import StoredCitationMapper
from .persistence import Store, closure


def check_saved_claim(store: Store, claim_id: str, audit_id: str) -> Claim:
    found = store.records.get_record(IdRequest(id=claim_id))
    if found.error and found.error.code == "not_found":
        raise CitationError("genuine_t04_claim_missing")
    claim = require(found)
    check(isinstance(claim, Claim), "genuine_t04_claim_missing")
    assert isinstance(claim, Claim)
    check(bool(claim.decision_ids), "completed_t04_evidence_missing")
    audit_bytes = store.bytes(audit_id)
    audit = FinalAudit.model_validate_json(audit_bytes)
    check(
        audit_id == extraction_identity("extraction-final", audit.work_key),
        "extraction_identity_mismatch",
    )
    check(claim in audit.extraction_result.claims, "claim_not_in_extraction_audit")
    check(
        any(claim.id in a.terminal_claim_ids for a in audit.target_accounting),
        "claim_not_accounted",
    )
    completion = json.loads(store.bytes(extraction_identity("extraction-complete", audit.work_key)))
    check(
        completion
        == {
            "version": "1",
            "work_key": audit.work_key,
            "final_output_artifact_id": audit_id,
            "final_output_sha256": digest(audit_bytes),
            "status": "complete",
        },
        "extraction_not_complete",
    )
    for id in audit.stage_artifact_ids:
        store.bytes(id)
    validations: set[str] = set()
    generated = False
    expected = {
        "t04.H.faithfulness": "faithful",
        "t04.H.atomicity": "atomic",
        "t04.H.self_containment": "self_contained",
    }
    for id in claim.decision_ids:
        decision = store.record(id, DecisionRecord)
        check(decision.analysis_run_id == claim.analysis_run_id, "invalid_t04_decision")
        # T04 preserves accumulated group decisions, including other candidates.
        # A failed unrelated candidate cannot be mistaken for this claim's validation.
        if decision.status != "succeeded":
            continue
        receipt = ModelReceipt.model_validate_json(store.bytes(role_id(id, "receipt")))
        check(
            receipt.record_id == id
            and receipt.complete
            and receipt.dispatched
            and not receipt.outcome_uncertain
            and receipt.raw_response_artifact is not None,
            "saved_dispatch_evidence_missing",
        )
        # T03 replay only parses saved bytes; this API accepts no model/transport.
        check(
            require(replay_saved_model_record(store.records, store.artifacts, id)) == decision,
            "t04_saved_decision_mismatch",
        )
        if isinstance(decision.result, GenerationResult) and decision.task_type == "t04.F":
            generated = True
        if isinstance(decision.result, DecisionResult) and decision.task_type in expected:
            prepared = PreparedRequest.model_validate_json(
                store.bytes(receipt.prepared_artifact.id)
            )
            state_id = prepared.request.settings.values.get("state_artifact_id")
            check(isinstance(state_id, str), "validation_state_missing")
            assert isinstance(state_id, str)
            state = json.loads(store.bytes(state_id))
            if state.get("normalized_claim") == claim.normalized_claim and state.get(
                "original_span"
            ) == claim.original_span.model_dump(mode="json"):
                check(
                    decision.result.label == expected[decision.task_type],
                    "claim_validation_not_positive",
                )
                validations.add(decision.task_type)
    check(generated and validations == set(expected), "completed_t04_evidence_missing")
    closure(store, (claim,))
    observation = store.record(claim.observation_id, Observation)
    check(
        require(replay_capture(store.records, store.artifacts, observation.request_id))
        == observation,
        "saved_observation_mismatch",
    )
    return claim


def blocked(*args: object, **kwargs: object) -> None:
    raise CitationError("network_forbidden")


def verify(
    source: Path, claim_id: str, index_id: str, extraction_audit_id: str
) -> dict[str, JsonValue]:
    with (
        patch.object(socket, "create_connection", blocked),
        patch.object(socket, "getaddrinfo", blocked),
        patch.object(socket.socket, "connect", blocked),
        patch.object(socket.socket, "connect_ex", blocked),
    ):
        before = fingerprint(source)
        destination = Path(tempfile.mkdtemp(prefix="binfocheck-t05-verification-")) / "store"
        try:
            shutil.copytree(source, destination, copy_function=shutil.copy2)
            with SQLiteStore(destination) as backend:
                originals = all_records(backend)
                store = Store(backend, backend)
                claim = check_saved_claim(store, claim_id, extraction_audit_id)
                request = ClaimRequest(
                    analysis_run_id=claim.analysis_run_id,
                    claim_id=claim.id,
                    settings=CitationSettings(index_artifact_id=index_id).envelope(),
                )
                result = require(StoredCitationMapper(backend, backend).map_citations(request))
                saved = all_records(backend)
                validate_links(RecordSet(records=saved))
                for record in saved:
                    if isinstance(record, ArtifactRef):
                        store.bytes(record.id)
            with SQLiteStore(destination) as backend:
                check(
                    require(StoredCitationMapper(backend, backend).map_citations(request))
                    == result,
                    "replay_changed",
                )
                check(all_records(backend) == saved, "replay_changed")
                for original in originals:
                    check(
                        require(backend.get_record(IdRequest(id=original.id))) == original,
                        "original_changed",
                    )
        finally:
            check(fingerprint(source) == before, "source_store_changed")
        return {
            "status": "passed",
            "claim_id": claim_id,
            "observation_id": claim.observation_id,
            "association_id": result.id,
            "citation_status": result.status.value,
            "reason": result.reason,
            "copied_store": str(destination),
            "source_unchanged": True,
            "replay_identical": True,
            "network_blocked": True,
            "provider_calls": 0,
            "model_calls": 0,
            "new_cost_usd": 0,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline T05 diagnostic using saved T04 evidence")
    parser.add_argument("--source-store", type=Path, required=True)
    parser.add_argument("--claim-id", required=True)
    parser.add_argument("--index-artifact-id", required=True)
    parser.add_argument("--extraction-audit-id", required=True)
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                verify(
                    Path(args.source_store),
                    str(args.claim_id),
                    str(args.index_artifact_id),
                    str(args.extraction_audit_id),
                )
            )
        )
        return 0
    except (CitationError, TextError, StorageInitializationError) as error:
        print(
            json.dumps(
                {
                    "status": "blocked"
                    if error.detail.code == "genuine_t04_claim_missing"
                    else "failed",
                    "error": error.detail.code,
                }
            )
        )
    except (OSError, ValueError):
        print(json.dumps({"status": "failed", "error": "saved_pair_verification_failed"}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
