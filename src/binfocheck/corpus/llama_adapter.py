"""Only explicit model-free ingestion transformations; T11A remains authoritative."""

from collections.abc import Sequence
from typing import Any

from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.schema import (
    BaseNode,
    Document,
    NodeRelationship,
    RelatedNodeInfo,
    TextNode,
    TransformComponent,
)

from binfocheck.domain.corpus import Passage
from binfocheck.domain.text import TextRecord

from .errors import check


class ExactPassages(TransformComponent):
    passages: tuple[Passage, ...]
    text_id: str

    def __call__(self, nodes: Sequence[BaseNode], **kwargs: Any) -> Sequence[BaseNode]:
        check(len(nodes) == 1 and isinstance(nodes[0], Document), "invalid_ingestion_document")
        document = nodes[0]
        assert isinstance(document, Document)
        check(document.id_ == self.text_id, "invalid_ingestion_document")
        result: list[BaseNode] = []
        for passage in self.passages:
            span = passage.span
            check(
                span.text_id == self.text_id
                and document.text[span.start : span.end] == span.exact_text,
                "node_span_mismatch",
            )
            result.append(
                TextNode(
                    id_=passage.id,
                    text=span.exact_text,
                    start_char_idx=span.start,
                    end_char_idx=span.end,
                    embedding=None,
                    relationships={NodeRelationship.SOURCE: RelatedNodeInfo(node_id=document.id_)},
                )
            )
        return result


def verify_nodes(text: TextRecord, passages: tuple[Passage, ...]) -> None:
    pipeline = IngestionPipeline(
        transformations=[ExactPassages(passages=passages, text_id=text.id)],
        vector_store=None,
        docstore=None,
        disable_cache=True,
    )
    nodes = pipeline.run(documents=[Document(id_=text.id, text=text.text)], num_workers=1)
    check(len(nodes) == len(passages), "node_count_mismatch")
    for node, passage in zip(nodes, passages, strict=True):
        check(isinstance(node, TextNode), "unexpected_node_type")
        assert isinstance(node, TextNode)
        check(
            node.id_ == passage.id
            and node.text == passage.span.exact_text
            and node.start_char_idx == passage.span.start
            and node.end_char_idx == passage.span.end
            and node.embedding is None
            and node.source_node is not None
            and node.source_node.node_id == text.id,
            "node_roundtrip_mismatch",
        )
