"""Zero-downtime deploy protocol for CV Glowup on Cloud Run.

The protocol (see ops/README.md):

  gate -> build candidate (--no-traffic) -> smoke candidate on its tagged URL
       -> promote traffic to it -> smoke prod -> auto-rollback if prod smoke fails

The old revision keeps serving 100% of traffic until the candidate has passed
smoke tests on its own URL, so a bad build never receives a single user request.

Commands:
  python ops/deploy.py deploy     full protocol (add --skip-gate in CI, where the
                                  gate already ran as its own job)
  python ops/deploy.py rollback   shift traffic to the previous READY revision
                                  (or --revision NAME)
  python ops/deploy.py promote --revision NAME   shift traffic forward manually
  python ops/deploy.py smoke      run the smoke checks against prod (or --url)
  python ops/deploy.py status     show serving revision, traffic and tags
  python ops/deploy.py gate       run the local test gate only

Configuration is code: every deploy passes the FULL env/secret/resource set
below, so anything added by hand with `gcloud run services update` is wiped on
the next deploy. Change it here, not in the console.

Stdlib only. Pure decision logic lives in top-level functions with unit tests
in ops/tests/test_deploy.py; only the thin command layer shells out to gcloud.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PROJECT = os.environ.get("GCP_PROJECT_ID", "project-60fad876-6da7-41f3-bfd")
REGION = os.environ.get("GCP_REGION", "europe-west1")
SERVICE = os.environ.get("CVG_SERVICE", "cvglowup")

# The complete runtime configuration. GEMINI_USE_VERTEX/GCP_PROJECT route
# server-side Gemini through Vertex AI (billed against the GenAI credit);
# removing them silently falls back to the free-tier API key (20 req/day).
ENV_VARS = {
    "GEMINI_USE_VERTEX": "1",
    "GCP_PROJECT": PROJECT,
    # Stripe: non-secret config. Price IDs come from ops/stripe_setup.py; re-run
    # it against live keys and update these when leaving test mode.
    "STRIPE_PRICE_PLUS": "price_1TuBYDCrTIUbpkXZZhbbETTG",
    "STRIPE_PRICE_PRO": "price_1TuBYECrTIUbpkXZK521Jifd",
    "PUBLIC_BASE_URL": "https://cvglowup.com",
}
SECRETS = {
    "SECRET_KEY": "SECRET_KEY:latest",
    "DATABASE_URL": "DATABASE_URL:latest",
    "GEMINI_API_KEY": "GEMINI_API_KEY:latest",
    "STRIPE_SECRET_KEY": "STRIPE_SECRET_KEY:latest",
    "STRIPE_WEBHOOK_SECRET": "STRIPE_WEBHOOK_SECRET:latest",
}
MEMORY = "512Mi"
CPU = "1"
CONCURRENCY = "80"
MIN_INSTANCES = "0"
MAX_INSTANCES = "20"

SMOKE_ATTEMPTS = 6
SMOKE_BACKOFF_S = 5
HTTP_TIMEOUT_S = 30


class DeployError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Pure decision logic (unit-tested, no I/O)
# ---------------------------------------------------------------------------

def candidate_tag(sha: str) -> str:
    """Cloud Run traffic tag for a candidate revision built from git SHA."""
    sha = sha.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{7,40}", sha):
        raise DeployError(f"not a git sha: {sha!r}")
    return f"cand-{sha[:12]}"


def tag_url(tag: str, service_url: str) -> str:
    """https://svc-xyz.a.run.app -> https://TAG---svc-xyz.a.run.app"""
    prefix = "https://"
    if not service_url.startswith(prefix):
        raise DeployError(f"unexpected service url: {service_url!r}")
    return f"{prefix}{tag}---{service_url[len(prefix):]}"


def parse_service(payload: dict) -> dict:
    """Reduce `gcloud run services describe --format json` to what we act on."""
    status = payload.get("status", {})
    traffic = [
        {
            "revision": t.get("revisionName", ""),
            "percent": int(t.get("percent") or 0),
            "tag": t.get("tag", ""),
            "url": t.get("url", ""),
        }
        for t in status.get("traffic", [])
    ]
    return {
        "url": status.get("url", ""),
        "latest_created": status.get("latestCreatedRevisionName", ""),
        "latest_ready": status.get("latestReadyRevisionName", ""),
        "traffic": traffic,
    }


def serving_revision(state: dict) -> str:
    """The single revision carrying 100% of traffic. Split traffic means a
    deploy or rollback died halfway; a human must look before we act."""
    live = [t for t in state["traffic"] if t["percent"] > 0]
    if len(live) != 1 or live[0]["percent"] != 100:
        raise DeployError(f"traffic is split, resolve manually first: {live}")
    if not live[0]["revision"]:
        raise DeployError(f"serving traffic target has no revision name: {live}")
    return live[0]["revision"]


