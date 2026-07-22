import base64
import json
from pathlib import Path

import httpx
import pytest

from laozhang_cli.adapters.gpt_image import GptImageAdapter
from laozhang_cli.adapters.nano_banana import NanoBananaAdapter
from laozhang_cli.config import Settings
from laozhang_cli.errors import ApiError, StorageError
from laozhang_cli.models import GenerationRequest, OutputImage


class _Storage:
    def __init__(self) -> None:
        self.images: list[tuple[bytes, str | None]] = []

    def save(
        self,
        _request: GenerationRequest,
        images: list[tuple[bytes, str | None]],
    ) -> list[OutputImage]:
        self.images = images
        return [
            OutputImage(path=f"output/image-{index}.webp", format="webp")
            for index, _image in enumerate(images, start=1)
        ]


def _request(model: str, **overrides: object) -> GenerationRequest:
    return GenerationRequest.from_dict(
        {
            "model": model,
            "system_prompt": "cinematic style",
            "prompt": "a city",
            "negative_prompt": "blur",
            **overrides,
        },
        Path("."),
    )


def test_gpt_image_posts_expected_payload_and_decodes_base64() -> None:
    image_bytes = b"webp-image"
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200,
            json={"data": [{"b64_json": base64.b64encode(image_bytes).decode()}]},
        )

    storage = _Storage()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = GptImageAdapter(Settings("secret-key"), client, storage)  # type: ignore[arg-type]

    result = adapter.generate(
        _request("gpt-image-2", resolution="4K", aspect_ratio="9:16", count=2)
    )

    sent = captured["request"]
    assert isinstance(sent, httpx.Request)
    assert sent.url == "https://api.laozhang.ai/v1/images/generations"
    assert sent.headers["Authorization"] == "Bearer secret-key"
    assert json.loads(sent.content) == {
        "model": "gpt-image-2-vip",
        "prompt": "cinematic style\n\na city\n\n需要避免的内容：blur",
        "size": "2160x3840",
        "quality": "high",
        "output_format": "webp",
        "n": 2,
    }
    assert storage.images == [(image_bytes, "image/webp")]
    assert result.http_status == 200
    assert result.success is True


def test_gpt_image_downloads_url_without_forwarding_authorization() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(200, json={"data": [{"url": "https://cdn.test/image.png"}]})
        return httpx.Response(200, content=b"png-image", headers={"content-type": "image/png"})

    storage = _Storage()
    client = httpx.Client(transport=httpx.MockTransport(handler))

    GptImageAdapter(Settings("secret-key"), client, storage).generate(  # type: ignore[arg-type]
        _request("gpt-image-2")
    )

    assert requests[1].url == "https://cdn.test/image.png"
    assert "Authorization" not in requests[1].headers
    assert storage.images == [(b"png-image", "image/png")]


def test_gpt_image_preserves_structured_upstream_error_and_status() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(429, json={"error": {"message": "rate limited"}})
        )
    )

    with pytest.raises(ApiError, match="rate limited") as raised:
        GptImageAdapter(Settings("secret-key"), client, _Storage()).generate(  # type: ignore[arg-type]
            _request("gpt-image-2")
        )

    assert raised.value.http_status == 429


def test_gpt_image_maps_download_http_failure_to_storage_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"data": [{"url": "https://cdn.test/missing.png"}]})
        return httpx.Response(404, text="not found")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(StorageError, match="image download failed") as raised:
        GptImageAdapter(Settings("secret-key"), client, _Storage()).generate(  # type: ignore[arg-type]
            _request("gpt-image-2")
        )

    assert raised.value.http_status == 404


@pytest.mark.parametrize(
    ("model", "path"),
    [
        ("nano-banana-2", "/v1beta/models/gemini-3.1-flash-image:generateContent"),
        ("nano-banana-pro", "/v1beta/models/gemini-3-pro-image:generateContent"),
    ],
)
def test_nano_banana_posts_expected_payload_and_decodes_inline_data(
    model: str,
    path: str,
) -> None:
    captured: dict[str, httpx.Request] = {}
    image_bytes = b"png-image"

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "ignored"},
                                {
                                    "inline_data": {
                                        "mime_type": "image/png",
                                        "data": base64.b64encode(image_bytes).decode(),
                                    }
                                },
                            ]
                        }
                    }
                ]
            },
        )

    storage = _Storage()
    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = NanoBananaAdapter(Settings("secret-key"), client, storage).generate(  # type: ignore[arg-type]
        _request(model, resolution="4K", aspect_ratio="16:9", count=2)
    )

    sent = captured["request"]
    assert sent.url.path == path
    assert sent.headers["Authorization"] == "Bearer secret-key"
    assert json.loads(sent.content) == {
        "contents": [
            {
                "parts": [
                    {"text": "cinematic style\n\na city\n\n需要避免的内容：blur"}
                ]
            }
        ],
        "generationConfig": {
            "candidateCount": 2,
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": "16:9", "imageSize": "4K"},
        },
    }
    assert storage.images == [(image_bytes, "image/png")]
    assert result.success is True
    assert result.http_status == 200


def test_adapter_rejects_success_response_without_images() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"data": []}))
    )

    with pytest.raises(ApiError, match="did not contain an image") as raised:
        GptImageAdapter(Settings("secret-key"), client, _Storage()).generate(  # type: ignore[arg-type]
            _request("gpt-image-2")
        )

    assert raised.value.http_status == 200
