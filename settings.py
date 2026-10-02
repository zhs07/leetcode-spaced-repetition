"""Explicit local/hosted configuration; hosted mode never falls back to SQLite."""

from dataclasses import dataclass
import os
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    mode: str = "local"
    database_url: str = ""
    supabase_url: str = ""
    allowed_origins: tuple[str, ...] = ()

    def __post_init__(self):
        if self.mode not in {"local", "hosted"}:
            raise ValueError("TRACKER_MODE must be local or hosted")
        if self.mode == "hosted":
            database = urlsplit(self.database_url)
            auth = urlsplit(self.supabase_url)
            if database.scheme not in {"postgres", "postgresql"} or not database.hostname:
                raise ValueError("Hosted mode requires TRACKER_DATABASE_URL")
            if (auth.scheme != "https" or not auth.hostname or auth.username or auth.password
                    or auth.path not in {"", "/"} or auth.query or auth.fragment):
                raise ValueError("SUPABASE_URL must be an HTTPS project origin")
            if not self.allowed_origins:
                raise ValueError("Hosted mode requires TRACKER_ALLOWED_ORIGINS")
        for origin in self.allowed_origins:
            parsed = urlsplit(origin)
            if (parsed.scheme not in {"https", "http"} or not parsed.hostname
                    or parsed.path or parsed.query or parsed.fragment
                    or parsed.username or parsed.password or "*" in origin
                    or (parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"})):
                raise ValueError("CORS origins must be exact HTTPS origins (HTTP allowed for localhost)")

    @classmethod
    def from_env(cls):
        mode = os.environ.get("TRACKER_MODE", "local")
        if os.environ.get("RENDER") and mode != "hosted":
            raise ValueError("Render deployment requires TRACKER_MODE=hosted")
        if mode == "local" and (os.environ.get("TRACKER_DATABASE_URL") or os.environ.get("SUPABASE_URL")):
            raise ValueError("Set TRACKER_MODE=hosted when configuring hosted credentials")
        return cls(
            mode=mode,
            database_url=os.environ.get("TRACKER_DATABASE_URL", ""),
            supabase_url=os.environ.get("SUPABASE_URL", "").rstrip("/"),
            allowed_origins=tuple(value.strip() for value in os.environ.get("TRACKER_ALLOWED_ORIGINS", "").split(",") if value.strip()),
        )