def ready_revisions(revisions_payload: list[dict]) -> list[str]:
    """Names of READY revisions, newest first."""
    rows = []
    for r in revisions_payload:
        conds = r.get("status", {}).get("conditions", [])
        if any(c.get("type") == "Ready" and c.get("status") == "True" for c in conds):
            rows.append((r["metadata"]["creationTimestamp"], r["metadata"]["name"]))
    return [name for _, name in sorted(rows, reverse=True)]


def rollback_target(ready_desc: list[str], serving: str, explicit: str | None = None) -> str:
    """Pick the revision to roll back to: the newest READY revision older than
    the serving one, unless an explicit target was requested."""
    if explicit:
        if explicit == serving:
            raise DeployError(f"{explicit} is already serving 100% of traffic")
        if explicit not in ready_desc:
            raise DeployError(f"{explicit} is not a READY revision of {SERVICE}: {ready_desc}")
        return explicit
    older = ready_desc[ready_desc.index(serving) + 1:] if serving in ready_desc else ready_desc
    if not older:
        raise DeployError("no older READY revision exists to roll back to")
    return older[0]


def deploy_args(tag: str) -> list[str]:
    env = ",".join(f"{k}={v}" for k, v in sorted(ENV_VARS.items()))
    sec = ",".join(f"{k}={v}" for k, v in sorted(SECRETS.items()))
    return [
        "run", "deploy", SERVICE,
        "--project", PROJECT,
        "--region", REGION,
        "--source", ".",
        "--no-traffic",
        "--tag", tag,
        "--allow-unauthenticated",
        "--memory", MEMORY,
        "--cpu", CPU,
        "--concurrency", CONCURRENCY,
        "--min-instances", MIN_INSTANCES,
        "--max-instances", MAX_INSTANCES,
        "--set-env-vars", env,
        "--set-secrets", sec,
        "--quiet",
    ]


def traffic_args(revision: str) -> list[str]:
    return [
        "run", "services", "update-traffic", SERVICE,
        "--project", PROJECT,
        "--region", REGION,
        "--to-revisions", f"{revision}=100",
        "--quiet",
    ]


def stale_candidate_tags(traffic: list[dict], keep_revision: str) -> list[str]:
    """cand-* tags left over from earlier deploys. Rollback works on revision
    names, not tags, so only the current candidate's tag is worth keeping."""
    return sorted(
        t["tag"]
        for t in traffic
        if t["tag"].startswith("cand-") and t["revision"] != keep_revision and t["percent"] == 0
    )


def check_health(payload: dict) -> list[str]:
    problems = []
    if payload.get("ok") is not True:
        problems.append(f"/api/healthz ok={payload.get('ok')!r}")
    if payload.get("db") is not True:
        problems.append(f"/api/healthz db={payload.get('db')!r} (DATABASE_URL broken?)")
    return problems


def check_config(payload: dict, require_gemini: bool = True, require_billing: bool = True) -> list[str]:
    problems = []
    mode = payload.get("ai_mode")
    if require_gemini and mode != "gemini":
        problems.append(f"/api/config ai_mode={mode!r}, prod must run gemini (key/Vertex misconfigured?)")
    if require_billing and payload.get("billing_enabled") is not True:
        problems.append(
            "/api/config billing_enabled is not true (Stripe secrets/price env vars missing?)"
        )
    template_ids = {t.get("id") for t in payload.get("templates", [])}
    if not {"onyx", "classic"} <= template_ids:
        problems.append(f"/api/config templates missing: {sorted(template_ids)}")
    plan_keys = {p.get("key") for p in payload.get("plans", [])}
    if not {"free", "plus", "pro"} <= plan_keys:
        problems.append(f"/api/config plans missing: {sorted(plan_keys)}")
    return problems


def check_index(html: str) -> list[str]:
    problems = []
    if 'id="root"' not in html:
        problems.append("/ index.html has no SPA root div (frontend build missing from image?)")
    if "CV Glowup" not in html:
        problems.append("/ index.html has no 'CV Glowup' title")
    return problems


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _bin(name: str) -> str:
    path = shutil.which(name) or shutil.which(f"{name}.cmd")
    if not path:
        raise DeployError(f"{name} not found on PATH")
    return path


def gcloud_json(args: list[str]) -> dict | list:
    cmd = [_bin("gcloud"), *args, "--format", "json"]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    if res.returncode != 0:
        raise DeployError(f"gcloud {' '.join(args)} failed:\n{res.stderr.strip()}")
    return json.loads(res.stdout or "null")


