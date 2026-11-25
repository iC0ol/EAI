"""One RoboTwin worker. The upstream rollout drives the observation/action loop."""

import argparse
import contextlib
import hashlib
import json
import os
import random
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from design import (
    CACHE_SHA, LIMITS, OPENPI_REVISION, POLICY_REVISION, PORT, ROOT, SIM, STAGES, TASKS,
    file_hash, methods, pair_dir, read_json, verify_record, write_json,
)

sys.path[:0] = [str(SIM / "pace/src"), str(SIM), str(SIM / "description/utils"), str(ROOT.parent)]
from pace import select_horizon
from pace.robotwin import load_cached_scenes, load_environment, restore_cached_scene_state, sample_instruction
from pace.rollout import run_episode


CAMERAS = ("cam_high", "cam_left_wrist", "cam_right_wrist")


def array_hash(array):
    array = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(array.shape).encode())
    digest.update(array.dtype.str.encode())
    digest.update(memoryview(array).cast("B"))
    return digest.hexdigest()


def save_npz(path, arrays, *, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".npz", delete=False) as stream:
        temp = Path(stream.name)
        np.savez_compressed(stream, **arrays)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        if exclusive:
            os.link(temp, path)
        else:
            temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def physical_state(env, task):
    # Privileged state belongs only to reset auditing, never to the controller or model.
    names = ("block1", "block2", "block3") if task == TASKS[0] else ("phone", "stand")
    state = []
    for name in names:
        pose = getattr(env, name).get_pose()
        state.extend(pose.p)
        state.extend(pose.q)
    for side in ("left", "right"):
        articulation = getattr(env.robot, f"{side}_entity")
        state.extend(articulation.get_qpos())
        state.extend(articulation.get_qvel())
    if task == "place_phone_stand":
        state.extend([env.phone_id, env.stand_id])
    return np.asarray(state, dtype=np.float64)


def success_snapshot(env, task):
    if task == "stack_blocks_three":
        points = [np.asarray(getattr(env, name).get_pose().p).tolist() for name in ("block1", "block2", "block3")]
    else:
        points = [np.asarray(getattr(env, name).get_functional_point(0))[:3].tolist() for name in ("phone", "stand")]
    return {"points": points, "grippers": [float(env.robot.get_left_gripper_val()), float(env.robot.get_right_gripper_val())],
            "native_predicate": bool(env.check_success())}


def first_observation(request, physics, anchor):
    current = {key: np.asarray(request["images"][key]) for key in CAMERAS}
    state = np.asarray(request["state"])
    if state.shape != (14,) or not np.isfinite(state).all() or not np.isfinite(physics).all():
        raise ValueError("invalid reset state")
    for frame in current.values():
        if frame.shape != (3, 240, 320) or frame.dtype != np.uint8:
            raise ValueError(f"unexpected official RGB {frame.shape} {frame.dtype}")
    if not anchor.exists():
        save_npz(anchor, {**current, "state": state, "physics": physics, "prompt": request["prompt"]},
                 exclusive=True)
    with np.load(anchor, allow_pickle=False) as saved:
        if str(saved["prompt"]) != request["prompt"]:
            raise ValueError("paired native instructions differ")
        distances = {
            "physics_max": float(np.max(np.abs(physics - saved["physics"]))),
            "state_max": float(np.max(np.abs(state - saved["state"]))),
        }
        if distances["physics_max"] > 1e-4 or distances["state_max"] > 1e-5:
            raise ValueError(f"paired native physical reset differs: {distances}")
        images = {key: saved[key] for key in CAMERAS}
        for key, frame in current.items():
            diff = np.abs(frame.astype(np.int16) - images[key])
            mean = float(diff.mean())
            p99 = float(np.percentile(diff, 99))
            distances[key] = {"mean_gray": mean, "p99_gray": p99, "native_sha256": array_hash(frame)}
            if mean > 5 or p99 > 30:
                raise ValueError(f"paired native cameras differ at {key}: {mean}, {p99}")
        result = {"state": saved["state"], "images": images, "prompt": request["prompt"]}
    return result, distances


