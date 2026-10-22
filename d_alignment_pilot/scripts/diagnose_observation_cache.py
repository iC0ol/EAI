"""Deployment diagnostic, not lag identification: inspect forced sensor refreshes."""
import h5py
import numpy as np

from d_alignment.environment import create_env
from d_alignment.io import ROOT, read_json, write_json

cfg = read_json(ROOT / "configs/gate1.json")
env, _ = create_env()
results = {"description": "Repeated forced observations at identical simulator states; no policy or lag estimator", "episodes": {}}
with h5py.File(ROOT / cfg["source_path"], "r") as f:
    for name in ["demo_0", "demo_1", "demo_2"]:
        ep = f["data"][name]
        initial = {"model": ep.attrs["model_file"], "states": ep["states"][0], "ep_meta": ep.attrs.get("ep_meta", None)}
        env.reset()
        env.reset_to(initial)
        records = []
        for t in range(len(ep["actions"])):
            obs1 = env.reset_to({"states": ep["states"][t]})
            obs2 = env.get_observation()
            row = {"t": t, "raw_object": ep["obs/object"][t].tolist(), "first_refresh": obs1["object"].tolist(), "second_refresh": obs2["object"].tolist(),
                "raw_eef_pos": ep["obs/robot0_eef_pos"][t].tolist(), "raw_eef_quat": ep["obs/robot0_eef_quat"][t].tolist(),
                "first_eef_pos": obs1["robot0_eef_pos"].tolist(), "second_eef_pos": obs2["robot0_eef_pos"].tolist(),
                "state_time": float(ep["states"][t,0])}
            records.append(row)
        # Once at the final state, repeated queries must no longer change obs.
        stationary = [env.get_observation()["object"].tolist() for _ in range(3)]
        arr_raw = np.asarray([r["raw_object"] for r in records])
        arr_1 = np.asarray([r["first_refresh"] for r in records])
        arr_2 = np.asarray([r["second_refresh"] for r in records])
        results["episodes"][name] = {"records": records, "stationary_refreshes": stationary,
            "first_vs_raw_max_abs_per_coordinate": np.max(np.abs(arr_raw-arr_1),axis=0).tolist(),
            "second_vs_raw_max_abs_per_coordinate": np.max(np.abs(arr_raw-arr_2),axis=0).tolist(),
            "refresh_change_max_abs_per_coordinate": np.max(np.abs(arr_1-arr_2),axis=0).tolist()}
        print(name, "first/raw", np.max(np.abs(arr_raw-arr_1),axis=0), "second/raw", np.max(np.abs(arr_raw-arr_2),axis=0), flush=True)
write_json(ROOT / "reports/gate1/observation_cache_diagnostic.json", results)
summary = {}
for name, ep in results["episodes"].items():
    raw = np.asarray([r["raw_object"] for r in ep["records"]])
    first = np.asarray([r["first_refresh"] for r in ep["records"]])
    second = np.asarray([r["second_refresh"] for r in ep["records"]])
    summary[name] = {
        "common_first_position_raw_max_m": float(np.abs(raw-first)[4:-4,:3].max()),
        "common_first_quat_raw_max": float(np.abs(raw-first)[4:-4,3:7].max()),
        "common_second_position_raw_max_m": float(np.abs(raw-second)[4:-4,:3].max()),
        "absolute_object_max": float(np.abs(raw-second)[:,7:].max()),
        "eef_pos_max": max(float(np.abs(np.asarray(r["raw_eef_pos"])-r["second_eef_pos"]).max()) for r in ep["records"])}
write_json(ROOT / "reports/gate1/observation_cache_summary.json", summary)
env.env.close()
