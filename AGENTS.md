# AGENTS.md

## Cursor Cloud specific instructions

`laozhang-cli` is a JSON-in/JSON-out Python CLI that wraps the api.laozhang.ai
text-to-image models. There is no GUI or long-running server: the only "service"
is the CLI itself, invoked once per run. Dependencies are managed with
[uv](https://docs.astral.sh/uv/) (see `README.md` "Python 环境与依赖").

Standard dev commands (already documented in `README.md` / `pyproject.toml`):

- Lint: `uv run ruff check .`
- Tests: `uv run pytest`
- Run the CLI: `uv run python -m laozhang_cli --input <request.json>`
  (examples live in `examples/`, e.g. `examples/request.json`, `examples/ppt.json`).

Non-obvious notes:

- The test suite is fully hermetic: adapters are tested against
  `httpx.MockTransport`, so `uv run pytest` needs no network access and no API
  key. Tests named `*_real.py` / `test_real_*.py` are still offline (the "real"
  refers to exercising real adapter/storage code, not live HTTP).
- Actual image generation requires a real `LAOZHANG_KEY`. The documented path is a
  project-root `.env` (`cp .env.sample .env`); Cursor Cloud secrets that inject
  `LAOZHANG_KEY` into the process environment also work, because
  `Settings.from_environment()` reads via `os.getenv` and `load_dotenv(...,
  override=False)`. Without a key the CLI still runs and returns a well-formed
  JSON error `{"success": false, ... "LAOZHANG_KEY is not configured"}` with exit
  code 3 — that is expected, not a setup failure. Never commit `.env`.
- The CLI never raises to stdout: it always prints one JSON object to stdout and
  writes diagnostics to stderr. Meaningful exit codes: `0` success, `2` input/JSON
  validation, `3` API/upstream error, `4` download/save/convert error.
- Upstream endpoints and the base URL are hard-coded in the adapters
  (`src/laozhang_cli/adapters/`); there is no env var to redirect them, so a real
  end-to-end generation needs the live api.laozhang.ai endpoint plus a valid key.
- Generated images default to `output/` (git-ignored). The bundled agent skill in
  `.codex/skills/generating-images-with-laozhang-cli/` is optional tooling and is
  covered by the same `uv run pytest` suite.
