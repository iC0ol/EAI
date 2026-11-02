"""CPU-only post-run verification of the already saved controlled experiment.

No simulator, GL, CUDA, torch, or model imports. This file was authored after
the terminal GPU run; it cannot create additional experimental observations.
"""
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
from PIL import Image, ImageDraw

P = Path(__file__).resolve().parents[1]
D = P.parent
REFERENCE = "688297023a217d9874c347fdd0a6821def4d0a57d6abc8899014c63860976c37"
FBO = ("offFBO", "offFBO_r", "shadowFBO")
RBO = ("offColor", "offColor_r", "offDepthStencil", "offDepthStencil_r")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def array_sha(value):
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def dump(name, value):
    (P / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def all_objects(record, context, ids, valid):
    if not record or record.get("state") != "MEASURED_IN_OWNER_CONTEXT":
        return False
    if record.get("owner_context") != context or record.get("ids") != ids:
        return False
    for category, names, flag in [("framebuffers", FBO, "is_framebuffer"),
                                  ("renderbuffers", RBO, "is_renderbuffer")]:
        for name in names:
            obj = record.get(category, {}).get(name, {})
            if obj.get("id") != ids[name] or obj.get(flag) is not valid:
                return False
    return True


def main():
    checks = []

    def check(name, value, evidence=None):
        checks.append(dict(name=name, passed=bool(value), evidence=evidence))

    def one(events, label, entry="CONTROLLED_RELEASE_A"):
        selected = [(i, e) for i, e in enumerate(events)
                    if e["event"] == label and e["entry"] == entry]
        check("unique:" + str(events[0]["worker"]) + ":" + entry + ":" + label,
              len(selected) == 1, [i for i, _ in selected])
        if len(selected) != 1:
            raise RuntimeError("missing/duplicate event: " + label)
        return selected[0]

    manifest = read(P / "run_manifest.json")
    completion = read(P / "completion.json")
    budget = read(P / "budget.json")
    counts = read(P / "counts.json")
    check("terminal_two_conditions", completion["state"] == "TERMINAL"
          and completion["reason"] == "BOTH_CONDITIONS_FINISHED")
    expected_counts = dict(workers=2, make_env=2, renders=4, readPixels=8,
                           ACT=0, env_steps=0, rollouts=0, optimizer_updates=0)
    check("exact_native_counts", counts == expected_counts, counts)
    check("GPU_time_cap", completion["gpu_allocation_seconds"] < 170
          and completion["gpu_allocation_seconds"] <= budget["gpu_seconds"],
          completion["gpu_allocation_seconds"])
    processes = completion["worker_processes"]
    check("sequential_fresh_exec", len(processes) == 2
          and all(x["exit_code"] == 0 for x in processes)
          and processes[0]["ended_epoch"] < processes[1]["started_epoch"]
          and processes[0]["identity"]["pid"] != processes[1]["identity"]["pid"])
    frozen = {name: sha(P / "scripts" / name) == digest
              for name, digest in manifest["scripts"].items()}
    sources = {name: sha(Path(name)) == digest
               for name, digest in manifest["sources"].items()}
    check("frozen_runtime_scripts_unchanged", all(frozen.values()), frozen)
    check("frozen_source_files_unchanged", all(sources.values()), sources)
    check("protocol_unchanged", sha(P / "PROTOCOL.md") == manifest["protocol_sha256"])
    check("CPU_mock_frozen_and_passed", sha(P / "cpu_mock.json") == manifest["cpu_mock_sha256"]
          and read(P / "cpu_mock.json")["passed"])

    reference = np.array(Image.open(manifest["reference"]["reference_path"]).convert("RGB"))
    check("reference_pixels", array_sha(reference) == REFERENCE)
    with np.load(D / "execution/inputs/sample_00.npz", allow_pickle=False) as sample:
        # MuJoCo's get_state().flatten() returns float64 after restoring f32.
        expected_state_sha = array_sha(sample["source_state_f32"].astype(np.float64))
        expected_T_sha = array_sha(sample["T_given"])

    frames = []
    releases = {}
    results = []
    for wid, mode in [(1, "baseline"), (2, "fix")]:
        directory = P / "results" / ("worker_%d_%s" % (wid, mode))
        result = read(directory / "result.json")
        results.append(result)
        fixture = read(directory / "fixture.json")
        events = lines(directory / "events.jsonl")
        A, B = fixture["A_context"], fixture["B_context"]
        ids_A, ids_B = fixture["A_initial_ids"], fixture["B_original_ids"]
        check(mode + ":fixture", fixture["renderer_count"] == fixture["context_count"] == 2
              and A != B and fixture["controlled_trigger_not_natural_GC"]
              and not fixture["A_sim_is_env_sim"] and fixture["B_sim_is_env_sim"])
        registered = [e for e in events if e["event"] == "context_registered"]
        created = [e for e in events if e["event"] == "renderer_constructed_and_fixture_held"]
        check(mode + ":exactly_two_original_contexts", len(registered) == len(created) == 2
              and {e["context"] for e in registered} == {A, B})
        check(mode + ":same_thread", len({e["thread_id"] for e in events}) == 1)
        check(mode + ":no_fatal", not result["fatal"] and not (directory / "fatal.json").exists())
        check(mode + ":completed_cleanup", result["state"] == "COMPLETE"
              and result["all_contexts_destroyed"] and result["fixture_strong_refs_remaining"] == 0
              and events[-1]["event"] == "worker_cleanup_completed")
        guard = read(directory / "guard_counts.json")
        for tag, values in guard.items():
            check(mode + ":exactly_once:" + tag,
                  all(values[k] == 1 for k in ["first_entries", "first_completed",
                                              "con_free_attempts", "con_free_returns",
                                              "context_destroy_successes"])
                  and values["skipped_RUNNING"] == 0
                  and values["invocations"] == 1 + values["skipped_DONE"], values)
        check(mode + ":only_DONE_duplicates", sum(e["event"] == "one_shot_skip_DONE" for e in events)
              == sum(v["skipped_DONE"] for v in guard.values())
              and not any(e["event"] == "one_shot_skip_RUNNING" for e in events))
        destroys = [e for e in events if e["event"] == "eglDestroyContext_exit"]
        check(mode + ":native_destroy_once_each", len(destroys) == 2
              and {e["actor_context"] for e in destroys} == {A, B}
              and all(e["returned"] for e in destroys))

        enter_i, enter = one(events, "controlled_A_release_enter")
        exit_i, exit_event = one(events, "controlled_A_release_exit")
        check(mode + ":same_controlled_trigger", enter_i < exit_i
              and enter["lock_locked"] and exit_event["lock_locked"]
              and enter["current_context"] == B and enter["owner_context"] == A
              and not exit_event["A_live"] and exit_event["B_live"])
        window = events[enter_i:exit_i + 1]
        check(mode + ":A_destroy_in_controlled_window", sum(e["event"] == "eglDestroyContext_exit"
              and e["actor_context"] == A and e["returned"] for e in window) == 1)
        prefix = "baseline" if mode == "baseline" else "owner_bound"
        before_i, before = one(events, prefix + "_before_con_free")
        after_i, after = one(events, prefix + "_after_con_free")
        check(mode + ":con_free_order", enter_i < before_i < after_i < exit_i)

        if mode == "baseline":
            check("baseline:wrong_owner_not_measured", all(
                e["owner_context"] == A and e["current_context"] == B
                and e["owner_objects"]["state"] == "NOT_MEASURED_WRONG_CONTEXT"
                for e in [before, after]))
            check("baseline:original_B_3FBO_4RBO_true_to_false",
                  all_objects(before["active_objects"], B, ids_B, True)
                  and all_objects(after["active_objects"], B, ids_B, False))
            check("baseline:no_restore_and_B_unbound", exit_event["current_context"] is None
                  and not any(e["event"] == "previous_restored" for e in window)
                  and not any(e["event"] == "eglMakeCurrent_enter" for e in window))
            releases[mode] = dict(con_before_event=before_i, con_after_event=after_i,
                                  damaged_namespace=B, FBOs=3, RBOs=4, current_after=None)
        else:
            restore_i, restore = one(events, "previous_restored")
            native_i, native = one(events, "restore_native_return")
            check("fix:owner_A_objects_really_freed", before["current_context"] == A
                  and after["current_context"] == A
                  and all_objects(before["owner_objects"], A, ids_A, True)
                  and all_objects(after["owner_objects"], A, ids_A, False))
            check("fix:real_live_previous_restored", after_i < native_i < restore_i < exit_i
                  and native["returned"] and native["previous_context"] == B
                  and native["current_context"] == restore["current_context"] == B
                  and exit_event["current_context"] == B
                  and all_objects(restore["active_objects"], B, ids_B, True)
                  and all_objects(exit_event["owner_objects"], B, ids_B, True))
            successful = [e["current_context"] for e in window
                          if e["event"] == "eglMakeCurrent_exit" and e["returned"]]
            check("fix:only_owner_unbind_previous_switches", successful == [A, None, B], successful)
            releases[mode] = dict(con_before_event=before_i, con_after_event=after_i,
                                  released_namespace=A, previous_restored_event=restore_i,
                                  native_restore_event=native_i, original_B_valid=True)
        # After controlled release until the saved after frame, no repair bind,
        # resource constructor, or new context may intervene in either condition.
        frame_after_i, _ = one(events, "frame_after", "after")
        check(mode + ":no_after_repair_or_rebuild", not any(e["event"] in [
            "eglMakeCurrent_enter", "renderer_constructor_enter", "EGL_constructor_enter"]
            for e in events[exit_i + 1:frame_after_i + 1]))

        readbacks = read(directory / "readback.json")
        check(mode + ":two_normal_four_native_reads", len(readbacks) == 2
              and sum(e["event"] == "mjr_readPixels_before" for e in events) == 4
              and sum(e["event"] == "mjr_readPixels_after" for e in events) == 4
              and sum(e["event"] == "mjr_render_before" for e in events) == 2)
        for entry in ["before", "after"]:
            row = next(x for x in readbacks if x["entry"] == entry)
            metrics = read(directory / (entry + "_metrics.json"))
            raw_path = P / row["raw"]["file"]
            raw = np.load(raw_path, allow_pickle=False)
            flip_in = np.load(directory / (entry + "_flip_input.npy"), allow_pickle=False)
            flip_out = np.load(directory / (entry + "_flip_output.npy"), allow_pickle=False)
            tensor = np.load(directory / (entry + "_tensor_rgb.npy"), allow_pickle=False)
            with np.load(directory / (entry + "_saved.npz"), allow_pickle=False) as z:
                saved = z["rgb_float"].copy()
            pixels = np.array(Image.open(directory / (entry + ".png")).convert("RGB"))
            boundaries = dict(raw_to_flip_input=np.array_equal(raw, flip_in),
                              flip_input_to_output=np.array_equal(np.flip(raw, 0), flip_out),
                              flip_output_to_tensor=np.array_equal(
                                  flip_out.transpose(2, 0, 1).astype(np.float32) / np.float32(255), tensor),
                              tensor_to_npz=np.array_equal(tensor, saved),
                              npz_to_png=np.array_equal(np.rint(saved.transpose(1, 2, 0) * 255)
                                                        .astype(np.uint8), pixels))
            check(mode + ":" + entry + ":five_boundaries", all(boundaries.values()), boundaries)
            check(mode + ":" + entry + ":array_hashes",
                  array_sha(raw) == row["raw"]["sha256"] and sha(raw_path) == row["raw"]["file_sha256"]
                  and array_sha(tensor) == metrics["tensor"]["sha256"]
                  and array_sha(pixels) == metrics["pixel_sha256"])
            check(mode + ":" + entry + ":state_T_preserved", metrics["state_sha256"] == expected_state_sha
                  and metrics["T_sha256"] == expected_T_sha)
            sentinel_after = next(e for e in events if e["event"] == "mjr_readPixels_after"
                                  and e["ordinal"] == row["ordinal"] + 1 and e["sentinel"])
            sentinel = np.load(P / sentinel_after["array"]["file"], allow_pickle=False)
            native_read_events = [e for e in events if e["entry"] == entry
                                  and e["event"] in ["mjr_readPixels_before", "mjr_readPixels_after"]]
            gl_ok = all(e["current_context"] == B and e["gl"] is not None
                        and e["gl"]["errors"]["codes"] == [0] for e in native_read_events)
            sentinel_equal = np.array_equal(raw, sentinel)
            healthy = gl_ok and sentinel_equal
            check(mode + ":" + entry + ":health_metadata_agrees",
                  healthy == metrics["readback_healthy"]
                  and sentinel_equal == row["sentinel"]["equal_preflip_raw"]
                  and row["sentinel"]["separate_buffer"] and row["sentinel"]["inside_original_lock"])
            is_healthy_frame = entry == "before" or mode == "fix"
            check(mode + ":" + entry + ":expected_health", healthy == is_healthy_frame)
            check(mode + ":" + entry + ":expected_reference", np.array_equal(pixels, reference) == is_healthy_frame)
            if mode == "fix":
                check("fix:" + entry + ":B_original_objects_at_readback", all(
                    all_objects(e["active_objects"], B, ids_B, True) for e in native_read_events))
            frames.append(dict(mode=mode, entry=entry, boundaries=boundaries,
                               pixel_sha256=array_sha(pixels), raw_sha256=array_sha(raw),
                               normal_sentinel_equal=bool(sentinel_equal), GL_read_errors_clear=gl_ok,
                               read_current_contexts=[e["current_context"] for e in native_read_events],
                               sentinel_165_fraction=float(np.mean(sentinel == 165)),
                               raw_165_fraction=float(np.mean(raw == 165))))

    check("same_state_T_XML_all_frames", all(len({r[entry][key] for r in results
          for entry in ["before", "after"]}) == 1
          for key in ["state_sha256", "T_sha256", "xml_sha256"]))
    originals = [read(P / "results" / ("worker_%d_%s" % (w, m)) / "original_destructor.json")
                 for w, m in [(1, "baseline"), (2, "fix")]]
    check("identical_upstream_destructor", originals[0]["source_sha256"] == originals[1]["source_sha256"]
          and originals[0]["upstream_file_sha256"] == originals[1]["upstream_file_sha256"])
    choice = read(P / "repair_choice.json")
    check("baseline_gate_recorded_before_fix", choice["supported"] and choice["B_objects_lost"]
          and choice["B_context_unbound"]
          and choice["events_sha256"] == sha(P / "results/worker_1_baseline/events.jsonl"))
    resources = lines(P / "resources.jsonl")
    peaks = {key: max(row[key] for row in resources) for key in
             ["rss", "vram", "device_vram_bytes", "new_disk_bytes"]}
    check("sampled_resource_limits", peaks["rss"] <= budget["rss_bytes"]
          and peaks["device_vram_bytes"] <= budget["vram_bytes"]
          and peaks["new_disk_bytes"] <= budget["new_disk_bytes"], peaks)

    # A montage of the actual saved PNGs; no pixel enhancement/interpolation.
    montage = Image.new("RGB", (552, 626), "#202428")
    draw = ImageDraw.Draw(montage)
    for row, mode in enumerate(["baseline", "fix"]):
        draw.text((12, 8 + row * 306), mode.upper() + " - controlled A release", fill="white")
        for col, entry in enumerate(["before", "after"]):
            x, y = 12 + col * 272, 48 + row * 306
            draw.text((x, y - 20), entry, fill="white")
            source = P / "results" / ("worker_%d_%s" % (row + 1, mode)) / (entry + ".png")
            montage.paste(Image.open(source).convert("RGB"), (x, y))
    montage.save(P / "montage.png")
    passed = all(c["passed"] for c in checks)
    output = dict(utc=datetime.now(timezone.utc).isoformat(),
                  verdict="LOCAL_CONTROLLED_PASS_PENDING_REVIEW" if passed else "PARTIAL_CHECK_FAILURE",
                  passed=passed, check_count=len(checks),
                  failed_checks=[c["name"] for c in checks if not c["passed"]],
                  boundary_comparisons=20, frames=frames, controlled_release=releases,
                  checks=checks, counts=counts, GPU_allocation_seconds=completion["gpu_allocation_seconds"],
                  sampled_resource_peaks=peaks, sampled_resources_are_not_continuous_peaks=True,
                  postprocess_source_sha256=sha(Path(__file__)),
                  protocol_sha256=manifest["protocol_sha256"],
                  scope="one fixed sample0, identical strong A/B fixture, one controlled release per condition",
                  not_established=["natural GC occurrence/frequency", "multi-view stability", "long-term stability",
                                   "thread safety", "old checkpoint 0/32 cause"],
                  old_0_of_32_cause="UNKNOWN", ACT="NOT_RUN", rollouts="NOT_RUN", optimizer_updates=0,
                  parent_review_required=True)
    dump("analysis.json", output)
    print(json.dumps({k: output[k] for k in ["verdict", "check_count", "failed_checks",
                                             "boundary_comparisons", "GPU_allocation_seconds"]}))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
