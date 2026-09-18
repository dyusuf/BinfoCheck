"""Fixture-only scripted doubles: no providers, algorithms, or storage backend."""

import json
from pathlib import Path

from pydantic import JsonValue

from binfocheck.domain import interfaces as api
from binfocheck.domain import storage
from binfocheck.domain.catalog import BOUNDARIES
from binfocheck.domain.claims import CitationAssociation
from binfocheck.domain.common import Contract, Outcome
from binfocheck.domain.decisions import DecisionRecord
from binfocheck.domain.evidence import AlternativeInspection, Finding
from binfocheck.domain.observations import CaptureRequest, Observation, TextUnit
from binfocheck.domain.records import Record
from binfocheck.domain.runs import Review
from binfocheck.domain.text import ArtifactRef


class Exchange(Contract):
    request: dict[str, JsonValue]
    response: dict[str, JsonValue]


class ScriptedDouble:
    def __init__(self, name: str, fixture: Path) -> None:
        self.name = name
        self.exchange = Exchange.model_validate_json(fixture.read_bytes())
        self.calls: list[str] = []

    def reply[T: Contract](self, name: str, request: Contract, response: type[T]) -> T:
        if name != self.name:
            raise AssertionError(f"Unexpected method: {name}")
        expected = BOUNDARIES[name].request.validate_json(json.dumps(self.exchange.request))
        if request != expected:
            raise AssertionError("Request differs from fixture")
        self.calls.append(name)
        return response.model_validate_json(json.dumps(self.exchange.response))


class ComponentDouble(ScriptedDouble):
    def capture(self, request: CaptureRequest) -> Outcome[Observation]:
        return self.reply("capture", request, Outcome[Observation])

    def index_answer(self, request: api.IndexRequest) -> Outcome[tuple[TextUnit, ...]]:
        return self.reply("index_answer", request, Outcome[tuple[TextUnit, ...]])

    def build_context(self, request: api.ContextRequest) -> Outcome[api.ContextResult]:
        return self.reply("build_context", request, Outcome[api.ContextResult])

    def extract_claims(self, request: api.ExtractionRequest) -> Outcome[api.ExtractionResult]:
        return self.reply("extract_claims", request, Outcome[api.ExtractionResult])

    def map_citations(self, request: api.ClaimRequest) -> Outcome[CitationAssociation]:
        return self.reply("map_citations", request, Outcome[CitationAssociation])

    def ingest(self, request: api.IngestionRequest) -> Outcome[api.IngestionResult]:
        return self.reply("ingest", request, Outcome[api.IngestionResult])

    def retrieve(self, request: api.RetrievalRequest) -> Outcome[api.RetrievalResult]:
        return self.reply("retrieve", request, Outcome[api.RetrievalResult])

    def expand_context(self, request: api.PairRequest) -> Outcome[api.ExpandedContext]:
        return self.reply("expand_context", request, Outcome[api.ExpandedContext])

    def decide(self, request: api.DecisionRequest) -> Outcome[DecisionRecord]:
        return self.reply("decide", request, Outcome[DecisionRecord])

    def generate(self, request: api.GenerationRequest) -> Outcome[DecisionRecord]:
        return self.reply("generate", request, Outcome[DecisionRecord])

    def verify_candidate(self, request: api.PairRequest) -> Outcome[DecisionRecord]:
        return self.reply("verify_candidate", request, Outcome[DecisionRecord])

    def judge_correspondence(self, request: api.PairRequest) -> Outcome[DecisionRecord]:
        return self.reply("judge_correspondence", request, Outcome[DecisionRecord])

    def inspect_alternatives(
        self, request: api.ClaimRequest
    ) -> Outcome[tuple[AlternativeInspection, ...]]:
        return self.reply(
            "inspect_alternatives", request, Outcome[tuple[AlternativeInspection, ...]]
        )

    def classify(self, request: api.ClassificationRequest) -> Outcome[Finding]:
        return self.reply("classify", request, Outcome[Finding])


class StorageDouble(ScriptedDouble):
    def put_artifact(self, request: storage.ArtifactPayload) -> Outcome[ArtifactRef]:
        return self.reply("put_artifact", request, Outcome[ArtifactRef])

    def get_artifact(self, request: storage.IdRequest) -> Outcome[storage.ArtifactPayload]:
        return self.reply("get_artifact", request, Outcome[storage.ArtifactPayload])

    def put_record(self, request: Record) -> Outcome[Record]:
        return self.reply("put_record", request, Outcome[Record])

    def get_record(self, request: storage.IdRequest) -> Outcome[Record]:
        return self.reply("get_record", request, Outcome[Record])

    def list_records(self, request: storage.ListRequest) -> Outcome[storage.RecordPage]:
        return self.reply("list_records", request, Outcome[storage.RecordPage])

    def append_decision(self, request: DecisionRecord) -> Outcome[DecisionRecord]:
        return self.reply("append_decision", request, Outcome[DecisionRecord])

    def append_review(self, request: Review) -> Outcome[Review]:
        return self.reply("append_review", request, Outcome[Review])
