"""Versioned, bounded T06 policy. No live authorization is supplied by this module."""

import hashlib
import json
from importlib.metadata import version
from typing import Annotated, Literal

from pydantic import Field, field_validator
from soupsieve import compile as compile_selector
from soupsieve.util import SelectorSyntaxError

from binfocheck.domain.common import Contract, Id, Settings, VersionRef

URLS = (
    "https://www.diabinfo.de/leben/diabetes-im-alltag/strassenverkehr.html",
    "https://www.diabinfo.de/leben/diabetes-im-alltag/ramadan.html",
    "https://www.diabinfo.de/leben/diabetes-im-alltag/reisen.html",
    "https://www.diabinfo.de/vorbeugen/diabetes/wie-hoch-ist-mein-risiko-fuer-diabetes-typ-2/haeufig-gestellte-fragen.html",
    "https://www.diabinfo.de/vorbeugen/was-kann-ich-tun/so-erreichen-sie-ihre-ziele.html",
)
ROBOTS = "https://www.diabinfo.de/robots.txt"
PACKAGES = {"beautifulsoup4": "4.15.0", "html5lib": "1.1", "llama-index-core": "0.14.24"}


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(role: str, value: object) -> str:
    return f"corpus-{role}-" + digest(canonical(value))


SETTINGS_VERSION = VersionRef(name="t06-corpus-settings", version="1")
FETCH_VERSION = VersionRef(name="t06-corpus-fetch", version="1")
PASSAGES_VERSION = VersionRef(name="t06-corpus-passages", version="1")


class FetchPolicy(Contract):
    request_limit: Literal[6] = 6
    retries: Literal[0] = 0
    redirects: Literal[0] = 0
    concurrency: Literal[1] = 1
    connect_seconds: Literal[10] = 10
    read_seconds: Literal[20] = 20
    request_seconds: Literal[30] = 30
    batch_seconds: Literal[900] = 900
    spacing_seconds: Literal[2] = 2
    max_page_bytes: Literal[5242880] = 5242880
    max_robots_bytes: Literal[524288] = 524288
    user_agent: Literal["BinfoCheck-T06/1.0"] = "BinfoCheck-T06/1.0"
    paid_request_limit: Literal[0] = 0
    cost_ceiling_usd: Literal[0] = 0


POLICY = FetchPolicy()


def capture_policy_sha256(robots_url: str, page_urls: tuple[str, ...], policy: FetchPolicy) -> str:
    """Fingerprint the exact proposed capture envelope; this grants no authorization."""
    return digest(
        canonical(
            {
                "format": "t06-live-authorization/1",
                "robots_url": robots_url,
                "page_urls": page_urls,
                "fetch_policy": policy.model_dump(mode="json"),
            }
        )
    )


class ParserConfig(Contract):
    # Provisional structural profile; real site selectors require saved-page inspection.
    roots: tuple[str, ...] = ("article",)
    chrome: tuple[str, ...] = (
        "nav",
        "script",
        "style",
        "form",
        ".consent",
        ".cookie-banner",
        ".breadcrumbs",
        ".share-tools",
        ".related-pages",
        ".local-toc",
    )
    protected: str = ".references, .sources, .footnotes, .article-meta, .advice"
    faq_heading: str = ".faq-question"
    unusable_titles: tuple[str, ...] = (
        "404",
        "Seite nicht gefunden",
        "Zugriff verweigert",
        "Just a moment...",
    )
    max_characters: Annotated[int, Field(ge=1, le=1_000_000)] = 1_000_000
    max_blocks: Annotated[int, Field(ge=1, le=20_000)] = 20_000
    max_nodes: Annotated[int, Field(ge=1, le=100_000)] = 100_000
    max_depth: Annotated[int, Field(ge=1, le=100)] = 80

    @field_validator("roots", "chrome")
    @classmethod
    def bounded_selectors(cls, selectors: tuple[str, ...]) -> tuple[str, ...]:
        if not 1 <= len(selectors) <= 32 or len(set(selectors)) != len(selectors):
            raise ValueError("invalid_selectors")
        for selector in selectors:
            cls.valid_selector(selector)
        return selectors

    @field_validator("protected", "faq_heading")
    @classmethod
    def valid_selector(cls, selector: str) -> str:
        if not 1 <= len(selector) <= 256:
            raise ValueError("invalid_selector")
        try:
            compile_selector(selector)
        except SelectorSyntaxError:
            raise ValueError("invalid_selector") from None
        return selector

    def version(self) -> VersionRef:
        return VersionRef(
            name="t06-corpus-parser",
            version="1",
            sha256=digest(
                canonical(
                    {
                        "settings": self.model_dump(mode="json"),
                        "packages": PACKAGES,
                    }
                )
            ),
        )


class ReplaySettings(Contract):
    mode: Literal["replay"] = "replay"
    batch_artifact_id: Id
    parser: ParserConfig = ParserConfig()
    previous_version_ids: tuple[Id | None, ...] = (None,) * 5

    def envelope(self) -> Settings:
        return Settings(version=SETTINGS_VERSION, values=self.model_dump(mode="json"))


def verify_packages() -> None:
    from .errors import check

    check(
        all(version(name) == expected for name, expected in PACKAGES.items()),
        "corpus_package_version_mismatch",
    )
