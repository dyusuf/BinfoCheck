from pathlib import Path

import pytest

from binfocheck.domain.interfaces import AnswerIndexer, ContextBuilder
from binfocheck.domain.records import RecordSet
from binfocheck.domain.storage import IdRequest
from binfocheck.domain.validation import validate_links
from binfocheck.storage import SQLiteStore
from binfocheck.text import IndexedContextBuilder, IndexSettings, StoredAnswerIndexer
from tests.storage.helpers import Store, all_records, failure, success

from .helpers import context, seed

TEXT = (
    "# Titel\r\n\r\nÄpfel 🍎 sind rot. Äpfel 🍎 sind rot.\r\n\r\n"
    "- Dr. A kommt. Danach geht er.\r\n- Café\tmit\u00a0Emoji 👩‍💻.\r\n\r\n"
    "## Zweiter Titel\r\n\r\nWeiter."
)


def test_index_contract_provenance_spans_and_idempotency(store: Store) -> None:
    request, answer = seed(store, TEXT)
    original = all_records(store)
    indexer: AnswerIndexer = StoredAnswerIndexer(store, store)
    units = success(indexer.index_answer(request))
    assert {u.unit_kind for u in units} == {"heading", "paragraph", "bullet", "sentence"}
    assert [u.order for u in units] == list(range(len(units)))
    assert all(u.input_ids == (request.observation_id, answer.id) for u in units)
    assert all(answer.text[u.span.start : u.span.end] == u.span.exact_text for u in units)
    assert all(u.heading_unit_id is None for u in units if u.unit_kind == "heading")
    by_id = {u.id: u for u in units}
    heading = None
    for unit in units:
        if unit.unit_kind == "heading":
            heading = unit.id
        else:
            assert unit.heading_unit_id == heading
        if unit.parent_unit_id:
            parent = by_id[unit.parent_unit_id]
            assert parent.span.start <= unit.span.start < unit.span.end <= parent.span.end
    repeats = [
        u for u in units if u.unit_kind == "sentence" and u.span.exact_text == "Äpfel 🍎 sind rot."
    ]
    assert len(repeats) == 2 and repeats[0].id != repeats[1].id
    assert repeats[0].span.start != repeats[1].span.start
    before = all_records(store)
    assert success(indexer.index_answer(request)) == units
    assert all_records(store) == before
    for record in original:
        assert success(store.get_record(IdRequest(id=record.id))) == record
    validate_links(RecordSet(records=before))


def test_persistent_reopen(tmp_path: Path) -> None:
    with SQLiteStore(tmp_path) as store:
        request, answer = seed(store, TEXT)
        units = success(StoredAnswerIndexer(store, store).index_answer(request))
        sentence = next(u for u in units if u.unit_kind == "sentence")
        ctx_request = context(request, answer, (sentence,))
        builder: ContextBuilder = IndexedContextBuilder(store, store)
        expected = success(builder.build_context(ctx_request))
        records = all_records(store)
    with SQLiteStore(tmp_path) as store:
        assert all_records(store) == records
        assert success(IndexedContextBuilder(store, store).build_context(ctx_request)) == expected
        assert success(StoredAnswerIndexer(store, store).index_answer(request)) == units
        validate_links(RecordSet(records=all_records(store)))


def test_index_bounds_and_settings_reject_before_writes(store: Store) -> None:
    request, _ = seed(store, TEXT)
    before = all_records(store)
    tiny = request.model_copy(update={"settings": IndexSettings(max_characters=1).envelope()})
    failure(StoredAnswerIndexer(store, store).index_answer(tiny), "index_limit_exceeded")
    tiny = request.model_copy(update={"settings": IndexSettings(max_units=1).envelope()})
    failure(StoredAnswerIndexer(store, store).index_answer(tiny), "index_limit_exceeded")
    bad = request.model_copy(deep=True)
    bad.settings.values["language"] = "en"
    failure(StoredAnswerIndexer(store, store).index_answer(bad), "invalid_index_settings")
    assert all_records(store) == before


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("answer_text_id", "other", "answer_mismatch"),
        ("analysis_run_id", "missing-run", "not_found"),
        ("observation_id", "missing-observation", "not_found"),
    ],
)
def test_bad_inputs(store: Store, field: str, value: str, code: str) -> None:
    request, _ = seed(store, TEXT)
    failure(
        StoredAnswerIndexer(store, store).index_answer(request.model_copy(update={field: value})),
        code,
    )
