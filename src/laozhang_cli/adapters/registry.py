import httpx

from laozhang_cli.config import Settings
from laozhang_cli.errors import ApiError
from laozhang_cli.services.storage import ImageStorage

from .base import ImageAdapter
from .gpt_image import GptImageAdapter
from .nano_banana import NanoBananaAdapter


class AdapterRegistry:
    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        storage: ImageStorage | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._storage = storage

    def get(self, model: str) -> ImageAdapter:
        dependencies = (self._settings, self._client, self._storage)
        if model == "gpt-image-2":
            return GptImageAdapter(*dependencies)
        if model in {"nano-banana-2", "nano-banana-pro"}:
            return NanoBananaAdapter(*dependencies)
        raise ApiError(f"unsupported model: {model}")
