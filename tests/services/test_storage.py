from pathlib import Path

from laozhang_cli.models import GenerationRequest
from laozhang_cli.services.storage import ImageStorage


def make_request(tmp_path: Path, **overrides: object) -> GenerationRequest:
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


def test_storage_allocates_numbered_paths(tmp_path: Path) -> None:
    request = make_request(tmp_path, filename="city", count=2)

    assert ImageStorage().allocate_paths(request, "webp") == [
        tmp_path / "city-01.webp",
        tmp_path / "city-02.webp",
    ]


def test_storage_allocates_single_image_filename(tmp_path: Path) -> None:
    request = make_request(tmp_path, filename="city")

    assert ImageStorage().allocate_paths(request, ".png") == [tmp_path / "city.png"]
