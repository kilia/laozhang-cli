from laozhang_cli.errors import ApiError
from laozhang_cli.models import GenerationRequest, GenerationResult


class GptImageAdapter:
    def generate(self, request: GenerationRequest) -> GenerationResult:
        raise ApiError("GPT Image API execution is not implemented in the skeleton")
