import hashlib
import json
from pathlib import Path

import pytest

from b2_test_data import passing_snapshot_validation, state_record

from gate_b_v2.authorization import (
    AuthorizationError,
    DISCOVERY_AUTHORIZATION_FILENAME,
    CONFIRMATION_AUTHORIZATION_FILENAME,
    PREFLIGHT_SUMMARY_FILENAME,
    preflight_status,
    require_preflight_seed,
    validate_confirmation_authorization,
    validate_discovery_authorization,
    validate_preflight_gate,
)
from gate_b_v2.core import sha256_tree
from gate_b_v2.evidence import export_preflight_evidence
from gate_b_v2.locks import (
    B2_PROTOCOL_VERSION,
    b2_record_environment_fields,
    build_b2_run_manifest,
    load_b1_full_manifest,
    load_fixed_project_config,
)


ROOT = Path(__file__).resolve().parents[1]
COMMIT = "a" * 40


def _runtime_like_b1(b1):
    runtime = dict(b1)
    runtime["device_requested"] = runtime.get("device", "cuda:0")
    runtime.pop("_manifest_path", None)
    runtime.pop("_manifest_sha256", None)
    return runtime


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _preflight_run(run_dir: Path, summary_overrides=None):
    run_dir.mkdir(parents=True, exist_ok=True)
    config = load_fixed_project_config()
    b1 = load_b1_full_manifest(ROOT / "reports" / "b1_full_run.json")
    runtime = _runtime_like_b1(b1)
    b2_manifest = build_b2_run_manifest(
        config, runtime, b1, split="preflight", command="test"
    )
    environment = b2_record_environment_fields(b2_manifest)
    environment_sha = hashlib.sha256(
        json.dumps(environment, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    audit_path = run_dir / "b2_geometry_audit.json"
    audit = {
        "marker": "PREFLIGHT",
        "scientific_data": False,
        "status": "PASS",
        "stage_gate_version": "B2_GEOMETRY_GATE_V1_20261116",
    }
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    validation_path = run_dir / "b2_preflight_snapshot_validation.json"
    validation = passing_snapshot_validation("preflight", {"pre_299999": "snapsha"})
    validation_path.write_text(json.dumps(validation), encoding="utf-8")

    summary = {
        "marker": "PREFLIGHT",
        "scientific_data": False,
        "status": "PASS",
        "seed": 299999,
        "preflight_seed": 299999,
        "protocol_version": B2_PROTOCOL_VERSION,
        "stage_gate_version": "B2_GEOMETRY_GATE_V1_20261116",
        "implementation_commit": COMMIT,
        "source_tree_sha256": sha256_tree(ROOT / "src" / "gate_b_v2"),
        "geometry_audit": audit_path.name,
        "geometry_status": "PASS",
        "geometry_audit_sha256": _sha(audit_path),
        "snapshot_validation": validation_path.name,
        "snapshot_validation_sha256": _sha(validation_path),
        "snapshot_validation_all_passed": True,
        "gate_reached": True,
        "fallback_used": False,
        "snapshot_file": "snapshots/preflight/pre_299999.pkl.gz",
        "snapshot_sha256": "snapsha",
        "environment_fingerprint": environment,
        "environment_fingerprint_sha256": environment_sha,
    }
    if summary_overrides:
        summary.update(summary_overrides)
    (run_dir / PREFLIGHT_SUMMARY_FILENAME).write_text(json.dumps(summary), encoding="utf-8")
    return run_dir, runtime, config, summary


def test_preflight_seed_is_frozen_and_gate_status_is_fail_closed():
    assert require_preflight_seed(299999) == 299999
    with pytest.raises(AuthorizationError, match="frozen at 299999"):
        require_preflight_seed(300000)
    assert preflight_status("PASS", True, True, False) == "PASS"
    assert preflight_status("PASS", False, True, False) == "BLOCKED"
    assert preflight_status("PASS", True, False, False) == "BLOCKED"
    assert preflight_status("PASS", True, True, True) == "BLOCKED"
    assert preflight_status("BLOCKED", True, True, False) == "BLOCKED"


def test_valid_preflight_gate_and_discovery_authorization(tmp_path):
    run_dir, runtime, config, summary = _preflight_run(tmp_path)
    preflight = validate_preflight_gate(
        run_dir, runtime, config=config, project_root=ROOT,
        expected_implementation_commit=COMMIT,
    )
    assert preflight["summary"]["status"] == "PASS"
    authorization = {
        "approved": True,
        "protocol_version": B2_PROTOCOL_VERSION,
        "implementation_commit": COMMIT,
        "preflight_summary_sha256": _sha(run_dir / PREFLIGHT_SUMMARY_FILENAME),
        "authorized_by": "research-lead",
        "authorized_at": "2026-11-17T12:00:00+08:00",
        "authorized_scope": ["discovery"],
    }
    (run_dir / DISCOVERY_AUTHORIZATION_FILENAME).write_text(
        json.dumps(authorization), encoding="utf-8"
    )
    result = validate_discovery_authorization(
        run_dir, runtime, config=config, project_root=ROOT,
        expected_implementation_commit=COMMIT,
    )
    assert result["scope"] == "discovery"


def test_unauthorized_discovery_is_rejected(tmp_path):
    run_dir, runtime, config, summary = _preflight_run(tmp_path)
    with pytest.raises(AuthorizationError, match="discovery authorization not found"):
        validate_discovery_authorization(
            run_dir, runtime, config=config, project_root=ROOT,
            expected_implementation_commit=COMMIT,
        )


@pytest.mark.parametrize(
    "override, message",
    [
        ({"approved": False}, "approved is not true"),
        ({"protocol_version": "old"}, "protocol_version"),
        ({"implementation_commit": "b" * 40}, "implementation_commit"),
        ({"preflight_summary_sha256": "0" * 64}, "preflight_summary_sha256"),
        ({"authorized_by": ""}, "authorized_by"),
        ({"authorized_scope": ["confirmation"]}, "authorized_scope"),
    ],
)
def test_discovery_authorization_tampering_is_rejected(tmp_path, override, message):
    run_dir, runtime, config, summary = _preflight_run(tmp_path)
    authorization = {
        "approved": True,
        "protocol_version": B2_PROTOCOL_VERSION,
        "implementation_commit": COMMIT,
        "preflight_summary_sha256": _sha(run_dir / PREFLIGHT_SUMMARY_FILENAME),
        "authorized_by": "research-lead",
        "authorized_at": "2026-11-17T12:00:00+08:00",
        "authorized_scope": ["discovery"],
    }
    authorization.update(override)
    (run_dir / DISCOVERY_AUTHORIZATION_FILENAME).write_text(
        json.dumps(authorization), encoding="utf-8"
    )
    with pytest.raises(AuthorizationError, match=message):
        validate_discovery_authorization(
            run_dir, runtime, config=config, project_root=ROOT,
            expected_implementation_commit=COMMIT,
        )


def test_preflight_gate_rejects_fallback_or_wrong_seed(tmp_path):
    run_dir, runtime, config, summary = _preflight_run(
        tmp_path, {"gate_reached": False, "fallback_used": True, "status": "BLOCKED"}
    )
    with pytest.raises(AuthorizationError, match="status is not PASS"):
        validate_preflight_gate(run_dir, runtime, config=config, project_root=ROOT)

    run_dir, runtime, config, summary = _preflight_run(tmp_path / "seed")
    summary["seed"] = 300000
    (run_dir / PREFLIGHT_SUMMARY_FILENAME).write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(AuthorizationError, match="seed must be 299999"):
        validate_preflight_gate(run_dir, runtime, config=config, project_root=ROOT)


def test_preflight_gate_rejects_environment_or_audit_mismatch(tmp_path):
    run_dir, runtime, config, summary = _preflight_run(tmp_path / "env")
    summary["environment_fingerprint"] = dict(summary["environment_fingerprint"])
    summary["environment_fingerprint"]["checkpoint_sha256"] = "0" * 64
    (run_dir / PREFLIGHT_SUMMARY_FILENAME).write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(AuthorizationError, match="environment fingerprint"):
        validate_preflight_gate(run_dir, runtime, config=config, project_root=ROOT)

    run_dir, runtime, config, summary = _preflight_run(tmp_path / "source")
    summary["source_tree_sha256"] = "0" * 64
    (run_dir / PREFLIGHT_SUMMARY_FILENAME).write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(AuthorizationError, match="source tree fingerprint"):
        validate_preflight_gate(run_dir, runtime, config=config, project_root=ROOT)

    run_dir, runtime, config, summary = _preflight_run(tmp_path / "audit")
    audit_path = run_dir / "b2_geometry_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit["status"] = "BLOCKED"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    summary["geometry_audit_sha256"] = _sha(audit_path)
    (run_dir / PREFLIGHT_SUMMARY_FILENAME).write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(AuthorizationError, match="geometry audit status"):
        validate_preflight_gate(run_dir, runtime, config=config, project_root=ROOT)


def _discovery_artifacts(root: Path, config, runtime, b1):
    root.mkdir(parents=True, exist_ok=True)
    manifest = build_b2_run_manifest(config, runtime, b1, split="discovery", command="test")
    (root / "b2_discovery_run.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "b2_discovery_episodes.jsonl").write_text("{}\n", encoding="utf-8")
    states = [state_record("discovery", 300000 + index, 100 + index, 0.001) for index in range(30)]
    (root / "b2_discovery_state_manifest.jsonl").write_text(
        "".join(json.dumps(state) + "\n" for state in states), encoding="utf-8",
    )
    validation = passing_snapshot_validation(
        "discovery", {state["state_id"]: state["snapshot_sha256"] for state in states},
    )
    (root / "b2_discovery_snapshot_validation.json").write_text(json.dumps(validation), encoding="utf-8")
    (root / "b2_discovery_summary.json").write_text(json.dumps({
        "status": "COMPLETE", "completeness_verified": True, "n_branch_records": 450,
    }), encoding="utf-8")
    (root / "b2_discovery_status.json").write_text(json.dumps({
        "status": "COMPLETE", "snapshot_validation_all_passed": True,
    }), encoding="utf-8")
    analysis = {
        "decision": "DISCOVERY_UNCERTAIN_CONFIRMATION_JUSTIFIED",
        "primary": {"E": 0.1},
    }
    (root / "b2_discovery_analysis.json").write_text(json.dumps(analysis), encoding="utf-8")
    (root / "B2_REPORT.md").write_text("# discovery report\n", encoding="utf-8")
    return root / "b2_discovery_analysis.json"


def _confirmation_auth(run_dir, discovery_dir, analysis_path):
    authorization = {
        "approved": True,
        "protocol_version": B2_PROTOCOL_VERSION,
        "implementation_commit": COMMIT,
        "preflight_summary_sha256": _sha(run_dir / PREFLIGHT_SUMMARY_FILENAME),
        "authorized_by": "research-lead",
        "authorized_at": "2026-11-17T12:00:00+08:00",
        "authorized_scope": ["confirmation"],
        "discovery_run_dir": str(discovery_dir),
        "discovery_analysis_sha256": _sha(analysis_path),
    }
    (run_dir / CONFIRMATION_AUTHORIZATION_FILENAME).write_text(
        json.dumps(authorization), encoding="utf-8"
    )
    return authorization


def test_unauthorized_confirmation_is_rejected(tmp_path):
    run_dir, runtime, config, summary = _preflight_run(tmp_path / "conf")
    b1 = load_b1_full_manifest(ROOT / "reports" / "b1_full_run.json")
    _discovery_artifacts(tmp_path / "conf" / "discovery", config, runtime, b1)
    with pytest.raises(AuthorizationError, match="confirmation authorization not found"):
        validate_confirmation_authorization(
            run_dir, runtime, config=config, project_root=ROOT,
            expected_implementation_commit=COMMIT,
        )


def test_confirmation_requires_discovery_results(tmp_path, monkeypatch):
    run_dir, runtime, config, summary = _preflight_run(tmp_path / "conf")
    b1 = load_b1_full_manifest(ROOT / "reports" / "b1_full_run.json")
    discovery_dir = tmp_path / "conf" / "discovery"
    discovery_dir.mkdir()
    analysis_path = discovery_dir / "b2_discovery_analysis.json"
    analysis_path.write_text(json.dumps({"decision": "DISCOVERY_UNCERTAIN_CONFIRMATION_JUSTIFIED"}), encoding="utf-8")
    _confirmation_auth(run_dir, discovery_dir, analysis_path)
    with pytest.raises(AuthorizationError, match="missing"):
        validate_confirmation_authorization(
            run_dir, runtime, config=config, project_root=ROOT,
            expected_implementation_commit=COMMIT,
        )


def test_confirmation_rejects_stop_or_wrong_analysis_sha(tmp_path, monkeypatch):
    monkeypatch.setattr("gate_b_v2.b2_protocol.validate_state_manifest", lambda *a, **k: None)
    monkeypatch.setattr("gate_b_v2.b2_protocol.validate_b2_records", lambda *a, **k: {})
    run_dir, runtime, config, summary = _preflight_run(tmp_path / "conf")
    b1 = load_b1_full_manifest(ROOT / "reports" / "b1_full_run.json")
    discovery_dir = tmp_path / "conf" / "discovery"
    analysis_path = _discovery_artifacts(discovery_dir, config, runtime, b1)
    auth = _confirmation_auth(run_dir, discovery_dir, analysis_path)

    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    analysis["decision"] = "STOP_LACKING_PLAUSIBLE_PRACTICAL_EFFECT"
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
    auth["discovery_analysis_sha256"] = _sha(analysis_path)
    (run_dir / CONFIRMATION_AUTHORIZATION_FILENAME).write_text(json.dumps(auth), encoding="utf-8")
    with pytest.raises(AuthorizationError, match="decision is STOP"):
        validate_confirmation_authorization(
            run_dir, runtime, config=config, project_root=ROOT,
            expected_implementation_commit=COMMIT,
        )

    analysis["decision"] = "DISCOVERY_UNCERTAIN_CONFIRMATION_JUSTIFIED"
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
    auth["discovery_analysis_sha256"] = "0" * 64
    (run_dir / CONFIRMATION_AUTHORIZATION_FILENAME).write_text(json.dumps(auth), encoding="utf-8")
    with pytest.raises(AuthorizationError, match="discovery_analysis_sha256"):
        validate_confirmation_authorization(
            run_dir, runtime, config=config, project_root=ROOT,
            expected_implementation_commit=COMMIT,
        )


def test_valid_confirmation_authorization(tmp_path, monkeypatch):
    monkeypatch.setattr("gate_b_v2.b2_protocol.validate_state_manifest", lambda *a, **k: None)
    monkeypatch.setattr("gate_b_v2.b2_protocol.validate_b2_records", lambda *a, **k: {})
    run_dir, runtime, config, summary = _preflight_run(tmp_path / "conf")
    b1 = load_b1_full_manifest(ROOT / "reports" / "b1_full_run.json")
    discovery_dir = tmp_path / "conf" / "discovery"
    analysis_path = _discovery_artifacts(discovery_dir, config, runtime, b1)
    _confirmation_auth(run_dir, discovery_dir, analysis_path)
    result = validate_confirmation_authorization(
        run_dir, runtime, config=config, project_root=ROOT,
        expected_implementation_commit=COMMIT,
    )
    assert result["scope"] == "confirmation"
    assert result["discovery_decision"] == "DISCOVERY_UNCERTAIN_CONFIRMATION_JUSTIFIED"


def test_export_preflight_evidence_rejects_non_pass_and_exports_marked_json(tmp_path):
    run_dir, runtime, config, summary = _preflight_run(tmp_path / "bad", {
        "status": "BLOCKED", "gate_reached": False, "fallback_used": True,
    })
    with pytest.raises(RuntimeError, match="Only a PASS preflight"):
        export_preflight_evidence(run_dir, tmp_path / "bad_out")

    run_dir, runtime, config, summary = _preflight_run(tmp_path / "good")
    manifest = export_preflight_evidence(run_dir, tmp_path / "good_out")
    assert manifest.is_file()
    for name in (
        "b2_geometry_audit.json",
        "b2_preflight_summary.json",
        "b2_preflight_snapshot_validation.json",
        "b2_preflight_environment.json",
        "PREFLIGHT_EVIDENCE_MANIFEST.json",
    ):
        path = tmp_path / "good_out" / name
        assert path.is_file()
        value = json.loads(path.read_text(encoding="utf-8"))
        assert value["marker"] == "PREFLIGHT"
        assert value["scientific_data"] is False
    assert not any(path.suffix in (".pkl", ".gz") for path in (tmp_path / "good_out").iterdir())
