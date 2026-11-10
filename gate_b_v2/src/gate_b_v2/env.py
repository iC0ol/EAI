from __future__ import annotations

import copy
import hashlib
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

from .core import sha256_array, stack_observation_history


def _seed_robosuite_rng(wrapper: Any, seed: int) -> None:
    """Seed robosuite's own RNG in place where supported, as well as NumPy global RNG."""
    np.random.seed(int(seed))
    robomimic_env = getattr(wrapper, "env", None)
    robosuite_env = getattr(robomimic_env, "env", None)
    rng = getattr(robosuite_env, "rng", None)
    if rng is None:
        return
    if hasattr(rng, "seed") and callable(rng.seed):
        rng.seed(int(seed))
    elif hasattr(rng, "bit_generator"):
        rng.bit_generator.state = np.random.default_rng(int(seed)).bit_generator.state


def create_square_image_env(dp_root: Path, dataset_path: Path, shape_meta: Mapping[str, Any]):
    """Create the same robomimic image environment used by the upstream DP runner."""
    dp_root = Path(dp_root).resolve()
    if str(dp_root) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(dp_root))

    import collections
    import h5py  # noqa: F401 - ensures the same hdf5 runtime is importable
    import robomimic.utils.env_utils as EnvUtils
    import robomimic.utils.file_utils as FileUtils
    import robomimic.utils.obs_utils as ObsUtils
    from diffusion_policy.env.robomimic.robomimic_image_wrapper import RobomimicImageWrapper

    modality_mapping = collections.defaultdict(list)
    for key, attr in shape_meta["obs"].items():
        modality_mapping[attr.get("type", "low_dim")].append(key)
    ObsUtils.initialize_obs_modality_mapping_from_dict(modality_mapping)

    env_meta = FileUtils.get_env_metadata_from_dataset(str(dataset_path))
    env_meta = copy.deepcopy(env_meta)
    env_meta["env_kwargs"]["use_object_obs"] = False
    # The official image runner disables hard reset to avoid repeated renderer allocation.
    env_meta["env_kwargs"]["hard_reset"] = False
    env = EnvUtils.create_env_from_metadata(
        env_meta=env_meta,
        render=False,
        render_offscreen=True,
        use_image_obs=True,
    )
    wrapper = RobomimicImageWrapper(env=env, shape_meta=dict(shape_meta), init_state=None)
    return wrapper, env_meta


class EpisodeEnv:
    def __init__(
        self,
        wrapper: Any,
        shape_meta: Mapping[str, Any],
        n_obs_steps: int,
        max_steps: int,
    ):
        self.wrapper = wrapper
        self.shape_meta = shape_meta
        self.n_obs_steps = int(n_obs_steps)
        self.max_steps = int(max_steps)
        self.history: Deque[Dict[str, np.ndarray]] = deque(maxlen=self.n_obs_steps)
        self.steps = 0
        self.max_reward = float("-inf")
        self.success_seen = False
        self.last_info: Dict[str, Any] = {}

    @property
    def robomimic_env(self):
        return self.wrapper.env

    @property
    def robosuite_env(self):
        return self.wrapper.env.env

    def reset(self, seed: int) -> Dict[str, np.ndarray]:
        # Bypass RobomimicImageWrapper's seed_state_map cache so each paired run
        # performs a true reset. The resulting initial simulator hash is checked
        # across all horizons before results are treated as paired.
        if hasattr(self.wrapper, "seed_state_map"):
            self.wrapper.seed_state_map.pop(int(seed), None)
        self.wrapper.seed(int(seed))
        _seed_robosuite_rng(self.wrapper, int(seed))
        obs = self.wrapper.reset()
        self.history.clear()
        for _ in range(self.n_obs_steps):
            self.history.append({k: np.array(v, copy=True) for k, v in obs.items()})
        self.steps = 0
        self.max_reward = float("-inf")
        self.success_seen = False
        self.last_info = {}
        return obs

    def policy_observation(self) -> Dict[str, np.ndarray]:
        return stack_observation_history(list(self.history), self.n_obs_steps, self.shape_meta)

    def step(self, action: np.ndarray):
        obs, reward, done, info = self.wrapper.step(np.asarray(action, dtype=np.float32))
        self.history.append({k: np.array(v, copy=True) for k, v in obs.items()})
        self.steps += 1
        self.max_reward = max(self.max_reward, float(reward))
        self.last_info = dict(info or {})
        success = self.last_info.get("is_success", False)
        if isinstance(success, Mapping):
            success = success.get("task", False)
        if not bool(success):
            try:
                success = self.robomimic_env.is_success().get("task", False)
            except Exception:
                success = False
        self.success_seen = self.success_seen or bool(success)
        return obs, float(reward), bool(done), self.last_info

    def success(self, threshold: Optional[float] = None) -> bool:
        # Use robomimic/robosuite is_success task predicate only. Do not infer task
        # success from shaped reward magnitude. The threshold argument is retained
        # for API compatibility but intentionally unused.
        return bool(self.success_seen)

    def initial_state_hash(self) -> str:
        state = self.robomimic_env.get_state()
        return sha256_array(np.asarray(state["states"]))

    def current_sim_state(self) -> np.ndarray:
        return np.asarray(self.robomimic_env.get_state()["states"]).copy()

    def snapshot(self) -> Dict[str, Any]:
        from .snapshot import capture_episode_snapshot
        return capture_episode_snapshot(self)

    def restore(self, snapshot: Mapping[str, Any]) -> Dict[str, np.ndarray]:
        from .snapshot import restore_episode_snapshot
        return restore_episode_snapshot(self, snapshot)

    def close(self) -> None:
        try:
            self.robomimic_env.close()
        except Exception:
            try:
                self.robosuite_env.close()
            except Exception:
                pass


def image_for_video(obs: Mapping[str, np.ndarray], key: str = "agentview_image") -> np.ndarray:
    if key not in obs:
        raise KeyError("Video observation key {!r} is unavailable".format(key))
    image = np.asarray(obs[key])
    if image.ndim != 3:
        raise ValueError("Expected 3D image observation, got {}".format(image.shape))
    if image.shape[0] in (1, 3, 4):
        image = np.transpose(image, (1, 2, 0))
    if image.dtype != np.uint8:
        image = np.clip(image, 0.0, 1.0) * 255.0 if image.max(initial=0) <= 1.0 else np.clip(image, 0, 255)
        image = image.astype(np.uint8)
    if image.shape[-1] == 1:
        image = np.repeat(image, 3, axis=-1)
    return np.ascontiguousarray(image[..., :3])
