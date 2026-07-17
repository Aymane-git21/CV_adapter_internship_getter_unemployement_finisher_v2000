"""Test environment. Env vars are pinned BEFORE app modules import so the
cached Settings pick them up."""
import os
import tempfile
import uuid
from pathlib import Path

os.environ["CVG_FAKE_AI"] = "1"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ENV"] = "dev"
_db_path = Path(tempfile.gettempdir()) / f"cvg_test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_path}"
# Billing: dummy values so billing_enabled is deterministically true in tests,
# isolated from any real keys in the developer's .env. Stripe calls are mocked.
os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
os.environ["STRIPE_PRICE_PLUS"] = "price_test_plus"
os.environ["STRIPE_PRICE_PRO"] = "price_test_pro"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_testsecret"

import httpx  # noqa: E402
import pytest  # noqa: E402

from backend.app import main as app_main  # noqa: E402
from backend.app.db import dispose_db, init_db  # noqa: E402
from backend.app.main import create_app  # noqa: E402


@pytest.fixture
async def client():
    await init_db()
    # The per-IP rate limiter is a module global; every test shares one "IP",
    # so leftovers from earlier tests would 429 later ones.
    app_main._hits.clear()
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await dispose_db()


def unique_email() -> str:
    return f"u{uuid.uuid4().hex[:10]}@test.dev"


SAMPLE_CV_TEXT = """Alex Martin
Machine Learning Engineer
ML engineer with 4 years of experience shipping LLM and vision systems to production.
alex.martin@example.com  +33 6 12 34 56 78  Paris, France
Built RAG platform serving 40k queries per day with python, pytorch and docker on gcp.
Led MLOps practice for a 12 person data team using kubernetes and airflow daily.
"""

SAMPLE_JD = """We are hiring a Machine Learning Engineer at Lumina AI in Paris.
You will design RAG pipelines, deploy models with docker and kubernetes on GCP,
and build evaluation harnesses in python. Experience with pytorch, airflow,
and LLM systems in production is required. Strong MLOps culture."""
