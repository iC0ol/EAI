#!/usr/bin/env python3
"""Serve the official OpenPI-PACE policy with reproducible episode keys."""

import argparse
import json
import logging
import os
from pathlib import Path
import time
from unittest.mock import patch

import jax
import numpy as np
import orbax.checkpoint as ocp

from openpi.policies import policy_config
from openpi.serving.websocket_policy_server import WebsocketPolicyServer
from openpi.training import config

from fetch_checkpoints import ASSETS, REVISION, TASKS


OPENPI_REVISION = "ba9876639cb7a4bf0c7db00ec39eeb9c8efd8b12"
RESTORE_CONCURRENT_GB = 6
LOGGER = logging.getLogger(__name__)


@jax.jit
def episode_key(seed, query_index):
    # Policy.infer splits this key once and uses the second key for sampling.
    return jax.lax.fori_loop(0, query_index, lambda _, key: jax.random.split(key)[0], jax.random.key(seed))


class EpisodeSeededPolicy:
    def __init__(self, policy):
        self.policy = policy

    def infer(self, request):
        if "episode_seed" not in request and "query_index" not in request:
            return self.policy.infer(request)

        seed = request.get("episode_seed")
        query = request.get("query_index")
        if type(seed) is not int or not 0 <= seed <= np.iinfo(np.uint32).max:
            raise ValueError("episode_seed must be a Python integer in the uint32 range")
        if type(query) is not int or not 0 <= query <= np.iinfo(np.int32).max:
            raise ValueError("query_index must be a nonnegative Python integer in the int32 range")

        observation = {key: value for key, value in request.items() if key not in {"episode_seed", "query_index"}}
        previous_rng = self.policy._rng
        try:
            self.policy._rng = episode_key(np.uint32(seed), np.int32(query))
            response = self.policy.infer(observation)
        finally:
            self.policy._rng = previous_rng
        return {**response, "episode_seed": seed, "query_index": query}


def memory_limited_checkpointer():
    # Same Orbax handler as PyTreeCheckpointer, with a host read-concurrency limit.
    return ocp.Checkpointer(ocp.PyTreeCheckpointHandler(restore_concurrent_gb=RESTORE_CONCURRENT_GB))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, choices=TASKS)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    logging.basicConfig(level=logging.INFO, force=True)
    devices = jax.devices("gpu")
    LOGGER.info("JAX %s GPU devices %s", jax.__version__, devices)
    manifest = json.loads((ASSETS / "manifest.json").read_text())
    checkpoint = next(model for model in manifest["models"] if model["task"] == args.task)
    tokenizer = Path(os.environ["OPENPI_DATA_HOME"]) / "big_vision" / "paligemma_tokenizer.model"
    if not tokenizer.is_file():
        raise FileNotFoundError(f"Missing local PaliGemma tokenizer: {tokenizer}")

    start = time.monotonic()
    with patch.object(ocp, "PyTreeCheckpointer", memory_limited_checkpointer):
        policy = policy_config.create_trained_policy(config.get_config(checkpoint["config"]), ASSETS / args.task)
    LOGGER.info("Model loaded in %.3f seconds", time.monotonic() - start)
    metadata = {
        **policy.metadata,
        "candidate_count": 1,
        "denoising_steps": 10,
        "episode_seeding": "jax.random.key(episode_seed), sequential split at zero-based query_index",
        "openpi_revision": OPENPI_REVISION,
        "checkpoint_revision": REVISION,
        "norm_stats_sha256": checkpoint["norm_stats_sha256"],
        "tokenizer_sha256": manifest["tokenizer"]["sha256"],
        "orbax_restore_concurrent_gb": RESTORE_CONCURRENT_GB,
    }
    WebsocketPolicyServer(EpisodeSeededPolicy(policy), "127.0.0.1", args.port, metadata).serve_forever()


if __name__ == "__main__":
    main()