class RecordedPolicy:
    def __init__(self, policy, env, method, scene_seed, threshold, task, anchor):
        self.policy = policy
        self.env = env
        self.method = method
        self.scene_seed = scene_seed
        self.threshold = threshold
        self.anchor = anchor
        self.physics = physical_state(env, task)
        self.kinematics = None
        if method == "component":
            from pace_robotwin.controller import AlohaKinematics
            self.kinematics = AlohaKinematics.from_robot(env.robot)
        self.queries = []
        self.raw = []
        self.output = []
        self.states = []
        self.reset_check = None

    def infer(self, request):
        index = len(self.raw)
        if index == 0:
            request, self.reset_check = first_observation(request, self.physics, self.anchor)
        started = time.perf_counter()
        reply = self.policy.infer({**request, "episode_seed": self.scene_seed, "query_index": index})
        rpc_s = time.perf_counter() - started
        if (reply.get("episode_seed"), reply.get("query_index")) != (self.scene_seed, index):
            raise ValueError("model did not use the registered episode key")
        raw = np.asarray(reply["actions"])
        if raw.shape != (50, 14) or raw.dtype.kind != "f" or not np.isfinite(raw).all():
            raise ValueError("policy must return one finite 50x14 float chunk")
        tick = time.perf_counter()
        horizon = int(self.method[5:]) if self.method.startswith("fixed") else int(select_horizon(raw, self.threshold))
        selection_s = time.perf_counter() - tick
        step = int(self.env.take_action_cnt)
        output = raw
        audit = None
        component_s = 0.
        if self.kinematics is not None:
            from pace_robotwin.controller import apply_component
            tick = time.perf_counter()
            prev_h = step - self.queries[-1]["step"] if index else None
            decision = apply_component(raw, request["state"], horizon, kinematics=self.kinematics,
                                       previous_raw=self.raw[-1] if index else None, prev_h=prev_h)
            output = decision.actions
            audit = decision.audit
            component_s = time.perf_counter() - tick
        inference_ms = float(reply["policy_timing"]["infer_ms"])
        server_ms = float(reply["server_timing"]["infer_ms"])
        if not all(np.isfinite(v) and v >= 0 for v in (inference_ms, server_ms)):
            raise ValueError("missing or invalid native policy timing")
        self.raw.append(raw.copy())
        self.states.append(np.array(request["state"], copy=True))
        self.output.append(output.copy())
        self.queries.append({
            "index": index, "step": step, "h": horizon, "rpc_s": rpc_s,
            "policy_s": inference_ms / 1000, "server_s": server_ms / 1000,
            "selection_s": selection_s, "component_s": component_s, "decision": audit,
        })
        return {"actions": output}

    def chosen_horizon(self, _actions):
        return self.queries[-1]["h"]


class TimedEnv:
    def __init__(self, env):
        self.env = env
        self.action_s = 0.
        self.observation_s = 0.
        self.applied = []

    def __getattr__(self, key):
        return getattr(self.env, key)

    def get_obs(self):
        start = time.perf_counter()
        result = self.env.get_obs()
        self.observation_s += time.perf_counter() - start
        return result

    def take_action(self, action):
        start = time.perf_counter()
        self.env.take_action(action)
        self.action_s += time.perf_counter() - start
        self.applied.append(np.array(action, copy=True))


