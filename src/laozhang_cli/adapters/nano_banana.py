from typing import Any

import httpx

from laozhang_cli.config import Settings
from laozhang_cli.errors import ApiError
from laozhang_cli.models import GenerationRequest, GenerationResult
from laozhang_cli.services.storage import ImageStorage

from .http import compose_prompt, decode_base64, download_image, post_json

_ENDPOINTS = {
    "nano-banana-2": (
        "https://api.laozhang.ai/v1beta/models/"
        "gemini-3.1-flash-image:generateContent"
    ),
    "nano-banana-pro": (
        "https://api.laozhang.ai/v1beta/models/"
        "gemini-3-pro-image:generateContent"
    ),
}


class NanoBananaAdapter:
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
        settings = self._settings or Settings.from_environment()
        client = self._client or httpx.Client(timeout=120.0, proxy=settings.proxy)
        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": compose_prompt(request)}]}],
            "generationConfig": {
                "candidateCount": request.count,
                "responseModalities": ["IMAGE"],
                "imageConfig": {
                    "aspectRatio": request.aspect_ratio,
                    "imageSize": request.resolution,
                },
            },
        }
        response, body = post_json(
            client,
            _ENDPOINTS[request.model],
            settings.api_key,
            payload,
        )
        images = self._extract_images(body, client, response.status_code)
        if not images:
            raise ApiError(
                "API response did not contain an image",
                http_status=response.status_code,
            )
        outputs = self._storage.save(request, images)
        return GenerationResult(True, response.status_code, "Image generated successfully", outputs)

    @staticmethod
    def _extract_images(
        body: Any,
        client: httpx.Client,
        http_status: int,
    ) -> list[tuple[bytes, str | None]]:
        images: list[tuple[bytes, str | None]] = []
        candidates = body.get("candidates") if isinstance(body, dict) else None
        if not isinstance(candidates, list):
            return images
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            parts = content.get("parts") if isinstance(content, dict) else None
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not isinstance(part, dict):
                    continue
                inline = part.get("inlineData") or part.get("inline_data")
                if isinstance(inline, dict) and isinstance(inline.get("data"), str):
                    mime_type = inline.get("mimeType") or inline.get("mime_type")
                    images.append(
                        (
                            decode_base64(inline["data"], http_status),
                            mime_type if isinstance(mime_type, str) else None,
                        )
                    )
                    continue
                file_data = part.get("fileData") or part.get("file_data")
                if isinstance(file_data, dict):
                    url = file_data.get("fileUri") or file_data.get("file_uri")
                    if isinstance(url, str):
                        images.append(download_image(client, url))
        return images
