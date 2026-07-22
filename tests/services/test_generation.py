from pathlib import Path

import pytest

from laozhang_cli.errors import ApiError
from laozhang_cli.models import GenerationRequest
from laozhang_cli.services.generation import GenerationService


@pytest.mark.parametrize(
    ("model", "message"),
    [
        ("gpt-image-2", "GPT Image API execution is not implemented in the skeleton"),
        ("nano-banana-2", "Nano Banana API execution is not implemented in the skeleton"),
        ("nano-banana-pro", "Nano Banana API execution is not implemented in the skeleton"),
    ],
)
def test_generation_service_raises_placeholder_error_for_supported_model(
    model: str,
    message: str,
) -> None:
    request = GenerationRequest.from_dict(
        {
            "model": model,
            "system_prompt": "style",
            "prompt": "subject",
        },
        Path("."),
    )

    with pytest.raises(ApiError, match=message):
        GenerationService().generate(request)
