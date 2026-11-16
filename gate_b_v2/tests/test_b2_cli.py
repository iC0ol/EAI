import json
from pathlib import Path

import pytest
import yaml

from gate_b_v2.cli import _project_root, _load_config, build_parser
from gate_b_v2.locks import (
    B2_LOCKED_ENVIRONMENT_KEYS,
    build_b2_run_manifest,
    load_b1_full_manifest,
    validate_b2_config,
)


def _config():
    return _load_config(None)


def _runtime_manifest_like_b1(b1_manifest):
    runtime = dict(b1_manifest)
    runtime["device_requested"] = runtime.get("device", "cuda:0")
    runtime["checkpoint"] = "/local/checkpoint"
    runtime["dataset"] = "/local/dataset"
    runtime["dp_root"] = "/local/dp"
    runtime.pop("_manifest_path", None)
    runtime.pop("_manifest_sha256", None)
    return runtime


def test_b2_cli_exposes_no_asset_or_runtime_overrides():
    parser = build_parser()
    args = parser.parse_args(["b2", "--split", "discovery", "--run-dir", "run"])
    assert args.command == "b2"
    assert args.split == "discovery"
    for forbidden in (
        "--config", "--checkpoint", "--dataset", "--dp-root", "--max-steps", "--device",
    ):
        with pytest.raises(SystemExit):
            parser.parse_args(["b2", "--split", "discovery", forbidden, "x"])


def test_b2_harvest_and_preflight_cli_are_split_separated_and_locked():
    parser = build_parser()
    harvest = parser.parse_args(["b2-harvest", "--split", "confirmation", "--run-dir", "run"])
    assert harvest.command == "b2-harvest"
    with pytest.raises(SystemExit):
        parser.parse_args(["b2-harvest", "--run-dir", "run"])
    preflight = parser.parse_args([
        "b2-preflight", "--run-dir", "pre", "--seed", "299999",
        "--fallback-step", "500", "--smoke-seeds", "299990,299991",
    ])
    assert preflight.seed == 299999
    with pytest.raises(SystemExit):
        parser.parse_args(["b2-preflight", "--checkpoint", "x"])


def test_b2_config_lock_and_no_numeric_stage_gate():
    config = _config()
    result = validate_b2_config(config)
    assert result["values"]["continuation_horizon"] == 15
    assert result["values"]["horizons"] == [1, 2, 4, 8, 15]
    assert result["values"]["discovery_primary_seed_start"] == 300000
    assert result["values"]["confirmation_primary_seed_start"] == 310000
    for forbidden in ("z_gap_min_m", "z_gap_max_m", "max_xy_center_distance_m"):
        assert forbidden not in config["b2"]
    broken = yaml.safe_load(yaml.safe_dump(config))
    broken["b2"]["continuation_horizon"] = 8
    with pytest.raises(RuntimeError, match="B2 config lock failed"):
        validate_b2_config(broken)


def test_b2_environment_lock_reads_real_b1_full_manifest():
    config = _config()
    manifest_path = _project_root() / config["paths"]["b1_full_manifest"]
    b1_manifest = load_b1_full_manifest(manifest_path)
    assert b1_manifest["checkpoint_sha256"] == "adaf17854fb8ff8acaccc56adbf6af321c7bec7fecb22de5257772ec81927c6d"
    assert b1_manifest["dataset_sha256"] == "7e58906366d79996f13785ff2dd0fe346230373532addc2afc7c92611ae42887"
    assert b1_manifest["dp_source_tree_sha256"] == "aec43e20abb0902b606e61fc4a391605ab755e59233ecb5f6bdbfbe8df372f21"
    for key in B2_LOCKED_ENVIRONMENT_KEYS:
        assert key in b1_manifest

    runtime = _runtime_manifest_like_b1(b1_manifest)
    built = build_b2_run_manifest(
        config, runtime, b1_manifest, split="discovery", command="test"
    )
    assert built["b1_full_manifest_sha256"] == b1_manifest["_manifest_sha256"]
    assert built["checkpoint_sha256"] == b1_manifest["checkpoint_sha256"]

    broken = dict(runtime)
    broken["checkpoint_sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="B2 environment lock failed"):
        build_b2_run_manifest(config, broken, b1_manifest, split="discovery", command="test")


def test_b1_full_manifest_missing_key_is_rejected(tmp_path):
    config = _config()
    source = _project_root() / config["paths"]["b1_full_manifest"]
    manifest = json.loads(source.read_text(encoding="utf-8"))
    manifest.pop("dp_source_tree_sha256")
    path = tmp_path / "b1_full.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="missing required keys"):
        load_b1_full_manifest(path)
