"""Application settings, loaded from environment / .env."""
import os
import re
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
    # Server-side calls can go through Vertex AI instead of an AI Studio key:
    # the Cloud Run service account authenticates, quotas are pay-as-you-go
    # (the free-tier key caps at 20 requests/DAY), and the GenAI-scoped GCP
    # credit covers the spend. BYOK requests always use the user's key.
    gemini_use_vertex: bool = False
    gcp_project: str = ""
    gcp_location: str = "global"
    # Override via GEMINI_MODEL / GEMINI_MODEL_LITE. Google retires older models
    # for new API keys (gemini-2.5-* now 404s "no longer available to new users"),
    # so these track current GA models; bump them when Google deprecates again.
    gemini_model: str = "gemini-3.5-flash"
    gemini_model_lite: str = "gemini-3.1-flash-lite"
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

    # Auto-apply pipeline (Phase 1)
    ft_client_id: str = ""
    ft_client_secret: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    poll_interval_minutes: int = 60
    internal_token: str = ""
    send_cap_daily: int = 15
    eml_out_dir: str = ""  # dev fallback output; empty -> <repo>/eml_out
    google_client_secret: str = ""  # OAuth code exchange for Gmail connect (Task 12)

    # LaTeX compile service (services/latexc). Feature stays dark until both
    # LATEXC_URL and LATEXC_TOKEN are set.
    latexc_url: str = ""
    latexc_token: str = ""
    latexc_service: str = "cvglowup-latexc"
    latexc_region: str = "europe-west1"
    latexc_idle_off_minutes: int = 240  # 0 disables the idle reaper (manual off only)

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
        if "+asyncpg" in url:
            # asyncpg speaks libpq-style `sslmode` under the name `ssl`, accepting the
            # same value names (require/verify-ca/verify-full/...). It cannot parse
            # `sslmode` or Neon's `channel_binding`, so translate/strip them.
            url = url.replace("sslmode=", "ssl=")
            url = re.sub(r"[?&]channel_binding=[^&]*", "", url)
            # Normalise separators left behind (e.g. stripped the leading `?param`).
            url = url.replace("?&", "?")
            if "?" not in url and "&" in url:
                url = url.replace("&", "?", 1)
            url = url.rstrip("?&")
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
        return (bool(self.gemini_api_key) or self.gemini_use_vertex) and not self.cvg_fake_ai

    @property
    def billing_enabled(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_price_plus and self.stripe_price_pro)

    @property
    def latex_enabled(self) -> bool:
        return bool(self.latexc_url and self.latexc_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()
