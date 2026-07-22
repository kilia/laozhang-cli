# Laozhang CLI Image Generation Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and install a cross-platform Codex skill that uses independent `laozhang-cli` subprocesses for bounded concurrent image generation and requires visual quality inspection without automatic retries.

**Architecture:** Keep the repository-local skill as the canonical source. A standard-library Python orchestrator expands one request template into independent single-image CLI jobs, runs them with a bounded executor, and emits one aggregate JSON result; a separate Python installer copies the skill into the user's Codex skill directory and records the CLI checkout. Codex owns prompt interpretation and visual inspection, while all API, adapter, storage, and WebP behavior remains in `laozhang-cli`.

**Tech Stack:** Python 3.11+, Python standard library, existing `uv`/`laozhang-cli`, pytest, Codex skill Markdown/YAML.

## Global Constraints

- The skill name is `generating-images-with-laozhang-cli`.
- The repository source is `.codex/skills/generating-images-with-laozhang-cli/`.
- The default model is exactly `nano-banana-2`.
- The default concurrency limit is exactly 4; `--concurrency` accepts any positive integer.
- Batch count means independent CLI invocations, each with request-level `count` set to 1.
- Use Python process and file APIs only; never invoke a shell or rely on Bash, PowerShell, WSL, Git Bash, pipes, redirection, or shell quoting.
- Never retry a failed or low-quality generation automatically.
- Never put `LAOZHANG_KEY` in request JSON, arguments, output, logs, or installed skill files.
- Run each CLI subprocess from the resolved checkout so its existing root `.env` is loaded.
- Preserve each CLI exit code, `http_status`, message, elapsed time, and image path.
- Codex must inspect every successfully generated image and explicitly warn about extensive garbled, distorted, invented, or unreadable Chinese text.

## File Map

- Create `.codex/skills/generating-images-with-laozhang-cli/SKILL.md`: concise agent workflow and mandatory quality-report contract.
- Create `.codex/skills/generating-images-with-laozhang-cli/agents/openai.yaml`: UI name, description, and `$generating-images-with-laozhang-cli` default prompt.
- Create `.codex/skills/generating-images-with-laozhang-cli/references/request-format.md`: public request fields, models, outputs, errors, and invocation examples.
- Create `.codex/skills/generating-images-with-laozhang-cli/scripts/generate.py`: request expansion, checkout resolution, subprocess concurrency, aggregation, and cleanup.
- Create `.codex/skills/generating-images-with-laozhang-cli/scripts/install.py`: personal installation and local checkout configuration.
- Create `tests/skill/test_generate.py`: orchestrator unit and subprocess-contract tests.
- Create `tests/skill/test_install.py`: installer tests.
- Create `tests/skill/scenarios.md`: baseline and skill-enabled behavioral scenario evidence.
- Modify `README.md`: add concise repository-local and personal installation usage.

---

### Task 1: Record Failing Baseline Skill Scenarios

**Files:**
- Create: `tests/skill/scenarios.md`

**Interfaces:**
- Consumes: the current repository README and examples, without the new skill.
- Produces: three exact prompts and recorded baseline observations used to shape `SKILL.md`.

- [ ] **Step 1: Create three baseline prompts**

Use these exact scenarios:

```text
Generate one 16:9 image for a Chinese product launch poster using laozhang-cli. The title must be “智启未来”.

Use laozhang-cli to generate 6 independent variants of the same Chinese PPT cover. Run at most 2 at once and summarize all results.

Use laozhang-cli to generate an image containing several Chinese labels. After generation, tell me whether the Chinese text is readable. Do not regenerate it.
```

- [ ] **Step 2: Run each prompt without loading the new skill**

Run each scenario in a fresh, read-only Codex execution from the repository root and save the raw responses outside the future skill directory:

```text
codex exec --ephemeral --sandbox read-only "<exact scenario text>"
```

Expected baseline evidence: at least one response lacks one or more required behaviors such as explicit `nano-banana-2` selection, bounded independent subprocesses, per-image aggregation, mandatory image inspection, Chinese corruption warnings, or the no-retry rule. If all three unexpectedly satisfy the entire contract, add a fourth scenario combining count 8, concurrency 3, one simulated failure, and quality inspection before authoring the skill.

- [ ] **Step 3: Write the evidence file**

