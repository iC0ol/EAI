"""Query the checkpoint policy on official stored observations.

This isolates model/action-convention errors from live-renderer differences:
the inputs come verbatim from the official robomimic image dataset. The policy
is expected to predict an absolute end-effector target close to the next
demonstration pose.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import h5py
import numpy as np

from gate_b_v2.policy import load_diffusion_policy_checkpoint, predict_full_future_chunk


def _image_chw(raw: np.ndarray) -> np.ndarray:
    return np.transpose(raw.astype(np.float32) / 255.0, (2, 0, 1))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--demo", default="demo_0")
    parser.add_argument("--indices", nargs="+", type=int, default=[51, 101, 151])
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    runtime = load_diffusion_policy_checkpoint(
        root / "third_party" / "diffusion_policy",
        root / "assets" / "square_mh" / "epoch=1950-test_mean_score=1.000.ckpt",
        "cpu",
    )
    results = []
    with h5py.File(args.dataset, "r") as handle:
        demo = handle["data"][args.demo]
        obs = demo["obs"]
        actions = demo["actions"][:]
        for index in args.indices:
            history = [index - 1, index]
            batch = {
                "agentview_image": np.stack(
                    [_image_chw(obs["agentview_image"][t]) for t in history]
                ),
                "robot0_eye_in_hand_image": np.stack(
                    [_image_chw(obs["robot0_eye_in_hand_image"][t]) for t in history]
                ),
                "robot0_eef_pos": np.stack(
                    [obs["robot0_eef_pos"][t] for t in history]
                ).astype(np.float32),
                "robot0_eef_quat": np.stack(
                    [obs["robot0_eef_quat"][t] for t in history]
                ).astype(np.float32),
                "robot0_gripper_qpos": np.stack(
                    [obs["robot0_gripper_qpos"][t] for t in history]
                ).astype(np.float32),
            }
            chunk = predict_full_future_chunk(
                runtime["policy"], runtime["torch"], batch, "cpu",
                runtime["n_obs_steps"], runtime["prediction_horizon"],
            )
            current = np.asarray(obs["robot0_eef_pos"][index], dtype=np.float64)
            following = np.asarray(obs["robot0_eef_pos"][index + 1], dtype=np.float64)
            predicted = chunk[0, :3].astype(np.float64)
            record = {
                "demo": args.demo,
                "index": int(index),
                "current_eef_pos": current.round(5).tolist(),
                "next_eef_pos": following.round(5).tolist(),
                "predicted_abs_pos": predicted.round(5).tolist(),
                "pred_vs_next_m": float(np.linalg.norm(predicted - following)),
                "pred_vs_current_m": float(np.linalg.norm(predicted - current)),
                "predicted_gripper": float(chunk[0, 9]),
                "stored_gripper_action": float(actions[index + 1, 6]),
                "predicted_rot6d": chunk[0, 3:9].round(5).tolist(),
            }
            results.append(record)
            print(json.dumps(record, indent=2, sort_keys=True))
    out = root / "reports" / "policy_replay_check.json"
    out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
