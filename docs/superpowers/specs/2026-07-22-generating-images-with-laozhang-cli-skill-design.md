# Laozhang CLI Image Generation Skill Design

## Goal

Create a Codex skill that turns a natural-language image request into one or more calls to the existing `laozhang-cli`, then reports generation results and visually checks every generated image. The skill will be maintained in this repository and installable as a personal Codex skill.

## Scope

The skill will:

- default to `nano-banana-2` when the user does not name a model;
- support every public request field documented by `laozhang-cli`;
- generate multiple independent images concurrently;
- use a default concurrency limit of 4 and allow an explicit override;
- invoke `laozhang-cli` once per requested image, with a separate JSON request and unique filename;
- collect successful and failed subprocess results without cancelling the remaining work;
- avoid automatic retries;
- require Codex to inspect every successful image and warn about visible defects, especially extensive garbled, distorted, or unreadable Chinese text;
- keep the API key out of request files, command arguments, logs, and skill files.

The skill will not duplicate the model adapters, HTTP requests, image conversion, or storage behavior already implemented by `laozhang-cli`. It will not automatically regenerate an image after a quality warning.

## Distribution

The canonical source will live at:

```text
.codex/skills/generating-images-with-laozhang-cli/
```

The same skill can be installed into the current user's Codex skills directory. Repository files remain the source of truth. A Python installer copies the skill and records the absolute path of the local `laozhang-cli` checkout in installation-local configuration, so the installed skill does not depend on a drive letter or current working directory.

## Components

```text
.codex/skills/generating-images-with-laozhang-cli/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   └── request-format.md
└── scripts/
    ├── generate.py
    └── install.py
```

### `SKILL.md`

Defines when the skill applies and how Codex should operate it. It instructs Codex to:

1. translate the user's request into model-independent CLI fields;
2. preserve user-provided wording when the image must contain exact text;
3. call `scripts/generate.py` rather than recreating concurrency logic;
4. parse the aggregate JSON result;
5. open every successful output image with the available local image-viewing tool;
6. report both process failures and visible quality findings;
7. never retry unless the user explicitly requests another generation.

### `scripts/generate.py`

A Python-standard-library orchestrator. It accepts generation fields plus batch controls, resolves the `laozhang-cli` checkout, creates one temporary request per image, and launches independent CLI subprocesses with bounded concurrency.

Important behavior:

- default model: `nano-banana-2`;
- default concurrency: 4;
- `--concurrency` accepts a positive integer override;
- `--count` is implemented as independent CLI calls whose request-level `count` is always 1;
- output filenames receive deterministic batch indexes and avoid collisions through the CLI's existing storage rules;
- output directories are resolved to absolute paths before the CLI runs;
- the CLI subprocess runs with the checkout as its working directory so the existing root `.env` is loaded;
- the subprocess command is an argument list, not a shell command;
- no shell syntax, shell executable, or platform-specific script is used;
- subprocess stdout must contain one JSON object; stderr is retained only for diagnostics and must not expose secrets;
- the final stdout contains exactly one aggregate JSON object;
- temporary request files are removed after all workers finish.

The aggregate result contains overall success, counts, elapsed time, concurrency, and one result per requested image. Each item records its index, exit code, CLI result fields, and absolute image paths. Partial success is represented explicitly rather than collapsed into a single generic failure.

### `scripts/install.py`

Installs the canonical skill into the personal Codex skills directory using Python file APIs. It:

- resolves the repository root from its own location;
- copies only the skill's distributable files;
- creates installation-local configuration containing the repository root;
- does not copy `.env` or any credentials;
- updates an existing installed copy safely without modifying repository source files;
- prints the installed path and configuration as a concise JSON result.

### `references/request-format.md`

Contains the request-field quick reference, supported values, model selection guidance, exact-text prompting advice, output contract, exit-code meanings, and common failure messages. `SKILL.md` points to it only when detailed parameter or troubleshooting information is needed.

## CLI Checkout Resolution

