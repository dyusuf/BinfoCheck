"""Conservative offline hostname classification, never browser normalization or DNS."""

import re
from typing import Literal
from urllib.parse import urlsplit

from binfocheck.domain.common import Contract

from .config import RULES


class HostAssessment(Contract):
    status: Literal["target", "other", "unclear"]
    reason: str
    hostname: str | None = None


def classify_host(url: str) -> HostAssessment:
    def unknown(reason: str) -> HostAssessment:
        return HostAssessment(status="unclear", reason=reason)

    # urlsplit strips some controls; reject them BEFORE parsing.
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url) or "\\" in url:
        return unknown("unsafe_url_characters")
    try:
        parsed = urlsplit(url)
        authority = parsed.netloc
        if parsed.scheme not in RULES.schemes or not authority:
            return unknown("unsupported_url")
        if "@" in authority:
            return unknown("userinfo")
        if not authority.isascii() or "%" in authority:
            return unknown("non_ascii_or_encoded_authority")
        # DNS authorities only. IP literals/IPv6 and other ambiguous forms stay unassessable.
        if authority.count(":") > 1 or "[" in authority or "]" in authority:
            return unknown("unsupported_authority")
        if ":" in authority:
            port = authority.rsplit(":", 1)[1]
            if not re.fullmatch(r"[0-9]+", port) or not 1 <= int(port) <= 65535:
                return unknown("invalid_port")
        host = parsed.hostname
        if not host:
            return unknown("invalid_hostname")
        host = host.lower().removesuffix(".")
        if len(host) > 253:
            return unknown("invalid_hostname")
        labels = host.split(".")
        for label in labels:
            if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label):
                return unknown("invalid_hostname")
            if label.startswith("xn--"):
                # Validate A-label roundtrip only; never use decoded Unicode for allowlisting.
                decoded = label.encode("ascii").decode("idna")
                if decoded.isascii() or decoded.encode("idna").decode("ascii") != label:
                    return unknown("invalid_idna")
        if host in RULES.allowed_hosts:
            return HostAssessment(status="target", reason="allowed_hostname", hostname=host)
        if host.endswith(".diabinfo.de"):
            return HostAssessment(status="unclear", reason="unlisted_subdomain", hostname=host)
        return HostAssessment(status="other", reason="other_hostname", hostname=host)
    except (ValueError, UnicodeError):
        return unknown("invalid_authority")
