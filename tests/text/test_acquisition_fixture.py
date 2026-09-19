from binfocheck.acquisition.persistence import persist_response
from binfocheck.domain.interfaces import IndexRequest
from binfocheck.domain.observations import SourceReference
from binfocheck.domain.records import RecordSet
from binfocheck.domain.runs import RunManifest
from binfocheck.domain.storage import IdRequest
from binfocheck.domain.text import TextRecord
from binfocheck.domain.validation import validate_links
from binfocheck.text import IndexedContextBuilder, IndexSettings, StoredAnswerIndexer
from tests.acquisition.helpers import AT, request, response
from tests.storage.helpers import Store, all_records, success

from .helpers import context, seed


def test_t01_fixture_preserves_answer_and_citations(store: Store) -> None:
    template, _ = seed(store, "Template.")
    run = success(store.get_record(IdRequest(id=template.analysis_run_id)))
    assert isinstance(run, RunManifest)
    capture = request()
    success(store.put_record(capture))
    observation = persist_response(store, store, capture, response(), AT)
    assert observation.answer_text_id is not None
    answer = success(store.get_record(IdRequest(id=observation.answer_text_id)))
    assert isinstance(answer, TextRecord)
    run = run.model_copy(
        update={
            "id": "t01-index-run",
            "observation_ids": (observation.id,),
            "input_ids": (observation.id, answer.id),
        }
    )
    success(store.put_record(run))
    before = all_records(store)
    query = IndexRequest(
        analysis_run_id=run.id,
        observation_id=observation.id,
        answer_text_id=answer.id,
        settings=IndexSettings().envelope(),
    )
    units = success(StoredAnswerIndexer(store, store).index_answer(query))
    assert answer.text[8:17] == "sind rot."
    citations = [r for r in before if isinstance(r, SourceReference) and r.citation_span]
    assert len(citations) == 2
    for citation in citations:
        span = citation.citation_span
        assert span is not None
        assert answer.text[span.start : span.end] == span.exact_text
    for original in before:
        assert success(store.get_record(IdRequest(id=original.id))) == original
    assert all(answer.text[u.span.start : u.span.end] == u.span.exact_text for u in units)
    success(IndexedContextBuilder(store, store).build_context(context(query, answer, (units[-1],))))
    validate_links(RecordSet(records=all_records(store)))