def gcloud_stream(args: list[str], timeout: int | None = None) -> None:
    """Run gcloud with output going straight to the console (build logs)."""
    cmd = [_bin("gcloud"), *args]
    res = subprocess.run(cmd, cwd=REPO_ROOT, timeout=timeout)
    if res.returncode != 0:
        raise DeployError(f"gcloud {' '.join(args[:3])}... exited {res.returncode}")


def http_get(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "cvglowup-deploy-smoke"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def git_sha() -> str:
    res = subprocess.run(
        [_bin("git"), "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT
    )
    if res.returncode != 0:
        raise DeployError(f"git rev-parse failed: {res.stderr.strip()}")
    return res.stdout.strip()


def git_dirty_tracked() -> str:
    res = subprocess.run(
        [_bin("git"), "status", "--porcelain", "-uno"], capture_output=True, text=True, cwd=REPO_ROOT
    )
    return res.stdout.strip()


# ---------------------------------------------------------------------------
# Protocol steps
# ---------------------------------------------------------------------------

def describe_service() -> dict:
    return parse_service(
        gcloud_json(["run", "services", "describe", SERVICE, "--project", PROJECT, "--region", REGION])
    )


def list_ready_revisions() -> list[str]:
    return ready_revisions(
        gcloud_json(
            ["run", "revisions", "list", "--service", SERVICE, "--project", PROJECT, "--region", REGION]
        )
    )


def smoke(base_url: str, require_gemini: bool = True) -> None:
    """Run all smoke checks against base_url, retrying to ride out cold starts.
    Raises DeployError with every failure listed if the last attempt fails."""
    base = base_url.rstrip("/")
    for attempt in range(1, SMOKE_ATTEMPTS + 1):
        problems: list[str] = []
        try:
            status, body = http_get(f"{base}/api/healthz")
            problems += [f"/api/healthz HTTP {status}"] if status != 200 else check_health(json.loads(body))

            status, body = http_get(f"{base}/api/config")
            problems += (
                [f"/api/config HTTP {status}"]
                if status != 200
                else check_config(json.loads(body), require_gemini=require_gemini)
            )

            status, body = http_get(f"{base}/")
            problems += (
                [f"/ HTTP {status}"] if status != 200 else check_index(body.decode("utf-8", "replace"))
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            problems.append(f"request failed: {e}")

        if not problems:
            print(f"  smoke OK on {base} (attempt {attempt})")
            return
        if attempt < SMOKE_ATTEMPTS:
            print(f"  smoke attempt {attempt}/{SMOKE_ATTEMPTS} failed ({'; '.join(problems)}), retrying...")
            time.sleep(SMOKE_BACKOFF_S)
    raise DeployError(f"smoke failed on {base}: " + "; ".join(problems))


def run_gate() -> None:
    """The local test gate: lint, backend tests, ops tests, frontend build."""
    steps: list[tuple[str, list[str], Path]] = [
        ("ruff", [sys.executable, "-m", "ruff", "check", "backend", "ops"], REPO_ROOT),
        ("backend tests", [sys.executable, "-m", "pytest", "backend/tests", "-q"], REPO_ROOT),
        ("ops tests", [sys.executable, "-m", "pytest", "ops/tests", "-q"], REPO_ROOT),
        ("frontend build", [_bin("npm"), "run", "build"], REPO_ROOT / "frontend"),
    ]
    for name, cmd, cwd in steps:
        print(f"[gate] {name}")
        res = subprocess.run(cmd, cwd=cwd)
        if res.returncode != 0:
            raise DeployError(f"gate failed at: {name}")
    print("[gate] all green")


def preflight() -> str:
    """Billing + clean-tree checks. Returns the git sha to deploy."""
    billing = gcloud_json(["billing", "projects", "describe", PROJECT])
    if not billing.get("billingEnabled"):
        raise DeployError(
            "GCP billing is DISABLED on the project. This is the past-due/threshold "
            "gotcha: open the billing console, pay the outstanding amount, retry."
        )
    dirty = git_dirty_tracked()
    if dirty:
        raise DeployError(f"tracked files have uncommitted changes, commit first:\n{dirty}")
    return git_sha()


def cmd_deploy(skip_gate: bool, no_promote: bool) -> None:
    if not skip_gate:
        run_gate()
    sha = preflight()
    tag = candidate_tag(sha)

    before = describe_service()
    previous = serving_revision(before)
    print(f"[deploy] serving now: {previous} (rollback target)")
    print(f"[deploy] building candidate {tag} from {sha[:12]} (prod traffic untouched)")

    gcloud_stream(deploy_args(tag))

    after = describe_service()
    new_revision = after["latest_created"]
    if new_revision == previous:
        raise DeployError("no new revision was created")
    cand = next((t for t in after["traffic"] if t["tag"] == tag), None)
    if not cand or not cand["url"]:
        raise DeployError(f"candidate tag {tag} not found in traffic config: {after['traffic']}")

    print(f"[deploy] candidate revision {new_revision} ready, smoking {cand['url']}")
    smoke(cand["url"])

    if no_promote:
        print(f"[deploy] --no-promote: candidate {new_revision} is live at {cand['url']}, prod unchanged.")
        print(f"[deploy] promote with: python ops/deploy.py promote --revision {new_revision}")
        return

    print(f"[deploy] promoting traffic: {previous} -> {new_revision}")
    gcloud_stream(traffic_args(new_revision))

    try:
        smoke(after["url"])
    except DeployError as e:
        print(f"[deploy] PROD SMOKE FAILED, rolling back to {previous}: {e}")
        gcloud_stream(traffic_args(previous))
        smoke(after["url"])
        raise DeployError(
            f"deploy of {new_revision} failed prod smoke and was rolled back to {previous}"
        ) from e

    stale = stale_candidate_tags(after["traffic"], keep_revision=new_revision)
    if stale:
        gcloud_stream(
            [
                "run", "services", "update-traffic", SERVICE,
                "--project", PROJECT, "--region", REGION,
                "--remove-tags", ",".join(stale), "--quiet",
            ]
        )
        print(f"[deploy] removed stale candidate tags: {', '.join(stale)}")

    print(f"[deploy] DONE: {new_revision} serves 100% at {after['url']}")
    print(f"[deploy] rollback option: python ops/deploy.py rollback   (returns to {previous})")


def cmd_rollback(revision: str | None) -> None:
    state = describe_service()
    serving = serving_revision(state)
    target = rollback_target(list_ready_revisions(), serving, revision)
    print(f"[rollback] shifting traffic: {serving} -> {target}")
    gcloud_stream(traffic_args(target))
    smoke(state["url"])
    print(f"[rollback] DONE: {target} serves 100% at {state['url']}")
    print(f"[rollback] roll forward again with: python ops/deploy.py promote --revision {serving}")


def cmd_promote(revision: str) -> None:
    state = describe_service()
    if revision not in list_ready_revisions():
        raise DeployError(f"{revision} is not a READY revision of {SERVICE}")
    print(f"[promote] shifting traffic: {serving_revision(state)} -> {revision}")
    gcloud_stream(traffic_args(revision))
    smoke(state["url"])
    print(f"[promote] DONE: {revision} serves 100% at {state['url']}")


def cmd_status() -> None:
    state = describe_service()
    print(f"service : {SERVICE} ({REGION}, {PROJECT})")
    print(f"url     : {state['url']}")
    print(f"serving : {serving_revision(state)}")
    print(f"latest  : {state['latest_ready']} (ready) / {state['latest_created']} (created)")
    for t in state["traffic"]:
        tag = f"  tag={t['tag']} {t['url']}" if t["tag"] else ""
        print(f"traffic : {t['revision']} {t['percent']}%{tag}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_deploy = sub.add_parser("deploy", help="full zero-downtime deploy protocol")
    p_deploy.add_argument("--skip-gate", action="store_true", help="skip local tests (CI runs them as a job)")
    p_deploy.add_argument("--no-promote", action="store_true", help="stop after candidate smoke; no traffic shift")

    p_rollback = sub.add_parser("rollback", help="shift traffic back to the previous READY revision")
    p_rollback.add_argument("--revision", help="explicit revision to roll back to")

    p_promote = sub.add_parser("promote", help="shift 100% traffic to a READY revision")
    p_promote.add_argument("--revision", required=True)

    p_smoke = sub.add_parser("smoke", help="run smoke checks")
    p_smoke.add_argument("--url", help="base url (default: the service url)")

    sub.add_parser("status", help="show traffic state")
    sub.add_parser("gate", help="run the local test gate only")

    args = parser.parse_args(argv)
    try:
        if args.command == "deploy":
            cmd_deploy(skip_gate=args.skip_gate, no_promote=args.no_promote)
        elif args.command == "rollback":
            cmd_rollback(args.revision)
        elif args.command == "promote":
            cmd_promote(args.revision)
        elif args.command == "smoke":
            smoke(args.url or describe_service()["url"])
        elif args.command == "status":
            cmd_status()
        elif args.command == "gate":
            run_gate()
    except DeployError as e:
        print(f"\nFAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
