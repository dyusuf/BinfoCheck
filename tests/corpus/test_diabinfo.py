from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from binfocheck.corpus import StoredCorpusIngestor
from binfocheck.corpus.artifacts import Store
from binfocheck.corpus.config import URLS, ParserConfig
from binfocheck.corpus.diabinfo import ROOTS, pilot_profile
from binfocheck.corpus.errors import CorpusError, require
from binfocheck.corpus.parsing import parse_html
from binfocheck.corpus.passages import construct
from binfocheck.corpus.transport import Response
from binfocheck.storage import MemoryStore

from .helpers import NOW, Transport, capture, request

FIXTURES = Path(__file__).parents[1] / "fixtures/corpus/diabinfo-v1"
HTML = (FIXTURES / "article.html").read_text()


def faq() -> str:
    soup = BeautifulSoup(HTML, "html5lib")
    body = soup.select_one(ROOTS[-1])
    assert body
    body.clear()
    fragment = BeautifulSoup((FIXTURES / "faq-body.html").read_text(), "html5lib")
    assert fragment.body
    for node in list(fragment.body.contents):
        body.append(node)
    return str(soup)


def parse(html: str = HTML, url: str = URLS[0]):
    return parse_html(
        html, url, "article-test", "receipt-test", "raw-test", "utf-8", pilot_profile()
    )


def test_explicit_profile_full_output() -> None:
    text, structure = parse()
    assert text == (FIXTURES / "article.txt").read_text().rstrip("\n")
    assert [h.level for h in structure.headings] == [1, 2, 3, 2, 2]
    assert [h.parent_index for h in structure.headings] == [None, 0, 1, 0, 0]
    assert [link.span.exact_text for link in structure.links if link.span] == [
        "Hinweis",
        "Weiterlesen",
        "Studie",
    ]
    assert structure.parser_version.version == "3"
    assert len(structure.roots) == 4
    assert any(e.rule == ".ce-gallery" for e in structure.exclusions)
    passages = construct(text, structure, NOW)
    assert any(
        p.span.exact_text.startswith("Nur bei Bedarf,") and "- Erstens" in p.span.exact_text
        for p in passages
    )
    for span in [
        *(b.span for b in structure.blocks),
        *(p.span for p in passages),
        *(h.span for h in structure.headings),
        *(i.span for i in structure.list_items),
        *(link.span for link in structure.links if link.span),
    ]:
        assert text[span.start : span.end] == span.exact_text
    assert parse() == (text, structure)


def test_faq_question_hierarchy_collapsed_answers_and_references() -> None:
    text, s = parse(faq(), URLS[3])
    assert [h.level for h in s.headings] == [1, 2, 3, 3]
    assert [h.parent_index for h in s.headings] == [None, 0, 1, 1]
    assert "Hinweis2: nicht immer." in text and "Noch nicht untersucht." in text
    assert "Quelle:\n\nBeleg\nHinweis2: nicht immer." in text
    assert len(s.links) == 2 and s.links[1].span and s.links[1].span.exact_text == "Beleg"
    assert "team@example.org" in text and "noSp@m" not in text
    passages = construct(text, s, NOW)
    answer = next(p for p in passages if p.span.exact_text == "Noch nicht untersucht.")
    assert [h.exact_text for h in answer.heading_spans][-2:] == [
        "Hintergrund",
        "2. Was bleibt ungewiss?",
    ]
    assert all(
        not ("Beleg" in p.span.exact_text and "Noch nicht" in p.span.exact_text) for p in passages
    )


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('id="main"', 'id="changed"'),
        ("frame-space-before-extra-small", "missing-credit"),
        ('href="#section"', 'href="#absent"'),
        ("<h2>Inhaltsverzeichnis</h2>", "<h2>Inhaltsverzeichnis geändert</h2>"),
        ("© Beispiel</figcaption>", "Wichtige neue Erklärung</figcaption>"),
        ('<source src="/nicht-abrufen.mp3">', "<p>Substantive transcript</p>"),
        ("<h2>Quellen:</h2>", "<h2>Unbekannte Rubrik</h2>"),
        ('<div class="news">', '<div class="unknown-content">'),
        (
            '<main id="main"><div class="container">',
            '<main id="main"><div class="container">'
            '<div class="frame"><p>Unselected article text</p></div>',
        ),
        ("<p>Auch kleine Schritte zählen.</p>", "<table><tr><td>Unbekannt</td></tr></table>"),
    ],
)
def test_unknown_layout_does_not_silently_become_ready(old: str, new: str) -> None:
    with pytest.raises(CorpusError):
        parse(HTML.replace(old, new))


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('aria-controls="a1"', 'aria-controls="wrong"'),
        ('aria-labelledby="q1"', 'aria-labelledby="wrong"'),
        (
            '<span class="close-on-mobile"></span>',
            '<span class="close-on-mobile">Substantive</span>',
        ),
        ("<path></path>", "<text>Substantive</text>"),
        ('class="h3"', 'class="wrong"'),
        ("noSp@m", "Substantive changed text"),
    ],
)
def test_changed_faq_structure_fails(old: str, new: str) -> None:
    with pytest.raises(CorpusError):
        parse(faq().replace(old, new), URLS[3])


