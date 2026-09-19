"""Natural blocks; no token windows, embeddings, lexical processing or retrieval."""

from datetime import datetime

from binfocheck.domain.corpus import Passage
from binfocheck.domain.text import SpanRef

from .config import PASSAGES_VERSION, identity
from .structure import Structure


def construct(text: str, structure: Structure, created_at: datetime) -> tuple[Passage, ...]:
    passages: list[Passage] = []
    blocks = structure.blocks
    i = 0
    while i < len(blocks):
        block = blocks[i]
        i += 1
        if block.kind == "heading":
            continue
        start, end = block.span.start, block.span.end
        if (
            block.kind == "paragraph"
            and block.span.exact_text.endswith(":")
            and i < len(blocks)
            and blocks[i].kind == "list"
            and blocks[i].heading_indices == block.heading_indices
        ):
            end = blocks[i].span.end
            i += 1
        passages.append(
            Passage(
                id=identity(
                    "passage",
                    [
                        structure.article_id,
                        PASSAGES_VERSION.model_dump(mode="json"),
                        len(passages),
                        start,
                        end,
                    ],
                ),
                created_at=created_at,
                article_version_id=structure.article_id,
                order=len(passages),
                span=SpanRef(
                    text_id=structure.cleaned_text_id,
                    start=start,
                    end=end,
                    exact_text=text[start:end],
                ),
                heading_spans=tuple(structure.headings[h].span for h in block.heading_indices),
                construction_version=PASSAGES_VERSION,
            )
        )
    return tuple(passages)
