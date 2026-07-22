from collections.abc import Callable
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from laozhang_cli.errors import StorageError
from laozhang_cli.models import GenerationRequest, OutputImage

_EXTENSIONS = {
    "BMP": "bmp",
    "GIF": "gif",
    "JPEG": "jpg",
    "PNG": "png",
    "TIFF": "tiff",
    "WEBP": "webp",
}


class ImageStorage:
    def __init__(self, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or datetime.now

    def allocate_paths(self, request: GenerationRequest, extension: str) -> list[Path]:
        stem = request.filename or self._now().strftime("%Y%m%d_%H%M%S")
        suffix = f".{extension.lstrip('.')}"
        if request.count == 1:
            return [request.output_dir / f"{stem}{suffix}"]
        return [
            request.output_dir / f"{stem}-{index:02d}{suffix}"
            for index in range(1, request.count + 1)
        ]

    def save(
        self,
        request: GenerationRequest,
        images: list[tuple[bytes, str | None]],
    ) -> list[OutputImage]:
        if not images:
            raise StorageError("no images to save")

        prepared = [self._prepare(data, request.convert_to_webp) for data, _mime in images]
        try:
            request.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise StorageError("unable to create output directory") from error

        stem = request.filename or self._now().strftime("%Y%m%d_%H%M%S")
        multiple = len(prepared) > 1
        outputs: list[OutputImage] = []
        created: list[Path] = []
        try:
            for index, (data, extension) in enumerate(prepared, start=1):
                path = self._write_exclusive(
                    request.output_dir,
                    stem,
                    extension,
                    index=index,
                    multiple=multiple,
                    data=data,
                )
                created.append(path)
                outputs.append(OutputImage(path=str(path), format=extension))
        except StorageError:
            for path in created:
                try:
                    path.unlink()
                except OSError:
                    pass
            raise
        return outputs

    def _prepare(self, data: bytes, convert_to_webp: bool) -> tuple[bytes, str]:
        try:
            with Image.open(BytesIO(data)) as source:
                source.load()
                source_format = source.format
                if source_format is None or source_format not in _EXTENSIONS:
                    raise StorageError("unsupported image format")
                if not convert_to_webp:
                    return data, _EXTENSIONS[source_format]
                if source_format == "WEBP":
                    return data, "webp"

                converted = source
                if source.mode not in {"RGB", "RGBA"}:
                    has_alpha = "A" in source.getbands() or "transparency" in source.info
                    converted = source.convert("RGBA" if has_alpha else "RGB")
                output = BytesIO()
                converted.save(output, "WEBP", quality=80, method=6)
                return output.getvalue(), "webp"
        except StorageError:
            raise
        except (OSError, UnidentifiedImageError, ValueError) as error:
            raise StorageError("unable to decode image") from error

    @staticmethod
    def _write_exclusive(
        output_dir: Path,
        stem: str,
        extension: str,
        *,
        index: int,
        multiple: bool,
        data: bytes,
    ) -> Path:
        suffix_number = index if multiple else 0
        while True:
            numbered = f"-{suffix_number:02d}" if suffix_number else ""
            candidate = output_dir / f"{stem}{numbered}.{extension}"
            try:
                with candidate.open("xb") as destination:
                    destination.write(data)
                return candidate
            except FileExistsError:
                suffix_number = max(1, suffix_number + 1)
            except OSError as error:
                raise StorageError("unable to save image") from error
