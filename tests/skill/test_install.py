from pathlib import Path

SCRIPT = (
    Path(__file__).parents[2]
    / ".codex"
    / "skills"
    / "generating-images-with-laozhang-cli"
    / "scripts"
    / "install.py"
)


def test_install_script_exists() -> None:
    assert SCRIPT.is_file(), "install.py is missing"
