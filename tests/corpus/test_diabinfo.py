from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from binfocheck.corpus import StoredCorpusIngestor
from binfocheck.corpus.artifacts import Store
from binfocheck.corpus.config import URLS, ParserConfig, SiteProfile
from binfocheck.corpus.diabinfo import ROOTS
from binfocheck.corpus.diabinfo import pilot_profile as latest_profile
from binfocheck.corpus.errors import CorpusError, require
from binfocheck.corpus.parsing import parse_html
from binfocheck.corpus.passages import construct
from binfocheck.corpus.transport import Response
from binfocheck.domain.interfaces import IngestionResult
from binfocheck.storage import MemoryStore

from .helpers import NOW, Transport, capture, request


def current_profile(profile: SiteProfile = "diabinfo-pilot/3") -> ParserConfig:
    # Preserve this suite's parser-4 regression coverage; parser 5 has its own suite.
    return latest_profile(profile)


def pilot_profile():
    # Existing regression suite pins historical parser 3; the positive policy is
    # exercised separately below, including replay of all historical versions.
    return current_profile("diabinfo-pilot/2")


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
        infographic, URLS[0], "a", "r", "t", "utf-8", current_profile("diabinfo-pilot/1")
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


def positive_html(media: str = "", *, faq_page: bool = False) -> str:
    soup = BeautifulSoup(faq() if faq_page else HTML, "html5lib")
    for node in soup.select(".ce-gallery, .frame-type-gddiabinfo_diabinfoaudio"):
        node.decompose()
    root = soup.select_one(ROOTS[-1])
    assert root
    fragment = BeautifulSoup(media, "html5lib")
    assert fragment.body
    for node in list(fragment.body.contents):
        root.append(node)
    return str(soup)


def positive_parse(media: str = "", url: str = URLS[4]):
    return parse_html(positive_html(media), url, "a", "r", "t", "utf-8", current_profile())


DECORATIVE = (FIXTURES / "decorative.html").read_text()
PODCAST = (FIXTURES / "podcast.html").read_text()


def test_known_decorative_and_podcast_exact_signatures() -> None:
    text, structure = positive_parse(DECORATIVE)
    assert "crazymedia" not in text and structure.parser_version.version == "4"
    assert text == (FIXTURES / "article.txt").read_text().rstrip("\n")
    text, _ = positive_parse(PODCAST, URLS[2])
    assert "Podcast" not in text
    with pytest.raises(CorpusError, match="unsupported informational media"):
        positive_parse(DECORATIVE, URLS[0])  # Correct media on an unreviewed page.


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (
            "Ein Mensch freut sich über den Aufstieg auf einen Berg.",
            "Diagramm zum Blutzuckerverlauf",
        ),
        (
            "Ein Mensch freut sich über den Aufstieg auf einen Berg.",
            "Blutzuckerverlauf während des Fastens",
        ),
        (
            "Ein Mensch freut sich über den Aufstieg auf einen Berg.",
            "Infografik: Wichtige Information",
        ),
        ("csm_Fotolia_94056501_web_0a92209623.jpg", "unknown.jpg"),
        ("ce-column", "unknown-layout"),
        ("© crazymedia / Fotolia</figcaption>", "© Beispiel: Wichtiges beachten</figcaption>"),
        ("© crazymedia / Fotolia</figcaption>", "Substantive Erklärung</figcaption>"),
        ('loading="lazy"', 'loading="lazy" aria-label="Neue Information"'),
        ("</figure>", "<img src='/unknown.svg'></figure>"),
        ("</figure>", "<div>Wichtiger Text</div></figure>"),
    ],
)
def test_unknown_media_always_fails_closed(before: str, after: str) -> None:
    with pytest.raises(CorpusError, match="unsupported informational media"):
        positive_parse(DECORATIVE.replace(before, after))


@pytest.mark.parametrize(
    "before,after",
    [
        ("icon-podcast.svg", "other.svg"),
        ("Podcast Icon", "Diagramm"),
        ("audio-element", "changed"),
        ("audio/mp3", "changed"),
        ("Ivo Rettig", "substantive transcript"),
    ],
)
def test_podcast_signature_changes_fail(before: str, after: str) -> None:
    with pytest.raises(CorpusError, match="unsupported informational media"):
        positive_parse(PODCAST.replace(before, after), URLS[2])


def test_positive_profile_preserves_history_and_blocks_missing_svg() -> None:
    versions = [
        ParserConfig(),
        current_profile("diabinfo-pilot/1"),
        current_profile("diabinfo-pilot/2"),
        current_profile("diabinfo-pilot/3"),
    ]
    assert [v.version().version for v in versions] == ["1", "2", "3", "4"]
    assert versions[1].version().sha256 == (
        "5a9e2078f27dd2e57f77fb76cc44581760f2c52ef9e7d119fd3040e4d9ac8584"
    )
    assert (
        versions[2].version().sha256
        == "b4cd5fdda187a0da1206547e17416f64eed93a767f8d4a0b5fa32808be13e85e"
    )
    svg = (
        '<div class="ce-gallery"><figure><img class="image-embed-item" '
        'alt="Infografik: Was sollten Menschen mit Diabetes beim Fasten beachten?" '
        'src="/fileadmin/diabinfo/Grafiken/0511_diabinfo_Ramadan_DE_ohne-Titel.svg">'
        "</figure></div>"
    )
    with MemoryStore() as backend:
        io = Store(backend, backend)
        batch = capture(
            io,
            transport=Transport(
                {
                    url: Response(
                        200,
                        (("content-type", "text/html; charset=utf-8"),),
                        positive_html(
                            svg
                            if url == URLS[1]
                            else PODCAST
                            if url == URLS[2]
                            else DECORATIVE
                            if url == URLS[4]
                            else "",
                            faq_page=url == URLS[3],
                        ).encode(),
                    )
                    for url in URLS
                }
            ),
        )
        ingestor = StoredCorpusIngestor(backend, backend)
        results: list[IngestionResult] = []
        for version in versions:
            previous = results[-1].manifest.article_version_ids if results else (None,) * 5
            result = require(
                ingestor.ingest(request(batch, parser=version, previous_version_ids=previous))
            )
            results.append(result)
        final = results[-1]
        assert [a.status for a in final.articles] == [
            "usable",
            "unusable",
            "usable",
            "usable",
            "usable",
        ]
        assert final.articles[1].reason == "unsupported_informational_media"
        assert final.manifest.status == "incomplete"
        for result in results:
            assert require(ingestor.load(result.manifest.id)) == result
        for old, new in zip(results[-2].articles, final.articles, strict=True):
            assert new.previous_version_id == old.id
            assert new.raw_artifact_id == old.raw_artifact_id


def test_unknown_image_cannot_hide_in_excluded_toc() -> None:
    html = positive_html().replace(
        "Inhaltsverzeichnis</h2>", 'Inhaltsverzeichnis</h2><img src="/unknown.svg">'
    )
    with pytest.raises(CorpusError, match="unsupported informational media"):
        parse_html(html, URLS[0], "a", "r", "t", "utf-8", current_profile())
