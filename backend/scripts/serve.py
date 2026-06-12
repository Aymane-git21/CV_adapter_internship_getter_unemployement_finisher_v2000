"""Dev server entrypoint — honors the PORT env var (used by preview tooling
and Cloud Run alike). Run: python -m backend.scripts.serve"""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1" if os.environ.get("ENV", "dev") == "dev" else "0.0.0.0",
        port=int(os.environ.get("PORT", "8011")),
    )