Create `tests/skill/scenarios.md` with the title `# Skill Behavior Scenarios`, then a `## Baseline: no skill` section containing the headings `### Exact Chinese title`, `### Bounded concurrent batch`, and `### Quality warning without retry`. Under every heading, record the exact prompt, a verbatim relevant response excerpt, and the observed missing behavior. End with an empty `## With skill` heading that Task 5 will populate using the same three prompts.

- [ ] **Step 4: Verify the RED evidence**

Run:

```text
rg -n "Relevant response excerpt|Missing behavior" tests/skill/scenarios.md
```

Expected: six populated `Relevant response excerpt` and `Missing behavior` lines.

- [ ] **Step 5: Commit**

```text
git add tests/skill/scenarios.md
git commit -m "test: record image skill baseline scenarios"
```

---

### Task 2: Build Request Expansion and Checkout Resolution

**Files:**
- Create: `.codex/skills/generating-images-with-laozhang-cli/scripts/generate.py`
- Create: `tests/skill/test_generate.py`

**Interfaces:**
- Consumes: `--request PATH`, optional `--count`, `--concurrency`, `--output-dir`, `--filename`, and `--cli-root`.
- Produces: `resolve_cli_root(explicit: Path | None, environ: Mapping[str, str], skill_dir: Path) -> Path`, `load_template(path: Path) -> dict[str, object]`, and `build_jobs(template: dict[str, object], count: int, output_dir: Path, filename: str | None) -> list[Job]`.
- Defines: `Job(index: int, request: dict[str, object])` as a frozen dataclass.

- [ ] **Step 0: Initialize the canonical skill skeleton**

Run the official initializer after the RED evidence exists:

```text
python C:/Users/carterwu/.codex/skills/.system/skill-creator/scripts/init_skill.py generating-images-with-laozhang-cli --path .codex/skills --resources scripts,references --interface display_name="Generate Images with Laozhang CLI" --interface short_description="Generate and inspect images through laozhang-cli" --interface default_prompt="Use $generating-images-with-laozhang-cli to generate and inspect an image from my description."
```

Expected: a new canonical skill folder containing `SKILL.md`, `agents/openai.yaml`, `scripts/`, and `references/`. Do not edit the generated `SKILL.md` until Task 5.

- [ ] **Step 1: Write failing tests for defaults, validation, and resolution order**

Create tests that import `generate.py` through `importlib.util.spec_from_file_location` and assert:

```python
def test_build_jobs_defaults_model_and_forces_single_image(tmp_path):
    template = {"system_prompt": "style", "prompt": "subject"}
    jobs = module.build_jobs(template, count=2, output_dir=tmp_path / "out", filename="card")
    assert [job.request["model"] for job in jobs] == ["nano-banana-2", "nano-banana-2"]
    assert [job.request["count"] for job in jobs] == [1, 1]
    assert [job.request["filename"] for job in jobs] == ["card-01", "card-02"]
    assert all(Path(job.request["output_dir"]).is_absolute() for job in jobs)


def test_resolve_cli_root_prefers_explicit_over_environment(tmp_path):
    explicit = make_checkout(tmp_path / "explicit")
    environment = make_checkout(tmp_path / "environment")
    assert module.resolve_cli_root(explicit, {"LAOZHANG_CLI_HOME": str(environment)}, tmp_path) == explicit


@pytest.mark.parametrize("value", [0, -1])
def test_positive_rejects_non_positive_values(value):
    with pytest.raises(argparse.ArgumentTypeError):
        module.positive_int(str(value))
```

Also test resolution through `LAOZHANG_CLI_HOME`, installed `config.json`, repository ancestry, and rejection of a directory missing either `pyproject.toml` or `src/laozhang_cli`.

- [ ] **Step 2: Run tests to verify RED**

Run:

```text
uv run pytest tests/skill/test_generate.py -q
```

Expected: FAIL because `generate.py` and its interfaces do not exist.

- [ ] **Step 3: Implement parsing, template validation, and job expansion**

Implement:

```python
@dataclass(frozen=True)
class Job:
    index: int
    request: dict[str, object]


def positive_int(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def build_jobs(template, count, output_dir, filename):
    base = dict(template)
    base.setdefault("model", "nano-banana-2")
    base["output_dir"] = str(output_dir.resolve())
    stem = filename or base.get("filename")
    width = max(2, len(str(count)))
    jobs = []
    for index in range(1, count + 1):
        request = dict(base)
        request["count"] = 1
        if stem:
            request["filename"] = f"{stem}-{index:0{width}d}" if count > 1 else str(stem)
        jobs.append(Job(index, request))
    return jobs
```

