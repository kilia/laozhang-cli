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
    / "install.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("laozhang_skill_install", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_checkout(path: Path) -> Path:
    (path / "src" / "laozhang_cli").mkdir(parents=True)
    (path / "pyproject.toml").write_text("[project]\nname='laozhang-cli'\n", encoding="utf-8")
    return path.resolve()


def _make_skill(path: Path, marker: str = "first") -> Path:
    (path / "agents").mkdir(parents=True)
    (path / "references").mkdir()
    (path / "scripts" / "__pycache__").mkdir(parents=True)
    (path / "SKILL.md").write_text(marker, encoding="utf-8")
    (path / "agents" / "openai.yaml").write_text("interface: {}\n", encoding="utf-8")
    (path / "references" / "request-format.md").write_text("fields", encoding="utf-8")
    (path / "scripts" / "generate.py").write_text("pass\n", encoding="utf-8")
    (path / "scripts" / "install.py").write_text("pass\n", encoding="utf-8")
    (path / "scripts" / "__pycache__" / "install.pyc").write_bytes(b"cache")
    (path / ".env").write_text("LAOZHANG_KEY=secret\n", encoding="utf-8")
    (path / "config.json").write_text(json.dumps({"cli_root": "stale"}), encoding="utf-8")
    return path


def test_default_destination_prefers_codex_home(tmp_path: Path) -> None:
    module = _load_module()

    result = module.default_skills_dir(
        {"CODEX_HOME": str(tmp_path / "codex")},
        tmp_path / "home",
    )

    assert result == (tmp_path / "codex" / "skills").resolve()


def test_default_destination_falls_back_to_home(tmp_path: Path) -> None:
    module = _load_module()

    assert module.default_skills_dir({}, tmp_path) == (tmp_path / ".codex" / "skills").resolve()


def test_install_copies_only_distributable_files_and_writes_config(tmp_path: Path) -> None:
    module = _load_module()
    source = _make_skill(tmp_path / "source")
    checkout = _make_checkout(tmp_path / "checkout")

    target = module.install(source, tmp_path / "skills", checkout)

    assert target == tmp_path / "skills" / "generating-images-with-laozhang-cli"
    assert (target / "SKILL.md").read_text(encoding="utf-8") == "first"
    assert (target / "agents" / "openai.yaml").is_file()
    assert (target / "references" / "request-format.md").is_file()
    assert (target / "scripts" / "generate.py").is_file()
    assert (target / "scripts" / "install.py").is_file()
    assert json.loads((target / "config.json").read_text(encoding="utf-8")) == {
        "cli_root": str(checkout)
    }
    assert not (target / ".env").exists()
    assert not (target / "scripts" / "__pycache__").exists()


def test_repeat_installation_updates_distributable_content(tmp_path: Path) -> None:
    module = _load_module()
    source = _make_skill(tmp_path / "source")
    checkout = _make_checkout(tmp_path / "checkout")
    destination = tmp_path / "skills"
    target = module.install(source, destination, checkout)
    (source / "SKILL.md").write_text("second", encoding="utf-8")

    repeated = module.install(source, destination, checkout)

    assert repeated == target
    assert (target / "SKILL.md").read_text(encoding="utf-8") == "second"


def test_install_rejects_invalid_checkout(tmp_path: Path) -> None:
    module = _load_module()
    source = _make_skill(tmp_path / "source")

    with pytest.raises(ValueError, match="valid laozhang-cli checkout"):
        module.install(source, tmp_path / "skills", tmp_path / "invalid")


def test_main_prints_one_json_result(tmp_path: Path, capsys) -> None:
    module = _load_module()
    checkout = _make_checkout(tmp_path / "checkout")
    destination = tmp_path / "skills"

    exit_code = module.main(["--destination", str(destination), "--cli-root", str(checkout)])

    output = capsys.readouterr().out
    assert output.count("\n") == 1
    payload = json.loads(output)
    assert payload["success"] is True
    assert (
        Path(payload["installed_path"])
        == (destination / "generating-images-with-laozhang-cli").resolve()
    )
    assert Path(payload["cli_root"]) == checkout
    assert exit_code == 0


def test_installer_has_no_shell_or_subprocess_dependency() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "subprocess" not in source
    assert "shell=" not in source
