"""Export saved raw comparisons and current runtime metadata; zero integration."""
import sys

import mujoco
import robomimic
import robosuite
import torch
import numpy as np

from common import ROOT, OUT, LOCAL, read_json, write_csv, write_json, sha256

for name in ["D1_P1_S00", "D2_P2_S00"]:
    boundaries = read_json(LOCAL/name/"boundaries.json")
    with np.load(LOCAL/name/"trace.npz") as z:
        records = []
        for t in range(53):
            r = {"attempt_id": name, "state_index": t,
                 "source_time": z["source_states"][t,0], "source_qpos23": z["source_states"][t,1:24],
                 "source_qvel21": z["source_states"][t,24:],
                 "live_time": z["states"][t,0], "live_qpos23": z["states"][t,1:24], "live_qvel21": z["states"][t,24:],
                 "source_observation16": z["source_obs"][t], "native_observation16": z["native_obs"][t],
                 "synchronous_observation16": z["sync_obs"][t],
                 "forced_observation16": z["forced_obs"][t] if name.startswith("D2") else None,
                 "previous_controller_command7": z["received_actions"][t-1] if t else None,
                 "controller_goal_xyz": boundaries[t]["controller"]["arm"].get("goal_pos"),
                 "controller_goal_orientation": boundaries[t]["controller"]["arm"].get("goal_ori"),
                 "gripper_current_action": boundaries[t]["controller"]["gripper"].get("current_action"),
                 "live_warmstart21": boundaries[t]["controller"]["qacc_warmstart"],
                 "source_warmstart21": None, "source_contact_data": None}
            records.append(r)
        write_csv(OUT/f"{name}_raw_control_boundaries.csv", records)
write_json(OUT/"runtime_audit.json", {"simulation_steps_in_this_export": 0, "environment_instances_in_this_export": 0,
    "python":sys.version,"python_prefix":sys.prefix,
    "versions":{"mujoco":mujoco.__version__,"robomimic":robomimic.__version__,"robosuite":robosuite.__version__,"torch":torch.__version__},
    "module_paths":{"mujoco":mujoco.__file__,"robomimic":robomimic.__file__,"robosuite":robosuite.__file__,"torch":torch.__file__},
    "cuda_available":torch.cuda.is_available(),"torch_threads_for_experiment":2,
    "note":"Library import/runtime inspection only; no policy loaded, no inference, no model download"})
assert mujoco.__version__=="3.2.3" and robosuite.__version__=="1.5.1" and robomimic.__version__=="0.4.0"
print("Exported two raw 53-row comparisons and runtime audit; zero simulation/inference")
