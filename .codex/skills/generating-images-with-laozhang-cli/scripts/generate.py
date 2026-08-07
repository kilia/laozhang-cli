"""Batch image generation through laozhang-cli."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "nano-banana-2"
DEFAULT_CONCURRENCY = 4
_PROCESS_LOCK = threading.Lock()
_ACTIVE_PROCESSES: set[subprocess.Popen[str]] = set()


class ArgumentError(ValueError):
    """Raised for command-line argument errors."""


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ArgumentError(message)


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
    reference_images = payload.get("reference_images")
    if isinstance(reference_images, list):
        payload["reference_images"] = [
            str((path.parent / item).resolve()) if isinstance(item, str) and item else item
            for item in reference_images
        ]
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
    if count > 1 and not stem:
        stem = f"batch-{uuid.uuid4().hex[:12]}"
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


def _redact_text(value: str) -> str:
    secret = os.environ.get("LAOZHANG_KEY", "")
    return value.replace(secret, "[REDACTED]") if secret else value


def _absolute_images(payload: object, cli_root: Path) -> list[dict[str, str]]:
    if not isinstance(payload, list):
        return []
    images: list[dict[str, str]] = []
    for image in payload:
        if not isinstance(image, dict):
            continue
        raw_path = image.get("path")
        image_format = image.get("format")
        if not isinstance(raw_path, str) or not isinstance(image_format, str):
            continue
        path = Path(raw_path)
        if not path.is_absolute():
            path = cli_root / path
        images.append({"path": str(path.resolve()), "format": image_format})
    return images


def _invalid_result(index: int, exit_code: int, stdout: str, stderr: str) -> dict[str, object]:
    diagnostic = stderr.strip() or stdout.strip() or "empty output"
    diagnostic = _redact_text(diagnostic[:500])
    return {
        "index": index,
        "exit_code": exit_code,
        "success": False,
        "http_status": None,
        "message": f"laozhang-cli returned invalid JSON: {diagnostic}",
        "elapsed_seconds": None,
        "images": [],
    }


def run_job(
    job: Job,
    cli_root: Path,
    uv_executable: str,
    temp_dir: Path,
) -> dict[str, object]:
    request_path = temp_dir / f"request-{job.index:04d}.json"
    request_path.write_text(
        json.dumps(job.request, ensure_ascii=False),
        encoding="utf-8",
    )
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
        errors="replace",
        shell=False,
    )
    with _PROCESS_LOCK:
        _ACTIVE_PROCESSES.add(process)
    try:
        stdout, stderr = process.communicate()
    finally:
        with _PROCESS_LOCK:
            _ACTIVE_PROCESSES.discard(process)

    try:
        payload: Any = json.loads(stdout)
    except json.JSONDecodeError:
        return _invalid_result(job.index, process.returncode, stdout, stderr)
    if not isinstance(payload, dict):
        return _invalid_result(job.index, process.returncode, stdout, stderr)

    success = bool(payload.get("success")) and process.returncode == 0
    message = _redact_text(str(payload.get("message", "")))
    return {
        "index": job.index,
        "exit_code": process.returncode,
        "success": success,
        "http_status": payload.get("http_status"),
        "message": message,
        "elapsed_seconds": payload.get("elapsed_seconds"),
        "images": _absolute_images(payload.get("images"), cli_root),
    }


def _terminate_active_processes() -> None:
    with _PROCESS_LOCK:
        processes = tuple(_ACTIVE_PROCESSES)
    for process in processes:
        if process.poll() is None:
            process.terminate()


def run_batch(
    jobs: Sequence[Job],
    cli_root: Path,
    concurrency: int,
    uv_executable: str,
) -> dict[str, object]:
    started = time.perf_counter()
    results: dict[int, dict[str, object]] = {}
    with tempfile.TemporaryDirectory(prefix="laozhang-skill-") as directory:
        task_dir = Path(directory)
        try:
            with ThreadPoolExecutor(max_workers=min(concurrency, len(jobs))) as executor:
                futures = {
                    executor.submit(run_job, job, cli_root, uv_executable, task_dir): job
                    for job in jobs
                }
                for future in as_completed(futures):
                    job = futures[future]
                    try:
                        results[job.index] = future.result()
                    except Exception as error:
                        results[job.index] = {
                            "index": job.index,
                            "exit_code": 1,
                            "success": False,
                            "http_status": None,
                            "message": _redact_text(f"orchestrator error: {error}"),
                            "elapsed_seconds": None,
                            "images": [],
                        }
        except KeyboardInterrupt:
            _terminate_active_processes()
            for job in jobs:
                results.setdefault(
                    job.index,
                    {
                        "index": job.index,
                        "exit_code": 130,
                        "success": False,
                        "http_status": None,
                        "message": "interrupted",
                        "elapsed_seconds": None,
                        "images": [],
                    },
                )

    items = [results[job.index] for job in jobs]
    succeeded = sum(bool(item["success"]) for item in items)
    return {
        "success": succeeded == len(jobs),
        "requested": len(jobs),
        "succeeded": succeeded,
        "failed": len(jobs) - succeeded,
        "concurrency": concurrency,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "items": items,
    }


def _parser() -> argparse.ArgumentParser:
    parser = _JsonArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--count", type=positive_int, default=1)
    parser.add_argument("--concurrency", type=positive_int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--filename")
    parser.add_argument("--cli-root", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    exit_code = 1
    try:
        args = _parser().parse_args(argv)
        template = load_template(args.request)
        output_dir = args.output_dir or Path(str(template.get("output_dir", "output")))
        jobs = build_jobs(template, args.count, output_dir, args.filename)
        skill_dir = Path(__file__).resolve().parents[1]
        cli_root = resolve_cli_root(args.cli_root, os.environ, skill_dir)
        uv_executable = shutil.which("uv")
        if uv_executable is None:
            raise ValueError("uv executable was not found")
        result = run_batch(jobs, cli_root, args.concurrency, uv_executable)
        exit_code = 0 if result["success"] else 1
    except ArgumentError as error:
        result = {
            "success": False,
            "requested": 0,
            "succeeded": 0,
            "failed": 0,
            "concurrency": None,
            "elapsed_seconds": 0.0,
            "items": [],
            "message": _redact_text(str(error)),
        }
        exit_code = 2
    except (OSError, ValueError, json.JSONDecodeError) as error:
        result = {
            "success": False,
            "requested": 0,
            "succeeded": 0,
            "failed": 0,
            "concurrency": None,
            "elapsed_seconds": 0.0,
            "items": [],
            "message": _redact_text(str(error)),
        }
    print(json.dumps(result, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
