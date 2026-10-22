"""One fixed run; no online logging, rollout selection or parameter search."""
import argparse
import json
import math
import random
import subprocess
import time
from pathlib import Path

import numpy as np
import torch

from d_alignment.data import CONDITIONS, SequenceData
from d_alignment.io import ROOT, read_json, sha256, write_json
from d_alignment.policy import make_ema, make_policy


def windows_on_gpu(ds):
    # These are precisely the audited, nonpadded sequences returned by the loader.
    samples = [ds[i] for i in range(len(ds))]
    return {"obs": torch.from_numpy(np.stack([s["obs"][:2] for s in samples])).cuda(),
            "action": torch.from_numpy(np.stack([s["action"] for s in samples])).cuda()}


def train(condition, seed):
    cfg = read_json(ROOT / "configs/gate1.json")
    split = read_json(ROOT / "data/manifests/splits.json")
    assert cfg["n_latency_steps"] == 0
    assert sha256(ROOT / "configs/gate1.json") == split["config_sha256"]
    frozen = read_json(ROOT / "data/manifests/frozen_protocol.json")
    for name, expected in {**frozen["files"], **frozen["data_manifests"]}.items():
        assert sha256(ROOT / name) == expected, f"Frozen input changed: {name}"
    assert seed in cfg["train_seeds"]
    run_name = f"{condition}_seed{seed}"
    run_dir = ROOT / "outputs/gate1" / run_name
    assert not run_dir.exists(), f"Refuse to overwrite or retrain {run_name}"
    # The protocol is fixed before any optimization. A corrupted run requires the
    # 50-episode Clean seed-42 gate to pass; the driver makes that decision.
    if condition != "clean":
        gate = read_json(ROOT / "outputs/gate1/clean_gate.json")
        assert gate["pass"], gate
        assert gate["clean_seeds_evaluated"] == cfg["train_seeds"]
    existing = list((ROOT / "outputs/gate1").glob("*/run.json"))
    assert len(existing) < cfg["max_policy_trainings"]
    run_dir.mkdir(parents=True)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(cfg["torch_cpu_threads"])
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    started = time.monotonic()
    metadata = {"condition": condition, "seed": seed, "status": "started", "updates_completed": 0,
        "config_sha256": split["config_sha256"], "source_sha256": split["source_sha256"],
        "versions": read_json(ROOT / "configs/versions.json"),
        "git_commit_at_start": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "config": cfg}
    write_json(run_dir / "run.json", metadata)
    try:
        train_ds, val_ds = SequenceData(condition), SequenceData("clean", "validation")
        data, val = windows_on_gpu(train_ds), windows_on_gpu(val_ds)
        policy = make_policy().cuda()
        ema = make_ema(policy)
        optimizer = torch.optim.AdamW(policy.parameters(), **cfg["optimizer"])
        metadata.update(train_sequences=len(train_ds), validation_sequences=len(val_ds), parameters=sum(p.numel() for p in policy.parameters()))
        write_json(run_dir / "run.json", metadata)
        # Dedicated index generator keeps sampled training windows identical across
        # conditions within seed. Validation uses fixed noise and diffusion steps.
        index_rng = torch.Generator(device="cuda").manual_seed(seed + 901)
        val_rng = np.random.default_rng(501)
        val_indices = val_rng.integers(0, len(val_ds), size=(cfg["validation_batches"], cfg["batch_size"]))
        val_indices = torch.as_tensor(val_indices, device="cuda", dtype=torch.long)
        torch.cuda.synchronize()
        optimize_started = time.monotonic()
        accumulated, block_started = [], time.monotonic()
        with open(run_dir / "metrics.jsonl", "w", buffering=1) as log:
            for step in range(1, cfg["updates"] + 1):
                policy.train()
                idx = torch.randint(len(train_ds), (cfg["batch_size"],), device="cuda", generator=index_rng)
                batch = {k: v[idx] for k, v in data.items()}
                lr_factor = min(step / cfg["warmup_updates"], 1.) if step <= cfg["warmup_updates"] else .5 * (1 + math.cos(math.pi * (step - cfg["warmup_updates"])/(cfg["updates"] - cfg["warmup_updates"])))
                for group in optimizer.param_groups:
                    group["lr"] = cfg["optimizer"]["lr"] * lr_factor
                optimizer.zero_grad(set_to_none=True)
                loss = policy.compute_loss(batch)
                assert torch.isfinite(loss), f"Nonfinite loss at {step}"
                loss.backward()
                optimizer.step()
                ema.step(policy)
                accumulated.append(float(loss.detach()))
                if step % 100 == 0 or step == 1:
                    torch.cuda.synchronize()
                    record = {"update": step, "train_noise_mse": float(np.mean(accumulated)), "lr": optimizer.param_groups[0]["lr"], "wall_seconds": time.monotonic()-started, "optimization_seconds": time.monotonic()-optimize_started, "block_seconds": time.monotonic()-block_started}
                    accumulated.clear()
                    block_started = time.monotonic()
                    if step % cfg["validation_every"] == 0:
                        cpu_state, gpu_state = torch.get_rng_state(), torch.cuda.get_rng_state()
                        torch.manual_seed(779)
                        torch.cuda.manual_seed_all(779)
                        with torch.no_grad():
                            policy.eval()
                            vals = [float(policy.compute_loss({k: v[vi] for k, v in val.items()})) for vi in val_indices]
                            ema_vals = [float(ema.averaged_model.compute_loss({k: v[vi] for k, v in val.items()})) for vi in val_indices]
                        torch.set_rng_state(cpu_state)
                        torch.cuda.set_rng_state(gpu_state)
                        record["validation_clean_noise_mse"] = float(np.mean(vals))
                        record["ema_validation_clean_noise_mse"] = float(np.mean(ema_vals))
                    log.write(json.dumps(record) + "\n")
                    print(json.dumps(record), flush=True)
                    metadata["updates_completed"] = step
                    write_json(run_dir / "run.json", metadata)
        torch.cuda.synchronize()
        checkpoint = ROOT / "outputs/gate1/checkpoints" / f"{run_name}.pt"
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"policy": ema.averaged_model.state_dict(), "config": cfg, "run": run_name, "updates": cfg["updates"]}, checkpoint)
        metadata.update(status="completed", checkpoint=str(checkpoint), checkpoint_sha256=sha256(checkpoint),
            wall_seconds=time.monotonic()-started, gpu_allocated_wall_hours=(time.monotonic()-optimize_started)/3600,
            peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(), peak_gpu_reserved_bytes=torch.cuda.max_memory_reserved())
        write_json(run_dir / "run.json", metadata)
        return metadata
    except Exception as exc:
        metadata.update(status="failed", error=repr(exc), wall_seconds=time.monotonic()-started,
                        peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated())
        write_json(run_dir / "run.json", metadata)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=CONDITIONS, required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    train(args.condition, args.seed)
