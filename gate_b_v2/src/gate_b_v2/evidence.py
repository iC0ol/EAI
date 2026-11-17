"""Export small, public, PREFLIGHT-only B2 evidence records.

No snapshot binary, checkpoint, dataset, virtual environment or large asset is
copied.  Every exported record is explicitly marked PREFLIGHT and
scientific_data=false.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .authorization import (
    GEOMETRY_AUDIT_FILENAME,
    PREFLIGHT_SEED,
    PREFLIGHT_SNAPSHOT_VALIDATION_FILENAME,
    PREFLIGHT_SUMMARY_FILENAME,
    STAGE_GATE_VERSION,
    sha256_file,
)
from .locks import B2_PROTOCOL_VERSION


def _load(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("{} must contain a JSON object".format(path))
    return value


def _write(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def export_preflight_evidence(preflight_dir: Path, output_dir: Path) -> Path:
    preflight_dir = Path(preflight_dir).resolve()
    output_dir = Path(output_dir).resolve()
    summary_path = preflight_dir / PREFLIGHT_SUMMARY_FILENAME
    audit_path = preflight_dir / GEOMETRY_AUDIT_FILENAME
    validation_path = preflight_dir / PREFLIGHT_SNAPSHOT_VALIDATION_FILENAME
    summary = _load(summary_path)
    audit = _load(audit_path)
    validation = _load(validation_path)

    if summary.get("marker") != "PREFLIGHT" or summary.get("scientific_data") is not False:
        raise RuntimeError("Preflight summary is not marked PREFLIGHT/scientific_data=false")
    if summary.get("status") != "PASS":
        raise RuntimeError("Only a PASS preflight can be exported as acceptance evidence")
    if int(summary.get("seed", -1)) != PREFLIGHT_SEED:
        raise RuntimeError("Preflight summary seed is not {}".format(PREFLIGHT_SEED))
    if summary.get("gate_reached") is not True:
        raise RuntimeError("Preflight did not reach the stage gate")
    if summary.get("protocol_version") != B2_PROTOCOL_VERSION:
        raise RuntimeError("Preflight protocol version is not frozen")
    if summary.get("stage_gate_version") != STAGE_GATE_VERSION:
        raise RuntimeError("Preflight stage gate version is not frozen")
    if audit.get("status") != "PASS" or audit.get("marker") != "PREFLIGHT":
        raise RuntimeError("Geometry audit is not a PASS PREFLIGHT record")
    if validation.get("all_passed") is not True or validation.get("marker") != "PREFLIGHT":
        raise RuntimeError("Snapshot validation is not a PASS PREFLIGHT record")

    # Sanitize absolute paths; keep only relative evidence names.
    clean_summary = dict(summary)
    for key in ("snapshot_file", "state_smoke_records"):
        value = clean_summary.get(key)
        if isinstance(value, str) and Path(value).is_absolute():
            try:
                clean_summary[key] = str(Path(value).resolve().relative_to(preflight_dir))
            except ValueError:
                clean_summary[key] = Path(value).name
    clean_summary["marker"] = "PREFLIGHT"
    clean_summary["scientific_data"] = False
    clean_summary["evidence_export"] = "public preflight evidence; no snapshot binary included"

    environment = clean_summary.get("environment_fingerprint")
    if not isinstance(environment, dict):
        raise RuntimeError("Preflight summary has no environment_fingerprint object")
    environment_record = {
        "marker": "PREFLIGHT",
        "scientific_data": False,
        "protocol_version": B2_PROTOCOL_VERSION,
        "stage_gate_version": STAGE_GATE_VERSION,
        "environment_fingerprint": environment,
        "environment_fingerprint_sha256": clean_summary.get("environment_fingerprint_sha256"),
        "note": "Environment fingerprint summary only; no paths to checkpoints or datasets.",
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        GEOMETRY_AUDIT_FILENAME: audit,
        PREFLIGHT_SUMMARY_FILENAME: clean_summary,
        PREFLIGHT_SNAPSHOT_VALIDATION_FILENAME: validation,
        "b2_preflight_environment.json": environment_record,
    }
    file_hashes = {}
    for name, value in outputs.items():
        path = output_dir / name
        _write(path, value)
        file_hashes[name] = sha256_file(path)
    manifest = {
        "marker": "PREFLIGHT",
        "scientific_data": False,
        "protocol_version": B2_PROTOCOL_VERSION,
        "stage_gate_version": STAGE_GATE_VERSION,
        "preflight_seed": PREFLIGHT_SEED,
        "source_run_directory_name": preflight_dir.name,
        "files": file_hashes,
        "note": (
            "PREFLIGHT engineering evidence only. No discovery/confirmation state, "
            "branch episode, snapshot binary, checkpoint, dataset or environment is included."
        ),
    }
    manifest_path = output_dir / "PREFLIGHT_EVIDENCE_MANIFEST.json"
    _write(manifest_path, manifest)
    return manifest_path
