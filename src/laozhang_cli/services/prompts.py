from dataclasses import replace

from laozhang_cli.errors import InputValidationError
from laozhang_cli.models import GenerationRequest, PromptValue


def _resolve(value: PromptValue | None) -> PromptValue | None:
    if value is None or value.file is None:
        return value

    try:
        text = value.file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise InputValidationError(f"unable to read prompt file: {value.file}") from error

    if not text.strip():
        raise InputValidationError(f"prompt file is empty: {value.file}")
    return PromptValue(text=text)


def resolve_prompts(request: GenerationRequest) -> GenerationRequest:
    system_prompt = _resolve(request.system_prompt)
    prompt = _resolve(request.prompt)
    assert system_prompt is not None
    assert prompt is not None
    return replace(
        request,
        system_prompt=system_prompt,
        prompt=prompt,
        negative_prompt=_resolve(request.negative_prompt),
    )
