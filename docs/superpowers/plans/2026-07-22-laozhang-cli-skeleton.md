# laozhang-cli Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a testable, GitHub-ready Python CLI skeleton that validates normalized image-generation requests and routes them to provider adapter boundaries.

**Architecture:** The CLI loads an input JSON file and returns only a normalized JSON result on stdout. A generation service resolves provider adapters through a registry, while adapter and storage interfaces keep upstream protocols and local file work separate from command handling.

**Tech Stack:** Python 3.11+, uv, pytest, Ruff, standard library dataclasses and argparse.

## Global Constraints

- Use a `src/laozhang_cli` package layout and run the command with `uv run python -m laozhang_cli --input request.json`.
- The input schema uses README defaults: `resolution="2K"`, `aspect_ratio="16:9"`, `count=1`, `output_dir="output"`, `convert_to_webp=true`, and `negative_prompt=null`.
- `system_prompt` and `prompt` are required non-empty strings or `{ "file": "..." }`; prompt references are relative to the input JSON directory.
- stdout contains one JSON result only; all diagnostics go to stderr.
- Exit codes are 0 (success), 2 (input/validation), 3 (API), and 4 (image storage).
- The skeleton must not make network requests or create image files.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `pyproject.toml` | uv package metadata, pytest and Ruff configuration. |
| `src/laozhang_cli/models.py` | Immutable normalized request/result values and validation. |
| `src/laozhang_cli/errors.py` | Typed operational errors carrying process exit-code meaning. |
| `src/laozhang_cli/adapters/base.py` | Common provider adapter contract. |
| `src/laozhang_cli/adapters/{gpt_image,nano_banana,registry}.py` | Provider boundaries and model routing. |
| `src/laozhang_cli/services/generation.py` | Adapter selection and placeholder execution boundary. |
| `src/laozhang_cli/services/storage.py` | Future output-storage contract. |
| `src/laozhang_cli/{cli,__main__,config}.py` | Command entry point, output serialization, runtime configuration. |
| `tests/` | Behavioural tests mirroring package areas. |
| `.env.sample`, `.gitignore`, `examples/request.json` | Safe configuration and runnable example. |

### Task 1: Establish package tooling and repository hygiene

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.sample`, `src/laozhang_cli/__init__.py`, `examples/request.json`, `tests/test_package.py`

**Interfaces:**
- Produces: an importable `laozhang_cli` package and `uv run pytest` command.

- [ ] **Step 1: Write the failing package test**

```python
from laozhang_cli import __version__