def test_legacy_identity_and_new_version_history() -> None:
    legacy = ParserConfig()
    assert "site_profile" not in legacy.model_dump(mode="json")
    assert (
        legacy.version().sha256
        == "c448c2e55730915600d812dd074b0f0787aae6270de7d06b4cab838a464d3898"
    )
    assert legacy.version().version == "1" and legacy.version() != pilot_profile().version()
    with MemoryStore() as backend:
        io = Store(backend, backend)
        batch = capture(
            io,
            transport=Transport(
                {
                    url: Response(
                        200,
                        (("content-type", "text/html; charset=utf-8"),),
                        (faq() if url == URLS[3] else HTML).encode(),
                    )
                    for url in URLS
                }
            ),
        )
        ingestor = StoredCorpusIngestor(backend, backend)
        old = require(ingestor.ingest(request(batch)))
        assert all(a.reason == "ambiguous_article_root" for a in old.articles)
        updated_request = request(
            batch,
            parser=pilot_profile(),
            previous_version_ids=old.manifest.article_version_ids,
        )
        new = require(ingestor.ingest(updated_request))
        assert new.manifest.status == "ready"
        for before, after in zip(old.articles, new.articles, strict=True):
            assert after.previous_version_id == before.id
            assert after.raw_artifact_id == before.raw_artifact_id
            assert after.content_sha256 == before.content_sha256
            assert after.raw_text_id == before.raw_text_id
        assert require(ingestor.ingest(updated_request)) == new
        assert require(ingestor.load(old.manifest.id)) == old
        assert require(ingestor.load(new.manifest.id)) == new


def test_callout_heading_ends_with_box_not_following_paragraph() -> None:
    boxed = HTML.replace(
        '<div class="frame"><header><h3>Gut zu wissen:</h3></header>'
        "<p>Auch kleine Schritte zählen.</p></div>",
        '<div class="background-container"><div class="frame">'
        "<header><h3>Gut zu wissen:</h3></header><p>Auch kleine Schritte zählen.</p>"
        '</div></div><div class="frame"><p>Zurück im Hauptabschnitt.</p></div>',
    )
    text, structure = parse(boxed)
    passages = construct(text, structure, NOW)
    outside = next(p for p in passages if p.span.exact_text == "Zurück im Hauptabschnitt.")
    assert [h.exact_text for h in outside.heading_spans] == [
        "Ein synthetischer Artikel",
        "1. Abschnitt",
    ]
    callout = next(h for h in structure.headings if h.span.exact_text == "Gut zu wissen:")
    assert callout.section_end == outside.span.start


def test_profile_is_not_an_arbitrary_url_or_rules_fallback() -> None:
    with pytest.raises(CorpusError, match="site profile url not allowed"):
        parse(HTML, "https://example.org/article")
    changed = pilot_profile().model_copy(update={"chrome": ()})
    with pytest.raises(CorpusError, match="site profile rules mismatch"):
        parse_html(HTML, URLS[0], "a", "r", "t", "utf-8", changed)


def test_faq_missing_group_or_unwrapped_button_text_fails() -> None:
    for html in [
        faq().replace("<h2>Hintergrund</h2>", "<p>Hintergrund</p>"),
        faq().replace('<h2 class="h3">1.', 'unwrapped<h2 class="h3">1.'),
    ]:
        with pytest.raises(CorpusError):
            parse(html, URLS[3])


def test_informational_image_blocks_readiness_even_when_html_text_is_usable() -> None:
    infographic = HTML.replace('alt="Dekoratives Motiv"', 'alt="Infografik: Wichtige Information"')
    with pytest.raises(CorpusError, match="unsupported informational media"):
        parse(infographic)
    # Preserve replayability of the explicitly unaccepted diagnostic candidate.
    _, old = parse_html(
        infographic, URLS[0], "a", "r", "t", "utf-8", pilot_profile("diabinfo-pilot/1")
    )
    assert old.parser_version.version == "2"
    with MemoryStore() as backend:
        io = Store(backend, backend)
        batch = capture(
            io,
            transport=Transport(
                {
                    url: Response(
                        200,
                        (("content-type", "text/html; charset=utf-8"),),
                        (
                            infographic if url == URLS[1] else faq() if url == URLS[3] else HTML
                        ).encode(),
                    )
                    for url in URLS
                }
            ),
        )
        result = require(
            StoredCorpusIngestor(backend, backend).ingest(request(batch, parser=pilot_profile()))
        )
        assert result.manifest.status == "incomplete"
        assert result.articles[1].status == "unusable"
        assert result.articles[1].reason == "unsupported_informational_media"
        assert all(p.article_version_id != result.articles[1].id for p in result.passages)
