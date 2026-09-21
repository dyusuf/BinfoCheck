import pytest

from binfocheck.citations.hosts import classify_host


@pytest.mark.parametrize(
    "url",
    [
        "https://diabinfo.de/a",
        "http://www.diabinfo.de",
        "HTTPS://WWW.DIABINFO.DE/a",
        "https://diabinfo.de./a",
        "https://WWW.DIABINFO.DE.:443/a",
        "http://diabinfo.de:1",
        "https://diabinfo.de:65535/",
        "https://diabinfo.de:00443/",
        "https://diabinfo.de/ä?q=ü",
    ],
)
def test_allowed_hosts(url: str) -> None:
    assert classify_host(url).status == "target"


@pytest.mark.parametrize(
    "url",
    [
        "https://diabinfo.de.example.org",
        "https://notdiabinfo.de",
        "https://diabinfo-de.org",
        "https://example.org/diabinfo.de?host=www.diabinfo.de",
        "https://xn--bcher-kva.de",
    ],
)
def test_other_hosts(url: str) -> None:
    assert classify_host(url).status == "other"


@pytest.mark.parametrize(
    "url",
    [
        "https://sub.diabinfo.de",
        "https://sub.www.diabinfo.de",
        "https://diabinfo.de..",
        "https://user@diabinfo.de",
        "https://diabinfo.de@evil.example",
        "https://user:secret@www.diabinfo.de",
        "https://diabinfo.de:",
        "https://diabinfo.de:0",
        "https://diabinfo.de:65536",
        "https://diabinfo.de:-1",
        "https://diabinfo.de:abc",
        "https://diabinfo.de:٤٤٣",
        "https://dіabinfo.de",
        "https://ｄiabinfo.de",
        "https://diabinfo。de",
        "https://%64iabinfo.de",
        "https://diabinfo.de%2e",
        "https://diabinfo.de\\@evil.org",
        " https://diabinfo.de",
        "https://diabinfo.de\n",
        "https://dia\tbinfo.de",
        "https://diabinfo.de/\x00",
        "https://[::1]",
        "https://[diabinfo.de",
        "https://-diabinfo.de",
        "https://diabinfo-.de",
        "https://diabinfo..de",
        "https://xn--.de",
        "https://xn--abc.de",
        "https:///diabinfo.de",
        "//diabinfo.de",
        "mailto:diabinfo.de",
        "https://diabinfo.de:443:1",
    ],
)
def test_unassessable_hosts(url: str) -> None:
    result = classify_host(url)
    assert result.status == "unclear"
    assert "secret" not in result.model_dump_json()
