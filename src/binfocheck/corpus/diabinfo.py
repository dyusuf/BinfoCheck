"""Explicit profile for the five saved pilot pages, never a general site extractor."""

from bs4 import BeautifulSoup, Comment, Tag
from bs4.element import NavigableString

from .config import URLS, ParserConfig, SiteProfile
from .errors import check
from .media import validate_media

PROFILE: SiteProfile = "diabinfo-pilot/3"
CONTAINER = "main#main > .container"
ROOTS = (
    CONTAINER + " > .frame:has(> header > h1)",
    CONTAINER + " > .frame.frame-space-before-extra-small",
    CONTAINER
    + " > .frame-type-gddiabinfo_diabinfobackground > .background-container"
    + " > .frame > .row.grid-container > .col-lg-9",
    CONTAINER + " > .frame-type-gddiabinfo_diabinfocolumns > .row.grid-container > .col-lg-9",
)
TOC = '.frame:has(> header > h2:-soup-contains("Inhaltsverzeichnis"))'
REFERENCES = '.frame:has(> header > h2:-soup-contains("Quellen:"))'
FAQ = "button.accordion-headline > h2.h3"
CHROME = (
    TOC,
    ".frame-type-news_pi1",
    ".frame-type-gddiabinfo_diabinfoaudio",
    ".ce-gallery",
    "hr",
    'a[data-mailto-token] > span[style="display: none;"]',
    ".accordion-item > span.close-on-mobile",
    'button.accordion-headline > svg[aria-hidden="true"]',
)


def pilot_profile(profile: SiteProfile = PROFILE) -> ParserConfig:
    return ParserConfig(
        site_profile=profile,
        roots=ROOTS,
        chrome=CHROME,
        protected=REFERENCES + ", .references, .sources, .footnotes, .advice",
        faq_heading=FAQ,
    )


