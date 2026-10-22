"""Fixed-policy paired analysis; no checkpoint selection or new experiments."""
import csv
import json
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from d_alignment.io import ROOT, read_json, write_json, sha256

cfg = read_json(ROOT / "configs/gate1.json")
conditions = ["clean", "mixed_small_lag", "larger_lag"]
seeds = cfg["train_seeds"]
expected_tests = read_json(ROOT / "data/manifests/eval_seeds.json")["seeds"]
result = {"runs": {}, "comparisons": {}, "step_d_eligible_conditions": [],
    "bootstrap_seed": cfg["bootstrap_seed"], "bootstrap_replicates": cfg["bootstrap_replicates"],
    "ci_scope": "Initial-condition uncertainty conditional on the actually trained policies; two training seeds do not identify training-population variance."}
outcomes = {}
for condition in conditions:
    for seed in seeds:
        name = f"{condition}_seed{seed}"
        path = ROOT / "outputs/gate1" / name
        if not (path / "run.json").exists():
            continue
        record = {"training": read_json(path / "run.json")}
        record["local_stdout"] = {}
        for phase in ("train", "eval"):
            log = ROOT / "reports/gate1/logs" / f"{phase}_{name}.txt"
            if log.exists():
                record["local_stdout"][phase] = {"path": str(log), "sha256": sha256(log)}
        if (path / "evaluation_summary.json").exists():
            rows = [json.loads(line) for line in (path / "evaluation.jsonl").read_text().splitlines()]
            assert sorted(r["test_seed"] for r in rows) == expected_tests
            assert all(r["steps"] == cfg["eval_max_steps"] for r in rows)
            by_seed = {r["test_seed"]: r for r in rows}
            success = np.asarray([by_seed[t]["success"] for t in expected_tests], dtype=int)
            outcomes[name] = success
            record["evaluation"] = read_json(path / "evaluation_summary.json")
            p, n, z = success.mean(), len(success), 1.959963984540054
            denom = 1 + z*z/n
            center = (p+z*z/(2*n))/denom
            radius = z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/denom
            record["wilson_success_95ci"] = [float(center-radius), float(center+radius)]
            record["auxiliary_means"] = {k: float(np.mean([r[k] for r in rows])) for k in ("gripper_sign_flips", "mean_action_delta_norm", "mean_translation_command_delta_norm", "min_nut_z", "max_contact_count")}
            record["nut_below_table_proxy_trials"] = sum(r["nut_below_table_proxy"] for r in rows)
        result["runs"][name] = record


def boot_ci(diff):
    rng = np.random.default_rng(cfg["bootstrap_seed"])
    idx = rng.integers(len(diff), size=(cfg["bootstrap_replicates"], len(diff)))
    return (100*np.quantile(diff[idx].mean(axis=1), [.025, .975])).tolist()


for condition in conditions[1:]:
    paired = {}
    differences = []
    for seed in seeds:
        clean, corrupt = f"clean_seed{seed}", f"{condition}_seed{seed}"
        if clean not in outcomes or corrupt not in outcomes:
            continue
        a, b = outcomes[clean], outcomes[corrupt]
        diff = a-b
        clean_only, corrupt_only = int(((a==1)&(b==0)).sum()), int(((a==0)&(b==1)).sum())
        ci = boot_ci(diff)
        paired[str(seed)] = {"clean_minus_corrupt_pp": float(100*diff.mean()), "paired_bootstrap_95ci_pp": ci,
            "both_success": int(((a==1)&(b==1)).sum()), "both_failure": int(((a==0)&(b==0)).sum()),
            "clean_only_success": clean_only, "corrupt_only_success": corrupt_only,
            "exact_mcnemar_two_sided_p": float(binomtest(clean_only, clean_only+corrupt_only).pvalue) if clean_only+corrupt_only else 1.,
            "predeclared_material_drop": bool(100*diff.mean() >= cfg["step_d_gate"]["min_drop_percentage_points_each_seed"] - 1e-8 and ci[0] > 0)}
        differences.append(diff)
    comparison = {"by_train_seed": paired, "all_train_seeds_available": len(paired)==len(seeds)}
    if len(differences)==len(seeds):
        avg = np.mean(differences, axis=0)
        comparison.update(mean_clean_minus_corrupt_pp=float(100*avg.mean()),
            paired_initial_condition_cluster_bootstrap_95ci_pp=boot_ci(avg),
            direction_consistent=all(d.mean()>0 for d in differences),
            step_d_eligible=all(v["predeclared_material_drop"] for v in paired.values()))
        if comparison["step_d_eligible"]:
            result["step_d_eligible_conditions"].append(condition)
    else:
        comparison["step_d_eligible"] = False
    result["comparisons"][condition] = comparison

write_json(ROOT / "outputs/gate1/comparison.json", result)
with open(ROOT / "outputs/gate1/paired_outcomes.csv", "w", newline="") as f:
    writer = csv.writer(f, lineterminator="\n")
    names = sorted(outcomes)
    writer.writerow(["test_seed"] + names)
    for i, test_seed in enumerate(expected_tests):
        writer.writerow([test_seed] + [int(outcomes[n][i]) for n in names])

print(json.dumps({"completed_training_runs": sum(r["training"]["status"]=="completed" for r in result["runs"].values()),
                  "evaluated_policy_runs": len(outcomes), "step_d_eligible_conditions": result["step_d_eligible_conditions"]}, indent=2))
