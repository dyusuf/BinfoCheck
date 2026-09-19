import codecs

import pytest

from binfocheck.corpus.config import URLS, ParserConfig
from binfocheck.corpus.decoding import decode_html
from binfocheck.corpus.errors import CorpusError
from binfocheck.corpus.parsing import parse_html
from binfocheck.corpus.passages import construct

from .helpers import FIXTURES, HTML, NOW


def parse(html: str, config: ParserConfig | None = None):
    return parse_html(
        html, URLS[0], "article-test", "receipt-test", "raw-test", "utf-8", config or ParserConfig()
    )


def test_full_expected_text_and_structure() -> None:
    text, structure = parse(HTML.decode())
    assert text == (FIXTURES / "article.txt").read_text().removesuffix("\n")
    assert [h.level for h in structure.headings] == [1, 2, 3, 2, 2]
    assert [h.parent_index for h in structure.headings] == [None, 0, 1, 0, 0]
    assert [i.marker for i in structure.list_items] == ["3.", "-", "7."]
    assert [i.depth for i in structure.list_items] == [0, 1, 0]
    assert len(structure.links) == 4
    assert structure.links[0].resolved == "https://www.diabinfo.de/quelle.html"
    assert structure.links[1].resolved == "https://example.org/a.pdf"
    assert not structure.links[-1].navigable
    assert all(link.span and link.span.exact_text in {"Beleg", "inert"} for link in structure.links)
    assert {e.rule for e in structure.exclusions} == {"nav", ".consent", ".share-tools", "script"}
    for block in structure.blocks:
        assert text[block.span.start : block.span.end] == block.span.exact_text
    for heading in structure.headings:
        assert heading.section_end > heading.span.start
    passages = construct(text, structure, NOW)
    assert len(passages) == 7
    assert any(
        p.span.exact_text == "Beispiele:\n\n3. Erster Beleg\n7. Zweiter\n  - Unterpunkt"
        for p in passages
    )
    assert all(text[p.span.start : p.span.end] == p.span.exact_text for p in passages)
    assert all(p.span.source_unit_id is None for p in passages)
    assert parse(HTML.decode()) == (text, structure)


def test_repeated_paragraphs_and_codepoints() -> None:
    text, structure = parse(
        "<article><h1>Test</h1><p>Äpfel 🍎 sind rot.</p><p>Äpfel 🍎 sind rot.</p></article>"
    )
    passages = construct(text, structure, NOW)
    assert passages[0].id != passages[1].id
    assert passages[0].span.exact_text == passages[1].span.exact_text
    assert passages[0].span.exact_text[8:17] == "sind rot."
    assert passages[1].span.start > passages[0].span.end


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ("<main><p>X</p></main>", "ambiguous_article_root"),
        ("<article><h1>A</h1></article><article><p>B</p></article>", "ambiguous_article_root"),
        ("<article><h1>A</h1></article>", "empty_article"),
        ("<article><p>A</p></article>", "missing_or_ambiguous_title"),
        (
            "<article><h1>A</h1><table><tr><td>B</td></tr></table></article>",
            "unsupported_article_structure",
        ),
        ("<article><h1>A</h1>unwrapped</article>", "unwrapped_article_text"),
        (
            '<article><h1>A</h1><nav><p class="references">Keep</p></nav><p>B</p></article>',
            "chrome_contains_article_reference",
        ),
        ('<html lang="en"><article><h1>A</h1><p>B</p></article></html>', "non_german_page"),
    ],
)
def test_unusable_not_lossy_fallback(body: str, code: str) -> None:
    with pytest.raises(CorpusError, match=code.replace("_", " ")):
        parse(body)


@pytest.mark.parametrize(
    "config",
    [
        ParserConfig(max_characters=5),
        ParserConfig(max_blocks=1),
        ParserConfig(max_nodes=2),
        ParserConfig(max_depth=2),
    ],
)
def test_resource_limits(config: ParserConfig) -> None:
    with pytest.raises(CorpusError):
        parse(HTML.decode(), config)


def test_preformatted_entities_links_and_unsafe_base() -> None:
    text, structure = parse(
        '<base href="https://evil.example/"><article><h1>A</h1>'
        '<pre> a\n  b &amp; c </pre><p><a href="/x"></a>Text</p></article>'
    )
    assert " a\n  b & c " in text
    assert structure.base_href == "https://evil.example/"
    assert structure.links[0].span is None
    assert structure.links[0].resolved == "https://www.diabinfo.de/x"


@pytest.mark.parametrize(
    ("body", "header", "encoding", "expected"),
    [
        (b"<p>ABC</p>\r\n", "text/html", "utf-8", "<p>ABC</p>\r\n"),
        ("<p>Ä</p>".encode("cp1252"), "text/html; charset=windows-1252", "cp1252", "<p>Ä</p>"),
        (
            b'<meta charset="iso-8859-1"><p>\xc4</p>',
            "text/html",
            "iso8859-1",
            '<meta charset="iso-8859-1"><p>Ä</p>',
        ),
        (codecs.BOM_UTF8 + b"A", "text/html; charset=utf-8", "utf-8", "\ufeffA"),
    ],
)
def test_decoding(body: bytes, header: str, encoding: str, expected: str) -> None:
    assert decode_html(body, header) == (expected, encoding)


@pytest.mark.parametrize(
    ("body", "header"),
    [
        (b"\xff", "text/html"),
        (b"A", "text/html; charset=made-up"),
        (b'<meta charset="cp1252">A', "text/html; charset=utf-8"),
        (codecs.BOM_UTF8 + b"A", "text/html; charset=iso-8859-1"),
    ],
)
def test_invalid_charset_never_replaced(body: bytes, header: str) -> None:
    with pytest.raises(CorpusError):
        decode_html(body, header)


def test_original_dom_locations_survive_chrome_removal() -> None:
    _, structure = parse(
        '<article><h1>A</h1><div class="consent">remove</div>'
        '<div><p><a href="/x">first</a></p></div>'
        '<ol><li><a href="/y">second</a></li></ol></article>'
    )
    assert structure.links[0].locator.endswith("/article[1]/div[2]/p[1]/a[1]")
    assert structure.links[1].locator.endswith("/article[1]/ol[1]/li[1]/a[1]")


def test_explicit_break_and_nested_list_tail() -> None:
    text, structure = parse(
        "<article><h1>A</h1><p>eins<br>zwei</p>"
        "<ul><li>vor<ul><li>innen</li></ul>nach</li></ul></article>"
    )
    assert "eins\nzwei" in text and "- innen nach" in text
    assert len(structure.list_items) == 2


@pytest.mark.parametrize(
    "body",
    [
        "<article><h1>Seite nicht gefunden</h1><p>Fehler.</p></article>",
        "<article><h1>A</h1><ol reversed><li>Text</li></ol></article>",
        '<article><h1>A</h1><ol type="A"><li>Text</li></ol></article>',
    ],
)
def test_soft_error_and_unsupported_list_style(body: str) -> None:
    with pytest.raises(CorpusError):
        parse(body)


def test_malformed_html_is_deterministic_without_rewriting_words() -> None:
    text, _ = parse("<article><h1>A</h1><p>eins<p>zwei &amp; drei</article>")
    assert text == "A\n\neins\n\nzwei & drei"


@pytest.mark.parametrize("roots", [(), ("article", "article"), ("[",)])
def test_invalid_selectors(roots: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        ParserConfig(roots=roots)
