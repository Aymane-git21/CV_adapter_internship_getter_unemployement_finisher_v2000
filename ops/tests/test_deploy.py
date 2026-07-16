"""Gate tests for the deploy protocol's decision logic. No network, no gcloud."""
import pytest

from ops.deploy import (
    DeployError,
    candidate_tag,
    check_config,
    check_health,
    check_index,
    deploy_args,
    parse_service,
    ready_revisions,
    rollback_target,
    serving_revision,
    stale_candidate_tags,
    tag_url,
    traffic_args,
)

SERVICE_URL = "https://cvglowup-i6e3w7o3sq-ew.a.run.app"


def describe_payload(traffic, latest_created="cvglowup-00011-abc", latest_ready="cvglowup-00011-abc"):
    return {
        "status": {
            "url": SERVICE_URL,
            "latestCreatedRevisionName": latest_created,
            "latestReadyRevisionName": latest_ready,
            "traffic": traffic,
        }
    }


# ---- candidate_tag / tag_url ----------------------------------------------

def test_candidate_tag_truncates_sha():
    assert candidate_tag("a48b8a1f00112233445566778899aabbccddeeff") == "cand-a48b8a1f0011"


def test_candidate_tag_rejects_garbage():
    for bad in ("", "main", "HEAD", "a48b8a1; rm -rf /", "xyz1234"):
        with pytest.raises(DeployError):
            candidate_tag(bad)


def test_tag_url_inserts_tag_before_host():
    assert tag_url("cand-a48b8a1f0011", SERVICE_URL) == (
        "https://cand-a48b8a1f0011---cvglowup-i6e3w7o3sq-ew.a.run.app"
    )


def test_tag_url_rejects_non_https():
    with pytest.raises(DeployError):
        tag_url("cand-abc1234", "http://insecure.example")


# ---- parse_service / serving_revision --------------------------------------

def test_parse_service_extracts_traffic():
    state = parse_service(
        describe_payload(
            [
                {"revisionName": "cvglowup-00010-hmk", "percent": 100, "latestRevision": True},
                {"revisionName": "cvglowup-00011-abc", "tag": "cand-abc", "url": "https://x"},
            ]
        )
    )
    assert state["url"] == SERVICE_URL
    assert state["latest_created"] == "cvglowup-00011-abc"
    assert state["traffic"][0] == {
        "revision": "cvglowup-00010-hmk", "percent": 100, "tag": "", "url": "",
    }
    assert state["traffic"][1]["percent"] == 0  # missing percent means 0, not a crash


def test_serving_revision_single():
    state = parse_service(describe_payload([{"revisionName": "cvglowup-00010-hmk", "percent": 100}]))
    assert serving_revision(state) == "cvglowup-00010-hmk"


def test_serving_revision_refuses_split_traffic():
    state = parse_service(
        describe_payload(
            [
                {"revisionName": "cvglowup-00010-hmk", "percent": 60},
                {"revisionName": "cvglowup-00009-zqk", "percent": 40},
            ]
        )
    )
    with pytest.raises(DeployError, match="split"):
        serving_revision(state)


# ---- ready_revisions / rollback_target --------------------------------------

REVISIONS = [
    {
        "metadata": {"name": "cvglowup-00009-zqk", "creationTimestamp": "2026-07-13T10:32:19Z"},
        "status": {"conditions": [{"type": "Ready", "status": "True"}]},
    },
    {
        "metadata": {"name": "cvglowup-00011-bad", "creationTimestamp": "2026-07-16T09:00:00Z"},
        "status": {"conditions": [{"type": "Ready", "status": "False"}]},
    },
    {
        "metadata": {"name": "cvglowup-00010-hmk", "creationTimestamp": "2026-07-13T10:35:01Z"},
        "status": {"conditions": [{"type": "Ready", "status": "True"}]},
    },
]


def test_ready_revisions_sorted_newest_first_and_filters_unready():
    assert ready_revisions(REVISIONS) == ["cvglowup-00010-hmk", "cvglowup-00009-zqk"]


def test_rollback_target_picks_previous_ready():
    ready = ["cvglowup-00011-new", "cvglowup-00010-hmk", "cvglowup-00009-zqk"]
    assert rollback_target(ready, serving="cvglowup-00011-new") == "cvglowup-00010-hmk"


