"""Install the laozhang image-generation skill for the current user."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path

SKILL_NAME = "generating-images-with-laozhang-cli"
_DISTRIBUTABLE_DIRECTORIES = ("agents", "references", "scripts")


def default_skills_dir(environ: Mapping[str, str], home: Path) -> Path:
    codex_home = environ.get("CODEX_HOME")
    root = Path(codex_home).expanduser() if codex_home else home / ".codex"
    return (root / "skills").resolve()


def _valid_checkout(path: Path) -> bool:
    return (path / "pyproject.toml").is_file() and (path / "src" / "laozhang_cli").is_dir()


def _validated_checkout(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not _valid_checkout(resolved):
        raise ValueError(f"not a valid laozhang-cli checkout: {resolved}")
    return resolved


def _resolve_cli_root(explicit: Path | None, source_skill: Path) -> Path:
    if explicit is not None:
        return _validated_checkout(explicit)

    config_path = source_skill / "config.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if isinstance(config, dict) and isinstance(config.get("cli_root"), str):
            return _validated_checkout(Path(config["cli_root"]))

    for candidate in (source_skill.resolve(), *source_skill.resolve().parents):
        if _valid_checkout(candidate):
            return candidate
    raise ValueError("could not find a valid laozhang-cli checkout")


def _ignore_generated(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name == "__pycache__" or name.endswith((".pyc", ".pyo"))}


def install(source_skill: Path, destination: Path, cli_root: Path) -> Path:
    source = source_skill.expanduser().resolve()
    checkout = _validated_checkout(cli_root)
    skill_md = source / "SKILL.md"
    if not skill_md.is_file():
        raise ValueError(f"SKILL.md not found: {skill_md}")

    target = destination.expanduser().resolve() / SKILL_NAME
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(skill_md, target / "SKILL.md")

    for directory_name in _DISTRIBUTABLE_DIRECTORIES:
        source_directory = source / directory_name
        if not source_directory.is_dir():
            continue
        target_directory = target / directory_name
        if target_directory.exists():
            shutil.rmtree(target_directory)
        shutil.copytree(
            source_directory,
            target_directory,
            ignore=_ignore_generated,
        )

    config = {"cli_root": str(checkout)}
    (target / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--cli-root", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        source_skill = Path(__file__).resolve().parents[1]
        cli_root = _resolve_cli_root(args.cli_root, source_skill)
        destination = args.destination or default_skills_dir(os.environ, Path.home())
        installed_path = install(source_skill, destination, cli_root)
        result = {
            "success": True,
            "installed_path": str(installed_path),
            "cli_root": str(cli_root),
        }
        exit_code = 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        result = {"success": False, "message": str(error)}
        exit_code = 1
    print(json.dumps(result, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
