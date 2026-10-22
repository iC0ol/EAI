"""One forward/backward without an optimizer update; deployment smoke only."""
import time

import numpy as np
import torch

from d_alignment.data import SequenceData
from d_alignment.io import ROOT, read_json, write_json
from d_alignment.policy import make_policy

cfg = read_json(ROOT / "configs/gate1.json")
torch.set_num_threads(cfg["torch_cpu_threads"])
ds = SequenceData()
samples = [ds[i] for i in range(cfg["batch_size"])]
batch = {k: torch.from_numpy(np.stack([s[k] for s in samples])).cuda() for k in ("obs", "action")}
policy = make_policy().cuda()
torch.cuda.synchronize()
start = time.monotonic()
loss = policy.compute_loss(batch)
loss.backward()
torch.cuda.synchronize()
elapsed = time.monotonic()-start
write_json(ROOT / "reports/gate1/gpu_smoke.json", {"optimizer_updates": 0, "forward_backward_seconds_including_cold_start": elapsed,
    "untrained_noise_mse": float(loss.detach()), "parameters": sum(p.numel() for p in policy.parameters()),
    "peak_allocated_bytes": torch.cuda.max_memory_allocated(), "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
    "gpu": torch.cuda.get_device_name(0), "torch": torch.__version__, "cuda": torch.version.cuda})
print(f"GPU forward/backward OK: {elapsed:.3f}s; no optimizer update performed")
