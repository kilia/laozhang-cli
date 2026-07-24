---
title: Repository, PyPI, and Agent Skill Standardization
status: approved
date: 2026-07-24
---

# Repository, PyPI, and Agent Skill Standardization

## Objective

Standardize `laozhang-cli` as a public Python project that can be built and installed from PyPI, follows normal GitHub repository conventions, and distributes its Codex Skill according to Agent Skill conventions. Preserve the current `src/` layout, public behavior, model adapters, and version `0.1.0` unless a packaging change requires a compatibility-preserving adjustment.

## Scope

### Python package and PyPI distribution

- Keep the `src/laozhang_cli/` package layout and the existing `tests/` layout.
- Complete `pyproject.toml` with public-project metadata: MIT license, author/project URLs, classifiers, keywords, supported Python version, package discovery, and the `laozhang-cli` console entry point.
- Keep `python -m laozhang_cli` working for compatibility.
- Use one authoritative version source so the package metadata and `laozhang_cli.__version__` cannot drift.
- Build both wheel and source distribution, then install the wheel in an isolated temporary environment and verify the installed command entry point.
- Keep runtime dependencies separate from development dependencies and retain `uv.lock` for reproducible development environments.

### GitHub repository conventions

Add the standard project-maintenance files that are useful for a public CLI project:

- `LICENSE` with MIT text.
- `CONTRIBUTING.md` describing environment setup, formatting/linting, tests, packaging checks, and pull-request expectations.
- `SECURITY.md` describing responsible reporting and the rule that credentials must never be committed.
- `CODE_OF_CONDUCT.md` using a recognized contributor conduct standard.
- GitHub Actions workflow for supported Python versions that runs linting, tests, and package build checks.
- Pull-request template and issue templates for bugs and feature requests when they add actionable structure.

Keep generated caches, virtual environments, `.env`, `output/`, build directories, and distribution artifacts ignored and out of version control. Repair README encoding and update its install, CLI, Skill, development, and release sections to match the actual project behavior.

### Agent Skill conventions

Keep the distributable Skill at:

```text
.codex/skills/generating-images-with-laozhang-cli/
├── SKILL.md
├── agents/openai.yaml
├── references/request-format.md
└── scripts/
    ├── generate.py
    └── install.py
```

- Keep Skill frontmatter limited to `name` and `description`.
- Make `description` begin with `Use when...`, describe concrete triggers, and avoid summarizing the workflow.
- Keep core safety and execution contracts in `SKILL.md`; keep detailed request/model information in the reference file; keep deterministic operations in scripts.
- Keep `agents/openai.yaml` aligned with the Skill name, purpose, and default prompt.
- Explicitly protect API keys from requests, commands, logs, reports, and copied Skill files.
- Preserve the existing batch contract: one underlying CLI call per image, bounded positive concurrency, no automatic retry, complete success/failure reporting, and visual inspection of successful images.
- The installer copies only distributable Skill content and excludes credentials, caches, and runtime artifacts.

## Validation strategy

Use repository tests and isolated command checks rather than a real image API call:

1. Run the existing unit and contract tests.
2. Add static Skill structure checks for frontmatter, naming, required files, metadata alignment, and prohibited artifacts.
3. Test installer behavior for clean installation, repeat installation, invalid checkout, configuration precedence, secret exclusion, and cache exclusion.
4. Test generator behavior for UTF-8 preservation, defaults, single-image enforcement, batch boundaries, invalid arguments, and aggregate failure reporting.
5. Run Ruff.
6. Build wheel and sdist.
7. Install the wheel in a temporary isolated environment and invoke the installed console script with a safe validation input.
8. Confirm Git contains no `.env`, cache, output, virtual-environment, or build artifacts.

If independent Agent subagent execution is unavailable, use repeatable contract and pressure-scenario tests as the local validation substitute; document that limitation rather than claiming a forward-test was run.

## Error handling and compatibility

- Packaging failures must be detected before release by the build and isolated-install checks.
- Existing JSON output and exit-code behavior remain unchanged.
- Skill failures continue to report every item and preserve successful outputs; no implicit retry is introduced.
- Documentation must state when an operation requires `LAOZHANG_KEY` and must never include a real key in examples.

## Non-goals

- Do not split the CLI and Skill into separate repositories or independently versioned distributions.
- Do not redesign model adapters or change the public request schema.
- Do not add unrelated application features, image assets, or external service integrations.

## Acceptance criteria

- `pip install .` and wheel installation expose a working `laozhang-cli` command.
- `python -m laozhang_cli` remains functional.
- MIT, GitHub collaboration, security, and CI files are present and accurate.
- README is valid UTF-8 and matches the implemented commands and file layout.
- Skill structure and metadata pass automated checks; installation excludes secrets and generated files.
- Full tests, Ruff, package build, isolated installation, and repository hygiene checks pass.
