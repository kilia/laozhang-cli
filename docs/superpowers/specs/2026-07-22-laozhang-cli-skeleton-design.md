# laozhang-cli Code Skeleton Design

## Goal

Create a GitHub-friendly Python project skeleton for `laozhang-cli`. The
skeleton establishes stable module boundaries, package tooling, tests, and
examples without sending real API requests.

## Scope

The skeleton will provide:

- A `src/`-layout Python package named `laozhang_cli`.
- A `python -m laozhang_cli --input request.json` command interface.
- Domain models for the README's normalized request and JSON result.
- Adapter abstractions and a model-to-adapter registry.
- Service boundaries for request orchestration and local image storage.
- An example request, environment-variable template, test layout, and project
  tooling configuration.

The skeleton will not perform network requests, download images, or convert
images to WebP. Those behaviours are deliberately deferred to follow-up
implementation tasks behind the interfaces defined here.

## Architecture

The command-line layer owns argument parsing, reading the input file, JSON
serialization, and process exit codes. It delegates validated work to a
generation service, so command handling remains independent from API protocol
details.

The generation service selects an adapter through a registry. Each adapter
implements a common interface and translates normalized request data to one
upstream protocol. Initial adapters represent GPT Image and Nano Banana
protocol families. A storage service is kept separate from adapters because
file naming, collision avoidance, and optional WebP conversion are local
concerns shared by all providers.

```text
request.json -> CLI -> normalized request -> generation service -> adapter registry -> adapter
                   |                                  |
                   v                                  v
              result JSON                         storage service
```

## Package Layout

```text
src/laozhang_cli/
  __init__.py       Package metadata and public version.
  __main__.py       `python -m laozhang_cli` entry point.
  cli.py            CLI parsing, result JSON output, and exit-code mapping.
  config.py         Runtime configuration loaded from environment variables.
  models.py         Normalized request, prompt reference, output image, and result models.
  adapters/
    base.py          Adapter protocol and protocol-specific request/result abstractions.
    gpt_image.py     GPT Image adapter boundary.
    nano_banana.py   Nano Banana adapter boundary.
    registry.py      Explicit model-name to adapter routing.
  services/
    generation.py    Orchestrates adapter selection and image generation.
    storage.py       Output paths and future image conversion boundary.
tests/
  test_cli.py
  test_models.py
  adapters/
  services/
examples/request.json
```

## Data Flow and Contracts

`GenerationRequest` represents the README's model-neutral JSON schema. Prompt
values accept inline text or `{ "file": "..." }`; file references are resolved
relative to the input JSON file by the application boundary. Adapters receive
resolved text and must not read arbitrary files.

`GenerationResult` is the only result shape passed to the CLI. It contains
`success`, `http_status`, `message`, and `images`; the CLI serializes it to
stdout only. Diagnostics use stderr. Failures before an HTTP request use a null
status and exit code 2; API failures map to 3; image-storage failures map to 4.

Adapters expose one async generation operation. The initial skeleton raises a
clear not-implemented domain error when execution reaches the network boundary,
while still allowing validation, routing, and result serialization to be tested
without credentials or network access.

## Tooling and Repository Hygiene

`pyproject.toml` will use uv-compatible PEP 621 metadata, a Python version
floor, runtime dependencies required by the completed architecture, and test /
lint configuration. The repository will include `.gitignore` for Python build
artefacts, virtual environments, output images, and `.env`; `.env.sample` will
document `LAOZHANG_KEY` without a secret. Tests use pytest and mirror package
areas. Ruff provides formatting and linting.

## Error Handling

Expected operational errors use domain-specific exceptions rather than printing
inside lower layers. CLI owns conversion of those errors into the specified
JSON response and exit code. Unexpected errors are also converted to JSON, with
diagnostics reserved for stderr so automated callers can always parse stdout.

## Testing Strategy

Tests will be written before implementation. They will cover normalized request
validation and defaults, prompt-reference parsing, model routing, CLI JSON
success/failure serialization, and placeholder service behaviour. Network and
Pillow-dependent tests are out of scope until concrete API and storage
implementations are added.

## Decisions

- Use a focused adapter layer rather than a single module: model protocols are
  explicitly different and expected to expand.
- Use one Nano Banana adapter family: its two listed models share the Gemini
  `generateContent` protocol and differ by endpoint/model metadata.
- Keep provider-specific size and image-format mapping inside adapters.
- Do not add a plugin framework: the adapter registry provides sufficient,
  explicit extension points for the current scope.
