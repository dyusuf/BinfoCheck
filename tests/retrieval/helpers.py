from collections.abc import Sequence

from binfocheck.corpus.artifacts import Store as CorpusStore
from binfocheck.corpus.config import URLS
from binfocheck.corpus.ingestion import StoredCorpusIngestor
from binfocheck.corpus.transport import Response
from binfocheck.domain.interfaces import IngestionResult, RetrievalRequest
from binfocheck.domain.runs import RunManifest
from binfocheck.retrieval import HybridClaimRetriever, request_settings
from binfocheck.retrieval.config import EmbeddingSpec
from tests.contracts.helpers import linked
from tests.corpus.helpers import Transport, capture, request
from tests.storage.helpers import Store, fixture_payloads, success


class SyntheticEmbedder:
    spec = EmbeddingSpec(
        model="synthetic-routing",
        revision="fixture-1",
        dimensions=3,
        max_tokens=32768,
        implementation="synthetic",
        software={"fixture": "1"},
    )

    def __init__(self) -> None:
        self.counted: list[str] = []
        self.encoded: list[list[str]] = []

    def count_tokens(self, text: str) -> int:
        self.counted.append(text)
        return len(text.split()) + 2

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        self.encoded.append(list(texts))
        return [[1.0, float(len(t) % 7), 0.5] for t in texts]


def setup(store: Store, count: int = 3) -> IngestionResult:
    html = (
        '<html lang="de"><body><article><h1>Äpfel und Gesundheit</h1>'
        "<h2>Abschnitt A</h2>"
        + "".join(
            f"<p>Äpfel sind nicht rot. Wert {i}: 3,5 mmol/l und 70 mg/dl.</p>" for i in range(count)
        )
        + "<h2>Abschnitt B</h2><p>Kein Zusatz. Nur 5 %.</p></article></body></html>"
    ).encode()
    transport = Transport(
        {url: Response(200, (("content-type", "text/html; charset=utf-8"),), html) for url in URLS}
    )
    batch = capture(CorpusStore(store, store), transport=transport)
    corpus = success(StoredCorpusIngestor(store, store).ingest(request(batch)))
    assert corpus.manifest.status == "ready"
    for artifact in fixture_payloads():
        success(store.put_artifact(artifact))
    for record in linked().records:
        if isinstance(record, RunManifest):
            record = record.model_copy(update={"corpus_manifest_id": corpus.manifest.id})
        success(store.put_record(record))
    return corpus


def prepared(
    store: Store, count: int = 3
) -> tuple[HybridClaimRetriever, RetrievalRequest, SyntheticEmbedder]:
    corpus = setup(store, count)
    retriever = HybridClaimRetriever(store, store)
    embedder = SyntheticEmbedder()
    index = success(retriever.prepare_index(corpus.manifest.id, embedder))
    query = success(retriever.prepare_query(index, "run-1", "claim-1", embedder))
    return (
        retriever,
        RetrievalRequest(
            analysis_run_id="run-1",
            claim_id="claim-1",
            index=index,
            settings=request_settings(query.id),
        ),
        embedder,
    )
