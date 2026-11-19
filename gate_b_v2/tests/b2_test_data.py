from pathlib import Path

from gate_b_v2.b2_protocol import (
    branch_order,
    branch_order_seed,
    policy_noise_schedule,
    repeat_seed,
    state_id,
)
from gate_b_v2.locks import B2_CONFIG_FINGERPRINT, b2_record_environment_fields, load_b1_full_manifest
from gate_b_v2.snapshot import B2_REFERENCE_SOURCE, REQUIRED_SNAPSHOT_CHECKS, SNAPSHOT_SCHEMA_VERSION

_B1 = load_b1_full_manifest(Path(__file__).resolve().parents[1] / "reports" / "b1_full_run.json")
RUNTIME = b2_record_environment_fields({
    **_B1, "config_fingerprint": B2_CONFIG_FINGERPRINT,
    "b1_full_manifest_sha256": _B1["_manifest_sha256"],
})
GEOMETRY = {
    "clearance_m": 0.001,
    "clearance_x_positive_m": 0.001,
    "clearance_x_negative_m": 0.002,
    "clearance_y_positive_m": 0.003,
    "clearance_y_negative_m": 0.004,
    "dx_m": 0.0,
    "dy_m": 0.0,
    "d_xy_m": 0.0,
    "relative_yaw_rad": 0.0,
    "z_gap_m": 0.005,
    "nut_bottom_local_z_m": -0.01,
    "peg_top_local_z_m": -0.015,
    "t_nut_m": 0.02,
    "nut_collision_thickness_m": 0.02,
    "r_hole_m": 0.032,
    "r_peg_m": 0.022,
    "hole_half_x_m": 0.02275,
    "hole_half_y_m": 0.02275,
    "peg_half_x_m": 0.016,
    "peg_half_y_m": 0.016,
    "peg_half_z_m": 0.05,
    "geometry_fingerprint": "square-test-model",
    "aperture_bar_geom_ids": [46, 47, 48, 49],
}


def state_record(split, seed, source_step, clearance, **environment):
    identifier = state_id(split, seed)
    geometry = dict(GEOMETRY, clearance_m=clearance, clearance_x_positive_m=clearance)
    return {
        "state_id": identifier,
        "split": split,
        "source_seed": seed,
        "source_step": source_step,
        "source_horizon": 8,
        "stage_gate_version": "B2_GEOMETRY_GATE_V1_20261116",
        "geometry": geometry,
        **geometry,
        "snapshot_file": "snapshots/{}/{}.pkl.gz".format(split, identifier),
        "snapshot_sha256": "{:064x}".format(seed),
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        **(environment or RUNTIME),
    }


def branch_record(config, state, repeat, horizon, success=False):
    split, seed = state["split"], state["source_seed"]
    order = branch_order(config, seed, repeat)
    noise_seed = repeat_seed(config, seed, repeat)
    steps = 500 - state["source_step"]
    calls = 1 + (max(steps - horizon, 0) + 14) // 15
    return {
        "phase": "B2",
        "split": split,
        "state_id": state["state_id"],
        "source_seed": seed,
        "source_step": state["source_step"],
        "horizon": horizon,
        "repeat_index": repeat,
        "repeat_seed": noise_seed,
        "branch_order_seed": branch_order_seed(config, seed, repeat),
        "randomized_order_index": order.index(horizon),
        "horizon_order": order,
        "continuation_horizon": 15,
        "preflight": False,
        "policy_reset_verified": True,
        "snapshot_sha256": state["snapshot_sha256"],
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        **state["geometry"],
        "success": success,
        "success_seen": success,
        "success_error": None,
        "max_reward": float(success),
        "termination": "max_steps",
        "steps_from_episode_start": 500,
        "steps_after_branch": steps,
        "policy_calls_after_branch": calls,
        "wall_time_s": 1.0 + 0.1 * horizon,
        "policy_noise_seed_schedule": policy_noise_schedule(noise_seed, calls),
        **{key: state[key] for key in RUNTIME},
    }


def passing_snapshot_validation(split, snapshot_hashes):
    return {
        "split": split,
        "marker": "PREFLIGHT" if split == "preflight" else "B2",
        "scientific_data": split != "preflight",
        "all_passed": True,
        "status": "PASS",
        "n_states": len(snapshot_hashes),
        "per_state": {
            identifier: {
                "status": "PASS",
                "passed": True,
                "reference_source": B2_REFERENCE_SOURCE,
                "snapshot_sha256": digest,
                "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
                "checks": dict.fromkeys(REQUIRED_SNAPSHOT_CHECKS, True),
                "state_max_abs": 1e-9,
                "observation_mean_abs_max": 1e-6,
                "geometry_abs_max": 1e-9,
            } for identifier, digest in snapshot_hashes.items()
        },
    }
