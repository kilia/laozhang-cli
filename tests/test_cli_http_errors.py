import json
from pathlib import Path

import pytest

from laozhang_cli.cli import main
from laozhang_cli.errors import ApiError, StorageError
from laozhang_cli.models import GenerationRequest, GenerationResult
from laozhang_cli.services.generation import GenerationService


@pytest.mark.parametrize(
    ("error_type", "message", "exit_code", "http_status"),
    [
        (ApiError, "rate limited", 3, 429),
        (StorageError, "image download failed", 4, 404),
    ],
)
def test_cli_preserves_http_status_for_domain_errors(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[ApiError] | type[StorageError],
    message: str,
    exit_code: int,
    http_status: int,
) -> None:
    error = error_type(message, http_status=http_status)
    source = tmp_path / "request.json"
    source.write_text(
        json.dumps(
            {
                "model": "gpt-image-2",
                "system_prompt": "style",
                "prompt": "subject",
            }
        ),
        encoding="utf-8",
    )

    def generate(
        _service: GenerationService,
        _request: GenerationRequest,
    ) -> GenerationResult:
        raise error

    monkeypatch.setattr(GenerationService, "generate", generate)

    assert main(["--input", str(source)]) == exit_code
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "success": False,
        "http_status": http_status,
        "message": str(error),
        "images": [],
    }
    assert captured.err == ""