def test_package_exposes_a_version() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_package.py -v`

Expected: FAIL because `laozhang_cli` cannot be imported.

- [ ] **Step 3: Add the minimal package and repository configuration**

```toml
# pyproject.toml
[project]
name = "laozhang-cli"
version = "0.1.0"
description = "A JSON-in/JSON-out CLI for api.laozhang.ai image models"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["-q"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.6"]
```

```python
# src/laozhang_cli/__init__.py
"""laozhang-cli package."""

__version__ = "0.1.0"
```

```gitignore
# .gitignore
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
*.py[cod]
build/
dist/
*.egg-info/
.env
output/
```

```dotenv
# .env.sample
LAOZHANG_KEY=
```

```json
{"model":"gpt-image-2","system_prompt":"Follow a cinematic visual style.","prompt":"A futuristic city at sunrise, viewed from above","resolution":"4K","aspect_ratio":"16:9"}
```

- [ ] **Step 4: Sync dependencies and verify the test**

Run: `uv sync --dev && uv run pytest tests/test_package.py -v && uv run ruff check .`

Expected: PASS; `uv.lock` is created; Ruff reports no violations.

- [ ] **Step 5: Commit the foundation**

```bash
git add pyproject.toml uv.lock .gitignore .env.sample examples/request.json src/laozhang_cli/__init__.py tests/test_package.py
git commit -m "build: initialize Python CLI package"
```

### Task 2: Add normalized request and result models

**Files:**
- Create: `src/laozhang_cli/models.py`, `src/laozhang_cli/errors.py`, `tests/test_models.py`

**Interfaces:**
- Consumes: raw JSON `dict[str, object]`.
- Produces: `GenerationRequest.from_dict(data, base_dir) -> GenerationRequest`, `GenerationResult`, `OutputImage`, and `InputValidationError`.

- [ ] **Step 1: Write failing model tests**

```python
from pathlib import Path

import pytest

from laozhang_cli.errors import InputValidationError
from laozhang_cli.models import GenerationRequest


def test_request_applies_readme_defaults() -> None:
    request = GenerationRequest.from_dict(
        {"model": "gpt-image-2", "system_prompt": "style", "prompt": "subject"}, Path(".")
    )
    assert (request.resolution, request.aspect_ratio, request.count) == ("2K", "16:9", 1)
    assert request.negative_prompt is None
    assert request.output_dir == Path("output")
    assert request.convert_to_webp is True


def test_request_rejects_unknown_keys() -> None:
    with pytest.raises(InputValidationError, match="unknown field: extra"):
        GenerationRequest.from_dict(
            {"model": "gpt-image-2", "system_prompt": "style", "prompt": "subject", "extra": 1},
            Path("."),
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_models.py -v`

Expected: FAIL because `laozhang_cli.models` does not exist.

- [ ] **Step 3: Implement the model boundary**

```python
# src/laozhang_cli/errors.py
class LaozhangCliError(Exception):
    exit_code = 1
    http_status: int | None = None


class InputValidationError(LaozhangCliError):
    exit_code = 2


class ApiError(LaozhangCliError):
    exit_code = 3


class StorageError(LaozhangCliError):
    exit_code = 4
```

```python
# src/laozhang_cli/models.py
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import InputValidationError

_ALLOWED = {"model", "system_prompt", "prompt", "negative_prompt", "resolution", "aspect_ratio", "count", "filename", "output_dir", "convert_to_webp"}

@dataclass(frozen=True)
class PromptValue:
    text: str | None = None
    file: Path | None = None

@dataclass(frozen=True)
class GenerationRequest:
    model: str; system_prompt: PromptValue; prompt: PromptValue; negative_prompt: PromptValue | None
    resolution: str; aspect_ratio: str; count: int; filename: str | None; output_dir: Path; convert_to_webp: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any], base_dir: Path) -> "GenerationRequest":
        unknown = set(data) - _ALLOWED
        if unknown: raise InputValidationError(f"unknown field: {sorted(unknown)[0]}")
        for key in ("model", "system_prompt", "prompt"):
            if key not in data: raise InputValidationError(f"missing required field: {key}")
        def prompt(key: str) -> PromptValue | None:
            value = data.get(key)
            if value is None: return None
            if isinstance(value, str) and value.strip(): return PromptValue(text=value)
            if isinstance(value, dict) and set(value) == {"file"} and isinstance(value["file"], str) and value["file"]: return PromptValue(file=base_dir / value["file"])
            raise InputValidationError(f"invalid prompt value: {key}")
        if not isinstance(data["model"], str) or not data["model"].strip(): raise InputValidationError("model must be a non-empty string")
        return cls(data["model"], prompt("system_prompt"), prompt("prompt"), prompt("negative_prompt"), data.get("resolution", "2K"), data.get("aspect_ratio", "16:9"), data.get("count", 1), data.get("filename"), Path(data.get("output_dir", "output")), data.get("convert_to_webp", True))

@dataclass(frozen=True)
class OutputImage:
    path: str; format: str

@dataclass(frozen=True)
class GenerationResult:
    success: bool; http_status: int | None; message: str; images: list[OutputImage]
```

- [ ] **Step 4: Verify models and formatting**

Run: `uv run pytest tests/test_models.py -v && uv run ruff check src tests`

Expected: PASS with no Ruff violations. Expand implementation only as required to enforce allowed resolution, aspect ratio, positive count, boolean conversion flag, and safe filename validation from README.

- [ ] **Step 5: Commit request and result contracts**

```bash
git add src/laozhang_cli/models.py src/laozhang_cli/errors.py tests/test_models.py
git commit -m "feat: add normalized request and result models"
```

### Task 3: Add adapters, model registry, and generation service

**Files:**
- Create: `src/laozhang_cli/adapters/__init__.py`, `src/laozhang_cli/adapters/base.py`, `src/laozhang_cli/adapters/gpt_image.py`, `src/laozhang_cli/adapters/nano_banana.py`, `src/laozhang_cli/adapters/registry.py`, `src/laozhang_cli/services/__init__.py`, `src/laozhang_cli/services/generation.py`, `tests/adapters/test_registry.py`, `tests/services/test_generation.py`

**Interfaces:**
- Consumes: `GenerationRequest`.
- Produces: `AdapterRegistry.get(model) -> ImageAdapter` and `GenerationService.generate(request) -> GenerationResult`.

- [ ] **Step 1: Write failing routing tests**

```python
import pytest
from laozhang_cli.adapters.gpt_image import GptImageAdapter
from laozhang_cli.adapters.nano_banana import NanoBananaAdapter
from laozhang_cli.adapters.registry import AdapterRegistry
from laozhang_cli.errors import ApiError

