import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).parents[2]
    / ".codex"
    / "skills"
    / "generating-images-with-laozhang-cli"
    / "scripts"
    / "generate.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("laozhang_skill_generate_edges", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_multiple_jobs_get_unique_filenames_without_a_stem(tmp_path: Path) -> None:
    module = _load_module()

    jobs = module.build_jobs(
        {"system_prompt": "style", "prompt": "subject"},
        count=3,
        output_dir=tmp_path / "output",
        filename=None,
    )

    filenames = [job.request["filename"] for job in jobs]
    assert len(set(filenames)) == 3
    assert filenames[0].endswith("-01")
    assert filenames[-1].endswith("-03")


def test_keyboard_interrupt_returns_controlled_batch_result(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    jobs = module.build_jobs(
        {"system_prompt": "style", "prompt": "subject"},
        count=2,
        output_dir=tmp_path / "output",
        filename="card",
    )

    class FakeExecutor:
        def __init__(self, max_workers):
            self.max_workers = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def submit(self, function, *args):
            return object()

    terminated = []
    monkeypatch.setattr(module, "ThreadPoolExecutor", FakeExecutor)
    monkeypatch.setattr(
        module,
        "as_completed",
        lambda futures: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    monkeypatch.setattr(module, "_terminate_active_processes", lambda: terminated.append(True))

    result = module.run_batch(jobs, tmp_path, 2, "uv")

    assert terminated == [True]
    assert result["success"] is False
    assert result["requested"] == 2
    assert result["failed"] == 2
    assert [item["message"] for item in result["items"]] == ["interrupted", "interrupted"]


def test_argument_error_is_single_json_result(capsys) -> None:
    module = _load_module()

    exit_code = module.main(["--count", "0"])

    output = capsys.readouterr().out
    assert output.count("\n") == 1
    payload = json.loads(output)
    assert payload["success"] is False
    assert "--request" in payload["message"] or "positive integer" in payload["message"]
    assert exit_code == 2
