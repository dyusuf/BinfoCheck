"""Pure stored-snapshot replay into shared domain records and immutable companions."""

from typing import Literal

from binfocheck.domain.common import Contract
from binfocheck.domain.corpus import ArticleVersion, CorpusManifest, Passage
from binfocheck.domain.interfaces import IngestionRequest, IngestionResult
from binfocheck.domain.records import Record, RecordSet
from binfocheck.domain.storage import ArtifactStore, IdRequest, RecordStore
from binfocheck.domain.text import ArtifactRef, TextRecord
from binfocheck.domain.validation import validate_links

from .artifacts import Store
from .capture import load_capture_start
from .config import (
    PASSAGES_VERSION,
    SETTINGS_VERSION,
    URLS,
    ParserConfig,
    ReplaySettings,
    canonical,
    digest,
    identity,
    verify_packages,
)
from .decoding import decode_html
from .errors import CorpusError, boundary, check, require
from .llama_adapter import verify_nodes
from .parsing import parse_html
from .passages import construct
from .receipts import Batch, Receipt
from .structure import Structure


class Member(Contract):
    id: str
    sha256: str


class Completion(Contract):
    format: Literal["t06-completion/1"] = "t06-completion/1"
    status: Literal["complete"] = "complete"
    settings: ReplaySettings
    manifest: CorpusManifest
    records: tuple[Member, ...]
    artifact_ids: tuple[str, ...]


def record_hash(record: Record) -> str:
    return digest(canonical(record.model_dump(mode="json")))


def article_identity(receipt: Receipt, parser: ParserConfig, previous: str | None) -> str:
    return identity("article", [receipt.id, parser.version().model_dump(mode="json"), previous])


