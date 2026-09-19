from importlib.metadata import version
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from binfocheck.text.sentences import GermanSentenceSegmenter

CASES = TypeAdapter(list[dict[str, str | list[str]]]).validate_json(
    (Path(__file__).parents[1] / "fixtures/text/v1/sentences.json").read_bytes()
)


@pytest.fixture(scope="module")
def segmenter() -> GermanSentenceSegmenter:
    return GermanSentenceSegmenter()


@pytest.mark.parametrize("case", CASES)
def test_golden_sentences(
    segmenter: GermanSentenceSegmenter, case: dict[str, str | list[str]]
) -> None:
    text = case["text"]
    assert isinstance(text, str)
    prefix = "not indexed 🍎\r\n"
    spans = segmenter.spans(prefix + text, len(prefix), len(prefix) + len(text))
    assert [(prefix + text)[a:b] for a, b in spans] == case["sentences"]
    assert all((prefix + text)[a:b] == (prefix + text)[a:b].strip() for a, b in spans)
    assert all(a >= len(prefix) and a < b for a, b in spans)
    assert spans == segmenter.spans(prefix + text, len(prefix), len(prefix) + len(text))


def test_pipeline_has_no_model(segmenter: GermanSentenceSegmenter) -> None:
    assert version("spacy") == "3.8.16"
    assert segmenter.nlp.lang == "de"
    assert segmenter.nlp.pipe_names == ["sentencizer"]
    assert segmenter.nlp(" \tÄ🍎\r\n").text == " \tÄ🍎\r\n"
