from pathlib import Path

import httpx
import pytest

from laozhang_cli.adapters.gpt_image import GptImageAdapter
from laozhang_cli.config import Settings
from laozhang_cli.errors import ApiError
from laozhang_cli.models import GenerationRequest


def test_upstream_error_cannot_echo_api_key() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                401,
                json={"error": {"message": "credential secret-key is invalid"}},
            )
        )
    )
    request = GenerationRequest.from_dict(
        {
            "model": "gpt-image-2",
            "system_prompt": "style",
            "prompt": "subject",
        },
        Path("."),
    )

    with pytest.raises(ApiError) as raised:
        GptImageAdapter(Settings("secret-key"), client).generate(request)

    assert "secret-key" not in str(raised.value)
    assert "[redacted]" in str(raised.value)
