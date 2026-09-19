from datetime import UTC, datetime
from pathlib import Path

from binfocheck.corpus.artifacts import Store
from binfocheck.corpus.capture import SnapshotCapture
from binfocheck.corpus.config import ROBOTS, URLS, ReplaySettings
from binfocheck.corpus.errors import require
from binfocheck.corpus.receipts import Batch
from binfocheck.corpus.transport import Response
from binfocheck.domain.interfaces import IngestionRequest

FIXTURES = Path(__file__).parents[1] / "fixtures" / "corpus" / "v1"
NOW = datetime(2026, 9, 19, 12, tzinfo=UTC)
HTML = (FIXTURES / "article.html").read_bytes()


class FakeClock:
    value = 0.0

    def clock(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class Transport:
    def __init__(self, overrides: dict[str, Response] | None = None) -> None:
        self.responses = {
            ROBOTS: Response(200, (), b"User-agent: *\nAllow: /\n"),
            **{
                url: Response(200, (("content-type", "text/html; charset=utf-8"),), HTML)
                for url in URLS
            },
            **(overrides or {}),
        }
        self.calls: list[str] = []

    def get(self, url: str, max_bytes: int) -> Response:
        self.calls.append(url)
        return self.responses[url]


def capture(store: Store, id: str = "batch-test", transport: Transport | None = None) -> Batch:
    clock = FakeClock()
    return require(
        SnapshotCapture(
            store, transport or Transport(), clock=clock.clock, sleep=clock.sleep, now=lambda: NOW
        ).capture(id, "synthetic")
    )


def request(batch: Batch, **kwargs: object) -> IngestionRequest:
    settings = ReplaySettings.model_validate({"batch_artifact_id": batch.id, **kwargs})
    return IngestionRequest(urls=URLS, settings=settings.envelope())