`generate.py` resolves the checkout in this order:

1. explicit `--cli-root`;
2. `LAOZHANG_CLI_HOME` environment variable;
3. installation-local configuration written by `install.py`;
4. repository ancestry when running the repository-local skill.

The resolved directory must contain `pyproject.toml` and `src/laozhang_cli`. Invalid or ambiguous locations produce a controlled JSON error before generation starts.

## Data Flow

1. The user requests one or more images in natural language.
2. Codex selects `nano-banana-2` unless the user specifies another supported model.
3. Codex invokes `generate.py` with explicit prompt, output, batch, and image parameters.
4. The orchestrator validates batch controls and finds the CLI checkout.
5. It creates a private temporary directory and one UTF-8 request JSON per image.
6. A bounded Python executor runs at most the configured number of CLI subprocesses simultaneously.
7. Each CLI process reads the checkout's `.env`, calls the upstream API, and saves its image to the requested absolute output directory.
8. The orchestrator parses every CLI JSON response and emits one aggregate JSON response.
9. Codex opens every successful image and records quality findings.
10. Codex reports paths, failures, and quality warnings without initiating another API call.

## Quality Inspection Contract

Process success is not equivalent to acceptable visual quality. After a successful subprocess result, Codex must inspect every returned image and classify it as:

- `acceptable`: no prominent defect is visible;
- `warning`: the image is usable but contains a visible concern;
- `failed_quality_check`: a major visible defect makes the intended content unreliable.

At minimum, inspection covers:

- the file opens and displays as an image;
- the composition broadly matches the request;
- there is no obvious blank, truncated, or severely corrupted output;
- requested text is present when visually determinable;
- large areas of Chinese text are not garbled, distorted, replaced with invented glyphs, or unreadable.

The report names each affected file and describes the visible problem. Inspection is advisory: it does not delete images, alter the generation result, or retry.

## Error Handling

- Invalid orchestrator arguments return a structured JSON failure without starting a CLI subprocess.
- Missing `uv`, Python, checkout files, or `LAOZHANG_KEY` is reported clearly.
- CLI exit codes and `http_status` values are preserved per item.
- Malformed CLI stdout is reported with a sanitized diagnostic.
- A failed item does not stop queued or running items.
- Keyboard interruption stops pending work, terminates owned child processes where practical, and returns a controlled failure.
- Credentials are never included in aggregate output or exception text generated by the skill.

## Testing Strategy

Tests will be written before implementation.

### Baseline skill scenarios

Before writing the skill instructions, representative prompts will be exercised without the new skill to document likely failures: inconsistent model selection, ad hoc request files, sequential generation, missing visual inspection, or unintended retries.

### Orchestrator tests

Automated tests will use fake CLI subprocess behavior and temporary directories to verify:

- defaults and argument validation;
- checkout resolution order;
- request JSON shape and UTF-8 preservation;
- independent filenames and request-level `count: 1`;
- concurrency limiting and user override;
- partial success aggregation;
- malformed CLI output handling;
- absence of shell invocation;
- cleanup of temporary task files;
- credential redaction.

### Installer tests

Tests will verify correct copying, local configuration, repeat installation, and exclusion of credentials.

### Skill validation

The completed skill will be checked against realistic single-image, exact-Chinese-text, concurrent batch, partial-failure, and quality-warning scenarios. A real API smoke test may generate a minimal batch using the configured key; it must not retry automatically.

## Acceptance Criteria

The work is complete when:

- the repository-local skill passes the official skill validator;
- its metadata triggers on requests to create images with `laozhang-cli`;
- a user can install it globally with the Python installer;
- single and concurrent generation use only Python process and file APIs;
- the default model is `nano-banana-2` and default concurrency is 4;
- users can override concurrency;
- no generation is retried automatically;
- results include usable absolute image paths;
- Codex inspects every successful image and explicitly warns about extensive Chinese text corruption;
- automated tests pass and a proportional end-to-end smoke test is documented.
