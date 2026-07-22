from datetime import datetime
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from laozhang_cli.errors import StorageError
from laozhang_cli.models import GenerationRequest
from laozhang_cli.services.storage import ImageStorage


def _request(tmp_path: Path, **overrides: object) -> GenerationRequest:
    return GenerationRequest.from_dict(
        {
            "model": "gpt-image-2",
            "system_prompt": "style",
            "prompt": "subject",
            "output_dir": str(tmp_path),
            **overrides,
        },
        tmp_path,
    )


def _png_bytes(size: tuple[int, int] = (7, 5)) -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", size, (255, 0, 0, 128)).save(buffer, "PNG")
    return buffer.getvalue()


def test_storage_converts_to_webp_with_project_quality_and_preserves_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    original_save = Image.Image.save

    def capturing_save(self, fp, format=None, **params):  # noqa: ANN001, ANN202
        if format == "WEBP":
            captured.update(params)
        return original_save(self, fp, format, **params)

    monkeypatch.setattr(Image.Image, "save", capturing_save)

    outputs = ImageStorage().save(
        _request(tmp_path, filename="city"),
        [(_png_bytes(), "image/png")],
    )

    target = tmp_path / "city.webp"
    assert outputs[0].path == str(target)
    assert outputs[0].format == "webp"
    assert captured == {"quality": 80, "method": 6}
    with Image.open(target) as converted:
        assert converted.format == "WEBP"
        assert converted.size == (7, 5)


def test_storage_preserves_raw_format_when_conversion_is_disabled(tmp_path: Path) -> None:
    data = _png_bytes()

    outputs = ImageStorage().save(
        _request(tmp_path, filename="city", convert_to_webp=False),
        [(data, "image/png")],
    )

    target = tmp_path / "city.png"
    assert target.read_bytes() == data
    assert outputs[0].path == str(target)
    assert outputs[0].format == "png"


def test_storage_never_overwrites_an_existing_file(tmp_path: Path) -> None:
    existing = tmp_path / "city.png"
    existing.write_bytes(b"existing")

    outputs = ImageStorage().save(
        _request(tmp_path, filename="city", convert_to_webp=False),
        [(_png_bytes(), "image/png")],
    )

    assert existing.read_bytes() == b"existing"
    assert outputs[0].path == str(tmp_path / "city-01.png")
    assert (tmp_path / "city-01.png").exists()


def test_storage_numbers_multiple_images(tmp_path: Path) -> None:
    outputs = ImageStorage().save(
        _request(tmp_path, filename="city", count=2, convert_to_webp=False),
        [(_png_bytes(), "image/png"), (_png_bytes(), "image/png")],
    )

    assert [image.path for image in outputs] == [
        str(tmp_path / "city-01.png"),
        str(tmp_path / "city-02.png"),
    ]


def test_storage_uses_local_timestamp_when_filename_is_omitted(tmp_path: Path) -> None:
    storage = ImageStorage(now=lambda: datetime(2026, 7, 22, 15, 30, 45))

    outputs = storage.save(
        _request(tmp_path, convert_to_webp=False),
        [(_png_bytes(), "image/png")],
    )

    assert outputs[0].path == str(tmp_path / "20260722_153045.png")


def test_storage_rejects_invalid_image_bytes(tmp_path: Path) -> None:
    with pytest.raises(StorageError, match="unable to decode image"):
        ImageStorage().save(
            _request(tmp_path),
            [(b"not-an-image", "image/png")],
        )
