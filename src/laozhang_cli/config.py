import os
from dataclasses import dataclass

from .errors import ApiError


@dataclass(frozen=True)
class Settings:
    api_key: str

    @classmethod
    def from_environment(cls) -> "Settings":
        api_key = os.getenv("LAOZHANG_KEY", "")
        if not api_key:
            raise ApiError("LAOZHANG_KEY is not configured")
        return cls(api_key=api_key)