def test_rollback_target_explicit():
    ready = ["cvglowup-00011-new", "cvglowup-00010-hmk", "cvglowup-00009-zqk"]
    assert rollback_target(ready, "cvglowup-00011-new", "cvglowup-00009-zqk") == "cvglowup-00009-zqk"


def test_rollback_target_rejects_current_and_unknown():
    ready = ["cvglowup-00011-new", "cvglowup-00010-hmk"]
    with pytest.raises(DeployError, match="already serving"):
        rollback_target(ready, "cvglowup-00011-new", "cvglowup-00011-new")
    with pytest.raises(DeployError, match="not a READY"):
        rollback_target(ready, "cvglowup-00011-new", "cvglowup-00007-t68")


def test_rollback_target_nothing_older():
    with pytest.raises(DeployError, match="no older"):
        rollback_target(["cvglowup-00011-new"], "cvglowup-00011-new")


# ---- deploy_args: the config-wipe regression guard --------------------------

def test_deploy_args_never_touches_traffic():
    assert "--no-traffic" in deploy_args("cand-abc1234")


def test_deploy_args_keeps_vertex_config():
    """Revision 00010 broke silently once when --set-env-vars wiped manually
    added vars. The full declarative set must always be present."""
    args = deploy_args("cand-abc1234")
    env = args[args.index("--set-env-vars") + 1]
    assert "GEMINI_USE_VERTEX=1" in env
    assert "GCP_PROJECT=" in env


def test_deploy_args_wires_all_secrets():
    args = deploy_args("cand-abc1234")
    sec = args[args.index("--set-secrets") + 1]
    for secret in ("SECRET_KEY=SECRET_KEY:latest", "DATABASE_URL=DATABASE_URL:latest",
                   "GEMINI_API_KEY=GEMINI_API_KEY:latest"):
        assert secret in sec


def test_traffic_args_pins_single_revision():
    args = traffic_args("cvglowup-00011-new")
    assert args[args.index("--to-revisions") + 1] == "cvglowup-00011-new=100"


def test_stale_candidate_tags_keeps_current_and_serving():
    traffic = [
        {"revision": "cvglowup-00011-new", "percent": 100, "tag": "cand-newsha11111", "url": "u"},
        {"revision": "cvglowup-00010-hmk", "percent": 0, "tag": "cand-oldsha00000", "url": "u"},
        {"revision": "cvglowup-00009-zqk", "percent": 0, "tag": "cand-oldsha99999", "url": "u"},
        {"revision": "cvglowup-00008-bcb", "percent": 0, "tag": "special", "url": "u"},
    ]
    assert stale_candidate_tags(traffic, keep_revision="cvglowup-00011-new") == [
        "cand-oldsha00000", "cand-oldsha99999",
    ]


# ---- smoke check logic -------------------------------------------------------

def test_check_health():
    assert check_health({"ok": True, "db": True}) == []
    assert any("db=" in p for p in check_health({"ok": True, "db": False}))
    assert check_health({}) != []


def test_check_config_happy():
    payload = {
        "ai_mode": "gemini",
        "templates": [{"id": "onyx"}, {"id": "classic"}, {"id": "compact"}],
        "plans": [{"key": "free"}, {"key": "plus"}, {"key": "pro"}],
    }
    assert check_config(payload) == []


def test_check_config_catches_offline_ai_in_prod():
    payload = {
        "ai_mode": "offline",
        "templates": [{"id": "onyx"}, {"id": "classic"}],
        "plans": [{"key": "free"}, {"key": "plus"}, {"key": "pro"}],
    }
    assert any("ai_mode" in p for p in check_config(payload))
    assert check_config(payload, require_gemini=False) == []


def test_check_config_catches_missing_plans():
    payload = {"ai_mode": "gemini", "templates": [{"id": "onyx"}, {"id": "classic"}], "plans": []}
    assert any("plans" in p for p in check_config(payload))


def test_check_index():
    assert check_index('<html><div id="root"></div><title>CV Glowup</title></html>') == []
    assert check_index("<html>Error</html>") != []
