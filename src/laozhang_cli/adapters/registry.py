from laozhang_cli.errors import ApiError

from .base import ImageAdapter
from .gpt_image import GptImageAdapter
from .nano_banana import NanoBananaAdapter


class AdapterRegistry:
    def get(self, model: str) -> ImageAdapter:
        if model == "gpt-image-2":
            return GptImageAdapter()

        if model in {"nano-banana-2", "nano-banana-pro"}:
            return NanoBananaAdapter()

        raise ApiError(f"unsupported model: {model}")