def validate_profile(soup: BeautifulSoup, roots: list[Tag], url: str, config: ParserConfig) -> None:
    """Check the observed layout and exclusion shapes before removing any nodes."""
    check(url in URLS, "site_profile_url_not_allowed")
    assert config.site_profile is not None
    expected = pilot_profile(config.site_profile)
    check(
        config.roots == expected.roots
        and config.chrome == expected.chrome
        and config.protected == expected.protected
        and config.faq_heading == expected.faq_heading,
        "site_profile_rules_mismatch",
    )
    check(len(soup.select(CONTAINER)) == 1 and len(roots) == 4, "site_layout_mismatch")
    container = soup.select(CONTAINER)[0]
    # Every outer content frame must belong to one of the four declared regions.
    # A newly added article frame outside them is an explicit layout change.
    check(
        not any(
            isinstance(child, NavigableString)
            and not isinstance(child, Comment)
            and str(child).strip()
            for child in container.children
        ),
        "site_unselected_content",
    )
    for child in container.find_all(recursive=False):
        if child.css.match("nav.nav-breadcrumb, div.shariff, script"):
            continue
        check(
            any(child is root or any(child is p for p in root.parents) for root in roots),
            "site_unselected_content",
        )
    title, credit, intro, body = roots
    check(len(title.select("h1")) == 1, "site_title_mismatch")
    check(
        credit.get_text(" ", strip=True).startswith("Wissenschaftliche Unterstützung")
        and bool(credit.select("p"))
        and bool(intro.select("p")),
        "site_intro_mismatch",
    )
    tocs = body.select(TOC)
    check(len(tocs) == 1, "site_toc_mismatch")
    toc = tocs[0]
    heading = toc.select_one("header > h2")
    check(
        heading is not None and heading.get_text(strip=True) == "Inhaltsverzeichnis",
        "site_toc_mismatch",
    )
    anchors = toc.select("li a")
    check(bool(anchors) and len(anchors) == len(toc.select("li")), "site_toc_mismatch")
    for anchor in anchors:
        href = str(anchor.get("href", ""))
        targets: list[Tag] = list(body.find_all(id=href[1:])) if href.startswith("#") else []
        check(len(targets) == 1 and toc not in targets[0].parents, "site_toc_target_mismatch")
    # TOC text may only be its heading, local links, and FAQ group labels.
    groups = {h.get_text(" ", strip=True) for h in body.select(":scope > .frame > header > h2")}
    for text in toc.stripped_strings:
        check(
            text == "Inhaltsverzeichnis"
            or text in groups
            or any(text in a.get_text() for a in anchors),
            "site_toc_unexpected_text",
        )
    for root in roots:
        if config.site_profile == "diabinfo-pilot/3":
            for image in root.select("img"):
                check(
                    any(
                        parent.css.match(".ce-gallery, .frame-type-news_pi1")
                        for parent in image.parents
                    ),
                    "unsupported_informational_media",
                )
        for marker in root.select('a[data-mailto-token] > span[style="display: none;"]'):
            check(
                marker.get_text() == "noSp@m" and not marker.find_all(True),
                "site_mail_marker_mismatch",
            )
        for gallery in root.select(".ce-gallery"):
            if config.site_profile == "diabinfo-pilot/3":
                validate_media(gallery, url, "gallery")
            if config.site_profile == "diabinfo-pilot/2":
                # Profile 1 is retained only to replay the unaccepted diagnostic
                # candidate. Its broad image exclusion missed an informational SVG.
                for figure in gallery.select("figure"):
                    images = figure.select("img.image-embed-item")
                    captions = figure.select("figcaption")
                    has_credit = bool(captions) and all(
                        c.get_text(strip=True).startswith("©") for c in captions
                    )
                    podcast = bool(images) and all(
                        image.get("alt") == "Podcast Icon" for image in images
                    )
                    check(
                        bool(images)
                        and (has_credit or podcast)
                        and not any(
                            str(image.get("alt", "")).startswith("Infografik:") for image in images
                        ),
                        "unsupported_informational_media",
                    )
            check(bool(gallery.select("img")), "site_media_mismatch")
            check(
                all(
                    t.name in {"div", "figure", "img", "noscript", "figcaption"}
                    for t in gallery.find_all(True)
                ),
                "site_media_mismatch",
            )
            # Only the observed credit-only captions may be excluded. A substantive
            # caption/diagram description is an unsupported change, not silent loss.
            check(
                all(c.get_text(strip=True).startswith("©") for c in gallery.select("figcaption")),
                "site_substantive_media_caption",
            )
            check(
                all(
                    t.parent and t.parent.name == "figcaption"
                    for t in gallery.find_all(string=True)
                    if str(t).strip()
                ),
                "site_media_mismatch",
            )
        for audio in root.select(".frame-type-gddiabinfo_diabinfoaudio"):
            if config.site_profile == "diabinfo-pilot/3":
                validate_media(audio, url, "audio")
            check(
                bool(audio.select("audio > source")) and bool(audio.select("header > h2")),
                "site_audio_mismatch",
            )
            check(
                all(
                    t.name in {"header", "h2", "span", "br", "div", "audio", "source"}
                    for t in audio.find_all(True)
                ),
                "site_audio_mismatch",
            )
            check(
                all(
                    t.find_parent("h2") is not None
                    for t in audio.find_all(string=True)
                    if str(t).strip()
                ),
                "site_audio_mismatch",
            )
        for news in root.select(".frame-type-news_pi1"):
            check(bool(news.select(":scope > .news")), "site_news_mismatch")
            check(
                all(
                    t.name == "header" or t.css.match(".news")
                    for t in news.find_all(recursive=False)
                ),
                "site_news_mismatch",
            )
    buttons = body.select("button.accordion-headline")
    check(bool(buttons) == (url == URLS[3]), "site_faq_presence_mismatch")
    if not buttons:
        references = body.select(REFERENCES)
        check(len(references) == 1 and bool(references[0].select("p")), "site_references_missing")
    for accordion in body.select(".frame-type-gddiabinfo_diabinfoaccordion"):
        group = accordion.find_previous_sibling()
        check(
            group is not None and group.select_one(":scope > header > h2") is not None,
            "site_faq_group_missing",
        )
    for button in buttons:
        check(
            not any(
                isinstance(child, NavigableString)
                and not isinstance(child, Comment)
                and str(child).strip()
                for child in button.children
            ),
            "site_faq_mismatch",
        )
        item = button.parent
        check(isinstance(item, Tag) and item.css.match(".accordion-item"), "site_faq_mismatch")
        assert isinstance(item, Tag)
        headings = button.select(":scope > h2.h3")
        answers = item.select(":scope > .accordion-content")
        check(len(headings) == 1 and len(answers) == 1, "site_faq_mismatch")
        check(
            bool(button.get("id"))
            and answers[0].get("aria-labelledby") == button.get("id")
            and button.get("aria-controls") == answers[0].get("id")
            and bool(answers[0].select("p, ul, ol")),
            "site_faq_mismatch",
        )
        check(
            all(
                t is headings[0] or (t.name == "svg" and t.get("aria-hidden") == "true")
                for t in button.find_all(recursive=False)
            ),
            "site_faq_mismatch",
        )
        for icon in button.select('svg[aria-hidden="true"]'):
            check(not icon.get_text(strip=True), "site_faq_icon_text")
        for control in item.select(":scope > span.close-on-mobile"):
            check(
                not control.get_text(strip=True) and not control.select("a"),
                "site_faq_control_text",
            )
