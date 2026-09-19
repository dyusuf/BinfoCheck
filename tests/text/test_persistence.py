import pytest

from binfocheck.domain.common import ErrorDetail, Outcome
from binfocheck.domain.records import Record
from binfocheck.domain.storage import ArtifactPayload, IdRequest
from binfocheck.domain.text import ArtifactRef
from binfocheck.storage import MemoryStore
from binfocheck.text import IndexedContextBuilder, StoredAnswerIndexer
from tests.storage.helpers import Store, all_records, failure, success

from .helpers import context, seed


class FailingStore(MemoryStore):
    fail: str | None = None

    def put_record(self, request: Record) -> Outcome[Record]:
        if self.fail == "unit" and request.kind == "text_unit" and request.order >= 1:
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="storage_io_error", message="storage io error"),
            )
        return super().put_record(request)

    def put_artifact(self, request: ArtifactPayload) -> Outcome[ArtifactRef]:
        if self.fail == "publication" and request.ref.storage_key == "text/index-completion-v1":
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="storage_io_error", message="storage io error"),
            )
        return super().put_artifact(request)


@pytest.mark.parametrize("stage", ["unit", "publication"])
def test_partial_write_never_complete_and_can_finish_identically(stage: str) -> None:
    with FailingStore() as store:
        request, answer = seed(store, "One. Two.")
        store.fail = stage
        indexer = StoredAnswerIndexer(store, store)
        failure(indexer.index_answer(request), "storage_io_error")
        partial = [r for r in all_records(store) if r.kind == "text_unit"]
        assert partial
        failure(
            IndexedContextBuilder(store, store).build_context(
                context(request, answer, (partial[0],))
            ),
            "index_incomplete",
        )
        store.fail = None
        units = success(indexer.index_answer(request))
        assert all(p in units for p in partial)
        success(
            IndexedContextBuilder(store, store).build_context(
                context(request, answer, (units[-1],))
            )
        )


@pytest.mark.parametrize("corrupt", [False, True])
def test_missing_or_changed_unit_is_not_partial_success(
    store: Store, monkeypatch: pytest.MonkeyPatch, corrupt: bool
) -> None:
    request, answer = seed(store, "One. Two.")
    units = success(StoredAnswerIndexer(store, store).index_answer(request))
    original = store.get_record

    def damaged(query: IdRequest) -> Outcome[Record]:
        if query.id == units[-1].id:
            if corrupt:
                return Outcome(
                    status="succeeded",
                    value=units[-1].model_copy(update={"heading_unit_id": units[0].id}),
                    error=None,
                )
            return Outcome(
                status="failed",
                value=None,
                error=ErrorDetail(code="not_found", message="not found"),
            )
        return original(query)

    monkeypatch.setattr(store, "get_record", damaged)
    failure(
        IndexedContextBuilder(store, store).build_context(context(request, answer, (units[-1],))),
        "invalid_unit_graph" if corrupt else "index_incomplete",
    )
