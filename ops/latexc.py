"""Deploy + warmth control for the latexc service (services/latexc) on Cloud Run.

Mirrors ops/deploy.py's zero-downtime protocol for the second service without
touching the app deploy path: build via Cloud Build (repo-root context so the
image gets the shared fonts) -> candidate revision (--no-traffic) -> smoke the
tagged URL with a real probe compile -> promote -> smoke again.

Commands:
  python ops/latexc.py deploy     build + candidate + smoke + promote
  python ops/latexc.py on         min-instances=1 (warm until turned off)
  python ops/latexc.py off        min-instances=0 (the manual off-switch)
  python ops/latexc.py status     traffic, min-instances, idle cost estimate
  python ops/latexc.py rollback   shift traffic to the previous READY revision
  python ops/latexc.py smoke      probe-compile against the live service

Warmth model: `on`/`off` here and the backend's /api/latex/warmup PATCH the
same knob (scaling.minInstanceCount). `off` is the manual kill switch the
feature contract promises; the backend's idle reaper (LATEXC_IDLE_OFF_MINUTES)
is the billing backstop. Configuration is code: the block below is the full
runtime set, console edits get wiped on the next deploy.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ops.deploy import (  # noqa: E402  (path bootstrap above)
    DeployError,
    candidate_tag,
    gcloud_json,
    gcloud_stream,
    git_dirty_tracked,
    git_sha,
    parse_service,
    ready_revisions,
    rollback_target,
    serving_revision,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

PROJECT = os.environ.get("GCP_PROJECT_ID", "project-60fad876-6da7-41f3-bfd")
REGION = os.environ.get("GCP_REGION", "europe-west1")
SERVICE = os.environ.get("CVG_LATEXC_SERVICE", "cvglowup-latexc")
# The AR repo `gcloud run deploy --source` already provisions for the app.
IMAGE_REPO = f"{REGION}-docker.pkg.dev/{PROJECT}/cloud-run-source-deploy/{SERVICE}"

MEMORY = "2Gi"
CPU = "1"
CONCURRENCY = "2"
MIN_INSTANCES = "0"  # cold by default; warmth is a runtime toggle (on/warmup)
MAX_INSTANCES = "2"
TIMEOUT_S = "120"
SECRETS = {"LATEXC_TOKEN": "LATEXC_TOKEN:latest"}

SMOKE_ATTEMPTS = 8
SMOKE_BACKOFF_S = 10
HTTP_TIMEOUT_S = 90  # first compile after boot includes the prewarm queue

IDLE_COST_LINE = "~$8/month while warm (1 vCPU + 2 GiB idle min-instance)"

_PROBE_TEX = (REPO_ROOT / "services" / "latexc" / "probe.tex").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Pure decision logic (unit-tested in ops/tests/test_latexc_ops.py)
# ---------------------------------------------------------------------------

def image_ref(sha: str) -> str:
    sha = sha.strip().lower()
    if not sha or not all(c in "0123456789abcdef" for c in sha) or len(sha) < 7:
        raise DeployError(f"not a git sha: {sha!r}")
    return f"{IMAGE_REPO}:{sha[:12]}"


def build_args(image: str) -> list[str]:
    return [
        "builds", "submit",
        "--project", PROJECT,
        "--config", "services/latexc/cloudbuild.yaml",
        "--substitutions", f"_IMAGE={image}",
        ".",
    ]


def deploy_args(tag: str, image: str) -> list[str]:
    sec = ",".join(f"{k}={v}" for k, v in sorted(SECRETS.items()))
    return [
        "run", "deploy", SERVICE,
        "--project", PROJECT,
        "--region", REGION,
        "--image", image,
        "--no-traffic",
        "--tag", tag,
        "--allow-unauthenticated",  # LATEXC_TOKEN is the auth boundary (401 without it)
        "--session-affinity",
        "--memory", MEMORY,
        "--cpu", CPU,
        "--concurrency", CONCURRENCY,
        "--min-instances", MIN_INSTANCES,
        "--max-instances", MAX_INSTANCES,
        "--timeout", TIMEOUT_S,
        "--set-secrets", sec,
        "--quiet",
    ]


def first_deploy_args(image: str) -> list[str]:
    """A brand-new service cannot take --no-traffic/--tag: first revision serves."""
    args = deploy_args("cand-unused000", image)
    out = []
    skip_next = False
    for a in args:
        if skip_next:
            skip_next = False
            continue
        if a == "--no-traffic":
            continue
        if a == "--tag":
            skip_next = True
            continue
        out.append(a)
    return out


def traffic_args(revision: str) -> list[str]:
    return [
        "run", "services", "update-traffic", SERVICE,
        "--project", PROJECT,
        "--region", REGION,
        "--to-revisions", f"{revision}=100",
        "--quiet",
    ]


def min_instances_args(n: int) -> list[str]:
    if n not in (0, 1):
        raise DeployError(f"min-instances must be 0 or 1, got {n}")
    return [
        "run", "services", "update", SERVICE,
        "--project", PROJECT,
        "--region", REGION,
        "--min-instances", str(n),
        "--quiet",
    ]


def parse_min_instances(payload: dict) -> int:
    """From `gcloud run services describe --format json` (v1 shape)."""
    ann = (
        payload.get("spec", {})
        .get("template", {})
        .get("metadata", {})
        .get("annotations", {})
    )
    try:
        return int(ann.get("autoscaling.knative.dev/minScale", "0"))
    except (TypeError, ValueError):
        return 0


def cost_line(min_instances: int) -> str:
    return IDLE_COST_LINE if min_instances >= 1 else "$0 idle (scaled to zero)"


def check_status_payload(payload: dict) -> list[str]:
    problems = []
    if payload.get("ok") is not True:
        problems.append(f"/v1/status ok={payload.get('ok')!r}")
    if payload.get("version") != "1":
        problems.append(f"/v1/status contract version={payload.get('version')!r}, expected '1'")
    return problems


def check_compile_payload(payload: dict) -> list[str]:
    problems = []
    if payload.get("ok") is not True:
        problems.append(
            f"probe compile failed: {payload.get('error_line') or payload.get('log_tail', '')[-300:]}"
        )
    if payload.get("pages") != 1:
        problems.append(f"probe compile pages={payload.get('pages')!r}")
    pdf = payload.get("pdf_b64") or ""
    if not pdf.startswith("JVBERi"):  # base64("%PDF")
        problems.append("probe compile returned no PDF")
    return problems


def probe_body() -> dict:
    return {
        "doc_id": "_ops-smoke",
        "files": [
            {
                "path": "main.tex",
                "content_b64": base64.b64encode(_PROBE_TEX.encode("utf-8")).decode(),
            }
        ],
        "want_svgs": True,
    }


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def fetch_token() -> str:
    """Read LATEXC_TOKEN from Secret Manager; never echo it."""
    res = subprocess.run(
        ["gcloud", "secrets", "versions", "access", "latest",
         "--secret", "LATEXC_TOKEN", "--project", PROJECT],
        capture_output=True, text=True, shell=os.name == "nt",
    )
    if res.returncode != 0:
        raise DeployError(
            "could not read LATEXC_TOKEN from Secret Manager (created it yet? "
            f"see docs/deploy.md):\n{res.stderr.strip()}"
        )
    return res.stdout.strip()


def _http(url: str, token: str, body: dict | None = None) -> tuple[int, bytes]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "cvglowup-latexc-ops",
        },
        method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def service_exists() -> bool:
    try:
        gcloud_json(["run", "services", "describe", SERVICE, "--project", PROJECT, "--region", REGION])
        return True
    except DeployError:
        return False


def describe() -> dict:
    return parse_service(
        gcloud_json(["run", "services", "describe", SERVICE, "--project", PROJECT, "--region", REGION])
    )


def describe_raw() -> dict:
    return gcloud_json(
        ["run", "services", "describe", SERVICE, "--project", PROJECT, "--region", REGION]
    )


def smoke(base_url: str, token: str) -> None:
    base = base_url.rstrip("/")
    for attempt in range(1, SMOKE_ATTEMPTS + 1):
        problems: list[str] = []
        try:
            status, raw = _http(f"{base}/v1/status", token)
            problems += (
                [f"/v1/status HTTP {status}"] if status != 200 else check_status_payload(json.loads(raw))
            )
            if not problems:
                status, raw = _http(f"{base}/v1/compile", token, probe_body())
                problems += (
                    [f"/v1/compile HTTP {status}: {raw[:200]!r}"]
                    if status != 200
                    else check_compile_payload(json.loads(raw))
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


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def preflight() -> str:
    billing = gcloud_json(["billing", "projects", "describe", PROJECT])
    if not billing.get("billingEnabled"):
        raise DeployError("GCP billing is DISABLED on the project (the past-due gotcha).")
    dirty = git_dirty_tracked()
    if dirty:
        raise DeployError(f"tracked files have uncommitted changes, commit first:\n{dirty}")
    return git_sha()


def cmd_deploy() -> None:
    sha = preflight()
    image = image_ref(sha)
    token = fetch_token()

    print(f"[latexc] building {image} via Cloud Build (repo-root context)")
    gcloud_stream(build_args(image), timeout=1800)

    if not service_exists():
        print(f"[latexc] first deploy of {SERVICE}: the initial revision takes traffic directly")
        gcloud_stream(first_deploy_args(image))
        state = describe()
        smoke(state["url"], token)
        print(f"[latexc] DONE: {SERVICE} live at {state['url']} (min-instances {MIN_INSTANCES})")
        print(f"[latexc] app wiring: deploy the app with CVG_LATEXC_URL={state['url']}")
        return

    tag = candidate_tag(sha)
    before = describe()
    previous = serving_revision(before)
    print(f"[latexc] serving now: {previous} (rollback target)")

    gcloud_stream(deploy_args(tag, image))
    after = describe()
    new_revision = after["latest_created"]
    if new_revision == previous:
        raise DeployError("no new revision was created")
    cand = next((t for t in after["traffic"] if t["tag"] == tag), None)
    if not cand or not cand["url"]:
        raise DeployError(f"candidate tag {tag} not found in traffic config: {after['traffic']}")

    print(f"[latexc] candidate {new_revision} ready, smoking {cand['url']}")
    smoke(cand["url"], token)

    print(f"[latexc] promoting traffic: {previous} -> {new_revision}")
    gcloud_stream(traffic_args(new_revision))
    try:
        smoke(after["url"], token)
    except DeployError as e:
        print(f"[latexc] PROD SMOKE FAILED, rolling back to {previous}: {e}")
        gcloud_stream(traffic_args(previous))
        raise DeployError(f"deploy of {new_revision} rolled back to {previous}") from e
    print(f"[latexc] DONE: {new_revision} serves 100% at {after['url']}")


def cmd_toggle(n: int) -> None:
    gcloud_stream(min_instances_args(n))
    print(f"[latexc] min-instances -> {n} ({cost_line(n)})")


def cmd_status() -> None:
    raw = describe_raw()
    state = parse_service(raw)
    mins = parse_min_instances(raw)
    print(f"service : {SERVICE} ({REGION}, {PROJECT})")
    print(f"url     : {state['url']}")
    print(f"serving : {serving_revision(state)}")
    print(f"warm    : min-instances={mins} ({cost_line(mins)})")
    for t in state["traffic"]:
        tag = f"  tag={t['tag']} {t['url']}" if t["tag"] else ""
        print(f"traffic : {t['revision']} {t['percent']}%{tag}")


def cmd_rollback(revision: str | None) -> None:
    state = describe()
    serving = serving_revision(state)
    ready = ready_revisions(
        gcloud_json(
            ["run", "revisions", "list", "--service", SERVICE, "--project", PROJECT, "--region", REGION]
        )
    )
    target = rollback_target(ready, serving, revision)
    print(f"[latexc] shifting traffic: {serving} -> {target}")
    gcloud_stream(traffic_args(target))
    smoke(state["url"], fetch_token())
    print(f"[latexc] DONE: {target} serves 100%")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("deploy", help="build + candidate + smoke + promote")
    sub.add_parser("on", help="min-instances=1 (warm until turned off)")
    sub.add_parser("off", help="min-instances=0 (the manual off-switch)")
    sub.add_parser("status", help="traffic, warmth and cost")
    p_rb = sub.add_parser("rollback", help="traffic back to the previous READY revision")
    p_rb.add_argument("--revision")
    p_smoke = sub.add_parser("smoke", help="probe compile against the live service")
    p_smoke.add_argument("--url", help="base url (default: the service url)")

    args = parser.parse_args(argv)
    try:
        if args.command == "deploy":
            cmd_deploy()
        elif args.command == "on":
            cmd_toggle(1)
        elif args.command == "off":
            cmd_toggle(0)
        elif args.command == "status":
            cmd_status()
        elif args.command == "rollback":
            cmd_rollback(args.revision)
        elif args.command == "smoke":
            smoke(args.url or describe()["url"], fetch_token())
    except DeployError as e:
        print(f"\nFAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
