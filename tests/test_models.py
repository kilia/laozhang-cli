from pathlib import Path

import pytest

from laozhang_cli.errors import InputValidationError
from laozhang_cli.models import GenerationRequest, GenerationResult, OutputImage, PromptValue


def valid_request_data() -> dict[str, object]:
    return {
        "model": "gpt-image-2",
        "system_prompt": "style",
        "prompt": "subject",
    }


def test_request_applies_readme_defaults() -> None:
    request = GenerationRequest.from_dict(valid_request_data(), Path("."))

    assert (request.resolution, request.aspect_ratio, request.count) == ("2K", "16:9", 1)
    assert request.negative_prompt is None
    assert request.output_dir == Path("output")
    assert request.convert_to_webp is True


def test_request_normalizes_inline_and_file_prompts() -> None:
    request = GenerationRequest.from_dict(
        {
            **valid_request_data(),
            "system_prompt": {"file": "prompts/style.md"},
            "negative_prompt": "avoid blur",
        },
        Path("requests"),
    )

    assert request.system_prompt == PromptValue(file=Path("requests/prompts/style.md"))
    assert request.prompt == PromptValue(text="subject")
    assert request.negative_prompt == PromptValue(text="avoid blur")


def test_request_accepts_explicit_valid_options() -> None:
    request = GenerationRequest.from_dict(
        {
            **valid_request_data(),
            "resolution": "4K",
            "aspect_ratio": "9:16",
            "count": 3,
            "filename": "city-01",
            "output_dir": "renders",
            "convert_to_webp": False,
        },
        Path("."),
    )

    assert request.resolution == "4K"
    assert request.aspect_ratio == "9:16"
    assert request.count == 3
    assert request.filename == "city-01"
    assert request.output_dir == Path("renders")
    assert request.convert_to_webp is False


def test_request_rejects_unknown_keys() -> None:
    with pytest.raises(InputValidationError, match="unknown field: extra"):
        GenerationRequest.from_dict({**valid_request_data(), "extra": 1}, Path("."))


@pytest.mark.parametrize("field", ["model", "system_prompt", "prompt"])
def test_request_rejects_missing_required_fields(field: str) -> None:
    data = valid_request_data()
    del data[field]

    with pytest.raises(InputValidationError, match=f"missing required field: {field}"):
        GenerationRequest.from_dict(data, Path("."))


@pytest.mark.parametrize("model", [None, "", "   ", 42])
def test_request_rejects_invalid_model(model: object) -> None:
    with pytest.raises(InputValidationError, match="model must be a non-empty string"):
        GenerationRequest.from_dict({**valid_request_data(), "model": model}, Path("."))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("system_prompt", None),
        ("prompt", ""),
        ("prompt", "   "),
        ("prompt", {"file": ""}),
        ("prompt", {"file": 4}),
        ("prompt", {"file": "prompt.md", "text": "subject"}),
        ("prompt", ["subject"]),
        ("negative_prompt", ""),
    ],
)
def test_request_rejects_invalid_prompt_values(field: str, value: object) -> None:
    with pytest.raises(InputValidationError, match=f"invalid prompt value: {field}"):
        GenerationRequest.from_dict({**valid_request_data(), field: value}, Path("."))


@pytest.mark.parametrize("resolution", ["8K", "2k", "", 2])
def test_request_rejects_invalid_resolution(resolution: object) -> None:
    with pytest.raises(InputValidationError, match="invalid resolution"):
        GenerationRequest.from_dict({**valid_request_data(), "resolution": resolution}, Path("."))


@pytest.mark.parametrize("aspect_ratio", ["2:3", "16/9", "", 1])
def test_request_rejects_invalid_aspect_ratio(aspect_ratio: object) -> None:
    with pytest.raises(InputValidationError, match="invalid aspect_ratio"):
        GenerationRequest.from_dict(
            {**valid_request_data(), "aspect_ratio": aspect_ratio}, Path(".")
        )


@pytest.mark.parametrize("count", [0, -1, 1.5, "2", True])
def test_request_rejects_invalid_count(count: object) -> None:
    with pytest.raises(InputValidationError, match="count must be a positive integer"):
        GenerationRequest.from_dict({**valid_request_data(), "count": count}, Path("."))


@pytest.mark.parametrize("filename", ["", "folder/name", "folder\\name", "image?.png", 3])
def test_request_rejects_unsafe_filename(filename: object) -> None:
    with pytest.raises(InputValidationError, match="invalid filename"):
        GenerationRequest.from_dict({**valid_request_data(), "filename": filename}, Path("."))


@pytest.mark.parametrize("output_dir", ["", 3, None])
def test_request_rejects_invalid_output_directory(output_dir: object) -> None:
    with pytest.raises(InputValidationError, match="output_dir must be a non-empty string"):
        GenerationRequest.from_dict({**valid_request_data(), "output_dir": output_dir}, Path("."))


@pytest.mark.parametrize("convert_to_webp", [0, 1, "true", None])
def test_request_rejects_non_boolean_conversion_flag(convert_to_webp: object) -> None:
    with pytest.raises(InputValidationError, match="convert_to_webp must be a boolean"):
        GenerationRequest.from_dict(
            {**valid_request_data(), "convert_to_webp": convert_to_webp}, Path(".")
        )


def test_result_models_hold_normalized_output() -> None:
    image = OutputImage(path="output/image.webp", format="webp")

    assert GenerationResult(
        success=True,
        http_status=200,
        message="generated",
        images=[image],
    ) == GenerationResult(True, 200, "generated", [image])


@pytest.mark.parametrize(
    ("field", "value"),
    [("resolution", ["2K"]), ("aspect_ratio", {"ratio": "1:1"})],
)
def test_request_rejects_unhashable_enum_values(field: str, value: object) -> None:
    with pytest.raises(InputValidationError, match=f"invalid {field}"):
        GenerationRequest.from_dict(
            {**valid_request_data(), field: value},
            Path("."),
        )