`load_template` must require a JSON object plus non-empty `system_prompt` and `prompt`; it may omit `model` so the orchestrator default applies. `resolve_cli_root` must use the exact precedence from the design and validate checkout markers.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run:

```text
uv run pytest tests/skill/test_generate.py -q
```

Expected: all request-expansion and checkout-resolution tests PASS.

- [ ] **Step 5: Run style checks**

Run:

```text
uv run ruff check .codex/skills/generating-images-with-laozhang-cli/scripts/generate.py tests/skill/test_generate.py
```

Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```text
git add .codex/skills/generating-images-with-laozhang-cli/scripts/generate.py tests/skill/test_generate.py
git commit -m "feat: expand laozhang image batch requests"
```

---

### Task 3: Add Bounded CLI Subprocess Orchestration

**Files:**
- Modify: `.codex/skills/generating-images-with-laozhang-cli/scripts/generate.py`
- Modify: `tests/skill/test_generate.py`

**Interfaces:**
- Consumes: `Job`, resolved checkout, `uv` executable, and a concurrency limit.
- Produces: `run_job(job: Job, cli_root: Path, uv_executable: str, temp_dir: Path) -> dict[str, object]`, `run_batch(jobs: Sequence[Job], cli_root: Path, concurrency: int, uv_executable: str) -> dict[str, object]`, and CLI `main(argv: Sequence[str] | None = None) -> int`.

- [ ] **Step 1: Write failing tests for process safety and aggregation**

Use a fake `uv` Python program in a temporary checkout that records start/end events, reads the generated request, and prints one CLI-compatible JSON object. Add tests asserting:

```python
def test_run_job_uses_argument_list_without_shell(monkeypatch, tmp_path):
    cli_root = make_checkout(tmp_path / "checkout")
    temp_dir = tmp_path / "tasks"
    temp_dir.mkdir()
    job = module.Job(
        1,
        {"model": "nano-banana-2", "system_prompt": "style", "prompt": "subject"},
    )
    calls = []
    monkeypatch.setattr(module.subprocess, "Popen", recording_popen(calls))
    result = module.run_job(job, cli_root, "uv", temp_dir)
    assert calls[0]["args"][:4] == ["uv", "run", "python", "-m"]
    assert calls[0]["shell"] is False
    assert calls[0]["cwd"] == cli_root
    assert result["index"] == job.index


def test_batch_never_exceeds_requested_concurrency(tmp_path):
    cli_root = make_checkout(tmp_path / "checkout")
    jobs = make_jobs(tmp_path, count=5)
    fake_uv, event_log = make_fake_uv(tmp_path)
    result = module.run_batch(jobs, cli_root, concurrency=2, uv_executable=fake_uv)
    assert peak_workers(event_log) == 2
    assert result["requested"] == 5
    assert result["succeeded"] == 5


def test_partial_failure_does_not_cancel_other_jobs(tmp_path):
    cli_root = make_checkout(tmp_path / "checkout")
    jobs = make_jobs(tmp_path, count=4)
    fake_uv, event_log = make_fake_uv(tmp_path, failing_indexes={2})
    result = module.run_batch(jobs, cli_root, concurrency=3, uv_executable=fake_uv)
    assert result["requested"] == 4
    assert result["succeeded"] == 3
    assert result["failed"] == 1
    assert [item["index"] for item in result["items"]] == [1, 2, 3, 4]
    assert started_indexes(event_log) == {1, 2, 3, 4}
```

Define `make_checkout`, `make_jobs`, `make_fake_uv`, `peak_workers`, `started_indexes`, and `recording_popen` in the same test module. `make_fake_uv` writes a deterministic executable Python fixture whose behavior is controlled only by temporary files and environment variables; it never accesses the network.

Also cover malformed stdout, preserved exit code and `http_status`, absolute image paths, removal of temporary request files, default concurrency 4, user override, no retry after failure, and absence of `LAOZHANG_KEY` in aggregate output.

- [ ] **Step 2: Run the new tests to verify RED**

Run:

```text
uv run pytest tests/skill/test_generate.py -q
```

Expected: FAIL because subprocess execution and aggregation are not implemented.

- [ ] **Step 3: Implement one-attempt subprocess execution**

