import pytest

from binfocheck.domain.observations import Observation
from binfocheck.domain.runs import RunManifest
from binfocheck.domain.storage import IdRequest
from binfocheck.text import StoredAnswerIndexer, index_reference_id
from binfocheck.text.errors import TextError
from binfocheck.text.persistence import UnitEntry, load_index, unit_hash, validate_units
from tests.storage.helpers import Store, success

from .helpers import seed


@pytest.mark.parametrize(
    "damage", ["order", "parent", "heading", "inputs", "span", "heading_hierarchy"]
)
def test_graph_validation_beyond_payload_hash(store: Store, damage: str) -> None:
    query, answer = seed(store, "# Heading\n\nOne. Two.")
    units = success(StoredAnswerIndexer(store, store).index_answer(query))
    run = success(store.get_record(IdRequest(id=query.analysis_run_id)))
    observation = success(store.get_record(IdRequest(id=query.observation_id)))
    assert isinstance(run, RunManifest) and isinstance(observation, Observation)
    manifest, _ = load_index(
        store, store, index_reference_id(query, answer), run, observation, answer
    )
    last = units[-1]
    match damage:
        case "order":
            last = last.model_copy(update={"order": 0})
        case "parent":
            last = last.model_copy(update={"parent_unit_id": last.id})
        case "heading":
            last = last.model_copy(update={"heading_unit_id": None})
        case "inputs":
            last = last.model_copy(update={"input_ids": (manifest.artifact_id,)})
        case "span":
            last = last.model_copy(
                update={"span": last.span.model_copy(update={"exact_text": "xxxx"})}
            )
        case "heading_hierarchy":
            manifest = manifest.model_copy(
                update={
                    "headings": (
                        manifest.headings[0].model_copy(update={"parent_heading_id": units[0].id}),
                    )
                }
            )
        case _:
            raise AssertionError("unknown test mutation")
    damaged = (*units[:-1], last)
    # Rehash so structural validation, not just checksum verification, must reject.
    manifest = manifest.model_copy(
        update={"units": tuple(UnitEntry(id=u.id, sha256=unit_hash(u)) for u in damaged)}
    )
    with pytest.raises(TextError) as error:
        validate_units(damaged, manifest, run, observation, answer)
    assert error.value.detail.code == "invalid_unit_graph"
