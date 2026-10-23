"""Budgeted passive reset/prefix instrumentation. Never changes expert commands."""
import gzip
import functools
import json
import random
import time
import traceback
from collections import deque

import h5py
import mujoco
import numpy as np

from common import ROOT, OUT, LOCAL, CODE, plan, verify, Ledger, read_json, write_json, write_csv, sha256, array_hash, digest, git
from m_direction.assets import create_env, data_path, flatten_obs, demo_obs
from m_direction.geometry import quat_angle
from m_direction.io import stable_seed
from m_direction.replay import ControllerTap, source_error, _simple_fields


def state(sim):
    return sim.get_state().flatten().copy()


def fingerprint(raw):
    d = raw.sim.data
    return digest({k: np.asarray(getattr(d, k)).copy() for k in ["qpos", "qvel", "act", "qacc_warmstart", "ctrl"]} | {"time": float(d.time)})


def controller(raw):
    robot = raw.robots[0]
    return {"arm": _simple_fields(robot.part_controllers["right"]),
            "gripper": _simple_fields(robot.gripper["right"]),
            "ctrl": raw.sim.data.ctrl.copy(), "qacc_warmstart": raw.sim.data.qacc_warmstart.copy()}


def caches(raw, last_calls):
    return {k: {"sample_period_s": v._sampling_timestep,
                "time_since_last_sample_s": v._time_since_last_sample,
                "sampled": v._sampled, "current_delay_s": v._current_delay,
                "value": np.asarray(v._current_observed_value).copy(),
                "last_sensor_call_sim_time": last_calls.get(k)}
            for k, v in raw._observables.items() if k in ["robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos", "SquareNut_pos", "SquareNut_quat"]}


class SyncObserver:
    """Kinematics on a separate MjData, preserving live dynamics and caches."""
    def __init__(self, env):
        self.raw = env.env
        self.model = self.raw.sim.model._model
        self.data = mujoco.MjData(self.model)
        robot = self.raw.robots[0]
        self.nut_body = self.raw.obj_body_id["SquareNut"]
        self.eef_site = robot.eef_site_id["right"]
        self.eef_body = self.raw.sim.model.body_name2id(robot.robot_model.eef_name["right"])
        self.gripper_idx = robot._ref_gripper_joint_pos_indexes["right"]
        self.nut_qadr = int(self.model.jnt_qposadr[self.raw.sim.model.joint_name2id("SquareNut_joint0")])
        self.nut_vadr = int(self.model.jnt_dofadr[self.raw.sim.model.joint_name2id("SquareNut_joint0")])

    def from_state(self, flat):
        d, m = self.data, self.model
        d.time = flat[0]
        d.qpos[:] = flat[1:1+m.nq]
        d.qvel[:] = flat[1+m.nq:1+m.nq+m.nv]
        mujoco.mj_kinematics(m, d)
        return np.r_[d.xpos[self.nut_body], d.xquat[self.nut_body][[1, 2, 3, 0]],
                     d.site_xpos[self.eef_site], d.xquat[self.eef_body][[1, 2, 3, 0]], d.qpos[self.gripper_idx]].astype(np.float32)

    def live(self):
        before = fingerprint(self.raw)
        out = self.from_state(state(self.raw.sim))
        assert fingerprint(self.raw) == before, "Kinematic observer changed live dynamics"
        return out


class StepGuard:
    """Count every true integration; disallow constructor/reset stepping or other APIs."""
    def __init__(self, capture):
        self.capture = capture
        self.allowed = False
        self.steps = 0
        self.control_index = -1

    def __enter__(self):
        from robosuite.utils.binding_utils import MjSim
        self.cls = MjSim
        self.original = {k: getattr(MjSim, k) for k in ["step", "step1", "step2"]}
        def step(sim, *args, **kwargs):
            if not self.allowed: raise RuntimeError("Unregistered integration during construction/reset")
            before = self.capture.before(sim) if self.capture else None
            result = self.original["step"](sim, *args, **kwargs)
            self.steps += 1
            if self.capture: self.capture.after(sim, before, self.control_index, self.steps)
            return result
        def forbidden(*args, **kwargs):
            raise RuntimeError("Unexpected step1/step2; frozen lite_physics=false required")
        MjSim.step, MjSim.step1, MjSim.step2 = step, forbidden, forbidden
        return self

    def __exit__(self, *args):
        for k, v in self.original.items(): setattr(self.cls, k, v)

    def env_step(self, env, action, control_index):
        self.control_index = control_index
        self.allowed = True
        before = self.steps
        try: out = env.step(action)
        finally: self.allowed = False
        assert self.steps-before == 25, "Unexpected number of simulation substeps"
        return out


