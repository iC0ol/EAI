"""Restore only the demo initial state, then physically replay every prefix step."""
from collections import deque
import hashlib
import json
import random
import time

import numpy as np

from .assets import create_env, flatten_obs, demo_obs
from .geometry import quat_angle
from .io import array_hash, config, encode, stable_seed


class FidelityError(RuntimeError):
    pass


class ControllerTap:
    """Passive receipt observers: originals called once with unmodified inputs."""
    def __init__(self, env):
        robot = env.env.robots[0]
        self.ctrl = robot.part_controllers["right"]
        self.composite = robot.composite_controller
        original_set = self.composite.set_goal
        original_scale = self.ctrl.scale_action

        def set_goal(action):
            self.composite_input = np.asarray(action).copy()
            return original_set(action)

        def scale_action(action):
            self.arm_input = np.asarray(action).copy()
            out = original_scale(action)
            self.arm_scaled = np.asarray(out).copy()
            self.goal_reference = self.ctrl.ref_pos.copy()
            return out

        self.composite.set_goal = set_goal
        self.ctrl.scale_action = scale_action
        self.begin()

    def begin(self):
        self.composite_input = self.arm_input = self.arm_scaled = self.goal_reference = None

    def receipt(self, requested):
        if self.composite_input is None or self.arm_scaled is None:
            raise FidelityError("controller receipt not observed")
        np.testing.assert_array_equal(self.composite_input, requested)
        np.testing.assert_array_equal(self.arm_input, np.asarray(requested)[:6])
        clipped = np.r_[np.clip(self.arm_input, self.ctrl.input_min, self.ctrl.input_max), requested[6]]
        expected = clipped[:6] * np.array([.05, .05, .05, .5, .5, .5])
        np.testing.assert_allclose(self.arm_scaled, expected, atol=1e-14, rtol=0)
        return {"composite_input": self.composite_input.copy(), "normalized_after_clip": clipped,
                "scaled_arm_command": self.arm_scaled.copy(),
                "command_clipped": bool(np.any(self.arm_input != clipped[:6])),
                "goal_pos": self.ctrl.goal_pos.copy(), "goal_reference": self.goal_reference.copy()}


def _simple_fields(obj):
    out = {}
    for k, v in vars(obj).items():
        if isinstance(v, np.ndarray) and v.dtype.kind in "fiub" and v.size < 20000:
            out[k] = v.copy()
        elif isinstance(v, (float, int, bool, str, type(None))):
            out[k] = v
    return out


def _digest(value):
    return hashlib.sha256(json.dumps(value, default=encode, sort_keys=True, allow_nan=False).encode()).hexdigest()


def snapshot(env, history):
    raw = env.env
    robot = raw.robots[0]
    ctrl = robot.part_controllers["right"]
    cache = {k: v.copy() if isinstance(v, np.ndarray) else v for k, v in raw._obs_cache.items()
             if isinstance(v, (np.ndarray, float, int, bool))}
    observable = {k: _simple_fields(v) for k, v in raw._observables.items()}
    state = raw.sim.get_state().flatten()
    return {"state_sha256": array_hash(state), "history_sha256": array_hash(np.stack(history)),
            "controller_sha256": _digest(_simple_fields(ctrl)), "cache_sha256": _digest(cache),
            "observables_sha256": _digest(observable),
            "qacc_warmstart_sha256": array_hash(raw.sim.data.qacc_warmstart.copy()),
            "actuator_ctrl_sha256": array_hash(raw.sim.data.ctrl.copy()),
            "gripper_sha256": _digest(_simple_fields(robot.gripper["right"])),
            "numpy_rng_sha256": _digest(list(np.random.get_state())),
            "python_rng_sha256": _digest(random.getstate()),
            "env_timestep": raw.timestep, "env_time": raw.cur_time}


def source_error(live_state, obs, source_state, source_obs):
    return {"selected_observation_max_abs": float(np.max(np.abs(obs-source_obs))),
            "eef_position_m": float(np.linalg.norm(obs[7:10]-source_obs[7:10])),
            "object_position_m": float(np.linalg.norm(obs[:3]-source_obs[:3])),
            "eef_rotation_rad": float(quat_angle(obs[10:14], source_obs[10:14])),
            "object_rotation_rad": float(quat_angle(obs[3:7], source_obs[3:7])),
            "state_max_abs": float(np.max(np.abs(live_state-source_state))),
            "time_s": float(abs(live_state[0]-source_state[0]))}


def prefix_replay(g, state, progress):
    seed = stable_seed(state["state_id"])
    random.seed(seed)
    np.random.seed(seed)
    wall, cpu = time.monotonic(), time.process_time()
    env = create_env()
    progress["env"] = env
    obs = env.reset_to({"states": g["states"][0], "model": g.attrs["model_file"],
                        "ep_meta": g.attrs.get("ep_meta", None)})
    flat = flatten_obs(obs)
    history = deque([flat.copy(), flat.copy()], maxlen=2)
    tap = ControllerTap(env)
    errors, observations, sim_states, receipts = [], [flat.copy()], [], []
    t = int(state["t"])
    for j in range(t+1):
        current = env.env.sim.get_state().flatten()
        sim_states.append(current.copy())
        errors.append(source_error(current, flat, g["states"][j], demo_obs(g, j)))
        if j == t:
            break
        expert = g["actions"][j]
        tap.begin()
        next_obs, _, _, _ = env.step(expert)
        progress["prefix_steps"] += 1
        receipts.append(tap.receipt(expert)["composite_input"])
        flat = flatten_obs(next_obs)
        observations.append(flat.copy())
        history.append(flat.copy())
    progress["prefix_wall_seconds"] = time.monotonic()-wall
    progress["prefix_cpu_seconds"] = time.process_time()-cpu
    maximum = {k: max(x[k] for x in errors) for k in errors[0]}
    progress["prefix_diagnostics"] = {"max_errors": maximum, "at_fork": errors[-1],
        "expected_prefix_steps": t, "actual_prefix_steps": progress["prefix_steps"],
        "live_fork_state_sha256": array_hash(sim_states[-1]),
        "source_fork_state_sha256": array_hash(g["states"][t]),
        "source_history_sha256": array_hash(np.stack([demo_obs(g, t-1), demo_obs(g, t)])),
        "fork_snapshot": snapshot(env, history),
        "official_success_at_fork": bool(env.is_success()["task"])}
    progress["prefix_trace"] = {"prefix_observations": np.stack(observations),
        "prefix_sim_states": np.stack(sim_states), "prefix_received_actions": np.asarray(receipts),
        "prefix_errors": np.array([[e[k] for k in maximum] for e in errors])}
    bad = {k: v for k, v in maximum.items() if v > config()["prefix_tolerances"][k]}
    if bad or progress["prefix_diagnostics"]["official_success_at_fork"]:
        raise FidelityError(f"Expert prefix fidelity rejected: {bad}; already successful={progress['prefix_diagnostics']['official_success_at_fork']}")
    return env, history, tap
