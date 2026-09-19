from pathlib import Path

import pytest

from binfocheck.acquisition.config import Credentials


def test_credentials_load_local_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATAFORSEO_LOGIN", raising=False)
    monkeypatch.delenv("DATAFORSEO_PASSWORD", raising=False)
    (tmp_path / ".env").write_text(
        "DATAFORSEO_LOGIN=dotenv-login\nDATAFORSEO_PASSWORD=dotenv-password\n",
        encoding="utf-8",
    )

    credentials = Credentials.from_environment()

    assert credentials.login.get_secret_value() == "dotenv-login"
    assert credentials.password.get_secret_value() == "dotenv-password"


def test_process_environment_overrides_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "DATAFORSEO_LOGIN=dotenv-login\nDATAFORSEO_PASSWORD=dotenv-password\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DATAFORSEO_LOGIN", "environment-login")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "environment-password")

    credentials = Credentials.from_environment()

    assert credentials.login.get_secret_value() == "environment-login"
    assert credentials.password.get_secret_value() == "environment-password"
