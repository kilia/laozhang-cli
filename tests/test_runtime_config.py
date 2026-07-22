from pathlib import Path

import pytest

from laozhang_cli.config import Settings


def test_settings_loads_api_key_from_dotenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LAOZHANG_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("LAOZHANG_KEY=dotenv-key\n", encoding="utf-8")

    assert Settings.from_environment(env_file) == Settings(api_key="dotenv-key")


def test_environment_api_key_takes_precedence_over_dotenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LAOZHANG_KEY", "environment-key")
    env_file = tmp_path / ".env"
    env_file.write_text("LAOZHANG_KEY=dotenv-key\n", encoding="utf-8")

    assert Settings.from_environment(env_file) == Settings(api_key="environment-key")
