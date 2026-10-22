"""Apply predeclared Clean stopping criteria, without selecting a checkpoint."""
from d_alignment.io import ROOT, read_json, write_json

cfg = read_json(ROOT / "configs/gate1.json")
checks = []
for seed in cfg["train_seeds"]:
    path = ROOT / f"outputs/gate1/clean_seed{seed}/evaluation_summary.json"
    if not path.exists():
        continue
    data = read_json(path)
    assert data["episodes"] == cfg["clean_gate"]["required_episodes"]
    count = data["successes"]
    reason = ("near_failure" if count <= cfg["clean_gate"]["near_failure_successes_at_most"] else
              "ceiling" if count >= cfg["clean_gate"]["ceiling_successes_at_least"] else "usable_success_range")
    checks.append({"seed": seed, "successes": count, "episodes": data["episodes"], "reason": reason, "pass": reason == "usable_success_range"})
assert checks
gate = {"pass": all(c["pass"] for c in checks), "clean_seeds_evaluated": [c["seed"] for c in checks],
        "all_clean_seeds_evaluated": len(checks) == len(cfg["train_seeds"]), "checks": checks,
        "rule": cfg["clean_gate"]}
write_json(ROOT / "outputs/gate1/clean_gate.json", gate)
print(gate)
