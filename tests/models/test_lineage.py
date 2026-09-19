"""Request lineage is checked locally before authorization, writes, or dispatch."""

import pytest

from binfocheck.domain.records import RecordSet
from binfocheck.domain.storage import ListRequest
from binfocheck.domain.validation import validate_links
from binfocheck.models import JevDecisionModel, OpenAIGenerationModel
from binfocheck.models.config import ModelAdapterConfig, Provider
from binfocheck.models.errors import require
from binfocheck.storage import MemoryStore
from tests.contracts.helpers import linked

from .helpers import (
    Clock,
    FakeTransport,
    decision_request,
    generation_request,
    resources,
    response,
    seed,
)


class CountingTransport(FakeTransport):
    checks = 0

    def check(self, config: ModelAdapterConfig, body: bytes, work_key: str) -> None:
        self.checks += 1


@pytest.mark.parametrize("provider", ["jev", "openai"])
@pytest.mark.parametrize(
    "case",
    [
        "missing_run",
        "wrong_kind_run",
        "missing_input",
        "cross_run_derived",
        "observation_outside_run",
        "missing_artifact",
        "wrong_kind_artifact",
        "valid",
    ],
)
def test_lineage_before_authorization_and_writes(provider: Provider, case: str) -> None:
    with MemoryStore() as store:
        request = decision_request() if provider == "jev" else generation_request()
        seed(store, request, provider)
        for record in linked().records:
            require(store.put_record(record))
        if case == "missing_run":
            request = request.model_copy(update={"analysis_run_id": "missing-run"})
        elif case == "wrong_kind_run":
            request = request.model_copy(update={"analysis_run_id": "t03-state"})
        elif case == "missing_input":
            request = request.model_copy(update={"input_ids": ("missing-input",)})
        elif case == "cross_run_derived":
            request = request.model_copy(update={"input_ids": ("decision-1",)})
        elif case == "observation_outside_run":
            request = request.model_copy(update={"input_ids": ("obs-1",)})
        elif case == "missing_artifact":
            request = request.model_copy(update={"input_artifact_ids": ("missing-artifact",)})
        elif case == "wrong_kind_artifact":
            request = request.model_copy(update={"input_artifact_ids": ("run-1",)})
        else:
            request = request.model_copy(
                update={"analysis_run_id": "run-1", "input_ids": ("obs-1", "decision-1")}
            )
        before = require(store.list_records(ListRequest(limit=1000))).records
        validate_links(RecordSet(records=before))
        transport = CountingTransport(response(provider))
        adapter = (JevDecisionModel if provider == "jev" else OpenAIGenerationModel)(
            store, store, resources(), ModelAdapterConfig(provider=provider), transport, Clock()
        )
        result = adapter.execute(request)
        after = require(store.list_records(ListRequest(limit=1000))).records
        if case == "valid":
            assert result.status == "succeeded"
            assert transport.checks == 1
            assert len(transport.calls) == 1
            validate_links(RecordSet(records=after))
            assert adapter.execute(request) == result
            assert transport.checks == 1
            assert len(transport.calls) == 1
        else:
            assert result.status == "failed" and result.value is None
            assert result.error is not None and result.error.code == "invalid_request_lineage"
            assert result.error.retryable is False
            assert transport.checks == 0
            assert transport.calls == []
            assert after == before  # No intent, response, receipt, or failed DecisionRecord.
