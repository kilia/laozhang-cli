import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).parents[2]
    / ".codex"
    / "skills"
    / "generating-images-with-laozhang-cli"
    / "scripts"
    / "generate.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("laozhang_skill_generate_batch", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_checkout(path: Path) -> Path:
    package = path / "laozhang_cli"
    package.mkdir(parents=True)
    (path / "src" / "laozhang_cli").mkdir(parents=True)
    (path / "pyproject.toml").write_text(
        "[project]\nname='fake-laozhang-cli'\nversion='0.0.0'\nrequires-python='>=3.11'\n",
        encoding="utf-8",
    )
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "__main__.py").write_text(
        """import argparse
import json
import os
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
args = parser.parse_args()
request = json.loads(Path(args.input).read_text(encoding="utf-8"))
filename = request.get("filename", "image")
index = int(filename.rsplit("-", 1)[-1]) if "-" in filename else 1
event_log = Path(os.environ["FAKE_EVENT_LOG"])
with event_log.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({"event": "start", "index": index, "time": time.time_ns()}) + "\\n")
time.sleep(0.15)
failed = index in {int(value) for value in os.environ.get("FAKE_FAIL", "").split(",") if value}
with event_log.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({"event": "end", "index": index, "time": time.time_ns()}) + "\\n")
if failed:
    print(json.dumps({
        "success": False, "http_status": 429, "message": "rate limited",
        "elapsed_seconds": 0.15, "images": []
    }))
    sys.exit(3)
image = {"path": f"generated/{filename}.webp", "format": "webp"}
print(json.dumps({
    "success": True, "http_status": 200, "message": "generated",
    "elapsed_seconds": 0.15, "images": [image]
}))
""",
        encoding="utf-8",
    )
    return path.resolve()


def _jobs(module, tmp_path: Path, count: int):
    return module.build_jobs(
        {"system_prompt": "style", "prompt": "subject"},
        count=count,
        output_dir=tmp_path / "output",
        filename="card",
    )


def _peak_workers(events: list[dict[str, object]]) -> int:
    active = 0
    peak = 0
    for event in sorted(events, key=lambda item: int(item["time"])):
        active += 1 if event["event"] == "start" else -1
        peak = max(peak, active)
    return peak


class _FakeProcess:
    returncode = 0

    def communicate(self):
        return (
            json.dumps(
                {
                    "success": True,
                    "http_status": 200,
                    "message": "generated",
                    "elapsed_seconds": 0.1,
                    "images": [],
                }
            ),
            "",
        )

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = -1


def test_run_job_uses_argument_list_without_shell(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    checkout = _make_checkout(tmp_path / "checkout")
    task_dir = tmp_path / "tasks"
    task_dir.mkdir()
    [job] = _jobs(module, tmp_path, 1)
    calls = []

    def fake_popen(args, **kwargs):
        calls.append({"args": args, **kwargs})
        return _FakeProcess()

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)

    result = module.run_job(job, checkout, "uv", task_dir)

    assert calls[0]["args"][:5] == ["uv", "run", "python", "-m", "laozhang_cli"]
    assert calls[0]["shell"] is False
    assert calls[0]["cwd"] == checkout
    assert result["index"] == 1


def test_batch_limits_concurrency_and_keeps_partial_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    checkout = _make_checkout(tmp_path / "checkout")
    event_log = tmp_path / "events.jsonl"
    event_log.touch()
    monkeypatch.setenv("FAKE_EVENT_LOG", str(event_log))
    monkeypatch.setenv("FAKE_FAIL", "2")
    uv = shutil.which("uv")
    assert uv is not None

    result = module.run_batch(_jobs(module, tmp_path, 5), checkout, 2, uv)

    events = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
    assert _peak_workers(events) == 2
    assert [event["index"] for event in events if event["event"] == "start"].count(2) == 1
    assert result["requested"] == 5
    assert result["succeeded"] == 4
    assert result["failed"] == 1
    assert result["success"] is False
    assert [item["index"] for item in result["items"]] == [1, 2, 3, 4, 5]
    assert result["items"][1]["exit_code"] == 3
    assert result["items"][1]["http_status"] == 429
    successful_path = Path(result["items"][0]["images"][0]["path"])
    assert successful_path.is_absolute()
    assert successful_path == checkout / "generated" / "card-01.webp"


def test_run_job_reports_malformed_stdout(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    checkout = _make_checkout(tmp_path / "checkout")
    task_dir = tmp_path / "tasks"
    task_dir.mkdir()
    [job] = _jobs(module, tmp_path, 1)

    class MalformedProcess(_FakeProcess):
        returncode = 1

        def communicate(self):
            return "not-json", "diagnostic"

    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: MalformedProcess())

    result = module.run_job(job, checkout, "uv", task_dir)

    assert result == {
        "index": 1,
        "exit_code": 1,
        "success": False,
        "http_status": None,
        "message": "laozhang-cli returned invalid JSON: diagnostic",
        "elapsed_seconds": None,
        "images": [],
    }


def test_run_job_redacts_api_key(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    checkout = _make_checkout(tmp_path / "checkout")
    task_dir = tmp_path / "tasks"
    task_dir.mkdir()
    [job] = _jobs(module, tmp_path, 1)
    monkeypatch.setenv("LAOZHANG_KEY", "secret-value")

    class SecretProcess(_FakeProcess):
        returncode = 3

        def communicate(self):
            return "not-json", "request failed with secret-value"

    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: SecretProcess())

    result = module.run_job(job, checkout, "uv", task_dir)

    serialized = json.dumps(result)
    assert "secret-value" not in serialized
    assert "[REDACTED]" in serialized


def test_main_uses_default_concurrency_and_prints_one_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    module = _load_module()
    checkout = _make_checkout(tmp_path / "checkout")
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps({"system_prompt": "style", "prompt": "subject"}),
        encoding="utf-8",
    )
    captured = {}

    def fake_run_batch(jobs, cli_root, concurrency, uv_executable):
        captured.update(
            jobs=jobs,
            cli_root=cli_root,
            concurrency=concurrency,
            uv_executable=uv_executable,
        )
        return {
            "success": True,
            "requested": 1,
            "succeeded": 1,
            "failed": 0,
            "concurrency": concurrency,
            "elapsed_seconds": 0.1,
            "items": [],
        }

    monkeypatch.setattr(module, "run_batch", fake_run_batch)
    monkeypatch.setattr(module.shutil, "which", lambda name: "uv")

    exit_code = module.main(["--request", str(request), "--cli-root", str(checkout)])

    output = capsys.readouterr().out
    assert output.count("\n") == 1
    assert json.loads(output)["success"] is True
    assert captured["concurrency"] == 4
    assert exit_code == 0
