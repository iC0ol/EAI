import json, sys
import h5py

path = sys.argv[1]
with h5py.File(path, "r") as f:
    for group_name in ("data",):
        attrs = dict(f[group_name].attrs)
        print(group_name, "attrs:", sorted(attrs))
        if "env_args" in attrs:
            raw = attrs["env_args"]
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            print(json.dumps(json.loads(raw), indent=2, sort_keys=True))
    demo = f["data"]["demo_0"]
    print("demo attrs:", sorted(dict(demo.attrs)))
    for key in ("actions", "states", "rewards", "dones"):
        if key in demo:
            print(key, demo[key].shape, demo[key].dtype)
    if "obs" in demo:
        for k in ("robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos"):
            print(k, demo["obs"][k].shape, demo["obs"][k].dtype)
