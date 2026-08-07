# AGENTS.md

## Cursor Cloud specific instructions

`laozhang-cli` is a JSON-in/JSON-out Python CLI that wraps the api.laozhang.ai
text-to-image models. There is no GUI or long-running server: the only "service"
is the CLI itself, invoked once per run. Dependencies are managed with
[uv](https://docs.astral.sh/uv/) (see `README.md` "Python 环境与依赖").

Standard dev commands (already documented in `README.md` / `pyproject.toml`):

- Lint: `uv run ruff check .`
- Tests: `uv run pytest`
- Sensitive-content audit over the whole git history: `uv run python scripts/audit_history.py`
 (add `--patterns-file .audit-patterns` for name/company keywords; that file is
 git-ignored on purpose so the keywords never enter the repository)
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
- This repository is public. Never commit real API keys, and never commit local
 environment details that identify a person (machine user names in
 `C:\Users\<user>\` paths, corporate e-mail addresses). `tests/test_no_sensitive_content.py`
 enforces this for the working tree; `scripts/audit_history.py` also covers old
 history blobs, which only `git filter-repo` can actually clean.
- Generated images default to `output/` (git-ignored). The bundled agent skill in
  `.codex/skills/generating-images-with-laozhang-cli/` is optional tooling and is
  covered by the same `uv run pytest` suite.

# Codex
## GitHub pull request workflow

- GitHub does not allow the author of a pull request to approve their own PR. Do not attempt self-approval.
- For routine changes, prefer committing directly when the repository workflow permits it.
- When a PR is required, create or use the PR, mark it Ready for review, and merge it directly when checks and policy allow; do not wait for self-approval.

## GitHub CLI proxy troubleshooting

- In the Codex Windows process, `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` and their lowercase variants may be set to `http://127.0.0.1:9`. This makes `gh api user` fail before reaching GitHub with a `proxyconnect tcp` error.
- This network failure can be misreported by `gh auth status` as an invalid keyring token. Verify connectivity before treating the token as invalid; the token may still be valid.
- For a process-local retry, clear both uppercase and lowercase proxy variables, then run `gh api user --jq .login` and `gh auth status`. Do not change persistent user or system proxy settings without explicit approval.


## Windows sandbox troubleshooting

### Latest verification after lowering the sandbox level and restarting Codex

- Default read access and regular process startup worked: `Get-Location`, `Get-Content`, `rg --version`, and `uv --version` all succeeded without escalation.
- `uv run pytest` with the default uv cache failed because `%LOCALAPPDATA%\uv\cache` was denied.
- Redirecting `UV_CACHE_DIR` and pytest cache/temp paths into the workspace allowed uv and most tests to start, but pytest still could not access child-process temp directories: `80 passed, 45 errors`.
- `uv run ruff check .` exited 0 with a local uv cache, but emitted permission warnings while handling its cache.
- `apply_patch` still failed with `windows unelevated restricted-token sandbox cannot enforce split writable root sets directly; refusing to run unsandboxed`.

Conclusion: the default Windows sandbox is partially usable for reads and simple process startup, but it is not fully usable for this repository's cache/temp-heavy tests or patch helper. Full test/lint workflows and edits still need the escalation or Git Bash fallback below.

### Fallback procedure

1. Retry a read-only command once. If it still fails, rerun it with `sandbox_permissions: require_escalated` and a concise justification.
2. Prefer `apply_patch` for edits. If its wrapper is rejected, use the repository's Git Bash and apply a minimal unified diff with `git apply` from the repository root.
3. Because the checkout uses CRLF in the worktree (`core.autocrlf=true`), use `git apply --unidiff-zero` for small insertions or replacements, then inspect `git diff` and `git diff --check`.
4. Keep cache/temp paths inside a known writable location only when diagnosing; do not use broad destructive commands, whole-file rewrites, shell redirection, or expose `.env`/API keys.
5. Run the relevant tests and lint checks after editing, and report whether escalation or the fallback was required.
