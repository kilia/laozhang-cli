import base64
import binascii
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from laozhang_cli.errors import ApiError, InputValidationError, StorageError
from laozhang_cli.models import GenerationRequest


def compose_prompt(request: GenerationRequest) -> str:
    if request.system_prompt.text is None or request.prompt.text is None:
        raise ApiError("prompt files were not resolved")
    parts = [request.system_prompt.text, request.prompt.text]
    if request.negative_prompt is not None:
        if request.negative_prompt.text is None:
            raise ApiError("prompt files were not resolved")
        parts.append(f"需要避免的内容：{request.negative_prompt.text}")
    return "\n\n".join(parts)


def post_json(
    client: httpx.Client,
    url: str,
    api_key: str,
    payload: dict[str, Any],
) -> tuple[httpx.Response, Any]:
    try:
        response = client.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    except httpx.RequestError as error:
        raise ApiError("API request failed") from error

    if not response.is_success:
        message = _error_message(response).replace(api_key, "[redacted]")
        raise ApiError(message, http_status=response.status_code)
    try:
        return response, response.json()
    except ValueError as error:
        raise ApiError("API returned invalid JSON", http_status=response.status_code) from error


def post_multipart(
    client: httpx.Client,
    url: str,
    api_key: str,
    data: dict[str, str],
    files: list[tuple[str, tuple[str, bytes, str]]],
) -> tuple[httpx.Response, Any]:
    try:
        response = client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            data=data,
            files=files,
        )
    except httpx.RequestError as error:
        raise ApiError("API request failed") from error

    if not response.is_success:
        message = _error_message(response).replace(api_key, "[redacted]")
        raise ApiError(message, http_status=response.status_code)
    try:
        return response, response.json()
    except ValueError as error:
        raise ApiError("API returned invalid JSON", http_status=response.status_code) from error


def load_reference_images(paths: tuple[Path, ...]) -> list[tuple[str, bytes, str]]:
    images: list[tuple[str, bytes, str]] = []
    for path in paths:
        try:
            data = path.read_bytes()
        except OSError as error:
            raise InputValidationError(f"unable to read reference image: {path}") from error
        if not data:
            raise InputValidationError(f"reference image is empty: {path}")
        mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        images.append((path.name, data, mime_type))
    return images


def decode_base64(value: str, http_status: int) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ApiError("API returned invalid base64 image data", http_status=http_status) from error


def download_image(client: httpx.Client, url: str) -> tuple[bytes, str | None]:
    try:
        response = client.get(url)
    except httpx.RequestError as error:
        raise StorageError("image download failed") from error
    if not response.is_success:
        raise StorageError("image download failed", http_status=response.status_code)
    if not response.content:
        raise StorageError("downloaded image was empty", http_status=response.status_code)
    mime_type = response.headers.get("content-type")
    if mime_type is not None:
        mime_type = mime_type.partition(";")[0].strip() or None
    return response.content, mime_type


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
        if isinstance(body.get("message"), str):
            return body["message"]
    text = response.text.strip()
    return text[:500] if text else f"API request failed with HTTP {response.status_code}"
