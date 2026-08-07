import base64
import json
from pathlib import Path

import httpx
import pytest

from laozhang_cli.adapters.gpt_image import GptImageAdapter
from laozhang_cli.adapters.nano_banana import NanoBananaAdapter
from laozhang_cli.config import Settings
from laozhang_cli.errors import ApiError, InputValidationError, StorageError
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
        _request(
            "gpt-image-2",
            resolution="4K",
            aspect_ratio="9:16",
            quality="medium",
            count=2,
        )
    )

    sent = captured["request"]
    assert isinstance(sent, httpx.Request)
    assert sent.url == "https://api.laozhang.ai/v1/images/generations"
    assert sent.headers["Authorization"] == "Bearer secret-key"
    assert json.loads(sent.content) == {
        "model": "gpt-image-2-vip",
        "prompt": "cinematic style\n\na city\n\n需要避免的内容：blur",
        "size": "2160x3840",
        "quality": "medium",
        "output_format": "webp",
        "n": 2,
    }
    assert storage.images == [(image_bytes, "image/webp")]
    assert result.http_status == 200
    assert result.success is True


def test_gpt_image_edit_posts_multiple_reference_images_as_multipart(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.jpg"
    first.write_bytes(b"first-image")
    second.write_bytes(b"second-image")
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200,
            json={"data": [{"b64_json": base64.b64encode(b"edited-image").decode()}]},
        )

    storage = _Storage()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    GptImageAdapter(Settings("secret-key"), client, storage).generate(  # type: ignore[arg-type]
        _request("gpt-image-2", reference_images=[str(first), str(second)])
    )

    sent = captured["request"]
    assert sent.url == "https://api2.laozhang.ai/v1/images/edits"
    assert sent.headers["Authorization"] == "Bearer secret-key"
    assert sent.headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert sent.content.count(b'name="image"') == 2
    assert b'filename="first.png"' in sent.content
    assert b'filename="second.jpg"' in sent.content
    assert b"first-image" in sent.content
    assert b"second-image" in sent.content
    assert storage.images == [(b"edited-image", "image/webp")]


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
        _request(model, resolution="4K", aspect_ratio="16:9", quality="medium", count=2)
    )

    sent = captured["request"]
    assert sent.url.path == path
    assert sent.headers["Authorization"] == "Bearer secret-key"
    assert json.loads(sent.content) == {
        "contents": [{"parts": [{"text": "cinematic style\n\na city\n\n需要避免的内容：blur"}]}],
        "generationConfig": {
            "candidateCount": 2,
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": "16:9", "imageSize": "4K"},
        },
    }
    assert storage.images == [(image_bytes, "image/png")]
    assert result.success is True
    assert result.http_status == 200


@pytest.mark.parametrize(
    ("model", "path"),
    [
        ("nano-banana-2", "/v1beta/models/gemini-3.1-flash-image:generateContent"),
        ("nano-banana-pro", "/v1beta/models/gemini-3-pro-image:generateContent"),
    ],
)
def test_nano_banana_edit_embeds_multiple_reference_images(
    tmp_path: Path,
    model: str,
    path: str,
) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.webp"
    first.write_bytes(b"first-image")
    second.write_bytes(b"second-image")
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "image/png",
                                        "data": base64.b64encode(b"edited-image").decode(),
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    NanoBananaAdapter(Settings("secret-key"), client, _Storage()).generate(  # type: ignore[arg-type]
        _request(model, reference_images=[str(first), str(second)])
    )

    sent = captured["request"]
    assert sent.url.host == "api2.laozhang.ai"
    assert sent.url.path == path
    parts = json.loads(sent.content)["contents"][0]["parts"]
    assert parts[1:] == [
        {
            "inline_data": {
                "mime_type": "image/png",
                "data": base64.b64encode(b"first-image").decode(),
            }
        },
        {
            "inline_data": {
                "mime_type": "image/webp",
                "data": base64.b64encode(b"second-image").decode(),
            }
        },
    ]


def test_adapter_rejects_missing_reference_image_before_http(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP request should not be sent")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(InputValidationError, match="unable to read reference image"):
        NanoBananaAdapter(Settings("secret-key"), client, _Storage()).generate(  # type: ignore[arg-type]
            _request("nano-banana-2", reference_images=[str(tmp_path / "missing.png")])
        )


def test_adapter_rejects_success_response_without_images() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"data": []}))
    )

    with pytest.raises(ApiError, match="did not contain an image") as raised:
        GptImageAdapter(Settings("secret-key"), client, _Storage()).generate(  # type: ignore[arg-type]
            _request("gpt-image-2")
        )

    assert raised.value.http_status == 200
