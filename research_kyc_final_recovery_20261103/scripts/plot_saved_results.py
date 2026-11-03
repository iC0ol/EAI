"""Static figures from original JSON exports. Never imports the experiment code."""
import json
import os
from pathlib import Path

P = Path(__file__).resolve().parents[1]
os.environ["MPLCONFIGDIR"] = str(P / "cache" / "matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

def read(name):
    return json.loads((P / name).read_text())

plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 160})
parent = read("artifacts/parent_model_recomputation.json")
names = ["official_prior", "mean", "median"]
labels = ["Frozen prior", "Weighted mean", "Weighted median"]
colors = ["#0072B2", "#D55E00", "#009E73"]
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
x = np.arange(4)
for j, method in enumerate(names):
    for ax, key in zip(axes, ["xyz_normalized_MAE", "gripper_sign_accuracy"]):
        vals = [s["metrics"][method][key] for s in parent["per_state"]]
        ax.bar(x+(j-1)*.24, vals, .23, color=colors[j], label=labels[j])
for ax in axes:
    ax.set_xticks(x, ["s0 (demo0, t0)", "s1 (demo50, t0)", "s4 (demo0, t52)", "s5 (demo50, t48)"])
    ax.tick_params(axis="x", labelsize=9)
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=.2)
axes[0].set_title("Translation error: lower is better")
axes[0].set_ylabel("Normalized xyz MAE")
axes[1].set_title("Gripper sign accuracy: higher is better")
axes[1].set_ylim(0, 1.05)
fig.suptitle("Four training states, two demos: 0/4 states beat BOTH constants", fontsize=14)
fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=3, frameon=False)
fig.tight_layout(rect=(0, .07, 1, .95))
for ext in ["png", "pdf"]: fig.savefig(P / f"artifacts/action_metrics.{ext}")
plt.close(fig)

common = read("review_packets/model_originals/common.json")["constants"]
fig, axes = plt.subplots(4, 4, figsize=(13, 10), sharex=True, sharey="col")
for row, sid in enumerate([0, 1, 4, 5]):
    data = read(f"review_packets/model_originals/sample_{sid:02d}.json")
    pred = next(q["arrays"]["raw_chunk"] for q in data["predictions"] if q["record"]["id"] == f"s{sid:02d}_official_prior")
    series = [data["target_raw_chunk"], pred, common["per_position_mean_raw"], common["per_position_median_raw"]]
    for col, dim in enumerate([0, 1, 2, 6]):
        ax = axes[row, col]
        for arr, label, color, style in zip(series, ["Expert", "Frozen prior", "Weighted mean", "Weighted median"], ["#222222", *colors], ["-", "-", "--", ":"]):
            values = np.asarray(arr)[:, dim] * (1000 if dim < 3 else 1)
            ax.plot(np.arange(30), values, label=label, color=color, linestyle=style, linewidth=1.5)
        ax.grid(alpha=.18)
        if row == 0: ax.set_title(["dx (mm)", "dy (mm)", "dz (mm)", "Gripper command"][col])
        if col == 0: ax.set_ylabel(f"s{sid}\ncommand value")
        if row == 3: ax.set_xlabel("Predicted chunk position")
        ax.set_xticks([0, 10, 20, 29])
fig.suptitle("Saved action chunks vs expert: no environment steps were executed", fontsize=14)
fig.legend(*axes[0,0].get_legend_handles_labels(), loc="lower center", ncol=4, frameon=False)
fig.tight_layout(rect=(0, .045, 1, .965))
for ext in ["png", "pdf"]: fig.savefig(P / f"artifacts/action_chunks.{ext}")
plt.close(fig)
print("Two static figures (PNG/PDF), from saved JSON only.")
