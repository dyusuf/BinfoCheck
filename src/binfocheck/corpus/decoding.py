"""Strict charset interpretation of complete HTTP content-decoded bytes."""

import codecs
import re

from bs4 import BeautifulSoup

from .errors import CorpusError, check

SUPPORTED = {"utf-8", "iso8859-1", "cp1252", "utf-16", "utf-16-le", "utf-16-be"}


def charset(name: str) -> str:
    try:
        result = codecs.lookup(name.strip()).name
    except LookupError:
        raise CorpusError("unsupported_charset") from None
    check(result in SUPPORTED, "unsupported_charset")
    return result


def decode_html(body: bytes, content_type: str) -> tuple[str, str]:
    declarations: list[str] = []
    match = re.search(r"charset\s*=\s*[\"\']?([^;\s\"\']+)", content_type, re.I)
    if match:
        declarations.append(charset(match[1]))
    # Meta declarations are ASCII-compatible; no replacement decoding of article text.
    head = BeautifulSoup(body[:4096].decode("latin-1"), "html5lib")
    for meta in head.find_all("meta"):
        declared = meta.get("charset")
        if isinstance(declared, str):
            declarations.append(charset(declared))
        content = meta.get("content")
        if isinstance(content, str) and str(meta.get("http-equiv", "")).lower() == "content-type":
            found = re.search(r"charset\s*=\s*([^;\s]+)", content, re.I)
            if found:
                declarations.append(charset(found[1]))
    bom: str | None = None
    if body.startswith(codecs.BOM_UTF8):
        bom = "utf-8"
    elif body.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        bom = "utf-16"
    chosen = bom or (declarations[0] if declarations else "utf-8")
    check(all(d == chosen for d in declarations), "conflicting_charset")
    try:
        # Keep the BOM as U+FEFF in the raw text for UTF-8. UTF-16's BOM is encoding metadata.
        return body.decode(chosen, errors="strict"), chosen
    except UnicodeError:
        raise CorpusError("invalid_charset_bytes") from None
