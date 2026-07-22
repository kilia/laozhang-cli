import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, NoReturn

from .errors import InputValidationError, LaozhangCliError
from .models import GenerationRequest, GenerationResult
from .services.generation import GenerationService


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise InputValidationError(message)


def _payload(result: GenerationResult) -> dict[str, Any]:
    return {
        "success": result.success,
        "http_status": result.http_status,
        "message": result.message,
        "elapsed_seconds": result.elapsed_seconds,
        "images": [{"path": image.path, "format": image.format} for image in result.images],
    }


def _error_payload(
    message: str,
    http_status: int | None = None,
    started: float | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "http_status": http_status,
        "message": message,
        "elapsed_seconds": round(time.perf_counter() - started, 3) if started is not None else None,
        "images": [],
    }


def main(argv: list[str] | None = None) -> int:
    started = time.perf_counter()
    try:
        parser = _JsonArgumentParser(add_help=False)
        parser.add_argument("--input", required=True)
        args = parser.parse_args(argv)
        source = Path(args.input)
        data = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise InputValidationError("input JSON must be an object")
        request = GenerationRequest.from_dict(data, source.parent)
        result = GenerationService().generate(request)
        result = GenerationResult(
            result.success,
            result.http_status,
            result.message,
            result.images,
            round(time.perf_counter() - started, 3),
        )
        print(json.dumps(_payload(result), ensure_ascii=False))
        return 0
    except LaozhangCliError as error:
        print(
            json.dumps(_error_payload(str(error), error.http_status, started), ensure_ascii=False)
        )
        return error.exit_code
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        print(json.dumps(_error_payload(str(error), started=started), ensure_ascii=False))
        return 2
    except Exception:
        traceback.print_exc(file=sys.stderr)
        print(
            json.dumps(
                _error_payload("unexpected internal error", started=started), ensure_ascii=False
            )
        )
        return 1
