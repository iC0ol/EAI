"""Evidence/inference boundary checks using synthetic rows only."""

import hashlib
import json

import pytest

import analyze
from audit import audit
import study


def fake_row(seed, arm, first=120):
    is_fixed = arm == "fixed15"
    initial = hashlib.sha256(str(seed).encode()).hexdigest()
    times = [t for t in range(500) if t % 15 == 0 or (not is_fixed and t % 15 == 6)]
    queries, events = [], []
    for t in times:
        count = 1 if t % 15 == 0 else 2
        queries.append(dict(t=t, phase="anchor" if count == 1 else "mid", candidate_count=count,
                            noise_seeds=[2000000 + (seed - 520000) * 4096 + 3*t + k for k in range(count)],
                            chunk_sha256=[initial] * count))
        if count == 2:
            events.append(dict(t=t, eligible=False, pre_success=first is None or first > t, mid_grasped=False,
                               anchor_grasped=False, all_commands_closed=False, actual_hole_lateral_start_m=0.0,
                               old_action_indices=list(range(6, 15)), new_action_indices=list(range(9)),
                               candidate_axial_rms_m=[0.0, 0.0], planned_down_m=0.0, actual_down_m=0.0,
                               admissible=False, stall=False, chosen_candidate=0, decision="fresh",
                               issued_hole_lateral_max_error_m=0.0, issued_orientation_max_error_rad=0.0,
                               issued_gripper_max_abs_error=0.0,
                               issued_hole_axial_minus_old_m=[0.0]*9, issued_hole_axial_minus_new_m=[0.0]*9))
    return dict(seed=seed, arm=arm, initial_state_hash=initial, first_chunk_sha256=initial, steps=500,
                initial_gripper_command=[0.0], prefix6_gripper_command=[1.0, -1.0],
                prefix6_state_sha256=initial, prefix6_observation_sha256=initial,
                success=first is not None, first_success_step=first, wall_seconds=2.0, inference_seconds=1.0,
                task_success_bits="0"*500 if first is None else "0"*(first-1) + "1"*(501-first),
                query_schedule=queries, policy_queries=len(queries), policy_samples=sum(q["candidate_count"] for q in queries),
                events=events)


def test_seed_order_and_hash_integrity(tmp_path):
    order = study.episode_order("overnight")
    assert len(set(order)) == len(order) == 160
    assert set(order[:5]) == {(520000, a) for a in study.ARMS}
    assert len(set(order[i][1] for i in (0, 5, 10, 15, 20))) == 5
    assert set(study.SEEDS["engineering"]).isdisjoint(study.SEEDS["overnight"])
    seed, arm = order[0]
    row = fake_row(seed, arm)
    path = tmp_path / "records" / f"{seed}_{arm}.json"
    study.save(path, dict(record=row, record_sha256=study.digest(row), code_fingerprint="frozen"))
    assert list(study.records(tmp_path, "overnight", "frozen")) == [(seed, arm)]
    data = json.loads(path.read_text())
    data["record"]["first_success_step"] = 1
    study.save(path, data)
    with pytest.raises(study.IntegrityError, match="hash"):
        study.records(tmp_path, "overnight", "frozen")


def test_validation_catches_timestamp_and_initial_state_errors():
    row = fake_row(520001, "adaptive")
    study.check_record(row)
    row["query_schedule"][1]["t"] += 1
    with pytest.raises(study.IntegrityError, match="query times"):
        study.check_record(row)
    other = fake_row(520001, "refresh")
    other["first_chunk_sha256"] = "0" * 64
    with pytest.raises(study.IntegrityError, match="differs by arm"):
        study.validate_pairs({(520001, "adaptive"): row, (520001, "refresh"): other})


def test_independent_predicate_audit(tmp_path):
    for arm in study.ARMS:
        row = fake_row(520096, arm, 212)
        study.save(tmp_path / "records" / f"520096_{arm}.json", {"record": row})
    result = audit(tmp_path, (520096,))
    assert result["official_predicates"] == 2500
    assert result["generated_chunks"] == 434
    path = tmp_path / "records" / "520096_adaptive.json"
    obj = study.read_json(path)
    obj["record"]["task_success_bits"] = "0"*500
    study.save(path, obj)
    with pytest.raises(ValueError, match="raw versus reported success"):
        audit(tmp_path, (520096,))


def test_paired_censoring_and_decision():
    # Keep this statistical test independent of the MidDecision implementation.
    rows = {}
    for seed in study.SEEDS["overnight"]:
        for arm in study.ARMS:
            first = 110 if arm == "adaptive" else 130
            if seed == 520000:
                first = None
            rows[seed, arm] = dict(arm=arm, first_success_step=first, success=first is not None, events=[],
                                  policy_queries=34 if arm == "fixed15" else 67,
                                  policy_samples=34 if arm == "fixed15" else 100,
                                  inference_seconds=1.0, wall_seconds=2.0)
    result = analyze.summarize(rows)
    assert result["paired_contrasts"]["refresh"]["mean_step_delta"] == -20 * 31 / 32
    assert result["arms"]["adaptive"]["mean_capped_steps"] == (500 + 31 * 110) / 32
    assert result["interpretation"]["enough_exposure"] is False
    assert result["interpretation"]["meets_speed_and_final_success_criteria"] is True
    assert "机会不足" in analyze.render(result)
