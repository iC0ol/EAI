"""Audited world-frame command/response signals and common time indices."""
import numpy as np
from scipy.spatial.transform import Rotation


def times(n, settings):
    result = np.arange(settings["left_guard"], n - settings["right_guard"])
    assert len(result) > 0
    return result


def motion(view):
    # Robosuite observations use xyzw. Left composition gives world increments.
    current = Rotation.from_quat(view["quaternion"])
    following = Rotation.from_quat(view["next_quaternion"])
    angular = (following * current.inv()).as_rotvec()
    return np.concatenate([view["next_position"] - view["position"], angular,
                           view["next_gripper"] - view["gripper"]], axis=1)


def commands(view, settings):
    result = view["command"].copy()
    result[:, :3] *= settings["translation_command_scale_m"]
    result[:, 3:6] *= settings["rotation_command_scale_rad"]
    return result


def features(view, history, candidate, settings):
    idx = times(len(view["command"]), settings)
    response, control = motion(view), commands(view, settings)
    command_indices = [idx - candidate - k for k in range(history)]
    state_indices = [idx - h for h in range(1, history + 1)]
    assert min(x.min() for x in command_indices + state_indices) >= 0
    assert max(x.max() for x in command_indices + state_indices) < len(control)
    x = np.concatenate([response[j] for j in state_indices] + [control[j] for j in command_indices], axis=1)
    return x, response[idx]


def change_signal(command):
    diff = np.diff(command, axis=0, prepend=command[:1])
    grip = np.diff(np.sign(command[:, 6]), prepend=np.sign(command[0, 6]))
    return np.linalg.norm(diff[:, :3], axis=1) + np.linalg.norm(diff[:, 3:6], axis=1) + .5 * np.abs(grip)


def group_mse(error):
    return float(np.mean([np.mean(error[:, :3]**2), np.mean(error[:, 3:6]**2), np.mean(error[:, 6:]**2)]))
