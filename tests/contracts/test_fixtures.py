import json
from datetime import timedelta

import pytest
from jsonschema import Draft202012Validator
from jsonschema import validate as validate_schema
from pydantic import TypeAdapter, ValidationError

from binfocheck.domain.catalog import BOUNDARIES, RECORD_MODELS
from binfocheck.domain.common import Availability, Available, UTCRecord
from binfocheck.domain.decisions import Usage
from binfocheck.domain.records import RECORD_ADAPTER
from binfocheck.domain.validation import validate_links
from tests.doubles.components import Exchange

from .helpers import FIXTURES, BoundaryCase, InvalidExchange, RecordCase, linked

RECORD_CASES = TypeAdapter(list[RecordCase]).validate_json((FIXTURES / "records.json").read_bytes())
BOUNDARY_CASES = TypeAdapter(list[BoundaryCase]).validate_json(
    (FIXTURES / "boundaries.json").read_bytes()
)


def test_fixture_coverage_is_exhaustive() -> None:
    expected = {model.model_fields["kind"].default for model in RECORD_MODELS}
    assert {case.kind for case in RECORD_CASES} == expected
    assert len(RECORD_CASES) == len(expected)
    assert {case.name for case in BOUNDARY_CASES} == set(BOUNDARIES)
    assert len(BOUNDARY_CASES) == len(BOUNDARIES)
    for case in RECORD_CASES:
        assert bool(case.unavailable) != bool(case.unavailable_not_applicable)


@pytest.mark.parametrize("case", RECORD_CASES, ids=lambda case: case.kind)
def test_record_examples(case: RecordCase) -> None:
    valid = RECORD_ADAPTER.validate_json((FIXTURES / case.valid).read_bytes())
    assert RECORD_ADAPTER.validate_json(valid.model_dump_json()) == valid
    validate_schema(
        json.loads(valid.model_dump_json()),
        type(valid).model_json_schema(),
        cls=Draft202012Validator,
    )
    with pytest.raises(ValidationError) as error:
        RECORD_ADAPTER.validate_json((FIXTURES / case.invalid).read_bytes())
    errors = error.value.errors()
    assert any(item["type"] == case.error.type for item in errors)
    if case.error.contains:
        assert case.error.contains in str(error.value)
    if case.unavailable:
        missing = RECORD_ADAPTER.validate_json((FIXTURES / case.unavailable).read_bytes())
        assert RECORD_ADAPTER.validate_json(missing.model_dump_json()) == missing
        validate_schema(
            json.loads(missing.model_dump_json()),
            type(missing).model_json_schema(),
            cls=Draft202012Validator,
        )


@pytest.mark.parametrize("case", BOUNDARY_CASES, ids=lambda case: case.name)
def test_boundary_examples(case: BoundaryCase) -> None:
    spec = BOUNDARIES[case.name]
    for path in (case.valid, case.unavailable):
        exchange = Exchange.model_validate_json((FIXTURES / path).read_bytes())
        for adapter, data in ((spec.request, exchange.request), (spec.response, exchange.response)):
            parsed = adapter.validate_json(json.dumps(data))
            assert adapter.validate_json(parsed.model_dump_json()) == parsed
            validate_schema(
                json.loads(parsed.model_dump_json()),
                adapter.json_schema(),
                cls=Draft202012Validator,
            )
    invalid = InvalidExchange.model_validate_json((FIXTURES / case.invalid).read_bytes())
    for adapter, data, expected in (
        (spec.request, invalid.request, invalid.request_error),
        (spec.response, invalid.response, invalid.response_error),
    ):
        with pytest.raises(ValidationError) as error:
            adapter.validate_json(json.dumps(data))
        assert any(item["type"] == expected.type for item in error.value.errors())
        if expected.contains:
            assert expected.contains in str(error.value)


def test_linked_bundle_round_trip() -> None:
    bundle = linked()
    validate_links(bundle)
    restored = type(bundle).model_validate_json(bundle.model_dump_json())
    assert restored == bundle
    validate_links(restored)
    by_id = {record.id: record for record in restored.records}
    assert by_id["obs-1"].kind == "observation"
    assert by_id["claim-1"].kind == "claim"
    assert by_id["finding-1"].kind == "finding"
    assert by_id["review-1"].kind == "review"
    assert by_id["review-2"].kind == "review"
    for record in restored.records:
        if isinstance(record, UTCRecord):
            assert record.created_at.utcoffset() == timedelta(0)


def test_availability_and_usage_never_collapse() -> None:
    adapter = TypeAdapter(Available[tuple[str, ...]])
    examples = [
        '{"availability":"available","data":[],"reason":null}',
        '{"availability":"incomplete","data":[],"reason":"capture truncated"}',
        '{"availability":"unavailable","data":null,"reason":"unsupported"}',
    ]
    records = [adapter.validate_json(example) for example in examples]
    assert len({record.availability for record in records}) == 3
    assert records[0].data == records[1].data == ()
    assert records[2].data is None
    for record in records:
        assert adapter.validate_json(record.model_dump_json()) == record
    usage = TypeAdapter(Available[Usage])
    unknown = usage.validate_json(examples[2])
    zero = usage.validate_json(
        '{"availability":"available","data":{"input_tokens":0,"output_tokens":0,'
        '"requests":0,"cost":0,"currency":"USD"},"reason":null}'
    )
    assert unknown.availability == Availability.UNAVAILABLE
    assert unknown.data is None
    assert zero.data is not None and zero.data.input_tokens == 0
    assert usage.validate_json(unknown.model_dump_json()) != usage.validate_json(
        zero.model_dump_json()
    )


@pytest.mark.parametrize(
    "data",
    [
        '{"availability":"unavailable","data":[],"reason":"unknown"}',
        '{"availability":"available","data":null}',
        '{"availability":"incomplete","data":[]}',
    ],
)
def test_invalid_availability_is_rejected(data: str) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(Available[tuple[str, ...]]).validate_json(data)
