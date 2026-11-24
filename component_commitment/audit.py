"""Reconstruct the two outcome measures and the executed budgets from saved evidence."""

import hashlib
import json
import math
from pathlib import Path
from statistics import mean

import numpy as np


def check(ok, message):
    if not ok:
        raise ValueError("Independent audit failed: " + message)


def audit(directory: Path, seeds, analysis=None):
    arms = ("fixed15", "refresh", "smooth", "always_split", "adaptive")
    observations = {}
    hashes = {}
    timed_queries = generated_chunks = confirmed_steps = material_seeds = released_seeds = 0
    files = sorted((directory / "records").glob("*.json"))
    for path in files:
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        row = wrapper["record"]
        seed, arm = row["seed"], row["arm"]
        check((seed, arm) not in observations and seed in seeds and arm in arms, "duplicate/unplanned row")
        bits = row["task_success_bits"]
        check(len(bits) == 500 and set(bits) <= {"0", "1"}, "raw task predicate trace")
        first = bits.find("1")
        first = first + 1 if first >= 0 else None
        final = bits[-1] == "1"
        check(first == row["first_success_step"] and final == row["success"], "raw versus reported success")
        observations[seed, arm] = (first, final, row["initial_state_hash"], row["first_chunk_sha256"])
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        schedule = row["query_schedule"]
        ordinary = list(range(0, 500, 15))
        midway = [] if arm == "fixed15" else list(range(6, 500, 15))
        check([s["t"] for s in schedule] == sorted(ordinary + midway), "physical query schedule")
        count = sum(len(s["chunk_sha256"]) for s in schedule)
        check(count == (34 if arm == "fixed15" else 100), "prediction sample count")
        generated_chunks += count
        timed_queries += len(schedule)
        confirmed_steps += len(bits)
        dose, released = False, False
        for event in row["events"]:
            if event["decision"] in ("split", "fresh"):
                check(event["issued_hole_lateral_max_error_m"] < 2e-6
                      and event["issued_orientation_max_error_rad"] < 2e-6, "fresh alignment lost")
            check(event["issued_gripper_max_abs_error"] < 2e-6, "fresh gripper target lost")
            if event["decision"] == "split":
                new = event["issued_hole_axial_minus_new_m"]
                check(max(abs(x) for x in event["issued_hole_axial_minus_old_m"]) < 2e-6,
                      "retained axis missed its reference")
                dose |= math.sqrt(mean(x * x for x in new)) >= 0.001
            released |= event["eligible"] and event["decision"] == "fresh"
        if arm == "adaptive":
            material_seeds += int(dose)
            released_seeds += int(released)
    check(len(observations) == len(seeds) * len(arms), "incomplete sample")
    states = set()
    for seed in seeds:
        cohort = [observations[seed, arm] for arm in arms]
        check(len({r[2:] for r in cohort}) == 1, "unpaired state or first prediction")
        states.add(cohort[0][2])
    check(len(states) == len(seeds), "physical initial state reused")
    successes = {arm: sum(observations[s, arm][1] for s in seeds) for arm in arms}
    steps = {arm: [observations[s, arm][0] or 500 for s in seeds] for arm in arms}
    delta = np.subtract(steps["adaptive"], steps["refresh"])
    if analysis is not None:
        index = np.random.RandomState(20261125).randint(len(seeds), size=(20000, len(seeds)))
        ci = np.percentile(np.mean(delta[index], axis=1), [2.5, 97.5])
        p = analysis["paired_contrasts"]["refresh"]
        check(np.allclose(ci, p["ci_steps"]) and math.isclose(float(np.mean(delta)), p["mean_step_delta"]),
              "reported primary result")
        for arm in arms:
            check(successes[arm] == analysis["arms"][arm]["final_success"]
                  and math.isclose(mean(steps[arm]), analysis["arms"][arm]["mean_capped_steps"]),
                  "arm outcome from raw trace")
        mechanism = analysis["arms"]["adaptive"]["mechanism"]
        check((material_seeds, released_seeds) == (mechanism["material_seeds"], mechanism["release_seeds"]),
              "operational exposure counts")
    return dict(passed=True, episodes=len(files), independent_initial_states=len(states),
                official_predicates=confirmed_steps, timed_queries=timed_queries, generated_chunks=generated_chunks,
                final_successes=successes, adaptive_minus_refresh_mean_steps=float(np.mean(delta)),
                adaptive_material_seeds=material_seeds, adaptive_release_seeds=released_seeds,
                record_files_sha256=hashes)
