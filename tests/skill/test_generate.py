from pathlib import Path

SCRIPT = (
    Path(__file__).parents[2]
    / ".codex"
    / "skills"
    / "generating-images-with-laozhang-cli"
    / "scripts"
    / "generate.py"
)


def test_generate_script_exists() -> None:
    assert SCRIPT.is_file(), "generate.py is missing"