def test_registry_routes_gpt_image() -> None:
    assert isinstance(AdapterRegistry().get("gpt-image-2"), GptImageAdapter)

def test_registry_routes_nano_banana_models() -> None:
    registry = AdapterRegistry()
    assert isinstance(registry.get("nano-banana-2"), NanoBananaAdapter)
    assert isinstance(registry.get("nano-banana-pro"), NanoBananaAdapter)

def test_registry_rejects_unknown_model() -> None:
    with pytest.raises(ApiError, match="unsupported model"):
        AdapterRegistry().get("unknown")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/adapters/test_registry.py -v`

Expected: FAIL because the adapter package does not exist.

- [ ] **Step 3: Implement adapter and service boundaries**

```python
# src/laozhang_cli/adapters/base.py
from typing import Protocol
from laozhang_cli.models import GenerationRequest, GenerationResult

class ImageAdapter(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResult: ...
```

```python
# src/laozhang_cli/adapters/gpt_image.py
from laozhang_cli.errors import ApiError
from laozhang_cli.models import GenerationRequest, GenerationResult

class GptImageAdapter:
    def generate(self, request: GenerationRequest) -> GenerationResult:
        raise ApiError("GPT Image API execution is not implemented in the skeleton")
```

```python
# src/laozhang_cli/adapters/nano_banana.py
from laozhang_cli.errors import ApiError
from laozhang_cli.models import GenerationRequest, GenerationResult

class NanoBananaAdapter:
    def generate(self, request: GenerationRequest) -> GenerationResult:
        raise ApiError("Nano Banana API execution is not implemented in the skeleton")
```

```python
# src/laozhang_cli/adapters/registry.py
from laozhang_cli.errors import ApiError
from .gpt_image import GptImageAdapter
from .nano_banana import NanoBananaAdapter

class AdapterRegistry:
    def get(self, model: str):
        if model == "gpt-image-2": return GptImageAdapter()
        if model in {"nano-banana-2", "nano-banana-pro"}: return NanoBananaAdapter()
        raise ApiError(f"unsupported model: {model}")
```

```python
# src/laozhang_cli/services/generation.py
from laozhang_cli.adapters.registry import AdapterRegistry
from laozhang_cli.models import GenerationRequest, GenerationResult

class GenerationService:
    def __init__(self, registry: AdapterRegistry | None = None) -> None:
        self._registry = registry or AdapterRegistry()
    def generate(self, request: GenerationRequest) -> GenerationResult:
        return self._registry.get(request.model).generate(request)
```

- [ ] **Step 4: Verify adapters and placeholder service behaviour**

Run: `uv run pytest tests/adapters/test_registry.py tests/services/test_generation.py -v && uv run ruff check src tests`

Expected: PASS; add a generation-service test asserting the selected skeleton adapter raises `ApiError`.

- [ ] **Step 5: Commit generation boundaries**

```bash
git add src/laozhang_cli/adapters src/laozhang_cli/services/generation.py tests/adapters tests/services/test_generation.py
git commit -m "feat: add adapter registry and generation service"
```

### Task 4: Add storage and environment configuration boundaries

**Files:**
- Create: `src/laozhang_cli/config.py`, `src/laozhang_cli/services/storage.py`, `tests/test_config.py`, `tests/services/test_storage.py`

**Interfaces:**
- Produces: `Settings.from_environment() -> Settings` and `ImageStorage.allocate_paths(request, extension) -> list[Path]`.

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path
from laozhang_cli.models import GenerationRequest
from laozhang_cli.services.storage import ImageStorage

def test_storage_allocates_numbered_paths(tmp_path: Path) -> None:
    request = GenerationRequest.from_dict({"model":"gpt-image-2","system_prompt":"s","prompt":"p","filename":"city","count":2,"output_dir":str(tmp_path)}, tmp_path)
    assert ImageStorage().allocate_paths(request, "webp") == [tmp_path / "city-01.webp", tmp_path / "city-02.webp"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_config.py tests/services/test_storage.py -v`

Expected: FAIL because configuration and storage modules do not exist.

- [ ] **Step 3: Implement minimal local boundaries**

```python
# src/laozhang_cli/config.py
import os
from dataclasses import dataclass
from laozhang_cli.errors import ApiError

@dataclass(frozen=True)
class Settings:
    api_key: str
    @classmethod
    def from_environment(cls) -> "Settings":
        key = os.getenv("LAOZHANG_KEY", "")
        if not key: raise ApiError("LAOZHANG_KEY is not configured")
        return cls(api_key=key)
```

```python
# src/laozhang_cli/services/storage.py
from pathlib import Path
from laozhang_cli.models import GenerationRequest

class ImageStorage:
    def allocate_paths(self, request: GenerationRequest, extension: str) -> list[Path]:
        stem = request.filename or "generated"
        suffix = f".{extension.lstrip('.')}"
        if request.count == 1: return [request.output_dir / f"{stem}{suffix}"]
        return [request.output_dir / f"{stem}-{index:02d}{suffix}" for index in range(1, request.count + 1)]
```

- [ ] **Step 4: Verify configuration and allocation tests**

Run: `uv run pytest tests/test_config.py tests/services/test_storage.py -v`

Expected: PASS. Add tests for missing key and a one-image filename.

- [ ] **Step 5: Commit local boundaries**

```bash
git add src/laozhang_cli/config.py src/laozhang_cli/services/storage.py tests/test_config.py tests/services/test_storage.py
git commit -m "feat: add runtime configuration and storage boundary"
```

### Task 5: Implement JSON-only CLI behaviour

**Files:**
- Create: `src/laozhang_cli/cli.py`, `src/laozhang_cli/__main__.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `main(argv: list[str] | None = None) -> int`.
- Produces: one `GenerationResult` JSON object on stdout and the specified exit code.

- [ ] **Step 1: Write failing CLI tests**

```python
import json
from pathlib import Path
from laozhang_cli.cli import main

def test_cli_emits_json_for_invalid_input(tmp_path: Path, capsys) -> None:
    source = tmp_path / "request.json"; source.write_text("{}", encoding="utf-8")
    assert main(["--input", str(source)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result == {"success": False, "http_status": None, "message": "missing required field: model", "images": []}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`

Expected: FAIL because `laozhang_cli.cli` does not exist.

- [ ] **Step 3: Implement command handling**

```python
# src/laozhang_cli/cli.py
import argparse, json
from pathlib import Path
from typing import Any
from .errors import LaozhangCliError
from .models import GenerationRequest, GenerationResult
from .services.generation import GenerationService

def _payload(result: GenerationResult) -> dict[str, Any]:
    return {"success": result.success, "http_status": result.http_status, "message": result.message, "images": [{"path": image.path, "format": image.format} for image in result.images]}

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)
    try:
        source = Path(args.input); data = json.loads(source.read_text(encoding="utf-8"))
        request = GenerationRequest.from_dict(data, source.parent)
        result = GenerationService().generate(request)
        print(json.dumps(_payload(result), ensure_ascii=False)); return 0
    except LaozhangCliError as error:
        print(json.dumps({"success": False, "http_status": error.http_status, "message": str(error), "images": []}, ensure_ascii=False)); return error.exit_code
    except (OSError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "http_status": None, "message": str(error), "images": []}, ensure_ascii=False)); return 2
