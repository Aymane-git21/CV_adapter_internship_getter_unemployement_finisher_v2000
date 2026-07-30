"""Unit tests for ops/latexc.py pure decision logic (no gcloud, no network)."""
import base64

import pytest

from ops.deploy import DeployError
from ops.latexc import (
    IMAGE_REPO,
    SERVICE,
    build_args,
    check_compile_payload,
    check_status_payload,
    cost_line,
    deploy_args,
    first_deploy_args,
    image_ref,
    min_instances_args,
    parse_min_instances,
    probe_body,
)


def test_image_ref_shortens_sha():
    ref = image_ref("a" * 40)
    assert ref == f"{IMAGE_REPO}:{'a' * 12}"
    with pytest.raises(DeployError):
        image_ref("not-a-sha")


def test_build_args_use_repo_root_context_and_config():
    args = build_args(f"{IMAGE_REPO}:abc123abc123")
    assert args[-1] == "."
    assert "--config" in args and "services/latexc/cloudbuild.yaml" in args
    assert f"_IMAGE={IMAGE_REPO}:abc123abc123" in args[args.index("--substitutions") + 1]


def test_deploy_args_shape():
    args = deploy_args("cand-abc123abc123", f"{IMAGE_REPO}:abc123abc123")
    assert args[:3] == ["run", "deploy", SERVICE]
    assert "--no-traffic" in args and "--session-affinity" in args
    assert "--image" in args and "--source" not in args
    assert args[args.index("--min-instances") + 1] == "0"
    assert args[args.index("--concurrency") + 1] == "2"
    assert "LATEXC_TOKEN=LATEXC_TOKEN:latest" in args[args.index("--set-secrets") + 1]


def test_first_deploy_args_drop_no_traffic_and_tag():
    args = first_deploy_args(f"{IMAGE_REPO}:abc123abc123")
    assert "--no-traffic" not in args
    assert "--tag" not in args
    assert "cand-unused000" not in args
    assert "--image" in args


def test_min_instances_args_bounds():
    on = min_instances_args(1)
    off = min_instances_args(0)
    assert on[on.index("--min-instances") + 1] == "1"
    assert off[off.index("--min-instances") + 1] == "0"
    with pytest.raises(DeployError):
        min_instances_args(3)


def test_parse_min_instances_reads_annotation():
    payload = {"spec": {"template": {"metadata": {"annotations": {"autoscaling.knative.dev/minScale": "1"}}}}}
    assert parse_min_instances(payload) == 1
    assert parse_min_instances({}) == 0
    assert parse_min_instances({"spec": {"template": {"metadata": {"annotations": {}}}}}) == 0


def test_cost_line():
    assert "$0" in cost_line(0)
    assert "month" in cost_line(1)


def test_check_status_payload():
    assert check_status_payload({"ok": True, "version": "1"}) == []
    assert check_status_payload({"ok": False, "version": "1"})
    assert check_status_payload({"ok": True, "version": "2"})


def test_check_compile_payload():
    good_pdf = base64.b64encode(b"%PDF-1.7 rest").decode()
    assert check_compile_payload({"ok": True, "pages": 1, "pdf_b64": good_pdf}) == []
    assert check_compile_payload({"ok": False, "pages": 0, "pdf_b64": "", "error_line": "boom"})
    assert check_compile_payload({"ok": True, "pages": 2, "pdf_b64": good_pdf})


def test_probe_body_is_valid_contract_payload():
    from services.latexc.contract import LatexCompileIn

    body = probe_body()
    parsed = LatexCompileIn.model_validate(body)
    assert parsed.doc_id == "_ops-smoke"
    assert base64.b64decode(parsed.files[0].content_b64).lstrip().startswith(b"%")