For each job, write UTF-8 JSON into a `TemporaryDirectory`, then start exactly one process with:

```python
args = [
    uv_executable,
    "run",
    "python",
    "-m",
    "laozhang_cli",
    "--input",
    str(request_path),
]
process = subprocess.Popen(
    args,
    cwd=cli_root,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    encoding="utf-8",
    shell=False,
)
```

Parse stdout as one JSON object. Return a controlled per-item failure for malformed output. Convert every returned image path to an absolute path relative to `cli_root` when needed. Do not start a second process for the same job.

- [ ] **Step 4: Implement bounded aggregation and interruption handling**

Use `ThreadPoolExecutor(max_workers=min(concurrency, len(jobs)))`. Store results by job index so completion order does not affect output order. Track owned `Popen` objects behind a lock; on `KeyboardInterrupt`, cancel pending futures and terminate still-running owned processes before producing a controlled aggregate failure.

The aggregate object must have this shape:

```json
{
  "success": true,
  "requested": 2,
  "succeeded": 2,
  "failed": 0,
  "concurrency": 4,
  "elapsed_seconds": 12.345,
  "items": [
    {
      "index": 1,
      "exit_code": 0,
      "success": true,
      "http_status": 200,
      "message": "Image generated successfully",
      "elapsed_seconds": 11.1,
      "images": [{"path": "C:/work/output/card-01.webp", "format": "webp"}]
    }
  ]
}
```

Overall `success` is true only when every item succeeds.

- [ ] **Step 5: Add the command-line entry point**

Support exactly:

```text
python generate.py --request REQUEST [--count N] [--concurrency N]
                   [--output-dir DIR] [--filename STEM] [--cli-root DIR]
```

Defaults: `count=1`, `concurrency=4`, output directory from the template or the caller's current `output/`, model from the template or `nano-banana-2`. Print exactly one JSON object to stdout and return 0 only when the aggregate `success` is true.

- [ ] **Step 6: Run tests and lint**

Run:

```text
uv run pytest tests/skill/test_generate.py -q
uv run ruff check .codex/skills/generating-images-with-laozhang-cli/scripts/generate.py tests/skill/test_generate.py
```

Expected: all tests PASS and Ruff prints `All checks passed!`.

- [ ] **Step 7: Commit**

```text
git add .codex/skills/generating-images-with-laozhang-cli/scripts/generate.py tests/skill/test_generate.py
git commit -m "feat: run bounded image generation batches"
```

---

### Task 4: Add the Cross-Platform Personal Installer

**Files:**
- Create: `.codex/skills/generating-images-with-laozhang-cli/scripts/install.py`
- Create: `tests/skill/test_install.py`

**Interfaces:**
- Consumes: optional `--destination DIR` and `--cli-root DIR`.
- Produces: `default_skills_dir(environ: Mapping[str, str], home: Path) -> Path`, `install(source_skill: Path, destination: Path, cli_root: Path) -> Path`, and `main(argv: Sequence[str] | None = None) -> int`.

- [ ] **Step 1: Write failing installer tests**

Assert:

```python
def test_default_destination_prefers_codex_home(tmp_path):
    result = module.default_skills_dir({"CODEX_HOME": str(tmp_path / "codex")}, tmp_path)
    assert result == tmp_path / "codex" / "skills"


def test_install_copies_distributable_files_and_writes_config(tmp_path):
    target = module.install(source_skill, tmp_path / "skills", cli_root)
    assert (target / "SKILL.md").is_file()
    assert (target / "scripts" / "generate.py").is_file()
    config = json.loads((target / "config.json").read_text(encoding="utf-8"))
    assert config == {"cli_root": str(cli_root.resolve())}
    assert not (target / ".env").exists()
```

Also test the `~/.codex/skills` fallback, repeat installation replacing changed distributable content, checkout validation, and JSON stdout.

- [ ] **Step 2: Run tests to verify RED**

Run:

```text
uv run pytest tests/skill/test_install.py -q
```

Expected: FAIL because `install.py` does not exist.

- [ ] **Step 3: Implement installation using Python file APIs**

Resolve the source skill from `Path(__file__).resolve().parents[1]`. Resolve the CLI checkout from `--cli-root` or repository ancestry and validate the same markers as `generate.py`. Copy only `SKILL.md`, `agents/`, `references/`, and `scripts/`; exclude `__pycache__`, bytecode, tests, `.env`, and existing installation-local `config.json`. Write a new UTF-8 `config.json` after copying.

