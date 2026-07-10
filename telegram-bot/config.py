from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _getenv(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    api_url: str
    jwt_username: str
    jwt_password: str
    default_language: str = "tj"
    supported_languages: tuple[str, ...] = ("tj", "ru", "en")

    @classmethod
    def from_env(cls) -> "Settings":
        supported = tuple(
            lang.strip()
            for lang in _getenv("SUPPORTED_LANGUAGES", "tj,ru,en").split(",")
            if lang.strip()
        )
        return cls(
            bot_token=_getenv("BOT_TOKEN"),
            api_url=_getenv("API_URL").rstrip("/"),
            jwt_username=_getenv("JWT_USERNAME"),
            jwt_password=_getenv("JWT_PASSWORD"),
            default_language=_getenv("DEFAULT_LANGUAGE", "tj") or "tj",
            supported_languages=supported or ("tj", "ru", "en"),
        )

    def validate(self) -> None:
        missing = []
        if not self.bot_token:
            missing.append("BOT_TOKEN")
        if not self.api_url:
            missing.append("API_URL")
        if not self.jwt_username:
            missing.append("JWT_USERNAME")
        if not self.jwt_password:
            missing.append("JWT_PASSWORD")
        if missing:
            names = ", ".join(missing)
            raise RuntimeError(f"Missing required Telegram bot settings: {names}")


settings = Settings.from_env()

# Backward-compatible names for any small scripts imported manually.
BOT_TOKEN = settings.bot_token
API_URL = settings.api_url
JWT_USERNAME = settings.jwt_username
JWT_PASSWORD = settings.jwt_password
DEFAULT_LANGUAGE = settings.default_language
SUPPORTED_LANGUAGES = list(settings.supported_languages)
