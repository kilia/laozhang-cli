from typing import Protocol

from laozhang_cli.models import GenerationRequest, GenerationResult


class ImageAdapter(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResult: ...
