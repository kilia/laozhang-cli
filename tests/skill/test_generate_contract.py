import argparse
import importlib.util
import json
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
    spec = importlib.util.spec_from_file_location("laozhang_skill_generate", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_checkout(path: Path) -> Path:
    (path / "src" / "laozhang_cli").mkdir(parents=True)
    (path / "pyproject.toml").write_text("[project]\nname='laozhang-cli'\n", encoding="utf-8")
    return path.resolve()


def test_build_jobs_defaults_model_and_forces_single_image(tmp_path: Path) -> None:
    module = _load_module()
    template = {"system_prompt": "风格", "prompt": "主题"}

    jobs = module.build_jobs(
        template,
        count=2,
        output_dir=tmp_path / "out",
        filename="card",
    )

    assert [job.index for job in jobs] == [1, 2]
    assert [job.request["model"] for job in jobs] == ["nano-banana-2"] * 2
    assert [job.request["count"] for job in jobs] == [1, 1]
    assert [job.request["filename"] for job in jobs] == ["card-01", "card-02"]
    assert all(Path(job.request["output_dir"]).is_absolute() for job in jobs)
    assert "model" not in template


def test_build_jobs_preserves_model_and_single_filename(tmp_path: Path) -> None:
    module = _load_module()
    template = {
        "model": "gpt-image-2",
        "system_prompt": "style",
        "prompt": "subject",
        "filename": "original",
    }

    [job] = module.build_jobs(template, 1, tmp_path / "out", None)

    assert job.request["model"] == "gpt-image-2"
    assert job.request["filename"] == "original"


@pytest.mark.parametrize("raw", ["0", "-1", "not-an-integer"])
def test_positive_int_rejects_invalid_values(raw: str) -> None:
    module = _load_module()

    with pytest.raises(argparse.ArgumentTypeError):
        module.positive_int(raw)


def test_load_template_preserves_utf8(tmp_path: Path) -> None:
    module = _load_module()
    source = tmp_path / "request.json"
    source.write_text(
        json.dumps({"system_prompt": "保持文字准确", "prompt": "智启未来"}, ensure_ascii=False),
        encoding="utf-8",
    )

    assert module.load_template(source)["prompt"] == "智启未来"


def test_load_template_resolves_reference_images_from_template_directory(tmp_path: Path) -> None:
    module = _load_module()
    source = tmp_path / "requests" / "request.json"
    source.parent.mkdir()
    source.write_text(
        json.dumps(
            {
                "system_prompt": "style",
                "prompt": "edit",
                "reference_images": ["images/one.png", "../shared/two.jpg"],
            }
        ),
        encoding="utf-8",
    )

    payload = module.load_template(source)

    assert payload["reference_images"] == [
        str((source.parent / "images/one.png").resolve()),
        str((source.parent / "../shared/two.jpg").resolve()),
    ]


@pytest.mark.parametrize(
    "payload,message",
    [
        ([], "request JSON must be an object"),
        ({"prompt": "subject"}, "missing required field: system_prompt"),
        ({"system_prompt": "style"}, "missing required field: prompt"),
    ],
)
def test_load_template_rejects_invalid_roots_and_required_fields(
    tmp_path: Path,
    payload: object,
    message: str,
) -> None:
    module = _load_module()
    source = tmp_path / "request.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        module.load_template(source)


def test_resolve_cli_root_prefers_explicit_over_environment(tmp_path: Path) -> None:
    module = _load_module()
    explicit = _make_checkout(tmp_path / "explicit")
    environment = _make_checkout(tmp_path / "environment")

    result = module.resolve_cli_root(
        explicit,
        {"LAOZHANG_CLI_HOME": str(environment)},
        tmp_path,
    )

    assert result == explicit


def test_resolve_cli_root_uses_environment_then_installed_config(tmp_path: Path) -> None:
    module = _load_module()
    environment = _make_checkout(tmp_path / "environment")
    configured = _make_checkout(tmp_path / "configured")
    skill_dir = tmp_path / "installed-skill"
    skill_dir.mkdir()
    (skill_dir / "config.json").write_text(
        json.dumps({"cli_root": str(configured)}),
        encoding="utf-8",
    )

    assert (
        module.resolve_cli_root(None, {"LAOZHANG_CLI_HOME": str(environment)}, skill_dir)
        == environment
    )
    assert module.resolve_cli_root(None, {}, skill_dir) == configured


def test_resolve_cli_root_finds_repository_ancestor(tmp_path: Path) -> None:
    module = _load_module()
    checkout = _make_checkout(tmp_path / "checkout")
    skill_dir = checkout / ".codex" / "skills" / "generating-images-with-laozhang-cli"
    skill_dir.mkdir(parents=True)

    assert module.resolve_cli_root(None, {}, skill_dir) == checkout


def test_resolve_cli_root_rejects_invalid_checkout(tmp_path: Path) -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="valid laozhang-cli checkout"):
        module.resolve_cli_root(tmp_path, {}, tmp_path)
