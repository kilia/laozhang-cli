import pytest

from laozhang_cli.adapters.gpt_image import GptImageAdapter
from laozhang_cli.adapters.nano_banana import NanoBananaAdapter
from laozhang_cli.adapters.registry import AdapterRegistry
from laozhang_cli.errors import ApiError


def test_registry_routes_gpt_image() -> None:
    adapter = AdapterRegistry().get("gpt-image-2")

    assert isinstance(adapter, GptImageAdapter)


@pytest.mark.parametrize("model", ["nano-banana-2", "nano-banana-pro"])
def test_registry_routes_nano_banana_models(model: str) -> None:
    adapter = AdapterRegistry().get(model)

    assert isinstance(adapter, NanoBananaAdapter)


def test_registry_rejects_unknown_model() -> None:
    with pytest.raises(ApiError, match="unsupported model: unknown"):
        AdapterRegistry().get("unknown")
