import json
import subprocess
import sys
from pathlib import Path

import pytest

from laozhang_cli.cli import main
from laozhang_cli.errors import ApiError, StorageError
from laozhang_cli.models import GenerationRequest, GenerationResult, OutputImage
from laozhang_cli.services.generation import GenerationService


def _write_valid_request(source: Path) -> None:
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


def _assert_single_json_output(output: str) -> dict[str, object]:
    assert output.count("\n") == 1
    return json.loads(output)


def test_cli_emits_json_for_invalid_input(tmp_path: Path, capsys) -> None:
    source = tmp_path / "request.json"
    source.write_text("{}", encoding="utf-8")

    assert main(["--input", str(source)]) == 2
    captured = capsys.readouterr()
    result = _assert_single_json_output(captured.out)
    assert result == {
        "success": False,
        "http_status": None,
        "message": "missing required field: model",
        "images": [],
    }
    assert captured.err == ""


def test_cli_rejects_a_non_object_json_root(tmp_path: Path, capsys) -> None:
    source = tmp_path / "request.json"
    source.write_text("[]", encoding="utf-8")

    assert main(["--input", str(source)]) == 2
    captured = capsys.readouterr()
    assert _assert_single_json_output(captured.out) == {
        "success": False,
        "http_status": None,
        "message": "input JSON must be an object",
        "images": [],
    }
    assert captured.err == ""


def test_cli_returns_json_for_invalid_utf8_input(tmp_path: Path, capsys) -> None:
    source = tmp_path / "request.json"
    source.write_bytes(b"\xff")

    assert main(["--input", str(source)]) == 2
    captured = capsys.readouterr()
    result = _assert_single_json_output(captured.out)
    assert result["success"] is False
    assert result["http_status"] is None
    assert result["images"] == []
    assert result["message"]
    assert captured.err == ""


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], "the following arguments are required: --input"),
        (["--help"], "the following arguments are required: --input"),
    ],
)
def test_cli_emits_json_for_argument_errors(
    argv: list[str],
    message: str,
    capsys,
) -> None:
    assert main(argv) == 2
    captured = capsys.readouterr()
    assert _assert_single_json_output(captured.out) == {
        "success": False,
        "http_status": None,
        "message": message,
        "images": [],
    }
    assert captured.err == ""


def test_cli_serializes_a_generation_result(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "request.json"
    _write_valid_request(source)

    def generate(
        _service: GenerationService,
        request: GenerationRequest,
    ) -> GenerationResult:
        assert request.model == "gpt-image-2"
        return GenerationResult(
            success=True,
            http_status=200,
            message="generated",
            images=[OutputImage(path="output/image.webp", format="webp")],
        )

    monkeypatch.setattr(GenerationService, "generate", generate)

    assert main(["--input", str(source)]) == 0
    captured = capsys.readouterr()
    assert _assert_single_json_output(captured.out) == {
        "success": True,
        "http_status": 200,
        "message": "generated",
        "images": [{"path": "output/image.webp", "format": "webp"}],
    }
    assert captured.err == ""


@pytest.mark.parametrize(
    ("error_type", "exit_code"),
    [(ApiError, 3), (StorageError, 4)],
)
def test_cli_maps_domain_errors_to_their_exit_codes(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[ApiError] | type[StorageError],
    exit_code: int,
) -> None:
    source = tmp_path / "request.json"
    _write_valid_request(source)

    def generate(
        _service: GenerationService,
        _request: GenerationRequest,
    ) -> GenerationResult:
        raise error_type("operation failed")

    monkeypatch.setattr(GenerationService, "generate", generate)

    assert main(["--input", str(source)]) == exit_code
    captured = capsys.readouterr()
    assert _assert_single_json_output(captured.out) == {
        "success": False,
        "http_status": None,
        "message": "operation failed",
        "images": [],
    }
    assert captured.err == ""


def test_cli_returns_controlled_json_for_unexpected_errors(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "request.json"
    _write_valid_request(source)

    def generate(
        _service: GenerationService,
        _request: GenerationRequest,
    ) -> GenerationResult:
        raise RuntimeError("generation blew up")

    monkeypatch.setattr(GenerationService, "generate", generate)

    assert main(["--input", str(source)]) == 1
    captured = capsys.readouterr()
    assert _assert_single_json_output(captured.out) == {
        "success": False,
        "http_status": None,
        "message": "unexpected internal error",
        "images": [],
    }
    assert "RuntimeError: generation blew up" in captured.err


def test_module_invocation_emits_json_for_missing_input() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "laozhang_cli"],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 2
    assert _assert_single_json_output(completed.stdout) == {
        "success": False,
        "http_status": None,
        "message": "the following arguments are required: --input",
        "images": [],
    }
    assert completed.stderr == ""
