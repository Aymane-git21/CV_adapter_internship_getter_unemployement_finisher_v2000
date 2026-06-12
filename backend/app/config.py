"""Application settings, loaded from environment / .env."""
import os
import shutil
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


def _discover_typst() -> str:
    found = shutil.which("typst")
    if found:
        return found
    # winget portable install location on Windows
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidate = Path(local) / "Microsoft" / "WinGet" / "Links" / "typst.exe"
        if candidate.exists():
            return str(candidate)
    return "typst"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    env: str = "dev"  # dev | prod
    secret_key: str = "dev-secret-change-me"
    database_url: str = f"sqlite+aiosqlite:///{REPO_ROOT / 'cvglowup.db'}"

    # AI
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_model_lite: str = "gemini-2.5-flash-lite"
    cvg_fake_ai: bool = False  # force the deterministic offline provider

    # Typst
    typst_bin: str = ""
    templates_dir: Path = REPO_ROOT / "templates"
    compile_concurrency: int = 4

    # Jobs
    job_concurrency: int = 6

    # Web
    allowed_origins: str = ""  # comma separated; sensible defaults applied below
    frontend_dist: Path = REPO_ROOT / "frontend" / "dist"

    # Billing (Phase 4) — all optional; billing is disabled until configured
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_plus: str = ""
    stripe_price_pro: str = ""
    public_base_url: str = ""  # e.g. https://cvglowup.com — used for Stripe redirect URLs

    # Optional integrations
    google_client_id: str = ""
    adsense_client: str = ""

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        # Accept Heroku/Neon-style URLs and upgrade them to the async driver.
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        # asyncpg does not understand ?sslmode=require (libpq syntax); it uses ssl=true.
        if "+asyncpg" in url and "sslmode=" in url:
            url = url.replace("sslmode=require", "ssl=true")
        return url

    @property
    def typst_command(self) -> str:
        return self.typst_bin or _discover_typst()

    @property
    def origins(self) -> list[str]:
        if self.allowed_origins:
            return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]
        return [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "https://cvglowup.com",
            "https://www.cvglowup.com",
        ]

    @property
    def ai_enabled(self) -> bool:
        return bool(self.gemini_api_key) and not self.cvg_fake_ai

    @property
    def billing_enabled(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_price_plus and self.stripe_price_pro)


@lru_cache
def get_settings() -> Settings:
    return Settings()
