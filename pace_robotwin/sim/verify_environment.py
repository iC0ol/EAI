"""Exercise the installed RoboTwin environment on released seed-2 scenes."""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import random
import time

import numpy as np

from pace.robotwin import load_cached_scenes, load_environment, restore_cached_scene_state, sample_instruction
from pace.rollout import encode_observation


TASKS = ("stack_blocks_three", "place_phone_stand")
CAMERAS = {"cam_high", "cam_left_wrist", "cam_right_wrist"}
SCENE_COLLECTION_SEED = 2


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def state_digest(state):
    return hashlib.sha256(np.ascontiguousarray(state).tobytes()).hexdigest()


def measured_joints(env):
    return np.asarray(env.robot.get_left_arm_real_jointState() + env.robot.get_right_arm_real_jointState())


def reset(env, config, task, scene, index):
    env.setup_demo(now_ep_num=index, seed=scene["scene_seed"], is_test=True, **config)
    info = scene["episode_info"]
    restore_cached_scene_state(task, env, info)
    random.seed(scene["scene_seed"])
    instruction = sample_instruction(task, {"info": info}, 100, "unseen")
    env.set_instruction(instruction)
    require(env.take_action_cnt == 0 and not env.eval_success, "Task did not reset its action counter and success latch")
    require(not env.check_success(), "Task starts with its success predicate already true")
    observation = encode_observation(env.get_obs(), env.get_instruction())
    require(observation["prompt"] == instruction and len(instruction.strip()) > 0, "Invalid unseen instruction")
    require(set(observation["images"]) == CAMERAS, "Unexpected PACE camera names")
    for name, rgb in observation["images"].items():
        require(rgb.shape == (3, 240, 320) and rgb.dtype == np.uint8, f"Unexpected RGB layout for {name}")
        require(rgb.min() < rgb.max(), f"Constant camera image {name}")
    state = observation["state"]
    require(state.shape == (14,) and np.isfinite(state).all(), "Expected a finite 14-D joint observation")
    return observation, instruction


def verify_task(task, index, expert):
    started = time.perf_counter()
    scenes, cache = load_cached_scenes(task, SCENE_COLLECTION_SEED, index + 1)
    scene = scenes[index]
    env, config = load_environment(task)
    require(config["embodiment"] == ["aloha-agilex"], "Unexpected RoboTwin embodiment")
    require(config["camera"]["head_camera_type"] == config["camera"]["wrist_camera_type"] == "D435", "Unexpected camera configuration")

    print(f"{task}: reset released engineering scene {scene['scene_seed']}", flush=True)
    try:
        observation, instruction = reset(env, config, task, scene, index)
        start_state = observation["state"].copy()
        start_joints = measured_joints(env)
        command = start_state.copy()
        command[0] += 0.02
        command[7] -= 0.02
        env.take_action(command)
        require(env.take_action_cnt == 1 and not env.eval_success, "Unexpected step count or success after test command")
        require(not env.check_success(), "Probe motion unexpectedly satisfies the task")
        end_observation = encode_observation(env.get_obs(), env.get_instruction())
        end_state = end_observation["state"]
        end_joints = measured_joints(env)
        require(np.isfinite(end_state).all() and np.linalg.norm(end_state - start_state) > 1e-4, "Joint observation did not respond to the control step")
        require(np.isfinite(end_joints).all() and np.linalg.norm(end_joints - start_joints) > 1e-4, "Physical arm joints did not respond to the control step")
        result = {
            "task": task,
            "scene_cache": cache,
            "scene_cache_seed": SCENE_COLLECTION_SEED,
            "scene_cache_index": index,
            "scene_seed": scene["scene_seed"],
            "instruction": instruction,
            "step_limit": int(env.step_lim),
            "cameras": {name: {"shape": list(image.shape), "dtype": str(image.dtype)} for name, image in observation["images"].items()},
            "state_shape": list(start_state.shape),
            "initial_joint_sha256": state_digest(start_state),
            "executed_test_actions": int(env.take_action_cnt),
            "post_action_joint_sha256": state_digest(end_state),
            "joint_change_l2": float(np.linalg.norm(end_state - start_state)),
            "physical_joint_change_l2": float(np.linalg.norm(end_joints - start_joints)),
            "probe_success": bool(env.eval_success),
        }
    finally:
        env.close_env(clear_cache=True)

    print(f"{task}: reset after probe and verify task bookkeeping", flush=True)
    try:
        observation, reset_instruction = reset(env, config, task, scene, index)
        require(np.allclose(observation["state"], start_state, rtol=0, atol=1e-6), "Reset did not reproduce the joint observation")
        require(np.allclose(measured_joints(env), start_joints, rtol=0, atol=1e-4), "Reset did not reproduce the physical arm joints")
        require(instruction == reset_instruction, "Engineering instruction was not reproduced")
        result["reset"] = {"action_count": int(env.take_action_cnt), "success": bool(env.eval_success)}
        if expert:
            print(f"{task}: run released scripted expert on the same engineering scene", flush=True)
            env.play_once()
            require(env.plan_success and env.check_success(), "Released engineering-scene expert did not reach task success")
            command = env.get_obs()["joint_action"]["vector"]
            env.take_action(command)
            require(env.eval_success and env.take_action_cnt == 1, "Official action loop did not latch achieved task success")
            env.take_action(command)
            require(env.take_action_cnt == 1, "A successful episode advanced after termination")
            result["expert_confirmation"] = {"success": True, "action_count_after_latch": int(env.take_action_cnt)}
    finally:
        env.close_env(clear_cache=True)

    if expert:
        try:
            reset(env, config, task, scene, index)
            result["post_success_reset"] = {"action_count": int(env.take_action_cnt), "success": bool(env.eval_success)}
        finally:
            env.close_env(clear_cache=True)
    result["wall_seconds"] = time.perf_counter() - started
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=TASKS, action="append")
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--expert", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 0 <= args.index < 100:
        parser.error("--index must be in the seed-2 cache range [0, 99]")
    if args.output is not None:
        args.output = args.output.resolve()
        require(not args.output.exists(), f"Refusing to overwrite {args.output}")

    import torch

    require(torch.cuda.is_available(), "The RoboTwin planner cannot access CUDA")
    os.chdir(os.environ["PACE_ROBOTWIN_ROOT"])
    result = {
        "status": "pass",
        "gpu": torch.cuda.get_device_name(0),
        "torch_cuda": torch.version.cuda,
        "versions": {
            name: importlib.metadata.version(name) for name in ("torch", "sapien", "mplib", "nvidia_curobo", "robotwin-pace")
        },
        "tasks": [verify_task(task, args.index, args.expert) for task in args.task or TASKS],
    }
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output is not None:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(rendered)
    print(rendered, end="", flush=True)


if __name__ == "__main__":
    main()
