"""latexc wire contract v1. Imported by the backend (services.latexc.contract)
and by the service itself (latexc.contract inside the container). Bump
CONTRACT_VERSION on breaking changes and update both deploys together."""
from pydantic import BaseModel, Field

CONTRACT_VERSION = "1"
FILE_NAME_RE = r"^[A-Za-z0-9._-]{1,64}$"
MAX_FILES = 16
MAX_TOTAL_BYTES = 4_000_000


class CompileFile(BaseModel):
    path: str = Field(pattern=FILE_NAME_RE)
    content_b64: str


class LatexCompileIn(BaseModel):
    doc_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    engine: str = "xelatex"  # xelatex (only value in v1)
    main: str = Field(default="main.tex", pattern=FILE_NAME_RE)
    files: list[CompileFile] = Field(min_length=1, max_length=MAX_FILES)
    want_svgs: bool = True
    timeout_s: int = Field(default=40, ge=5, le=60)


class LatexCompileOut(BaseModel):
    ok: bool
    cache: str = "cold"  # hit | warm | cold
    pages: int = 0
    pdf_b64: str | None = None
    svgs: list[str] = Field(default_factory=list)
    log_tail: str = ""
    error_line: str | None = None
    timings_ms: dict[str, int] = Field(default_factory=dict)


class LatexStatus(BaseModel):
    ok: bool = True
    version: str = CONTRACT_VERSION
    uptime_s: int = 0
    projects: int = 0
    disk_mb: float = 0.0
