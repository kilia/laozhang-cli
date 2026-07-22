import json
from pathlib import Path

from laozhang_cli.cli import main


def test_cli_emits_json_for_invalid_input(tmp_path: Path, capsys) -> None:
    source = tmp_path / "request.json"
    source.write_text("{}", encoding="utf-8")

    assert main(["--input", str(source)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result == {
        "success": False,
        "http_status": None,
        "message": "missing required field: model",
        "images": [],
    }
