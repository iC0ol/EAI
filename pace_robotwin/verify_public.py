"""Check the published episode outcomes and paired estimates without the robot runtimes."""

import json
from collections import defaultdict
from math import isclose
from statistics import mean

from analyze_formal import paired_success
from design import LIMITS, ROOT, STAGES, TASKS, file_hash, read_json


def check(condition, message):
    if not condition:
        raise ValueError(message)


def verify():
    release = ROOT / "results"
    for entry in (release / "SHA256SUMS").read_text().splitlines():
        expected, filename = entry.split("  ", 1)
        check(file_hash(release / filename) == expected, f"Checksum mismatch: {filename}")
    audit = read_json(release / "AUDIT.json")
    analysis = read_json(release / "ANALYSIS.json")
    check(file_hash(release / "AUDIT.json") == analysis["audit_sha256"], "Analysis audit binding")
    check(file_hash(release / "MANIFEST.json") == audit["manifest_sha256"] == analysis["manifest_sha256"],
          "Scientific manifest binding")

    scenes = defaultdict(dict)
    identifiers = set()
    steps = queries = 0
    for line in (release / "episodes.jsonl").read_text().splitlines():
        row = json.loads(line)
        stage, task, index, method = (row[k] for k in ("stage", "task", "index", "method"))
        key = f"{stage}/{task}/scene_{index:03d}/{method}"
        check(key not in identifiers and audit["record_manifests"].get(key) == row["record_manifest_sha256"], key)
        check(type(row["success"]) is bool and 0 < row["steps"] <= LIMITS[task], key)
        check(row["success"] or row["steps"] == LIMITS[task], key)
        identifiers.add(key)
        scenes[stage, task, index][method] = row
        steps += row["steps"]
        queries += row["queries"]
    check(identifiers == set(audit["record_manifests"]), "Missing or extra episodes")
    check(len(identifiers) == audit["verified_records"] == 1600 and len(scenes) == audit["verified_pairs"] == 400,
          "Unexpected episode or scene total")
    check((steps, queries) == (audit["verified_control_steps"], audit["verified_single_candidate_queries"]),
          "Control step or policy query total")

    for task in TASKS:
        seeds = set()
        for stage in ("reproduction", "heldout"):
            methods = STAGES[stage][1]
            groups = {method: [] for method in methods}
            for i in range(100):
                group = scenes[stage, task, i]
                check(set(group) == set(methods), f"Incomplete scene {stage}/{task}/{i}")
                anchors = {(r["scene_seed"], r["initial_sha256"], r["first_raw_sha256"]) for r in group.values()}
                check(len(anchors) == 1, f"Scene pairing mismatch {stage}/{task}/{i}")
                seed, _, _ = anchors.pop()
                check(seed not in seeds, f"Reused scene seed {task}/{seed}")
                seeds.add(seed)
                for method in methods:
                    groups[method].append(group[method])
            for method, rows in groups.items():
                cell = analysis["cells"][f"{stage}/{task}/{method}"]
                successes = [r for r in rows if r["success"]]
                check((len(rows), len(successes)) == (cell["n"], cell["success"]), f"Success count {task}/{method}")
                for name, subset in (("all", rows), ("success_only", successes)):
                    if not subset:
                        check(cell[name] is None, f"Empty subset {task}/{method}/{name}")
                        continue
                    for cost in ("steps", "queries", "setup_s", "rollout_s", "attempt_s"):
                        check(isclose(mean(r[cost] for r in subset), cell[name][cost], abs_tol=1e-10),
                              f"Mean {cost} differs in {stage}/{task}/{method}/{name}")
            if stage == "heldout":
                effects = paired_success(groups["component"], groups["pace"])
                check(effects == analysis["paired"][task], f"Paired estimates differ for {task}")
                print(task, effects)
    print(f"Verified {len(identifiers)} episodes, {len(scenes)} paired scenes, {steps} control steps, {queries} queries.")


if __name__ == "__main__":
    verify()
