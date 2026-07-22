# Real API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the placeholder adapters with testable real HTTP generation, response decoding, prompt resolution, and safe local image persistence.

**Architecture:** `GenerationService` resolves prompt files before selecting a protocol adapter. Adapters receive injected `httpx.Client`, settings, and storage dependencies, translate requests, decode base64 or download URL results, and delegate bytes plus MIME metadata to shared storage. Domain exceptions retain the upstream HTTP status and let the CLI preserve its single-JSON stdout and exit-code contract.

**Tech Stack:** Python 3.11+, httpx, python-dotenv, Pillow, pytest, Ruff

## Global Constraints

- Load `LAOZHANG_KEY` from the process environment or the working-directory `.env` without overriding an existing environment variable.
- Never include credentials or authorization headers in errors or output.
- API errors exit 3; prompt/input errors exit 2; image download/save/convert errors exit 4.
- WebP conversion uses `quality=80` and `method=6` without resizing.
- Never overwrite an existing output image.

---

### Task 1: Configuration and prompt resolution

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/laozhang_cli/config.py`
- Create: `src/laozhang_cli/services/prompts.py`
- Test: `tests/test_config.py`
- Test: `tests/services/test_prompts.py`

**Interfaces:**
- Consumes: `GenerationRequest` and `PromptValue`
- Produces: `Settings.from_environment(env_file: Path | None = None)` and `resolve_prompts(request: GenerationRequest) -> GenerationRequest`

- [ ] **Step 1: Write failing tests** for `.env` loading/preference and UTF-8 prompt resolution relative to the request file.
- [ ] **Step 2: Run tests to verify they fail:** `uv run pytest tests/test_config.py tests/services/test_prompts.py -q`.
- [ ] **Step 3: Implement minimal configuration and resolver code**, converting filesystem failures to `InputValidationError` without exposing file contents.
- [ ] **Step 4: Run the focused tests to verify they pass.**

### Task 2: Protocol adapters and HTTP errors

**Files:**
- Modify: `src/laozhang_cli/errors.py`
- Modify: `src/laozhang_cli/adapters/gpt_image.py`
- Modify: `src/laozhang_cli/adapters/nano_banana.py`
- Modify: `src/laozhang_cli/adapters/registry.py`
- Modify: `src/laozhang_cli/services/generation.py`
- Create: `src/laozhang_cli/adapters/http.py`
- Test: `tests/adapters/test_gpt_image.py`
- Test: `tests/adapters/test_nano_banana.py`
- Test: `tests/services/test_generation.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: injected `httpx.Client`, `Settings`, and `ImageStorage`
- Produces: adapters that POST exact protocol payloads and turn base64/URL response images into saved `OutputImage` objects

- [ ] **Step 1: Write failing tests** for headers, GPT size mapping, Nano model endpoints, prompt composition, base64/URL decoding, structured error messages/statuses, and transport failures.
- [ ] **Step 2: Run tests to verify expected failures:** `uv run pytest tests/adapters tests/services/test_generation.py tests/test_cli.py -q`.
- [ ] **Step 3: Implement the minimal injected HTTP transport and adapter behavior.**
- [ ] **Step 4: Run focused tests and confirm all pass.**

### Task 3: Collision-safe image storage and WebP conversion

**Files:**
- Modify: `src/laozhang_cli/services/storage.py`
- Test: `tests/services/test_storage.py`

**Interfaces:**
- Consumes: image bytes plus optional MIME type
- Produces: `ImageStorage.save(request, images) -> list[OutputImage]`

- [ ] **Step 1: Write failing tests** for raw saves, existing-file collisions, timestamp names, multi-image numbering, invalid bytes, and Pillow WebP conversion preserving dimensions.
- [ ] **Step 2: Run storage tests to verify expected failures:** `uv run pytest tests/services/test_storage.py -q`.
- [ ] **Step 3: Implement MIME/format detection, in-memory conversion, directory creation, and exclusive output writes.**
- [ ] **Step 4: Run storage tests and confirm all pass.**
- [ ] **Step 5: Run full verification:** `uv run pytest` and `uv run ruff check .`.
- [ ] **Step 6: Review the diff for secrets and commit the complete implementation.**
