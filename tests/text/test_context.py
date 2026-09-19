import pytest

from binfocheck.text import IndexedContextBuilder, IndexSettings, StoredAnswerIndexer
from tests.storage.helpers import Store, failure, success

from .helpers import context, seed


def test_context_order_dedup_and_heading_clipping(store: Store) -> None:
    request, answer = seed(store, "# A\n\nEins. Zwei. Drei.\n\n# B\n\nVier. Fünf.")
    units = success(StoredAnswerIndexer(store, store).index_answer(request))
    sentences = [u for u in units if u.unit_kind == "sentence"]
    headings = [u for u in units if u.unit_kind == "heading"]
    builder = IndexedContextBuilder(store, store)
    result = success(
        builder.build_context(context(request, answer, (sentences[2], sentences[1], sentences[2])))
    )
    assert result.ordered_unit_ids == (headings[0].id, *(u.id for u in sentences[:3]))
    assert set(result.model_dump()) == {"observation_id", "ordered_unit_ids"}
    result = success(
        builder.build_context(context(request, answer, (sentences[2],), clip_at_heading=False))
    )
    assert result.ordered_unit_ids == (
        headings[0].id,
        sentences[1].id,
        sentences[2].id,
        headings[1].id,
        sentences[3].id,
    )
    result = success(builder.build_context(context(request, answer, (headings[1],))))
    assert result.ordered_unit_ids == (headings[1].id, sentences[3].id, sentences[4].id)


def test_structural_and_opaque_targets(store: Store) -> None:
    request, answer = seed(store, "# A\n\n- Eins. Zwei.\n\n```\nopaque. code.\n```\n\n# Empty")
    units = success(StoredAnswerIndexer(store, store).index_answer(request))
    builder = IndexedContextBuilder(store, store)
    for target in units:
        result = success(
            builder.build_context(context(request, answer, (target,), before=0, after=0))
        )
        if target.unit_kind == "bullet":
            assert result.ordered_unit_ids == (
                units[0].id,
                *(u.id for u in units if u.parent_unit_id == target.id),
            )
        if target.span.exact_text.startswith("```"):
            assert result.ordered_unit_ids == (units[0].id, target.id)
        if target.span.exact_text == "# Empty":
            assert result.ordered_unit_ids == (target.id,)


def test_foreign_observation_and_exact_cohort(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, answer = seed(store, "Same. Same.", "one")
    other, other_answer = seed(store, "Same. Same.", "two")
    indexer = StoredAnswerIndexer(store, store)
    units = success(indexer.index_answer(request))
    others = success(indexer.index_answer(other))
    revised = request.model_copy(update={"settings": IndexSettings(max_units=99).envelope()})
    revision = success(indexer.index_answer(revised))
    assert {u.id for u in units}.isdisjoint(u.id for u in revision)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Context must load cohort IDs, not list insertion order")

    monkeypatch.setattr(store, "list_records", forbidden)
    builder = IndexedContextBuilder(store, store)
    first = next(u for u in units if u.unit_kind == "sentence")
    result = success(builder.build_context(context(request, answer, (first,))))
    assert result.ordered_unit_ids == tuple(u.id for u in units if u.unit_kind == "sentence")
    failure(
        builder.build_context(context(request, answer, (others[-1],))), "context_target_mismatch"
    )
    failure(
        builder.build_context(context(request, answer, (revision[-1],))), "context_target_mismatch"
    )
    foreign = context(other, other_answer, (others[-1],))
    foreign.settings.values["index_artifact_id"] = context(
        request, answer, (first,)
    ).settings.values["index_artifact_id"]
    failure(builder.build_context(foreign), "context_target_mismatch")


def test_missing_cohort_and_limits(store: Store) -> None:
    request, answer = seed(store, "One. Two. Three.")
    units = success(StoredAnswerIndexer(store, store).index_answer(request))
    builder = IndexedContextBuilder(store, store)
    target = next(u for u in units if u.unit_kind == "sentence")
    failure(
        builder.build_context(context(request, answer, (target,), index_artifact_id="missing")),
        "index_not_found",
    )
    failure(
        builder.build_context(context(request, answer, (target,), max_units=1)),
        "context_limit_exceeded",
    )
    invalid = context(request, answer, (target,))
    invalid.settings.values["before"] = -1
    failure(builder.build_context(invalid), "invalid_context_settings")
    many = context(request, answer, (target,) * 21)
    failure(builder.build_context(many), "context_limit_exceeded")
