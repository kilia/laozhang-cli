from laozhang_cli.adapters.registry import AdapterRegistry
from laozhang_cli.models import GenerationRequest, GenerationResult


class GenerationService:
    def __init__(self, registry: AdapterRegistry | None = None) -> None:
        self._registry = registry if registry is not None else AdapterRegistry()

    def generate(self, request: GenerationRequest) -> GenerationResult:
        adapter = self._registry.get(request.model)
        return adapter.generate(request)
