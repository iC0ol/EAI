"""Compare live OSMesa renders against official robomimic image observations.

Loads states from the official image.hdf5, restores them into the same
robosuite environment, renders through the harness, and reports pixel
differences for the stored (upright) images. This is a rendering/domain check,
not a B2 snapshot/restore experiment.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import h5py
import imageio.v2 as imageio
import numpy as np


def _to_hwc_uint8(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image)
    if array.ndim != 3:
        raise ValueError("Expected 3-D image, got {}".format(array.shape))
    if array.shape[0] == 3:
        array = np.transpose(array, (1, 2, 0))
    if array.dtype != np.uint8:
        array = (np.clip(array, 0.0, 1.0) * 255.0).round().astype(np.uint8)
    return array


def _stats(live: np.ndarray, stored: np.ndarray) -> dict:
    live_f = live.astype(np.float64)
    stored_f = stored.astype(np.float64)
    diff = np.abs(live_f - stored_f)
    return {
        "mean_abs_diff_255": float(diff.mean()),
        "max_abs_diff_255": float(diff.max()),
        "corr": float(np.corrcoef(live_f.ravel(), stored_f.ravel())[0, 1]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--image-keys", nargs="+", default=["agentview_image", "robot0_eye_in_hand_image"])
    parser.add_argument("--demo", default="demo_0")
    parser.add_argument("--indices", nargs="+", type=int, default=[0, 50, 100])
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    from gate_b_v2.env import create_square_image_env

    root = Path(__file__).resolve().parents[1]
    shape_meta = json.loads(
        (root / "reports" / "checkpoint_audit.json").read_text(encoding="utf-8")
    )["shape_meta"]
    wrapper, _ = create_square_image_env(
        root / "third_party" / "diffusion_policy",
        root / "assets" / "square_mh" / "low_dim.hdf5",
        shape_meta,
        abs_action=True,
    )
    robomimic_env = wrapper.env
    # Initialise renderer once.
    robomimic_env.reset()

    results = []
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with h5py.File(args.dataset, "r") as handle:
        demo = handle["data"][args.demo]
        states = demo["states"][:]
        for index in args.indices:
            robomimic_env.reset_to({"states": np.array(states[index], copy=True)})
            raw = robomimic_env.get_observation()
            obs = wrapper.get_observation(raw)
            record = {"demo": args.demo, "index": int(index)}
            for key in args.image_keys:
                live = _to_hwc_uint8(obs[key])
                stored = _to_hwc_uint8(demo["obs"][key][index])
                variants = {
                    "direct": _stats(live, stored),
                    "vertical_flip": _stats(live[::-1], stored),
                    "horizontal_flip": _stats(live[:, ::-1], stored),
                }
                record[key] = variants
                best = min(variants, key=lambda name: variants[name]["mean_abs_diff_255"])
                record[key]["best"] = best
                side = np.concatenate(
                    [stored, np.full((stored.shape[0], 4, 3), 255, np.uint8), live],
                    axis=1,
                )
                imageio.imwrite(
                    args.out_dir / "{}_{}_{}_compare.png".format(args.demo, key, index),
                    side,
                )
                np.savez_compressed(
                    args.out_dir / "{}_{}_{}.npz".format(args.demo, key, index),
                    stored=stored, live=live,
                )
            results.append(record)
            print(json.dumps(record, indent=2, sort_keys=True))

    (args.out_dir / "comparison.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