Use `shutil.copy2`, `shutil.copytree(source, target, dirs_exist_ok=True)`, and explicit resolved paths. Do not invoke shell commands.

- [ ] **Step 4: Run installer tests and lint**

Run:

```text
uv run pytest tests/skill/test_install.py -q
uv run ruff check .codex/skills/generating-images-with-laozhang-cli/scripts/install.py tests/skill/test_install.py
```

Expected: all tests PASS and Ruff prints `All checks passed!`.

- [ ] **Step 5: Commit**

```text
git add .codex/skills/generating-images-with-laozhang-cli/scripts/install.py tests/skill/test_install.py
git commit -m "feat: install laozhang image skill globally"
```

---

### Task 5: Author and Validate the Skill Instructions

**Files:**
- Modify: `.codex/skills/generating-images-with-laozhang-cli/SKILL.md`
- Create: `.codex/skills/generating-images-with-laozhang-cli/references/request-format.md`
- Modify: `.codex/skills/generating-images-with-laozhang-cli/agents/openai.yaml`
- Modify: `tests/skill/scenarios.md`

**Interfaces:**
- Consumes: `scripts/generate.py --request REQUEST` aggregate JSON and local image-viewing capability.
- Produces: a discoverable Codex workflow that generates, inspects, and reports images without retrying.

- [ ] **Step 1: Verify the initialized structure before authoring**

Run:

```text
rg --files .codex/skills/generating-images-with-laozhang-cli
```

Expected: the generated `SKILL.md` and `agents/openai.yaml` plus the implemented `scripts/generate.py` and `scripts/install.py`. Remove any initializer example files before continuing; keep only files named in the plan's File Map.

- [ ] **Step 2: Write minimal behavior-shaping instructions**

Use this frontmatter:

```yaml
---
name: generating-images-with-laozhang-cli
description: Use when Codex needs to create or batch-generate images through laozhang-cli, including Chinese text images, concurrent variant generation, nano-banana or GPT Image models, and post-generation visual quality inspection.
---
```

The body must prescribe this output-producing recipe in order:

1. Read `references/request-format.md` when selecting non-default fields or diagnosing a failure.
2. Convert the request into a UTF-8 JSON template; default model to `nano-banana-2` and preserve exact requested text verbatim.
3. Invoke `generate.py` with an argument list, default concurrency 4, and an explicit user override when supplied.
4. Parse the aggregate JSON and do not retry any item.
5. Open every successful image with the local image-viewing tool.
6. Classify every image as `acceptable`, `warning`, or `failed_quality_check`.
7. Name affected files and explicitly flag extensive garbled, distorted, invented, or unreadable Chinese text.
8. Report requested/succeeded/failed counts, elapsed time, absolute paths, generation errors, and quality findings.

Include one complete invocation example. Keep detailed field tables out of `SKILL.md`.

- [ ] **Step 3: Write the request reference**

Document the three models, prompt string/file forms, valid resolutions and ratios, filenames, output directories, WebP behavior, aggregate output, CLI exit codes 0/2/3/4, checkout resolution, and common errors. State that batch `--count` creates independent single-image calls and that concurrency changes simultaneous process count, not API retry behavior.

- [ ] **Step 4: Generate UI metadata deterministically**

Run:

```text
python C:/Users/carterwu/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py .codex/skills/generating-images-with-laozhang-cli --interface display_name="Generate Images with Laozhang CLI" --interface short_description="Generate and inspect images through laozhang-cli" --interface default_prompt="Use $generating-images-with-laozhang-cli to generate and inspect an image from my description."
```

Expected: quoted strings in `agents/openai.yaml`; no icon, color, MCP dependency, or policy fields.

- [ ] **Step 5: Validate the skill metadata and content**

Run:

```text
python C:/Users/carterwu/.codex/skills/.system/skill-creator/scripts/quick_validate.py .codex/skills/generating-images-with-laozhang-cli
rg -n "nano-banana-2|concurrency|Do not retry|garbled|Chinese|view" .codex/skills/generating-images-with-laozhang-cli/SKILL.md
```

Expected: `Skill is valid!` and matches for every mandatory behavior.

- [ ] **Step 6: Re-run the exact baseline scenarios with the skill**

