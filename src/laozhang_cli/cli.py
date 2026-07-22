import argparse
import json
from pathlib import Path
from typing import Any

from .errors import LaozhangCliError
from .models import GenerationRequest, GenerationResult
from .services.generation import GenerationService


def _payload(result: GenerationResult) -> dict[str, Any]:
    return {
        "success": result.success,
        "http_status": result.http_status,
        "message": result.message,
        "images": [
            {"path": image.path, "format": image.format} for image in result.images
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)

    try:
        source = Path(args.input)
        data = json.loads(source.read_text(encoding="utf-8"))
        request = GenerationRequest.from_dict(data, source.parent)
        result = GenerationService().generate(request)
        print(json.dumps(_payload(result), ensure_ascii=False))
        return 0
    except LaozhangCliError as error:
        print(
            json.dumps(
                {
                    "success": False,
                    "http_status": error.http_status,
                    "message": str(error),
                    "images": [],
                },
                ensure_ascii=False,
            )
        )
        return error.exit_code
    except (OSError, json.JSONDecodeError) as error:
        print(
            json.dumps(
                {
                    "success": False,
                    "http_status": None,
                    "message": str(error),
                    "images": [],
                },
                ensure_ascii=False,
            )
        )
        return 2