class Capture:
    def __init__(self, f):
        self.f = f
        self.raw = None
        self.summary = []

    def before(self, sim):
        return {"time": float(sim.data.time), "qpos": sim.data.qpos.copy(), "qvel": sim.data.qvel.copy(),
                "warmstart": sim.data.qacc_warmstart.copy(), "actuator_ctrl": sim.data.ctrl.copy()}

    def after(self, sim, before, control_index, substep):
        raw, d, m = self.raw, sim.data._data, sim.model._model
        contacts = []
        square_normals = []
        for i in range(d.ncon):
            c = d.contact[i]
            force = np.zeros(6)
            mujoco.mj_contactForce(m, d, i, force)
            names = [mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, int(g)) if g >= 0 else "flex" for g in c.geom]
            contact = {"geom_ids": c.geom.copy(), "geom_names": names, "position_world": c.pos.copy(),
                       "normal_geom0_to_geom1_world": c.frame[:3].copy(), "contact_frame": c.frame.copy(),
                       "distance_m": float(c.dist), "efc_address": int(c.efc_address),
                       "force_torque_contact_frame": force, "force_dt_impulse_proxy": force*float(m.opt.timestep)}
            contacts.append(contact)
            if any("SquareNut" in (n or "") for n in names): square_normals.append(float(force[0]))
        row = {"control_action_index": control_index, "integration_index": substep,
               "integration_before": before, "integration_after": self.before(sim),
               "contact_solver_timestamp_note": "Native solved contact data; qpos_after is after integration. No extra forward.",
               "ncon": int(d.ncon), "contacts": contacts, "controller": controller(raw)}
        self.f.write(json.dumps(row, default=__import__("m_direction.io", fromlist=["encode"]).encode, allow_nan=False)+"\n")
        self.summary.append({"control_action_index": control_index, "integration_index": substep,
                             "time_before": before["time"], "time_after": float(d.time), "ncon": int(d.ncon),
                             "square_contact_count": len(square_normals), "square_normal_force_sum_N": sum(square_normals),
                             "max_square_normal_force_N": max(square_normals, default=0.)})


def metrics(current, native, sync, source, source_obs, observer):
    old = source_error(current, native, source, source_obs)
    aligned = source_error(current, sync, source, source_obs)
    m = observer.model
    qd = current[1:1+m.nq]-source[1:1+m.nq]
    vd = current[1+m.nq:]-source[1+m.nq:]
    nv = observer.nut_vadr
    return {"old_native": old, "new_aligned": {"time_s": aligned["time_s"], "state_max_abs": aligned["state_max_abs"],
          "eef_position_m": aligned["eef_position_m"], "object_position_m": aligned["object_position_m"],
          "eef_rotation_rad": aligned["eef_rotation_rad"], "object_rotation_rad": aligned["object_rotation_rad"],
          "state_aligned_obs_max_abs": aligned["selected_observation_max_abs"]},
          "qpos_max_abs": float(np.abs(qd).max()), "qvel_max_abs": float(np.abs(vd).max()),
          "robot_qvel_max_abs": float(np.abs(vd[:7]).max()), "gripper_qvel_max_abs": float(np.abs(vd[7:9]).max()),
          "square_linear_qvel_max_abs": float(np.abs(vd[nv:nv+3]).max()),
          "square_angular_qvel_max_abs": float(np.abs(vd[nv+3:nv+6]).max()),
          "act_max_abs": 0. if m.na == 0 else None,
          "native_vs_sync_object_m": float(np.linalg.norm(native[:3]-sync[:3]))}