def verify_server(client, task):
    metadata = client.get_server_metadata()
    expected = {
        "task": task, "config": f"pi05_robotwin_{task}", "action_horizon": 50, "action_dim": 14,
        "action_space": "absolute_joint", "candidate_count": 1, "denoising_steps": 10,
        "checkpoint_revision": POLICY_REVISION, "openpi_revision": OPENPI_REVISION,
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError(f"unexpected policy metadata for {task}: {metadata}")
    return metadata


def run_cell(args, client, metadata, env, config, cached, threshold, index, method):
    scene_seed = int(cached["scene_seed"])
    identity = dict(stage=args.stage, task=args.task, index=index, method=method, scene_seed=scene_seed,
                    manifest_sha256=args.manifest)
    pair = pair_dir(args.output, args.stage, args.task, index)
    target = pair / method
    if target.exists():
        verify_record(target, identity)
        return
    pair.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    random.seed(scene_seed)
    env.setup_demo(now_ep_num=index, seed=scene_seed, is_test=True, **config)
    try:
        restore_cached_scene_state(args.task, env, cached["episode_info"])
        random.seed(scene_seed)
        instruction = sample_instruction(args.task, {"info": cached["episode_info"]}, 100, "unseen")
        env.set_instruction(instruction)
        if int(env.step_lim) != LIMITS[args.task] or env.eval_success or int(env.take_action_cnt) != 0:
            raise ValueError("reset flags or task control limit differ from the registered condition")
        initial_success = success_snapshot(env, args.task)
        if initial_success["native_predicate"]:
            raise ValueError("an evaluation scene already satisfied the task before any action")
        anchor = pair / "initial.npz"
        policy = RecordedPolicy(client, env, method, scene_seed, threshold, args.task, anchor)
        native_fk = {}
        if args.stage == "engineering":
            from pace_robotwin.controller.validation import compare_native_fk
            native_fk["initial"] = compare_native_fk(env.robot)
        clock_env = TimedEnv(env)
        setup_s = time.perf_counter() - start
        tick = time.perf_counter()
        # Upstream emits per-step ANSI progress. The task telemetry lives in the per-query trace.
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink):
            outcome = run_episode(clock_env, policy, policy.chosen_horizon)
        rollout_s = time.perf_counter() - tick
        if outcome["steps"] != len(clock_env.applied) or outcome["queries"] != len(policy.queries):
            raise ValueError("native counters differ from recorded commands")
        if not outcome["success"] and outcome["steps"] != LIMITS[args.task]:
            raise ValueError("incomplete trial cannot be marked as failure")
        if args.stage == "engineering":
            native_fk["terminal"] = compare_native_fk(env.robot)
        terminal_success = success_snapshot(env, args.task)
    finally:
        env.close_env(clear_cache=((index + 2) % config["clear_cache_freq"] == 0))
    native_s = time.perf_counter() - start
    record = {
        **identity, **outcome, "step_limit": LIMITS[args.task], "cache_sha256": CACHE_SHA,
        "policy_metadata": metadata, "instruction": instruction, "initial_sha256": file_hash(anchor),
        "native_reset": policy.reset_check, "native_fk": native_fk, "first_raw_sha256": array_hash(policy.raw[0]),
        "predicate_initial": initial_success, "predicate_terminal": terminal_success,
        "setup_s": setup_s, "action_s": clock_env.action_s, "observation_s": clock_env.observation_s,
        "rollout_s": rollout_s, "attempt_s": native_s, "query_log": policy.queries,
    }
    partial = Path(tempfile.mkdtemp(prefix=f".{method}-", dir=pair))
    save_npz(partial / "chunks.npz", {"raw": policy.raw, "proposed": policy.output,
                                     "issued": clock_env.applied, "states": policy.states})
    write_json(partial / "record.json", record)
    write_json(partial / "timing.json", {"attempt_s": native_s, "wall_with_io_s": time.perf_counter() - start})
    write_json(partial / "sha256.json", {
        f: file_hash(partial / f) for f in ("record.json", "chunks.npz", "timing.json")
    })
    if target.exists():
        raise FileExistsError(target)
    partial.rename(target)
    print(f"COMMITTED {args.stage} {args.task} scene {index} {method} {native_s:.1f}s", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument("task", choices=TASKS)
    parser.add_argument("start", type=int)
    parser.add_argument("stop", type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    if not 0 <= args.start < args.stop <= 100:
        raise ValueError("scene indices must be in the released batch")
    args.output = args.output.resolve()
    if args.stage != "engineering":
        from supervise import FORMAL, accepted_root
        receipt_root = accepted_root(False)
        if args.output != FORMAL or file_hash(receipt_root / "MANIFEST.json") != args.manifest:
            raise ValueError("formal cell is not bound to the accepted experiment")
    elif args.start != 0 or args.stop != 1:
        raise ValueError("the engineering comparison is frozen to the first seed-2 scene")
    os.chdir(SIM)
    cached, info = load_cached_scenes(args.task, STAGES[args.stage][0], 100)
    if info["sha256"] != CACHE_SHA:
        raise ValueError("upstream cache digest differs")
    calibration = read_json(SIM / "pace/configs/calibration" / f"{args.task}.json")
    from openpi_client.websocket_client_policy import WebsocketClientPolicy
    client = WebsocketClientPolicy("127.0.0.1", args.port)
    metadata = verify_server(client, args.task)
    env, config = load_environment(args.task)
    env.suc = env.test_num = 0
    for index in range(args.start, args.stop):
        for method in methods(args.stage, index):
            run_cell(args, client, metadata, env, config, cached[index], calibration["threshold"], index, method)


if __name__ == "__main__":
    main()
