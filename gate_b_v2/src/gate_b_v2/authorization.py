"""Fail-closed B2 formal-authorization gates.

Formal discovery/confirmation harvesting and branch execution are blocked unless
the same run directory contains a passing PREFLIGHT and the researcher has
created the relevant authorization JSON.  This module never creates those files.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from .core import sha256_tree
from .locks import (
    B2_CONFIG_FINGERPRINT,
    B2_LOCKED_CONFIG_VALUES,
    B2_PROTOCOL_VERSION,
    PREFLIGHT_SEED,
    b2_record_environment_fields,
    build_b2_run_manifest,
    load_b1_full_manifest,
    load_fixed_project_config,
    validate_b2_config,
    validate_b2_run_manifest,
)
from .snapshot import require_passed_snapshot_validation

PREFLIGHT_SUMMARY_FILENAME = "b2_preflight_summary.json"
GEOMETRY_AUDIT_FILENAME = "b2_geometry_audit.json"
PREFLIGHT_SNAPSHOT_VALIDATION_FILENAME = "b2_preflight_snapshot_validation.json"
DISCOVERY_AUTHORIZATION_FILENAME = "B2_DISCOVERY_AUTHORIZATION.json"
CONFIRMATION_AUTHORIZATION_FILENAME = "B2_CONFIRMATION_AUTHORIZATION.json"
STAGE_GATE_VERSION = "B2_GEOMETRY_GATE_V1_20261116"

DISCOVERY_PROCEED_DECISIONS = {
    "DISCOVERY_STRONG_SIGNAL_CONFIRMATION_JUSTIFIED",
    "DISCOVERY_UNCERTAIN_CONFIRMATION_JUSTIFIED",
}
DISCOVERY_STOP_DECISIONS = {
    "STOP_LACKING_PLAUSIBLE_PRACTICAL_EFFECT",
    "BLOCKED_OR_UNINFORMATIVE",
}


class AuthorizationError(RuntimeError):
    """Raised when a formal B2 action is not authorized or preflight is invalid."""


def require_preflight_seed(seed: int) -> int:
    if int(seed) != PREFLIGHT_SEED:
        raise AuthorizationError(
            "Formal B2 preflight seed is frozen at {}; got {}".format(PREFLIGHT_SEED, seed)
        )
    return PREFLIGHT_SEED


def preflight_status(
    geometry_status: str,
    gate_reached: bool,
    validation_all_passed: bool,
    fallback_used: bool,
) -> str:
    """PASS requires the real gate and a fully validated snapshot, never a fallback."""
    if (
        geometry_status == "PASS"
        and bool(gate_reached) is True
        and bool(validation_all_passed) is True
        and bool(fallback_used) is False
    ):
        return "PASS"
    return "BLOCKED"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> Dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise AuthorizationError("{} not found: {}".format(label, path))
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuthorizationError("{} is not valid JSON: {}: {}".format(label, path, exc))
    if not isinstance(value, dict):
        raise AuthorizationError("{} must contain a JSON object".format(label))
    return value


def _require_fields(value: Mapping[str, Any], fields: Sequence[str], label: str) -> None:
    missing = [field for field in fields if field not in value]
    if missing:
        raise AuthorizationError("{} is missing required fields: {}".format(label, missing))


def _require_nonempty_string(value: Mapping[str, Any], key: str, label: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise AuthorizationError("{} field {!r} must be a non-empty string".format(label, key))
    return item.strip()


def _scope_contains(scope: Any, required: str) -> bool:
    if isinstance(scope, str):
        return required in {part.strip() for part in scope.replace(",", " ").split()}
    if isinstance(scope, (list, tuple)):
        return required in {str(item).strip() for item in scope}
    return False


def _load_b1_manifest(config: Mapping[str, Any], project_root: Optional[Path]) -> Dict[str, Any]:
    manifest_path = Path(str(config["paths"]["b1_full_manifest"]))
    if not manifest_path.is_absolute():
        root = Path(project_root).resolve() if project_root is not None else Path(__file__).resolve().parents[2]
        manifest_path = (root / manifest_path).resolve()
    return load_b1_full_manifest(manifest_path)


def _preflight_environment(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    return b2_record_environment_fields(manifest)


def validate_preflight_gate(
    run_dir: Path,
    runtime_manifest: Mapping[str, Any],
    config: Optional[Mapping[str, Any]] = None,
    project_root: Optional[Path] = None,
    expected_implementation_commit: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate the same-run-directory PREFLIGHT evidence required before formal work."""
    run_dir = Path(run_dir)
    config = config or load_fixed_project_config(project_root)
    validate_b2_config(config)
    b1_full_manifest = _load_b1_manifest(config, project_root)
    b2_manifest = build_b2_run_manifest(
        config=config,
        runtime_manifest=runtime_manifest,
        b1_full_manifest=b1_full_manifest,
        split="preflight",
        command="b2-preflight-gate",
    )
    current_environment = _preflight_environment(b2_manifest)

    summary_path = run_dir / PREFLIGHT_SUMMARY_FILENAME
    summary = _load_json(summary_path, "B2 preflight summary")
    _require_fields(summary, (
        "marker", "scientific_data", "status", "seed", "protocol_version",
        "stage_gate_version", "implementation_commit", "source_tree_sha256",
        "geometry_audit", "geometry_status", "geometry_audit_sha256",
        "snapshot_validation", "snapshot_validation_sha256",
        "snapshot_validation_all_passed", "gate_reached",
        "snapshot_sha256",
        "environment_fingerprint", "environment_fingerprint_sha256",
    ), "B2 preflight summary")
    if summary.get("marker") != "PREFLIGHT":
        raise AuthorizationError("B2 preflight summary marker is not PREFLIGHT")
    if bool(summary.get("scientific_data")) is not False:
        raise AuthorizationError("B2 preflight summary must have scientific_data=false")
    if summary.get("status") != "PASS":
        raise AuthorizationError("B2 preflight summary status is not PASS")
    if int(summary.get("seed", -1)) != PREFLIGHT_SEED:
        raise AuthorizationError(
            "B2 preflight seed must be {}, got {!r}".format(PREFLIGHT_SEED, summary.get("seed"))
        )
    if summary.get("protocol_version") != B2_PROTOCOL_VERSION:
        raise AuthorizationError("B2 preflight protocol_version is not the frozen version")
    if summary.get("stage_gate_version") != STAGE_GATE_VERSION:
        raise AuthorizationError("B2 preflight stage_gate_version is not the frozen version")
    if bool(summary.get("gate_reached")) is not True:
        raise AuthorizationError("B2 preflight did not reach the stage gate")
    if bool(summary.get("fallback_used", False)) is not False:
        raise AuthorizationError("B2 preflight used a diagnostic fallback snapshot")
    if bool(summary.get("snapshot_validation_all_passed")) is not True:
        raise AuthorizationError("B2 preflight snapshot validation did not pass")
    if summary.get("geometry_status") != "PASS":
        raise AuthorizationError("B2 preflight geometry status is not PASS")

    implementation_commit = _require_nonempty_string(
        summary, "implementation_commit", "B2 preflight summary"
    )
    if expected_implementation_commit is not None and implementation_commit != expected_implementation_commit:
        raise AuthorizationError(
            "B2 preflight implementation_commit {} != current {}".format(
                implementation_commit, expected_implementation_commit
            )
        )

    root = Path(project_root).resolve() if project_root is not None else Path(__file__).resolve().parents[2]
    current_source_tree = sha256_tree(root / "src" / "gate_b_v2")
    if summary.get("source_tree_sha256") != current_source_tree:
        raise AuthorizationError(
            "B2 preflight source tree fingerprint does not match the current implementation"
        )

    audit_path = run_dir / str(summary["geometry_audit"])
    audit = _load_json(audit_path, "B2 geometry audit")
    if sha256_file(audit_path) != str(summary.get("geometry_audit_sha256")):
        raise AuthorizationError("B2 geometry audit SHA256 does not match the preflight summary")
    if audit.get("status") != "PASS":
        raise AuthorizationError("B2 geometry audit status is not PASS")
    if audit.get("marker") != "PREFLIGHT":
        raise AuthorizationError("B2 geometry audit marker is not PREFLIGHT")
    if bool(audit.get("scientific_data", True)) is not False:
        raise AuthorizationError("B2 geometry audit must have scientific_data=false")
    if audit.get("stage_gate_version") != STAGE_GATE_VERSION:
        raise AuthorizationError("B2 geometry audit stage gate version is not frozen")

    validation_path = run_dir / str(summary["snapshot_validation"])
    validation = _load_json(validation_path, "B2 preflight snapshot validation")
    if sha256_file(validation_path) != str(summary.get("snapshot_validation_sha256")):
        raise AuthorizationError("B2 snapshot validation SHA256 does not match the preflight summary")
    try:
        require_passed_snapshot_validation(validation, "preflight", {"pre_299999": summary["snapshot_sha256"]})
    except RuntimeError as exc:
        raise AuthorizationError(str(exc)) from exc

    recorded_environment = summary.get("environment_fingerprint")
    if not isinstance(recorded_environment, dict):
        raise AuthorizationError("B2 preflight environment_fingerprint must be an object")
    if recorded_environment != current_environment:
        raise AuthorizationError(
            "B2 preflight environment fingerprint does not match the current run environment"
        )
    expected_environment_sha = hashlib.sha256(
        json.dumps(current_environment, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    if summary.get("environment_fingerprint_sha256") != expected_environment_sha:
        raise AuthorizationError("B2 preflight environment fingerprint SHA256 is inconsistent")

    return {
        "summary": summary,
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "environment_fingerprint": current_environment,
        "environment_fingerprint_sha256": expected_environment_sha,
        "source_tree_sha256": current_source_tree,
        "implementation_commit": implementation_commit,
        "geometry_audit_sha256": sha256_file(audit_path),
        "snapshot_validation_sha256": sha256_file(validation_path),
    }


def _validate_authorization_common(
    authorization: Mapping[str, Any],
    label: str,
    preflight: Mapping[str, Any],
    expected_scope: str,
    expected_implementation_commit: Optional[str],
) -> None:
    _require_fields(authorization, (
        "approved", "protocol_version", "implementation_commit",
        "preflight_summary_sha256", "authorized_by", "authorized_at",
        "authorized_scope",
    ), label)
    if authorization.get("approved") is not True:
        raise AuthorizationError("{} approved is not true".format(label))
    if authorization.get("protocol_version") != B2_PROTOCOL_VERSION:
        raise AuthorizationError("{} protocol_version is not the frozen version".format(label))
    commit = _require_nonempty_string(authorization, "implementation_commit", label)
    if commit != preflight["implementation_commit"]:
        raise AuthorizationError("{} implementation_commit does not match preflight".format(label))
    if expected_implementation_commit is not None and commit != expected_implementation_commit:
        raise AuthorizationError("{} implementation_commit does not match current HEAD".format(label))
    if str(authorization.get("preflight_summary_sha256")) != preflight["summary_sha256"]:
        raise AuthorizationError("{} preflight_summary_sha256 does not match".format(label))
    _require_nonempty_string(authorization, "authorized_by", label)
    _require_nonempty_string(authorization, "authorized_at", label)
    if not _scope_contains(authorization.get("authorized_scope"), expected_scope):
        raise AuthorizationError(
            "{} authorized_scope does not include {!r}".format(label, expected_scope)
        )


def validate_discovery_authorization(
    run_dir: Path,
    runtime_manifest: Mapping[str, Any],
    config: Optional[Mapping[str, Any]] = None,
    project_root: Optional[Path] = None,
    expected_implementation_commit: Optional[str] = None,
) -> Dict[str, Any]:
    """Require preflight + an explicit researcher-created discovery authorization."""
    run_dir = Path(run_dir)
    preflight = validate_preflight_gate(
        run_dir, runtime_manifest, config, project_root, expected_implementation_commit
    )
    authorization_path = run_dir / DISCOVERY_AUTHORIZATION_FILENAME
    authorization = _load_json(authorization_path, "B2 discovery authorization")
    _validate_authorization_common(
        authorization,
        "B2 discovery authorization",
        preflight,
        "discovery",
        expected_implementation_commit,
    )
    return {
        "scope": "discovery",
        "preflight": preflight,
        "authorization": authorization,
        "authorization_sha256": sha256_file(authorization_path),
        "authorization_path": str(authorization_path),
    }


def _resolve_discovery_dir(run_dir: Path, authorization: Mapping[str, Any]) -> Path:
    raw = authorization.get("discovery_run_dir")
    if raw is None:
        return run_dir
    if not isinstance(raw, str) or not raw.strip():
        raise AuthorizationError("B2 confirmation authorization discovery_run_dir is invalid")
    path = Path(raw).expanduser()
    return path.resolve() if path.is_absolute() else (run_dir / path).resolve()


def validate_confirmation_authorization(
    run_dir: Path,
    runtime_manifest: Mapping[str, Any],
    config: Optional[Mapping[str, Any]] = None,
    project_root: Optional[Path] = None,
    expected_implementation_commit: Optional[str] = None,
) -> Dict[str, Any]:
    """Require preflight + confirmation authorization + valid discovery results."""
    from .b2_protocol import validate_b2_records, validate_state_manifest
    from .core import load_jsonl

    run_dir = Path(run_dir)
    config = config or load_fixed_project_config(project_root)
    preflight = validate_preflight_gate(
        run_dir, runtime_manifest, config, project_root, expected_implementation_commit
    )
    authorization_path = run_dir / CONFIRMATION_AUTHORIZATION_FILENAME
    authorization = _load_json(authorization_path, "B2 confirmation authorization")
    _require_fields(
        authorization,
        ("discovery_analysis_sha256",),
        "B2 confirmation authorization",
    )
    _validate_authorization_common(
        authorization,
        "B2 confirmation authorization",
        preflight,
        "confirmation",
        expected_implementation_commit,
    )

    discovery_dir = _resolve_discovery_dir(run_dir, authorization)
    required_discovery = {
        "episodes": discovery_dir / "b2_discovery_episodes.jsonl",
        "states": discovery_dir / "b2_discovery_state_manifest.jsonl",
        "run_manifest": discovery_dir / "b2_discovery_run.json",
        "snapshot_validation": discovery_dir / "b2_discovery_snapshot_validation.json",
        "summary": discovery_dir / "b2_discovery_summary.json",
        "status": discovery_dir / "b2_discovery_status.json",
        "analysis": discovery_dir / "b2_discovery_analysis.json",
        "report": discovery_dir / "B2_REPORT.md",
    }
    missing = [str(path) for path in required_discovery.values() if not path.is_file()]
    if missing:
        raise AuthorizationError(
            "B2 confirmation requires completed discovery artifacts; missing: {}".format(missing)
        )
    summary = _load_json(required_discovery["summary"], "B2 discovery summary")
    if summary.get("status") != "COMPLETE":
        raise AuthorizationError("B2 discovery summary status is not COMPLETE")
    if bool(summary.get("completeness_verified")) is not True:
        raise AuthorizationError("B2 discovery completeness_verified is not true")
    if int(summary.get("n_branch_records", -1)) != 450:
        raise AuthorizationError("B2 discovery n_branch_records is not 450")
    status = _load_json(required_discovery["status"], "B2 discovery status")
    if status.get("status") != "COMPLETE":
        raise AuthorizationError("B2 discovery status is not COMPLETE")
    if bool(status.get("snapshot_validation_all_passed")) is not True:
        raise AuthorizationError("B2 discovery snapshot validation was not fully passed")

    b1_full_manifest = _load_b1_manifest(config, project_root)
    discovery_run_manifest = _load_json(required_discovery["run_manifest"], "B2 discovery run manifest")
    validate_b2_run_manifest(discovery_run_manifest, "discovery", b1_full_manifest)
    discovery_states = load_jsonl(required_discovery["states"])
    discovery_records = load_jsonl(required_discovery["episodes"])
    validate_state_manifest(discovery_states, "discovery", config)
    validation = _load_json(required_discovery["snapshot_validation"], "B2 discovery snapshot validation")
    try:
        require_passed_snapshot_validation(
            validation, "discovery", {state["state_id"]: state["snapshot_sha256"] for state in discovery_states},
        )
    except RuntimeError as exc:
        raise AuthorizationError(str(exc)) from exc
    validate_b2_records(
        discovery_records,
        discovery_states,
        "discovery",
        config,
        runtime_manifest=discovery_run_manifest,
    )

    analysis_sha = sha256_file(required_discovery["analysis"])
    if str(authorization.get("discovery_analysis_sha256")) != analysis_sha:
        raise AuthorizationError(
            "B2 confirmation authorization discovery_analysis_sha256 does not match"
        )
    analysis = _load_json(required_discovery["analysis"], "B2 discovery analysis")
    decision = str(analysis.get("decision"))
    if decision in DISCOVERY_STOP_DECISIONS:
        raise AuthorizationError("B2 discovery decision is STOP/BLOCKED: {}".format(decision))
    if decision not in DISCOVERY_PROCEED_DECISIONS:
        raise AuthorizationError("B2 discovery decision is not a confirmation-justified result")
    if required_discovery["report"].stat().st_size == 0:
        raise AuthorizationError("B2_REPORT.md is empty")

    return {
        "scope": "confirmation",
        "preflight": preflight,
        "authorization": authorization,
        "authorization_sha256": sha256_file(authorization_path),
        "authorization_path": str(authorization_path),
        "discovery_dir": str(discovery_dir),
        "discovery_analysis_sha256": analysis_sha,
        "discovery_decision": decision,
    }


def validate_formal_authorization(
    run_dir: Path,
    split: str,
    runtime_manifest: Mapping[str, Any],
    config: Optional[Mapping[str, Any]] = None,
    project_root: Optional[Path] = None,
    expected_implementation_commit: Optional[str] = None,
) -> Dict[str, Any]:
    if split == "discovery":
        return validate_discovery_authorization(
            run_dir, runtime_manifest, config, project_root, expected_implementation_commit
        )
    if split == "confirmation":
        return validate_confirmation_authorization(
            run_dir, runtime_manifest, config, project_root, expected_implementation_commit
        )
    raise AuthorizationError("Formal authorization is defined only for discovery/confirmation")
