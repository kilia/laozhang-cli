import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .errors import ApiError


@dataclass(frozen=True)
class Settings:
    api_key: str
    proxy: str | None = None

    @classmethod
    def from_environment(cls, env_file: Path | None = None) -> "Settings":
        load_dotenv(dotenv_path=env_file or Path.cwd() / ".env", override=False)
        api_key = os.getenv("LAOZHANG_KEY", "")
        if not api_key:
            raise ApiError("LAOZHANG_KEY is not configured")
        proxy = os.getenv("LAOZHANG_PROXY") or None
        return cls(api_key=api_key, proxy=proxy)
