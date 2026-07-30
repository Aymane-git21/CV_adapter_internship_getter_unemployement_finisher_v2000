"""Per-document compile-dir cache: the warm state that makes recompiles not
start from zero (Overleaf CLSI model: the project dir persists between
requests; latexmk's .fdb/aux files ride along). Content-addressed outputs
short-circuit unchanged recompiles entirely."""
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from .contract import LatexCompileIn


def _max_projects() -> int:
    return int(os.environ.get("LATEXC_MAX_PROJECTS", "40"))


def _max_total_mb() -> int:
    return int(os.environ.get("LATEXC_MAX_TOTAL_MB", "512"))

# Artifacts the cache layer owns; user files are tracked in manifest.json and
# anything else (aux, fdb, logs) is latexmk's warm state.
_STATE_FILES = {"last.json", "manifest.json"}


def compile_root() -> Path:
    root = Path(os.environ.get("COMPILE_ROOT", "/tmp/compiles"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def project_dir(doc_id: str) -> Path:
    return compile_root() / doc_id


def content_key(inp: LatexCompileIn) -> str:
    h = hashlib.sha256()
    h.update(inp.engine.encode())
    h.update(b"\x00")
    h.update(inp.main.encode())
    for f in sorted(inp.files, key=lambda f: f.path):
        h.update(b"\x00")
        h.update(f.path.encode())
        h.update(b"\x00")
        h.update(f.content_b64.encode())
    return h.hexdigest()


def load_cached(pdir: Path, key: str) -> dict | None:
    """Stored outputs for this exact input, or None."""
    meta_path = pdir / "last.json"
    pdf_path = pdir / "last.pdf"
    if not (meta_path.exists() and pdf_path.exists()):
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if meta.get("content_key") != key:
        return None
    svgs = []
    for i in range(1, int(meta.get("pages", 0)) + 1):
        svg_path = pdir / f"page-{i}.svg"
        if not svg_path.exists():
            return None
        svgs.append(svg_path.read_text(encoding="utf-8"))
    return {"pages": int(meta.get("pages", 0)), "pdf": pdf_path.read_bytes(), "svgs": svgs}


def store(pdir: Path, key: str, pages: int, pdf: bytes, svgs: list[str]) -> None:
    (pdir / "last.pdf").write_bytes(pdf)
    for old in pdir.glob("page-*.svg"):
        old.unlink(missing_ok=True)
    for i, svg in enumerate(svgs, start=1):
        (pdir / f"page-{i}.svg").write_text(svg, encoding="utf-8")
    (pdir / "last.json").write_text(
        json.dumps({"content_key": key, "pages": pages, "ts": time.time()}),
        encoding="utf-8",
    )


def dir_size_bytes(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            continue
    return total


def evict(keep: Path) -> int:
    """LRU-evict project dirs beyond the caps; never the dir just used."""
    root = compile_root()
    dirs = [d for d in root.iterdir() if d.is_dir() and d != keep]
    dirs.sort(key=lambda d: d.stat().st_mtime)  # oldest first
    removed = 0
    total_cap = _max_total_mb() * 1024 * 1024

    def over_budget() -> bool:
        live = [d for d in root.iterdir() if d.is_dir()]
        if len(live) > _max_projects():
            return True
        return dir_size_bytes(root) > total_cap

    for d in dirs:
        if not over_budget():
            break
        shutil.rmtree(d, ignore_errors=True)
        removed += 1
    return removed


def clear_project(doc_id: str) -> bool:
    pdir = project_dir(doc_id)
    if pdir.exists():
        shutil.rmtree(pdir, ignore_errors=True)
        return True
    return False


def stats() -> tuple[int, float]:
    root = compile_root()
    dirs = [d for d in root.iterdir() if d.is_dir()]
    return len(dirs), round(dir_size_bytes(root) / (1024 * 1024), 1)
