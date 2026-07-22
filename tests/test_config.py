from pathlib import Path

import pytest

from laozhang_cli.config import Settings
from laozhang_cli.errors import ApiError


def test_settings_reads_api_key_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAOZHANG_KEY", "test-key")

    assert Settings.from_environment() == Settings(api_key="test-key")


def test_settings_rejects_missing_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LAOZHANG_KEY", raising=False)

    with pytest.raises(ApiError, match="LAOZHANG_KEY is not configured"):
        Settings.from_environment(tmp_path / ".env")
