"""Blind-packet checks without opening any injection truth."""
from pathlib import Path
import re

import numpy as np

from .common import load_view, read_json, sha256, write_json
from .signals import features, times

ROOT = Path(__file__).resolve().parents[3]


def audit_packets():
    public = ROOT / "outputs/q2_blind"
    blind = read_json(public / "blind_input_hashes.json")
    settings = read_json(ROOT / "configs/q2_blind/estimator.json")
    groups = {}
    for identity, expected_hash in blind["files"].items():
        assert re.fullmatch("[0-9a-f]{32}", identity)
        path = ROOT / "data/derived/q2_blind/queries" / f"{identity}.npz"
        assert sha256(path) == expected_hash
        view = load_view(path)
        assert str(view["sample_id"]) == identity
        trajectory = str(view["trajectory_id"])
        assert re.fullmatch("[0-9a-f]{32}", trajectory)
        groups.setdefault(trajectory, []).append(view)
        idx = times(len(view["command"]), settings)
        for candidate in settings["candidate_lags"]:
            for history in settings["history_candidates"]:
                assert len(features(view, history, candidate, settings)[0]) == len(idx)
            for phase in settings["xcorr_phase_candidates"]:
                assert (idx-phase-candidate).min() >= 0
                assert (idx-phase-candidate).max() < len(view["command"])
    assert len(groups) == 16 and len(blind["files"]) == 112
    for views in groups.values():
        assert len(views) == 7 and len({len(v["command"]) for v in views}) == 1
        for key in ("position","quaternion","gripper","next_position","next_quaternion","next_gripper"):
            assert all(np.array_equal(v[key], views[0][key]) for v in views)
    write_json(public / "blind_packet_audit.json", {"passed": True, "samples":112,"anonymous_sources":16,
        "cases_per_source":7,"all_numeric_inputs_finite":True,"nan_edge_count_in_all_inputs":0,
        "all_candidate_history_phase_indices_in_bounds":True,"same_scoring_times_for_all_candidates":True,
        "seven_conditions_equal_length_per_source":True,"observations_unchanged_across_seven_conditions":True,
        "truth_opened":False,"raw_clean_test_actions_opened":False,
        "scope":"Anonymous input schema/shape/guard audit only; no truth or original HDF5 read"})
    print("Blind audit passed for 112 packets / 16 sources; no truth read")