def run_prefix(item):
    registration = verify()
    assert item in plan()["prefix_plan"], "Unregistered prefix path/state"
    ledger = Ledger(); ledger.reserve(item, "prefix")
    begin, cpu = time.monotonic(), time.process_time()
    result = {**item, "status": "started", "protocol_commit": registration["protocol_commit"],
              "execution_commit": git("rev-parse", "HEAD"), "cpu_seconds": 0., "wall_seconds": 0.,
              "expert_control_steps": 0, "integration_steps": 0, "gpu_inference_calls": 0,
              "code_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in sorted(CODE.glob("*.py"))}}
    env, guard, sub_file = None, None, None
    arrays = {k: [] for k in ["states", "native_obs", "sync_obs", "source_obs", "source_states", "received_actions", "forced_obs"]}
    boundaries, rows, reset_states = [], [], []
    local = LOCAL/item["attempt_id"]; local.mkdir(parents=True, exist_ok=False)
    try:
        with h5py.File(data_path(), "r") as data:
            g = data[f"data/{item['source_episode']}"]
            sub_file = gzip.open(local/"substeps.jsonl.gz", "xt", encoding="utf-8")
            capture = Capture(sub_file)
            with StepGuard(capture) as guard:
                seed = stable_seed(item["state_id"])
                random.seed(seed); np.random.seed(seed)
                env = create_env()
                reset_states.append({"point": "constructed", "state": state(env.env.sim), "controller": controller(env.env)})
                env.reset()
                reset_states.append({"point": "after_outer_reset", "state": state(env.env.sim), "controller": controller(env.env)})
                obs = env.reset_to({"model": g.attrs["model_file"], "states": g["states"][0], "ep_meta": g.attrs.get("ep_meta", None)})
                raw = env.env; capture.raw = raw
                assert not raw.lite_physics
                observer = SyncObserver(env)
                m = observer.model
                assert (m.nq, m.nv, m.na) == (23, 21, 0)
                result["model"] = {"nq": m.nq, "nv": m.nv, "na": m.na, "timestep": m.opt.timestep,
                                   "integrator_enum": int(m.opt.integrator), "solver_enum": int(m.opt.solver),
                                   "solver_iterations": int(m.opt.iterations), "solver_tolerance": float(m.opt.tolerance),
                                   "nut_qpos_adr": observer.nut_qadr, "nut_dof_adr": observer.nut_vadr}
                reset_states.append({"point": "after_reset_to", "state": state(raw.sim), "controller": controller(raw)})
                source_check = max(float(np.max(np.abs(observer.from_state(g["states"][j])-demo_obs(g, j)))) for j in range(item["t"]+1))
                result["source_sync_observer_max_abs"] = source_check
                assert source_check <= plan()["source_observer_validation_max_abs"], "Source observation cannot be reconstructed by registered kinematic observer"
                tap = ControllerTap(env)
                calls = {}
                for name, observable in raw._observables.items():
                    original = observable._sensor
                    def sensor(cache, original=original, name=name):
                        calls[name] = float(raw.sim.data.time)
                        return original(cache)
                    observable._sensor = functools.wraps(original)(sensor)
                history = deque(maxlen=2)
                for j in range(item["t"]+1):
                    current = state(raw.sim); native = flatten_obs(obs); sync = observer.live()
                    expected = demo_obs(g, j); source = g["states"][j]
                    em = metrics(current, native, sync, source, expected, observer)
                    row = {"attempt_id": item["attempt_id"], "t": j, **{f"old_{k}": v for k, v in em["old_native"].items()},
                           **{f"new_{k}": v for k, v in em["new_aligned"].items()},
                           **{k: v for k, v in em.items() if k not in ["old_native", "new_aligned"]},
                           "ncon_native_solved": int(raw.sim.data.ncon)}
                    boundary = {"t": j, "controller": controller(raw), "cache_before_forcing": caches(raw, calls),
                                "physical_hash_before_forcing": fingerprint(raw)}
                    forced = np.full(16, np.nan)
                    if item["path"] == "P2":
                        forced = flatten_obs(env.get_observation())
                        boundary["cache_after_forcing"] = caches(raw, calls)
                        boundary["physical_hash_after_forcing"] = fingerprint(raw)
                        assert boundary["physical_hash_before_forcing"] == boundary["physical_hash_after_forcing"], "Force-refresh changed physical integration state"
                        row["forced_vs_source_max_abs"] = float(np.max(abs(forced-expected)))
                        row["forced_vs_sync_object_m"] = float(np.linalg.norm(forced[:3]-sync[:3]))
                    arrays["states"].append(current); arrays["native_obs"].append(native)
                    arrays["sync_obs"].append(sync); arrays["source_obs"].append(expected); arrays["source_states"].append(source)
                    arrays["forced_obs"].append(forced)
                    rows.append(row); boundaries.append(boundary); history.append(sync.copy())
                    if j == item["t"]: break
                    command = g["actions"][j]
                    tap.begin()
                    obs, _, _, _ = guard.env_step(env, command, j)
                    result["expert_control_steps"] += 1
                    receipt = tap.receipt(command)
                    arrays["received_actions"].append(receipt["composite_input"])
                result["new_max_errors"] = {k: max(r[f"new_{k}"] for r in rows) for k in plan()["physical_limits"]}
                from common import old_limits
                result["old_max_errors"] = {k: max(r[f"old_{k}"] for r in rows) for k in old_limits()}
                result["old_at_fork"] = {k: rows[-1][f"old_{k}"] for k in old_limits()}
                result["new_at_fork"] = {k: rows[-1][f"new_{k}"] for k in plan()["physical_limits"]}
                result["new_failures"] = {k: v for k, v in result["new_max_errors"].items() if v > plan()["physical_limits"][k]}
                result["old_gate_A_would_pass"] = all(v <= old_limits()[k] for k, v in result["old_max_errors"].items())
                result["source_actions_byte_identical"] = np.array_equal(np.stack(arrays["received_actions"]), g["actions"][:item["t"]])
                assert result["source_actions_byte_identical"]
                result["already_successful_at_fork"] = bool(env.is_success()["task"])
                result["technical_pass"] = not result["new_failures"] and not result["already_successful_at_fork"]
                result["status"] = "completed"
                result["fork_snapshot"] = {"physical": fingerprint(raw), "controller": digest(controller(raw)),
                                            "synchronous_history": array_hash(np.stack(history)), "cache": digest(caches(raw, calls))}
                context = {"env": env, "observer": observer, "tap": tap, "history": history,
                           "numpy_rng": np.random.get_state(), "python_rng": random.getstate(),
                           "state_id": item["state_id"], "episode": item["source_episode"], "t": item["t"]}
    except Exception as exc:
        result.update({"status": "invalid", "technical_pass": False, "error": str(exc), "traceback": traceback.format_exc()})
        context = None
    finally:
        if sub_file: sub_file.close()
        result["integration_steps"] = guard.steps if guard else 0
        result["wall_seconds"] = time.monotonic()-begin
        result["cpu_seconds"] = time.process_time()-cpu
        result["partial_control_integration_steps"] = result["integration_steps"]-25*result["expert_control_steps"]
        if result["partial_control_integration_steps"]:
            result.update({"status": "invalid", "technical_pass": False,
                           "partial_step_note": "Partial control step retained; no automatic retry"})
        if rows: write_csv(OUT/f"{item['attempt_id']}_by_step.csv", rows)
        if boundaries: write_json(local/"boundaries.json", boundaries)
        if reset_states: write_json(local/"reset_snapshots.json", reset_states)
        with (local/"trace.npz").open("xb") as f:
            np.savez_compressed(f, **{k: np.asarray(v) for k, v in arrays.items()})
        if guard and guard.capture and guard.capture.summary:
            write_csv(OUT/f"{item['attempt_id']}_contact_by_substep.csv", guard.capture.summary)
        result["local_files"] = [{"path": str(p.relative_to(ROOT)), "sha256": sha256(p), "bytes": p.stat().st_size} for p in sorted(local.iterdir())]
        write_json(OUT/f"{item['attempt_id']}.json", result)
        ledger.append({"event": "finish", "kind": "prefix", "attempt_id": item["attempt_id"], "status": result["status"],
                       "expert_control_steps": result["expert_control_steps"], "integration_steps": result["integration_steps"],
                       "result_sha256": sha256(OUT/f"{item['attempt_id']}.json")})
        if result["status"] != "completed" and env is not None: env.env.close()
        print(json.dumps({k: result.get(k) for k in ["attempt_id", "status", "expert_control_steps", "integration_steps", "technical_pass", "new_failures", "error", "wall_seconds"]}), flush=True)
    return result, context
