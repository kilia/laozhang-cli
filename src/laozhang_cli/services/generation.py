from laozhang_cli.adapters.registry import AdapterRegistry
from laozhang_cli.models import GenerationRequest, GenerationResult
from laozhang_cli.services.prompts import resolve_prompts


class GenerationService:
    def __init__(self, registry: AdapterRegistry | None = None) -> None:
        self._registry = registry if registry is not None else AdapterRegistry()

    def generate(self, request: GenerationRequest) -> GenerationResult:
        resolved_request = resolve_prompts(request)
        adapter = self._registry.get(resolved_request.model)
        return adapter.generate(resolved_request)
