from laozhang_cli.errors import ApiError
from laozhang_cli.models import GenerationRequest, GenerationResult


class NanoBananaAdapter:
    def generate(self, request: GenerationRequest) -> GenerationResult:
        raise ApiError("Nano Banana API execution is not implemented in the skeleton")
