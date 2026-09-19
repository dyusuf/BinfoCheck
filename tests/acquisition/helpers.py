import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import JsonValue

from binfocheck.acquisition.config import CapturePolicy, CaptureSettings
from binfocheck.acquisition.normalize import object_value, parse
from binfocheck.acquisition.transport import HttpResponse
from binfocheck.domain.common import Settings, VersionRef
from binfocheck.domain.observations import CaptureRequest
from binfocheck.domain.storage import ArtifactStore, RecordStore

AT = datetime(2026, 9, 19, 12, tzinfo=UTC)
FIXTURE = Path(__file__).parents[1] / "fixtures/acquisition/dataforseo/success.json"


class Store(RecordStore, ArtifactStore, Protocol):
    def close(self) -> None: ...


def request(record_id: str = "request-1") -> CaptureRequest:
    return CaptureRequest(
        id=record_id,
        created_at=AT,
        query_id="query-1",
        query="Welche Farbe haben die Äpfel?",
        product="google_ai_mode",
        provider="dataforseo",
        requested_settings=Settings(
            version=VersionRef(name="dataforseo-ai-mode-settings", version="1"),
            values=CaptureSettings().model_dump(mode="json"),
        ),
    )


def fixture() -> dict[str, JsonValue]:
    return parse(FIXTURE.read_bytes())


def task(data: dict[str, JsonValue]) -> dict[str, JsonValue]:
    tasks = data["tasks"]
    assert isinstance(tasks, list)
    return object_value(tasks[0])


def result(data: dict[str, JsonValue]) -> dict[str, JsonValue]:
    results = task(data)["result"]
    assert isinstance(results, list)
    return object_value(results[0])


def overview(data: dict[str, JsonValue]) -> dict[str, JsonValue]:
    items = result(data)["items"]
    assert isinstance(items, list)
    return object_value(items[0])


def response(data: dict[str, JsonValue] | None = None, status: int = 200) -> HttpResponse:
    return HttpResponse(
        payload=FIXTURE.read_bytes()
        if data is None
        else json.dumps(data, ensure_ascii=False).encode(),
        status=status,
        headers=(
            ("Content-Type", "application/json"),
            ("X-Request-ID", "synthetic-http-id"),
            ("Set-Cookie", "synthetic-secret-cookie"),
        ),
    )


class FakeTransport:
    def __init__(self, value: HttpResponse | Exception) -> None:
        self.value = value
        self.calls: list[bytes] = []

    def post(self, body: bytes, policy: CapturePolicy) -> HttpResponse:
        self.calls.append(body)
        if isinstance(self.value, Exception):
            raise self.value
        return self.value
