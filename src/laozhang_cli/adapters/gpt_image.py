from typing import Any

import httpx

from laozhang_cli.config import Settings
from laozhang_cli.errors import ApiError
from laozhang_cli.models import GenerationRequest, GenerationResult
from laozhang_cli.services.storage import ImageStorage

from .http import (
    compose_prompt,
    decode_base64,
    download_image,
    load_reference_images,
    post_json,
    post_multipart,
)

_ENDPOINT = "https://api.laozhang.ai/v1/images/generations"
_EDIT_ENDPOINT = "https://api2.laozhang.ai/v1/images/edits"
_TIMEOUT_SECONDS = 300.0
_SIZES = {
    ("1K", "16:9"): "1024x576",
    ("1K", "4:3"): "1024x768",
    ("1K", "1:1"): "1024x1024",
    ("1K", "3:4"): "768x1024",
    ("1K", "9:16"): "576x1024",
    ("2K", "16:9"): "2048x1152",
    ("2K", "4:3"): "2048x1536",
    ("2K", "1:1"): "2048x2048",
    ("2K", "3:4"): "1536x2048",
    ("2K", "9:16"): "1152x2048",
    ("4K", "16:9"): "3840x2160",
    ("4K", "4:3"): "3840x2880",
    ("4K", "1:1"): "3840x3840",
    ("4K", "3:4"): "2880x3840",
    ("4K", "9:16"): "2160x3840",
}


class GptImageAdapter:
    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        storage: ImageStorage | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._storage = storage or ImageStorage()

    def generate(self, request: GenerationRequest) -> GenerationResult:
        references = load_reference_images(request.reference_images)
        settings = self._settings or Settings.from_environment()
        client = self._client or httpx.Client(timeout=_TIMEOUT_SECONDS, proxy=settings.proxy)
        payload: dict[str, Any] = {
            "model": "gpt-image-2-vip",
            "prompt": compose_prompt(request),
            "size": _SIZES[(request.resolution, request.aspect_ratio)],
            "quality": request.quality,
            "output_format": "webp",
            "n": request.count,
        }
        if request.reference_images:
            multipart_data = {key: str(value) for key, value in payload.items()}
            files = [("image", reference) for reference in references]
            response, body = post_multipart(
                client,
                _EDIT_ENDPOINT,
                settings.api_key,
                multipart_data,
                files,
            )
        else:
            response, body = post_json(client, _ENDPOINT, settings.api_key, payload)
        images: list[tuple[bytes, str | None]] = []
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                encoded = item.get("b64_json")
                if isinstance(encoded, str):
                    images.append((decode_base64(encoded, response.status_code), "image/webp"))
                    continue
                url = item.get("url")
                if isinstance(url, str):
                    images.append(download_image(client, url))
        if not images:
            raise ApiError(
                "API response did not contain an image",
                http_status=response.status_code,
            )
        outputs = self._storage.save(request, images)
        return GenerationResult(True, response.status_code, "Image generated successfully", outputs)
