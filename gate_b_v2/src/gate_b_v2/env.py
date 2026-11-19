from __future__ import annotations

import copy
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Deque, Dict, List, Mapping, Optional, Tuple

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


def image_camera_names(shape_meta: Mapping[str, Any]) -> List[str]:
    """Derive robosuite camera names from the checkpoint's RGB observation keys."""
    names = [
        key[: -len("_image")] for key, attr in shape_meta["obs"].items()
        if key.endswith("_image") and attr.get("type", "low_dim") == "rgb"
    ]
    if not names:
        raise RuntimeError("shape_meta has no RGB image observations")
    return names


def create_square_image_env(
    dp_root: Path,
    dataset_path: Path,
    shape_meta: Mapping[str, Any],
    abs_action: bool = False,
):
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
    # The low-dim metadata omits the image dataset's camera_names list. Rebuild
    # it from the checkpoint's RGB observation keys so both cameras are rendered.
    env_meta["env_kwargs"]["camera_names"] = image_camera_names(shape_meta)
    if abs_action:
        # DP's RobomimicImageRunner switches the OSC controller to absolute pose
        # when the checkpoint was trained with abs_action=True.
        controllers = env_meta["env_kwargs"].get("controller_configs")
        if not isinstance(controllers, dict):
            raise RuntimeError("Dataset env_args has no controller_configs for abs_action")
        controllers["control_delta"] = False
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
        self.success_error: Optional[str] = None
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
        self.success_error = None
        self.last_info = {}
        return obs

    def policy_observation(self) -> Dict[str, np.ndarray]:
        return stack_observation_history(list(self.history), self.n_obs_steps, self.shape_meta)

    def step(self, action: np.ndarray, *, strict: bool = False):
        action = np.asarray(action, dtype=np.float32)
        if strict and not np.isfinite(action).all():
            raise RuntimeError("Non-finite B2 environment action")
        if strict:
            sim = self.robosuite_env.sim
            previous_time = float(sim.data.time)
        obs, reward, done, info = self.wrapper.step(action)
        if strict:
            if not isinstance(done, (bool, np.bool_)):
                raise RuntimeError("Invalid B2 environment termination signal: {!r}".format(done))
            if not np.isfinite(reward):
                raise RuntimeError("Non-finite B2 environment reward: {!r}".format(reward))
            if not np.isfinite(sim.get_state().flatten()).all() or not sim.data.time > previous_time:
                raise RuntimeError("Invalid or non-advancing B2 simulator state after step")
            if set(obs) != set(self.shape_meta["obs"]) or any(
                not np.isfinite(value).all() for value in obs.values()
            ):
                raise RuntimeError("Missing, unexpected or non-finite B2 step observation")
        self.history.append({k: np.array(v, copy=True) for k, v in obs.items()})
        self.steps += 1
        self.max_reward = max(self.max_reward, float(reward))
        self.last_info = dict(info or {})
        success = self.last_info.get("is_success", False)
        if isinstance(success, Mapping):
            success = success.get("task", False)
        if not bool(success):
            if strict:
                success = self.success(strict=True)
            else:
                try:
                    success = self.robomimic_env.is_success().get("task", False)
                except Exception:
                    success = False
        self.success_seen = self.success_seen or bool(success)
        return obs, float(reward), bool(done), self.last_info

    def success(self, threshold: Optional[float] = None, *, strict: bool = False) -> bool:
        # Use the robomimic/robosuite is_success task predicate on the final
        # simulator state, matching robomimic's own rollout evaluation. The sticky
        # success_seen flag is logged separately as a diagnostic, not as success.
        # Do not infer task success from shaped reward magnitude. The threshold
        # argument is retained for API compatibility but intentionally unused.
        try:
            value = self.robomimic_env.is_success()
            if strict:
                if isinstance(value, Mapping):
                    value = value["task"]
                if not isinstance(value, (bool, np.bool_)):
                    raise ValueError("task success must be boolean, got {!r}".format(value))
        except Exception as exc:
            self.success_error = repr(exc)
            if strict:
                raise RuntimeError("B2 task success predicate failed: {}".format(self.success_error)) from exc
            return False
        self.success_error = None
        if isinstance(value, Mapping):
            value = value.get("task", False)
        return bool(value)

    def initial_state_hash(self) -> str:
        state = self.robomimic_env.get_state()
        return sha256_array(np.asarray(state["states"]))

    def current_sim_state(self) -> np.ndarray:
        return np.asarray(self.robomimic_env.get_state()["states"]).copy()

    @contextmanager
    def track_b2_observation_pose(self):
        """Remember the qpos used by the final Euler substep's forward kinematics."""
        sim = self.robosuite_env.sim
        if (sim.nsubsteps != 1 or sim.udd_callback is not None or sim.udd_state
                or sim.substep_callback_ptr or int(sim.model.opt.integrator) != 0):
            raise RuntimeError("B2 observation timing requires the locked single-substep Euler simulator")
        pose = np.empty_like(sim.data.qpos)

        def before_physics_step(live_sim):
            pose[:] = live_sim.data.qpos
            return {}

        sim.udd_callback = before_physics_step
        try:
            yield pose
        finally:
            sim.udd_callback = None

    def fresh_observation(self) -> Dict[str, np.ndarray]:
        """Force robosuite sensors, including camera renders, at the live pose."""
        rs_env = self.robosuite_env
        cache = rs_env._obs_cache
        rs_env._obs_cache = {}
        try:
            raw_obs = rs_env._get_observations(force_update=True)
        finally:
            rs_env._obs_cache = cache
        obs = self.wrapper.get_observation(self.robomimic_env.get_observation(raw_obs))
        return {key: np.array(value, copy=True) for key, value in obs.items()}

    def snapshot(
        self, metadata: Optional[Mapping[str, Any]] = None,
        observation_qpos: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        from .snapshot import capture_episode_snapshot
        return capture_episode_snapshot(self, metadata=metadata, observation_qpos=observation_qpos)

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