Run each Task 1 prompt in a fresh Codex execution with the explicit skill path. The generation call itself may be replaced with a fake orchestrator result for the concurrency and partial-failure cases; the quality scenario must use an actual local image artifact so image inspection is observable. Record exact relevant excerpts under `## With skill` in `tests/skill/scenarios.md`.

Expected: all responses select/default correctly, use bounded independent calls, avoid retries, inspect successful images, and provide explicit Chinese text quality findings.

- [ ] **Step 7: Close observed instruction gaps and revalidate**

If a skill-enabled response omits a required output slot, revise the positive recipe or report contract in `SKILL.md`, rerun that exact scenario, and replace the evidence excerpt. Do not add a rationalization table unless the observed failure is a deliberate rule violation rather than an output-shape omission.

- [ ] **Step 8: Commit**

```text
git add .codex/skills/generating-images-with-laozhang-cli tests/skill/scenarios.md
git commit -m "feat: add laozhang image generation skill"
```

---

### Task 6: Install, Smoke-Test, and Document Usage

**Files:**
- Modify: `README.md`
- Installed outside repository: `${CODEX_HOME}/skills/generating-images-with-laozhang-cli/` or `~/.codex/skills/generating-images-with-laozhang-cli/`

**Interfaces:**
- Consumes: completed repository-local skill and configured `LAOZHANG_KEY` in the CLI checkout `.env`.
- Produces: installed personal skill and documented commands for local/global use.

- [ ] **Step 1: Add concise README usage**

Document:

```text
python .codex/skills/generating-images-with-laozhang-cli/scripts/install.py
python .codex/skills/generating-images-with-laozhang-cli/scripts/generate.py --request <request.json> --count 4 --concurrency 4
```

State that the installer is pure Python, personal installation keeps this checkout as its CLI backend, the default model is `nano-banana-2`, generation does not retry, and Codex performs post-generation visual inspection.

- [ ] **Step 2: Run the complete automated suite**

Run:

```text
uv run pytest -q
uv run ruff check .
```

Expected: all tests PASS and Ruff prints `All checks passed!`.

- [ ] **Step 3: Install to a temporary destination first**

Run:

```text
python .codex/skills/generating-images-with-laozhang-cli/scripts/install.py --destination C:/tmp/laozhang-skill-install
python C:/Users/carterwu/.codex/skills/.system/skill-creator/scripts/quick_validate.py C:/tmp/laozhang-skill-install/generating-images-with-laozhang-cli
```

Expected: installer JSON identifies the temporary installed path and checkout; validator prints `Skill is valid!`.

- [ ] **Step 4: Run a proportional generation smoke test**

Create a temporary UTF-8 request whose prompt asks for one simple `1K`, `1:1` image with no text, then run:

```text
python .codex/skills/generating-images-with-laozhang-cli/scripts/generate.py --request <temporary-request.json> --count 1 --concurrency 1 --output-dir <temporary-output-directory>
```

Expected: aggregate JSON with `requested: 1`, `succeeded: 1`, `failed: 0`, one absolute image path, and no retry. Open the resulting image and record the quality classification. If the live API is unavailable, retain the automated fake-subprocess evidence and report the external failure accurately rather than claiming an end-to-end pass.

- [ ] **Step 5: Install into the personal Codex skill directory**

Run:

```text
python .codex/skills/generating-images-with-laozhang-cli/scripts/install.py
```

Expected: installer JSON points to the user's Codex skills directory and contains the resolved `D:\workspace\laozhang-cli` checkout in the installed `config.json`. Confirm `.env` is absent from the installed skill.

- [ ] **Step 6: Verify repository status and final diff**

Run:

```text
git status --short
git diff --check HEAD
git diff --stat HEAD~4..HEAD
```

Expected: only intentional README/skill/test changes remain; no credential, generated image, temporary request, cache, or installed personal copy is staged.

- [ ] **Step 7: Commit documentation**

```text
git add README.md
git commit -m "docs: explain laozhang image skill usage"
```

- [ ] **Step 8: Final verification after the last commit**

Run:

```text
uv run pytest -q
uv run ruff check .
python C:/Users/carterwu/.codex/skills/.system/skill-creator/scripts/quick_validate.py .codex/skills/generating-images-with-laozhang-cli
git status --short
```

Expected: tests PASS, lint passes, validator prints `Skill is valid!`, and the worktree is clean.
