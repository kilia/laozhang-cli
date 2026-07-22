from pathlib import Path

import pytest

from laozhang_cli.errors import InputValidationError
from laozhang_cli.models import GenerationRequest, GenerationResult, PromptValue
from laozhang_cli.services.generation import GenerationService


class _CapturingAdapter:
    def __init__(self) -> None:
        self.request: GenerationRequest | None = None

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.request = request
        return GenerationResult(True, 200, "generated", [])


class _Registry:
    def __init__(self, adapter: _CapturingAdapter) -> None:
        self.adapter = adapter

    def get(self, _model: str) -> _CapturingAdapter:
        return self.adapter


def test_generation_resolves_prompt_files_before_adapter_selection(tmp_path: Path) -> None:
    (tmp_path / "style.md").write_text("cinematic style", encoding="utf-8")
    (tmp_path / "negative.md").write_text("avoid blur", encoding="utf-8")
    request = GenerationRequest.from_dict(
        {
            "model": "gpt-image-2",
            "system_prompt": {"file": "style.md"},
            "prompt": "a city",
            "negative_prompt": {"file": "negative.md"},
        },
        tmp_path,
    )
    adapter = _CapturingAdapter()

    GenerationService(registry=_Registry(adapter)).generate(request)  # type: ignore[arg-type]

    assert adapter.request is not None
    assert adapter.request.system_prompt == PromptValue(text="cinematic style")
    assert adapter.request.prompt == PromptValue(text="a city")
    assert adapter.request.negative_prompt == PromptValue(text="avoid blur")


def test_generation_reports_missing_prompt_file_as_input_error(tmp_path: Path) -> None:
    request = GenerationRequest.from_dict(
        {
            "model": "gpt-image-2",
            "system_prompt": {"file": "missing.md"},
            "prompt": "a city",
        },
        tmp_path,
    )

    with pytest.raises(InputValidationError, match="unable to read prompt file"):
        GenerationService(registry=_Registry(_CapturingAdapter())).generate(request)  # type: ignore[arg-type]
