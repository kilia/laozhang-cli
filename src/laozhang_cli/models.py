from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import InputValidationError

_ALLOWED_FIELDS = {
    "model",
    "system_prompt",
    "prompt",
    "negative_prompt",
    "resolution",
    "aspect_ratio",
    "count",
    "filename",
    "output_dir",
    "convert_to_webp",
}
_ALLOWED_RESOLUTIONS = {"1K", "2K", "4K"}
_ALLOWED_ASPECT_RATIOS = {"1:1", "4:3", "3:4", "16:9", "9:16"}
_INVALID_FILENAME_CHARACTERS = frozenset('\\/:*?"<>|')


@dataclass(frozen=True)
class PromptValue:
    text: str | None = None
    file: Path | None = None


@dataclass(frozen=True)
class GenerationRequest:
    model: str
    system_prompt: PromptValue
    prompt: PromptValue
    negative_prompt: PromptValue | None
    resolution: str
    aspect_ratio: str
    count: int
    filename: str | None
    output_dir: Path
    convert_to_webp: bool

    @classmethod
    def from_dict(cls, data: dict[str, object], base_dir: Path) -> GenerationRequest:
        unknown_fields = set(data) - _ALLOWED_FIELDS
        if unknown_fields:
            first_unknown = sorted(unknown_fields)[0]
            raise InputValidationError(f"unknown field: {first_unknown}")

        for field in ("model", "system_prompt", "prompt"):
            if field not in data:
                raise InputValidationError(f"missing required field: {field}")

        model = data["model"]
        if not isinstance(model, str) or not model.strip():
            raise InputValidationError("model must be a non-empty string")

        system_prompt = _parse_prompt("system_prompt", data["system_prompt"], base_dir)
        prompt = _parse_prompt("prompt", data["prompt"], base_dir)
        negative_prompt = _parse_prompt(
            "negative_prompt",
            data.get("negative_prompt"),
            base_dir,
            allow_none=True,
        )
        assert system_prompt is not None
        assert prompt is not None

        resolution = data.get("resolution", "2K")
        if not isinstance(resolution, str):
            raise InputValidationError(f"invalid resolution: {resolution}")
        if resolution not in _ALLOWED_RESOLUTIONS:
            raise InputValidationError(f"invalid resolution: {resolution}")

        aspect_ratio = data.get("aspect_ratio", "16:9")
        if not isinstance(aspect_ratio, str):
            raise InputValidationError(f"invalid aspect_ratio: {aspect_ratio}")
        if aspect_ratio not in _ALLOWED_ASPECT_RATIOS:
            raise InputValidationError(f"invalid aspect_ratio: {aspect_ratio}")

        count = data.get("count", 1)
        if type(count) is not int or count < 1:
            raise InputValidationError("count must be a positive integer")

        filename = data.get("filename")
        if filename is not None and not _is_safe_filename(filename):
            raise InputValidationError("invalid filename")

        output_dir = data.get("output_dir", "output")
        if not isinstance(output_dir, str) or not output_dir:
            raise InputValidationError("output_dir must be a non-empty string")

        convert_to_webp = data.get("convert_to_webp", True)
        if type(convert_to_webp) is not bool:
            raise InputValidationError("convert_to_webp must be a boolean")

        return cls(
            model=model,
            system_prompt=system_prompt,
            prompt=prompt,
            negative_prompt=negative_prompt,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            count=count,
            filename=filename,
            output_dir=Path(output_dir),
            convert_to_webp=convert_to_webp,
        )


@dataclass(frozen=True)
class OutputImage:
    path: str
    format: str


@dataclass(frozen=True)
class GenerationResult:
    success: bool
    http_status: int | None
    message: str
    images: list[OutputImage]
    elapsed_seconds: float | None = None


def _parse_prompt(
    field: str,
    value: object,
    base_dir: Path,
    *,
    allow_none: bool = False,
) -> PromptValue | None:
    if value is None and allow_none:
        return None
    if isinstance(value, str) and value.strip():
        return PromptValue(text=value)
    if isinstance(value, dict) and set(value) == {"file"}:
        file_value = value["file"]
        if isinstance(file_value, str) and file_value:
            return PromptValue(file=base_dir / file_value)
    raise InputValidationError(f"invalid prompt value: {field}")


def _is_safe_filename(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not any(character in _INVALID_FILENAME_CHARACTERS for character in value)
    )
