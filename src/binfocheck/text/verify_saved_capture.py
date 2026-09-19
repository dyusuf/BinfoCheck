"""Copy first, then offline T11A verification. Never open the original with SQLiteStore."""

import argparse
import hashlib
import json
import shutil
import socket
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from pydantic import JsonValue

from binfocheck.domain.common import ProcessingStatus, VersionRef
from binfocheck.domain.interfaces import ContextRequest, IndexRequest
from binfocheck.domain.observations import Observation, SourceReference, TextUnit
from binfocheck.domain.records import Record, RecordSet
from binfocheck.domain.runs import Budget, RunManifest
from binfocheck.domain.storage import IdRequest, ListRequest, RecordStore
from binfocheck.domain.text import ArtifactRef, TextRecord
from binfocheck.domain.validation import validate_links
from binfocheck.storage import SQLiteStore, StorageInitializationError

from .config import SPACY_VERSION, ContextSettings, IndexSettings
from .context import IndexedContextBuilder
from .errors import TextError, require
from .indexing import StoredAnswerIndexer
from .persistence import index_reference_id


def fingerprint(root: Path) -> dict[str, tuple[str, int, int]]:
    if not root.is_dir() or root.is_symlink():
        raise TextError("saved_capture_missing")
    result: dict[str, tuple[str, int, int]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise TextError("unsafe_source_store")
        if path.is_file():
            stat = path.stat()
            result[str(path.relative_to(root))] = (
                hashlib.sha256(path.read_bytes()).hexdigest(),
                stat.st_mtime_ns,
                stat.st_mode,
            )
    return result


def all_records(store: RecordStore) -> tuple[Record, ...]:
    records: list[Record] = []
    cursor: str | None = None
    while True:
        page = require(store.list_records(ListRequest(limit=1000, cursor=cursor)))
        records.extend(page.records)
        if page.next_cursor is None:
            return tuple(records)
        cursor = page.next_cursor


def blocked(*args: object, **kwargs: object) -> None:
    raise TextError("network_forbidden")


def verify(source: Path, observation_id: str) -> dict[str, JsonValue]:
    with (
        patch.object(socket, "create_connection", blocked),
        patch.object(socket.socket, "connect", blocked),
        patch.object(socket.socket, "connect_ex", blocked),
    ):
        before = fingerprint(source)
        destination = Path(tempfile.mkdtemp(prefix="binfocheck-t02-verification-")) / "store"
        # Complete private directory copy before any T11A initialization or reads.
        shutil.copytree(source, destination, copy_function=shutil.copy2)
        try:
            with SQLiteStore(destination) as store:
                originals = all_records(store)
                validate_links(RecordSet(records=originals))
                observation = require(store.get_record(IdRequest(id=observation_id)))
                if not isinstance(observation, Observation) or observation.answer_text_id is None:
                    raise TextError("invalid_index_inputs")
                answer = require(store.get_record(IdRequest(id=observation.answer_text_id)))
                if not isinstance(answer, TextRecord):
                    raise TextError("answer_mismatch")
                citation_spans = [
                    r.citation_span
                    for r in originals
                    if isinstance(r, SourceReference)
                    and r.observation_id == observation.id
                    and r.citation_span is not None
                ]
                if not all(
                    s.text_id == answer.id and answer.text[s.start : s.end] == s.exact_text
                    for s in citation_spans
                ):
                    raise TextError("verification_failed")
                for record in originals:
                    if isinstance(record, ArtifactRef):
                        require(store.get_artifact(IdRequest(id=record.id)))
                config = IndexSettings()
                run = RunManifest(
                    id="t02-verification-" + uuid4().hex,
                    created_at=datetime.now(UTC),
                    input_ids=(observation.id, answer.id),
                    observation_ids=(observation.id,),
                    corpus_manifest_id=None,
                    purpose="diagnostic",
                    mode="reanalysis",
                    capture_settings=observation.requested_settings,
                    configuration=VersionRef(name="t02-text-index", version="1"),
                    model_ids=(),
                    prompt_versions=(),
                    rubric_versions=(),
                    budget=Budget(
                        request_limit=0,
                        cost_limit=0.0,
                        currency="USD",
                        timeout_seconds=60.0,
                        concurrency=1,
                        retry_limit=0,
                    ),
                    status=ProcessingStatus.SUCCEEDED,
                )
                require(store.put_record(run))
                request = IndexRequest(
                    analysis_run_id=run.id,
                    observation_id=observation.id,
                    answer_text_id=answer.id,
                    settings=config.envelope(),
                )
                indexer = StoredAnswerIndexer(store, store)
                units = require(indexer.index_answer(request))
                if require(indexer.index_answer(request)) != units:
                    raise TextError("verification_failed")
                target = next((u for u in units if u.unit_kind == "sentence"), units[0])
                ctx_request = ContextRequest(
                    analysis_run_id=run.id,
                    observation_id=observation.id,
                    target_unit_ids=(target.id,),
                    settings=ContextSettings(
                        index_artifact_id=index_reference_id(request, answer)
                    ).envelope(),
                )
                context = require(IndexedContextBuilder(store, store).build_context(ctx_request))
                saved = all_records(store)
                validate_links(RecordSet(records=saved))
            with SQLiteStore(destination) as store:
                if all_records(store) != saved:
                    raise TextError("verification_failed")
                if (
                    require(IndexedContextBuilder(store, store).build_context(ctx_request))
                    != context
                ):
                    raise TextError("verification_failed")
                for record in originals:
                    if require(store.get_record(IdRequest(id=record.id))) != record:
                        raise TextError("verification_failed")
                validate_links(RecordSet(records=all_records(store)))
                recovered = tuple(require(store.get_record(IdRequest(id=u.id))) for u in units)
                if recovered != units or not all(
                    isinstance(u, TextUnit)
                    and answer.text[u.span.start : u.span.end] == u.span.exact_text
                    for u in recovered
                ):
                    raise TextError("verification_failed")
        finally:
            if fingerprint(source) != before:
                raise TextError("source_store_changed")
        counts: dict[str, JsonValue] = dict(Counter(u.unit_kind for u in units))
        return {
            "status": "passed",
            "spacy_version": SPACY_VERSION,
            "observation_id": observation.id,
            "answer_text_id": answer.id,
            "answer_sha256": hashlib.sha256(answer.text.encode()).hexdigest(),
            "answer_characters": len(answer.text),
            "unchanged_citation_spans": len(citation_spans),
            "units": len(units),
            "unit_kinds": counts,
            "context_units": len(context.ordered_unit_ids),
            "source_unchanged": True,
            "original_records_unchanged": True,
            "exact_spans": True,
            "validate_links": True,
            "idempotent": True,
            "reopen_context_identical": True,
            "network_blocked": True,
            "provider_calls": 0,
            "copied_store": str(destination),
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline T02 verification on a complete private copy"
    )
    parser.add_argument("--source-store", type=Path, required=True)
    parser.add_argument("--observation-id", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(Path(args.source_store), str(args.observation_id))))
        return 0
    except (TextError, StorageInitializationError) as error:
        print(json.dumps({"status": "failed", "error": error.detail.code}))
    except (OSError, ValueError):
        print(json.dumps({"status": "failed", "error": "verification_failed"}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
