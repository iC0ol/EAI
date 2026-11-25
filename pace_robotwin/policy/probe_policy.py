#!/usr/bin/env python3
"""Measure synthetic warmup and RNG replay through the existing OpenPI client."""

import argparse
import hashlib
import json
from pathlib import Path
import time
from urllib.request import urlopen

import numpy as np
from openpi_client.websocket_client_policy import WebsocketClientPolicy

from fetch_checkpoints import REVISION, TASKS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, choices=TASKS)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    with urlopen(f"http://127.0.0.1:{args.port}/healthz", timeout=5) as health:
        if health.status != 200:
            raise RuntimeError("OpenPI-PACE service is unhealthy")
    client = WebsocketClientPolicy("127.0.0.1", args.port)
    metadata = client.get_server_metadata()
    expected = {
        "task": args.task,
        "config": f"pi05_robotwin_{args.task}",
        "checkpoint_revision": REVISION,
        "action_horizon": 50,
        "action_dim": 14,
        "action_space": "absolute_joint",
        "candidate_count": 1,
        "denoising_steps": 10,
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError(f"Unexpected policy metadata: {metadata}")

    rng = np.random.default_rng(0)
    observation = {
        "state": np.zeros(14, dtype=np.float32),
        "images": {
            camera: rng.integers(0, 256, (3, 240, 320), dtype=np.uint8)
            for camera in ("cam_high", "cam_left_wrist", "cam_right_wrist")
        },
        "prompt": args.task.replace("_", " "),
    }
    measurements = []

    def query(label, seed=None, index=None):
        request = dict(observation)
        if seed is not None:
            request.update(episode_seed=seed, query_index=index)
        start = time.perf_counter()
        response = client.infer(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        actions = response["actions"]
        if actions.shape != (50, 14) or not np.isfinite(actions).all():
            raise ValueError(f"Invalid action chunk: shape={actions.shape}, dtype={actions.dtype}")
        if seed is not None and (response.get("episode_seed"), response.get("query_index")) != (seed, index):
            raise ValueError("Policy service did not confirm the requested seed and query index")
        measurements.append({
            "label": label,
            "episode_seed": seed,
            "query_index": index,
            "action_shape": list(actions.shape),
            "action_dtype": str(actions.dtype),
            "action_sha256": hashlib.sha256(actions.tobytes()).hexdigest(),
            "client_roundtrip_ms": elapsed_ms,
            "server_infer_ms": response["server_timing"]["infer_ms"],
            "policy_dispatch_ms": response["policy_timing"]["infer_ms"],
        })
        return actions

    first = query("synthetic_warmup", 300001, 0)
    alternate = query("alternate_seed", 300002, 0)
    replay = query("synthetic_replay", 300001, 0)
    if not np.array_equal(first, replay):
        raise ValueError("Same seed and observation did not replay exactly")
    if np.array_equal(first, alternate):
        raise ValueError("Different seeds unexpectedly produced an identical action chunk")
    for index in (0, 1):
        seeded = query("explicit_seed_zero", 0, index)
        legacy = query("upstream_seed_zero_sequence")
        if not np.array_equal(seeded, legacy):
            raise ValueError(f"Seed zero does not match the upstream RNG sequence at query {index}")

    result = json.dumps({
        "kind": "synthetic_engineering_probe",
        "metadata": metadata,
        "same_seed_exact": True,
        "different_seed_differs": True,
        "matches_upstream_seed_zero_sequence": True,
        "measurements": measurements,
    }, indent=2) + "\n"
    if args.output:
        args.output.write_text(result)
    print(result, end="")


if __name__ == "__main__":
    main()
