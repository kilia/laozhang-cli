from pathlib import Path

import httpx
import pytest

from laozhang_cli.adapters.registry import AdapterRegistry
from laozhang_cli.config import Settings
from laozhang_cli.errors import ApiError
from laozhang_cli.models import GenerationRequest
from laozhang_cli.services.generation import GenerationService


@pytest.mark.parametrize("model", ["gpt-image-2", "nano-banana-2", "nano-banana-pro"])
def test_generation_service_routes_supported_models_without_real_network(model: str) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(503, json={"message": "maintenance"})
        )
    )
    registry = AdapterRegistry(settings=Settings("test-key"), client=client)
    request = GenerationRequest.from_dict(
        {
            "model": model,
            "system_prompt": "style",
            "prompt": "subject",
        },
        Path("."),
    )

    with pytest.raises(ApiError, match="maintenance") as raised:
        GenerationService(registry=registry).generate(request)

    assert raised.value.http_status == 503