class StoredCorpusIngestor:
    def __init__(self, records: RecordStore, artifacts: ArtifactStore) -> None:
        self.store = Store(records, artifacts)

    @boundary
    def ingest(self, request: IngestionRequest) -> IngestionResult:
        verify_packages()
        check(
            request.urls == URLS and request.settings.version == SETTINGS_VERSION,
            "invalid_corpus_request",
        )
        settings = ReplaySettings.model_validate_json(canonical(request.settings.values))
        check(len(settings.previous_version_ids) == 5, "invalid_previous_versions")
        batch = self.store.load(settings.batch_artifact_id, Batch)
        check(
            batch.id == settings.batch_artifact_id
            and batch.urls == URLS
            and len(batch.receipt_ids) == 5
            and len(set(batch.receipt_ids)) == 5,
            "invalid_capture_batch",
        )
        articles: list[ArticleVersion] = []
        passages: list[Passage] = []
        # The graph tracks exactly this publication's dependencies, not all records in the store.
        graph: dict[str, Record] = {}
        artifact_ids: set[str] = set()

        def artifact(id: str) -> None:
            self.store.bytes(id)
            graph[id] = self.store.record(id, ArtifactRef)
            artifact_ids.add(id)

        def save(record: Record) -> None:
            self.store.put(record)
            graph[record.id] = record

        def previous_graph(id: str, url: str, seen: set[str]) -> None:
            check(id not in seen, "article_history_cycle")
            seen.add(id)
            old = self.store.record(id, ArticleVersion)
            check(old.url == url, "previous_article_url_mismatch")
            graph[id] = old
            if old.raw_artifact_id:
                artifact(old.raw_artifact_id)
            for text_id in (old.raw_text_id, old.cleaned_text_id):
                if text_id:
                    text = self.store.record(text_id, TextRecord)
                    graph[text.id] = text
                    artifact(text.artifact_id)
            if old.previous_version_id:
                previous_graph(old.previous_version_id, url, seen)

        artifact(batch.id)
        artifact(batch.id + ".start.v1")
        start = load_capture_start(self.store, batch)
        if start.authorization_artifact_id:
            artifact(start.authorization_artifact_id)
        if batch.robots_receipt_id:
            artifact(batch.robots_receipt_id)
            robots = self.store.load(batch.robots_receipt_id, Receipt)
            check(robots.batch_id == batch.id, "receipt_batch_mismatch")
            for id in (
                robots.body_artifact_id,
                robots.encoded_artifact_id,
                robots.partial_artifact_id,
            ):
                if id:
                    artifact(id)
        for index, (url, receipt_id, previous) in enumerate(
            zip(URLS, batch.receipt_ids, settings.previous_version_ids, strict=True), start=1
        ):
            receipt = self.store.load(receipt_id, Receipt)
            check(
                receipt.id == receipt_id
                and receipt.batch_id == batch.id
                and receipt.url == url
                and receipt.ordinal == index,
                "receipt_batch_mismatch",
            )
            artifact(receipt_id)
            if previous:
                previous_graph(previous, url, set())
            for id in (
                receipt.body_artifact_id,
                receipt.encoded_artifact_id,
                receipt.partial_artifact_id,
            ):
                if id:
                    artifact(id)
            article_id = article_identity(receipt, settings.parser, previous)
            raw_text: TextRecord | None = None
            cleaned: TextRecord | None = None
            structure: Structure | None = None
            raw_bytes = (
                self.store.bytes(receipt.body_artifact_id) if receipt.body_artifact_id else None
            )
            media = receipt.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            raw_html_id = receipt.body_artifact_id if media == "text/html" else None
            status: Literal["usable", "failed", "unusable"] = "failed"
            reason: str | None = receipt.error or "http_failure"
            if (
                receipt.complete
                and receipt.error is None
                and receipt.status == 200
                and raw_bytes is not None
            ):
                status = "unusable"
                try:
                    check(media == "text/html", "not_html")
                    html, encoding = decode_html(raw_bytes, receipt.headers.get("content-type", ""))
                    raw_text = TextRecord(
                        id=identity("raw-text", [receipt.body_artifact_id, encoding, "charset/1"]),
                        text=html,
                        artifact_id=receipt.body_artifact_id or "missing",
                    )
                    text, structure = parse_html(
                        html, url, article_id, receipt.id, raw_text.id, encoding, settings.parser
                    )
                    cleaned = TextRecord(
                        id=structure.cleaned_text_id,
                        text=text,
                        artifact_id=identity("clean-text", digest(text.encode())),
                        source_text_id=raw_text.id,
                        transformation=settings.parser.version(),
                    )
                    status, reason = "usable", None
                except CorpusError as failure:
                    reason = failure.detail.code
            if raw_text:
                save(raw_text)
            if cleaned:
                cleaned_ref = self.store.blob(
                    cleaned.text.encode(), "clean-text", "text/plain; charset=utf-8"
                )
                artifact(cleaned_ref.id)
                save(cleaned)
            article = ArticleVersion(
                id=article_id,
                created_at=receipt.created_at,
                url=url,
                raw_artifact_id=raw_html_id,
                raw_text_id=raw_text.id if raw_text else None,
                cleaned_text_id=cleaned.id if cleaned else None,
                title=structure.title if structure else None,
                heading_spans=tuple(h.span for h in structure.headings) if structure else (),
                fetched_at=receipt.finished_at if receipt.complete else None,
                content_sha256=digest(raw_bytes) if raw_bytes is not None and raw_html_id else None,
                parser_version=settings.parser.version(),
                status=status,
                reason=reason,
                previous_version_id=previous,
            )
            save(article)
            articles.append(article)
            if structure and cleaned and status == "usable":
                structure_id = article.id + ".structure.v1"
                self.store.json(structure, "structure", structure_id)
                artifact(structure_id)
                created = construct(cleaned.text, structure, article.created_at)
                check(bool(created), "article_without_passages")
                verify_nodes(cleaned, created)
                for passage in created:
                    save(passage)
                passages.extend(created)
        usable = sum(a.status == "usable" for a in articles)
        manifest_status: Literal["ready", "incomplete", "failed"] = (
            "ready" if usable == 5 else "incomplete" if usable else "failed"
        )
        manifest = CorpusManifest(
            id=identity(
                "manifest",
                [
                    batch.id,
                    [a.id for a in articles],
                    [p.id for p in passages],
                    PASSAGES_VERSION.model_dump(mode="json"),
                    manifest_status,
                ],
            ),
            created_at=batch.created_at,
            article_version_ids=tuple(a.id for a in articles),
            passage_ids=tuple(p.id for p in passages),
            construction_version=PASSAGES_VERSION,
            status=manifest_status,
            reason=None if usable == 5 else "pilot_pages_not_usable",
        )
        graph[manifest.id] = manifest
        validate_links(RecordSet(records=tuple(graph.values())))
        result = IngestionResult(
            articles=tuple(articles), passages=tuple(passages), manifest=manifest
        )
        self._validate_result(result, settings)
        # Read back all dependencies before the completion marker. Manifest is written last.
        for record in graph.values():
            if record.id != manifest.id:
                check(
                    self.store.record(record.id, type(record)) == record, "record_readback_mismatch"
                )
        completion = Completion(
            settings=settings,
            manifest=manifest,
            records=tuple(
                Member(id=r.id, sha256=record_hash(r))
                for r in graph.values()
                if r.id != manifest.id
            ),
            artifact_ids=tuple(sorted(artifact_ids)),
        )
        self.store.json(completion, "completion", manifest.id + ".completion.v1")
        self.store.put(manifest)
        return self._load(manifest.id)

    def _validate_result(self, result: IngestionResult, settings: ReplaySettings) -> None:
        check(tuple(a.url for a in result.articles) == URLS, "corpus_url_membership")
        check(
            tuple(a.id for a in result.articles) == result.manifest.article_version_ids
            and tuple(p.id for p in result.passages) == result.manifest.passage_ids,
            "corpus_member_mismatch",
        )
        check(
            len(set(result.manifest.passage_ids)) == len(result.manifest.passage_ids),
            "duplicate_passage",
        )
        usable = sum(a.status == "usable" for a in result.articles)
        expected = "ready" if usable == 5 else "incomplete" if usable else "failed"
        check(result.manifest.status == expected, "invalid_readiness")
        batch = self.store.load(settings.batch_artifact_id, Batch)
        load_capture_start(self.store, batch)
        check(
            batch.id == settings.batch_artifact_id
            and batch.urls == URLS
            and len(batch.receipt_ids) == 5
            and len(settings.previous_version_ids) == 5,
            "invalid_capture_batch",
        )
        check(
            result.manifest.construction_version == PASSAGES_VERSION
            and result.manifest.created_at == batch.created_at
            and result.manifest.id
            == identity(
                "manifest",
                [
                    batch.id,
                    list(result.manifest.article_version_ids),
                    list(result.manifest.passage_ids),
                    PASSAGES_VERSION.model_dump(mode="json"),
                    expected,
                ],
            ),
            "manifest_identity_mismatch",
        )
        receipt_set = tuple(self.store.load(id, Receipt) for id in batch.receipt_ids)
        robots = (
            self.store.load(batch.robots_receipt_id, Receipt) if batch.robots_receipt_id else None
        )
        check(
            robots is not None and robots.batch_id == batch.id and robots.ordinal == 0,
            "missing_robots_receipt",
        )
        assert robots is not None
        check(
            batch.requests_dispatched == sum(r.dispatched for r in (*receipt_set, robots)),
            "capture_request_count_mismatch",
        )
        for ordinal, (article, receipt_id, previous) in enumerate(
            zip(result.articles, batch.receipt_ids, settings.previous_version_ids, strict=True),
            start=1,
        ):
            receipt = self.store.load(receipt_id, Receipt)
            media = receipt.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            expected_raw = receipt.body_artifact_id if media == "text/html" else None
            check(
                receipt.id == receipt_id
                and receipt.batch_id == batch.id
                and receipt.url == article.url
                and receipt.ordinal == ordinal
                and article.id == article_identity(receipt, settings.parser, previous)
                and article.previous_version_id == previous
                and article.raw_artifact_id == expected_raw
                and article.created_at == receipt.created_at
                and article.fetched_at == (receipt.finished_at if receipt.complete else None),
                "article_receipt_mismatch",
            )
            acquired = receipt.complete and receipt.status == 200 and receipt.error is None
            check((article.status != "failed") == acquired, "article_capture_status_mismatch")
            seen = {article.id}
            prior = previous
            while prior:
                check(prior not in seen, "article_history_cycle")
                seen.add(prior)
                predecessor = self.store.record(prior, ArticleVersion)
                check(predecessor.url == article.url, "previous_article_url_mismatch")
                prior = predecessor.previous_version_id
            members = tuple(p for p in result.passages if p.article_version_id == article.id)
            if article.raw_artifact_id:
                check(
                    article.content_sha256 == digest(self.store.bytes(article.raw_artifact_id)),
                    "raw_html_hash_mismatch",
                )
            if article.status != "usable":
                check(not members, "unusable_article_passages")
                continue
            check(bool(members) and article.cleaned_text_id is not None, "article_without_passages")
            assert article.cleaned_text_id is not None
            cleaned = self.store.record(article.cleaned_text_id, TextRecord)
            check(
                self.store.bytes(cleaned.artifact_id) == cleaned.text.encode(),
                "cleaned_bytes_mismatch",
            )
            structure = self.store.load(article.id + ".structure.v1", Structure)
            check(structure.receipt_id == receipt.id, "structure_receipt_mismatch")
            check(
                structure.article_id == article.id
                and structure.cleaned_text_id == cleaned.id
                and structure.raw_text_id == article.raw_text_id
                and structure.cleaned_sha256 == digest(cleaned.text.encode())
                and structure.parser_version == article.parser_version == settings.parser.version(),
                "structure_identity_mismatch",
            )
            assert article.raw_text_id is not None and article.raw_artifact_id is not None
            raw = self.store.record(article.raw_text_id, TextRecord)
            html, encoding = decode_html(
                self.store.bytes(article.raw_artifact_id), receipt.headers.get("content-type", "")
            )
            check(raw.text == html and encoding == structure.charset, "raw_text_bytes_mismatch")
            # Recompute metadata and spans from saved raw HTML; no trust in companion offsets.
            text, rebuilt = parse_html(
                html, article.url, article.id, receipt.id, raw.id, encoding, settings.parser
            )
            check(text == cleaned.text and rebuilt == structure, "structure_replay_mismatch")
            check(
                construct(cleaned.text, structure, article.created_at) == members,
                "passage_replay_mismatch",
            )

    @boundary
    def load(self, manifest_id: str) -> IngestionResult:
        return self._load(manifest_id)

    def _load(self, manifest_id: str) -> IngestionResult:
        verify_packages()
        manifest = self.store.record(manifest_id, CorpusManifest)
        completion = self.store.load(manifest_id + ".completion.v1", Completion)
        check(completion.manifest == manifest, "completion_manifest_mismatch")
        graph: list[Record] = [manifest]
        for member in completion.records:
            record = require(self.store.records.get_record(IdRequest(id=member.id)))
            check(record_hash(record) == member.sha256, "completion_record_mismatch")
            graph.append(record)
        for id in completion.artifact_ids:
            self.store.bytes(id)
        validate_links(RecordSet(records=tuple(graph)))
        result = IngestionResult(
            articles=tuple(
                self.store.record(id, ArticleVersion) for id in manifest.article_version_ids
            ),
            passages=tuple(self.store.record(id, Passage) for id in manifest.passage_ids),
            manifest=manifest,
        )
        self._validate_result(result, completion.settings)
        return result