```

```python
# src/laozhang_cli/__main__.py
from .cli import main
raise SystemExit(main())
```

- [ ] **Step 4: Verify CLI contract and module execution**

Run: `uv run pytest tests/test_cli.py -v && uv run python -m laozhang_cli --input examples/request.json; uv run ruff check .`

Expected: invalid-input test passes; example prints a JSON API-boundary failure and exits with code 3; Ruff passes.

- [ ] **Step 5: Commit the runnable skeleton**

```bash
git add src/laozhang_cli/cli.py src/laozhang_cli/__main__.py tests/test_cli.py
git commit -m "feat: add JSON-only command-line interface"
```

### Task 6: Perform full verification and document current limits

**Files:**
- Modify: `README.md`

**Interfaces:**
- Produces: an accurate statement that the repository has a runnable skeleton but does not yet send API requests.

- [ ] **Step 1: Write a failing documentation acceptance check**

```python
from pathlib import Path

def test_readme_labels_api_execution_as_future_work() -> None:
    assert "当前代码骨架不会发起真实 API 请求" in Path("README.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the check to verify it fails**

Run: `uv run pytest tests/test_readme.py -v`

Expected: FAIL because the test file and README statement do not exist.

- [ ] **Step 3: Add the test and README note**

```markdown
## 当前实现状态

当前代码骨架已经提供输入校验、模型路由、JSON 输出与测试结构；不会发起真实 API 请求、下载图片或执行 WebP 转换。这些能力将在后续实现中接入既定的适配器和存储接口。
```

- [ ] **Step 4: Run the complete verification suite**

Run: `uv run pytest && uv run ruff check . && uv run python -m laozhang_cli --input examples/request.json`

Expected: pytest and Ruff pass; the example emits a valid failure JSON and returns exit code 3.

- [ ] **Step 5: Commit documentation and final verification**

```bash
git add README.md tests/test_readme.py
git commit -m "docs: describe current skeleton capabilities"
```

