"""Batch image generation through laozhang-cli."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "nano-banana-2"


@dataclass(frozen=True)
class Job:
    index: int
    request: dict[str, object]


def positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def load_template(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("request JSON must be an object")
    for field in ("system_prompt", "prompt"):
        if field not in payload:
            raise ValueError(f"missing required field: {field}")
    return payload


def build_jobs(
    template: dict[str, object],
    count: int,
    output_dir: Path,
    filename: str | None,
) -> list[Job]:
    base = dict(template)
    base.setdefault("model", DEFAULT_MODEL)
    base["output_dir"] = str(output_dir.resolve())
    stem = filename if filename is not None else base.get("filename")
    width = max(2, len(str(count)))
    jobs: list[Job] = []
    for index in range(1, count + 1):
        request = dict(base)
        request["count"] = 1
        if stem:
            request["filename"] = f"{stem}-{index:0{width}d}" if count > 1 else str(stem)
        jobs.append(Job(index=index, request=request))
    return jobs


def _is_checkout(path: Path) -> bool:
    return (path / "pyproject.toml").is_file() and (path / "src" / "laozhang_cli").is_dir()


def _validated_checkout(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not _is_checkout(resolved):
        raise ValueError(f"not a valid laozhang-cli checkout: {resolved}")
    return resolved


def resolve_cli_root(
    explicit: Path | None,
    environ: Mapping[str, str],
    skill_dir: Path,
) -> Path:
    if explicit is not None:
        return _validated_checkout(explicit)

    environment_path = environ.get("LAOZHANG_CLI_HOME")
    if environment_path:
        return _validated_checkout(Path(environment_path))

    config_path = skill_dir / "config.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict) or not isinstance(config.get("cli_root"), str):
            raise ValueError(f"invalid skill configuration: {config_path}")
        return _validated_checkout(Path(config["cli_root"]))

    for candidate in (skill_dir.resolve(), *skill_dir.resolve().parents):
        if _is_checkout(candidate):
            return candidate

    raise ValueError("could not find a valid laozhang-cli checkout")
