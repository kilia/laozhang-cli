from pathlib import Path

from laozhang_cli.models import GenerationRequest


class ImageStorage:
    def allocate_paths(self, request: GenerationRequest, extension: str) -> list[Path]:
        stem = request.filename or "generated"
        suffix = f".{extension.lstrip('.')}"
        if request.count == 1:
            return [request.output_dir / f"{stem}{suffix}"]
        return [
            request.output_dir / f"{stem}-{index:02d}{suffix}"
            for index in range(1, request.count + 1)
        ]
