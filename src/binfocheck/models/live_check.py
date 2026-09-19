"""Explicit T03 smoke preparation/execution. Default is offline preparation only.

    uv run --offline --locked python -m binfocheck.models.live_check --provider jev

Execution additionally requires --execute, --store and a reviewed --authorization
file. Creating such a file does not supply user authorization by itself.
"""

import argparse
import base64
from pathlib import Path
from typing import Protocol

from binfocheck.domain.common import ProcessingStatus
from binfocheck.domain.interfaces import DecisionRequest, GenerationRequest
from binfocheck.domain.runs import RunManifest
from binfocheck.domain.storage import ArtifactPayload, ArtifactStore, RecordStore
from binfocheck.domain.text import ArtifactRef
from binfocheck.storage import MemoryStore, SQLiteStore

from .config import (
    CONFIG_VERSION,
    LiveAuthorization,
    ModelAdapterConfig,
    ModelCredentials,
    Provider,
)
from .errors import ModelError, require
from .json import canonical, digest
from .persistence import prepare
from .receipt import PreparedRequest
from .resources import ResourceRegistry


class SmokeStore(RecordStore, ArtifactStore, Protocol):
    pass


def prepare_smoke(
    store: SmokeStore,
    fixtures: Path,
    provider: Provider,
) -> tuple[PreparedRequest, ResourceRegistry]:
    # Paths are operator-owned local fixture paths, never provider output.
    request_type = DecisionRequest if provider == "jev" else GenerationRequest
    request = request_type.model_validate_json(
        (fixtures / provider / "smoke-domain-request.json").read_bytes()
    )
    state = (fixtures / "resources/state.txt").read_bytes()
    require(
        store.put_artifact(
            ArtifactPayload(
                ref=ArtifactRef(
                    id="t03-state",
                    storage_key="synthetic/t03/state",
                    sha256=digest(state),
                    media_type="text/plain",
                    access="shareable_fixture",
                ),
                content_base64=base64.b64encode(state).decode("ascii"),
            )
        )
    )
    registry = ResourceRegistry(
        {
            ("t03-smoke-rubric", "1"): (fixtures / "resources/rubric.json").read_bytes(),
            ("t03-smoke-prompt", "1"): (fixtures / "resources/prompt.txt").read_bytes(),
            ("t03-smoke-output", "1"): (fixtures / "resources/output.schema.json").read_bytes(),
        }
    )
    config = ModelAdapterConfig(provider=provider)
    from datetime import UTC, datetime

    require(
        store.put_record(
            RunManifest(
                id=request.analysis_run_id,
                created_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
                input_ids=request.input_ids,
                observation_ids=(),
                corpus_manifest_id=None,
                purpose="diagnostic",
                mode="reanalysis",
                capture_settings=request.settings,
                configuration=CONFIG_VERSION,
                model_ids=(request.requested_model_id,),
                prompt_versions=(request.prompt_version,) if request.prompt_version else (),
                rubric_versions=(request.rubric_version,) if request.rubric_version else (),
                budget=config.budget,
                status=ProcessingStatus.PENDING,
            )
        )
    )
    prepared = prepare(request, config, registry, store)
    expected = (fixtures / provider / "smoke-request.json").read_bytes()
    if canonical(prepared.body) != expected:
        raise ModelError("smoke_payload_changed")
    return prepared, registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=("jev", "openai"))
    parser.add_argument("--fixtures", type=Path, default=Path("tests/fixtures/models"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--store", type=Path)
    parser.add_argument("--authorization", type=Path)
    args = parser.parse_args()
    provider: Provider = "jev" if args.provider == "jev" else "openai"
    fixtures = Path(args.fixtures)
    if not args.execute:
        with MemoryStore() as store:
            prepared, _ = prepare_smoke(store, fixtures, provider)
            print(
                canonical(
                    {
                        "mode": "offline-preparation",
                        "model": prepared.request.requested_model_id,
                        "work_key": prepared.work_key,
                        "record_id": prepared.record_id,
                        "request_sha256": digest(canonical(prepared.body)),
                        "body": prepared.body,
                        "proposed_cost_ceiling_usd": 0.01,
                        "live_authorized": False,
                    }
                ).decode("utf-8")
            )
        return 0
    if args.authorization is None or args.store is None:
        parser.error("execution requires an explicit authorization file and private store")
    from .decision import JevDecisionModel
    from .generation import OpenAIGenerationModel
    from .transport import FixedHttpsTransport

    authorization = LiveAuthorization.model_validate_json(Path(args.authorization).read_bytes())
    with SQLiteStore(Path(args.store)) as store:
        prepared, registry = prepare_smoke(store, fixtures, provider)
        # Credentials are loaded only after explicit execution and authorization parsing.
        transport = FixedHttpsTransport(ModelCredentials.from_environment(provider), authorization)
        adapter = (JevDecisionModel if provider == "jev" else OpenAIGenerationModel)(
            store,
            store,
            registry,
            prepared.config,
            transport,
        )
        result = adapter.execute(prepared.request)
        print(
            canonical(
                {
                    "record_id": prepared.record_id,
                    "status": result.status,
                    "error_code": result.error.code if result.error else None,
                }
            ).decode()
        )
        return 0 if result.status == "succeeded" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ModelError, ValueError, OSError):
        raise SystemExit(
            "Smoke check failed; inspect restricted records. No automatic retry."
        ) from None
