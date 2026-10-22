"""Standalone figures; explicitly mark incomplete training loss traces."""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from d_alignment.io import ROOT, read_json

result = read_json(ROOT / "outputs/gate1/comparison.json")
dest = ROOT / "reports/gate1"
colors = {"clean": "#27749c", "mixed_small_lag": "#d58b32", "larger_lag": "#b34b58"}
labels = {"clean": "Clean", "mixed_small_lag": "Mixed small lag", "larger_lag": "Larger lag"}


def save_figure(figure, stem):
    figure.savefig(dest / f"{stem}.png", dpi=160)
    svg = dest / f"{stem}.svg"
    figure.savefig(svg)
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")


ordered_runs = sorted(result["runs"].items(), key=lambda item: (list(labels).index(item[1]["training"]["condition"]), item[1]["training"]["seed"]))
fig, axes = plt.subplots(1, 2, figsize=(10, 3.7), constrained_layout=True)
for name, run in ordered_runs:
    train = run["training"]
    path = ROOT / "outputs/gate1" / name / "metrics.jsonl"
    if not path.exists():
        continue
    metrics = [json.loads(line) for line in path.read_text().splitlines()]
    cond, seed = train["condition"], train["seed"]
    val = [m for m in metrics if "ema_validation_clean_noise_mse" in m]
    line = "-" if seed == 42 else "--"
    suffix = " (interrupted)" if train["status"] != "completed" else ""
    axes[0].plot([m["update"] for m in metrics], [m["train_noise_mse"] for m in metrics], color=colors[cond], ls=line, alpha=.85, label=f"{labels[cond]}, {seed}{suffix}")
    axes[1].plot([m["update"] for m in val], [m["ema_validation_clean_noise_mse"] for m in val], color=colors[cond], ls=line, alpha=.85)
for ax, title in zip(axes, ["Training labels: denoising loss", "Clean validation: EMA denoising loss"]):
    ax.set(xlabel="Optimizer updates", ylabel="Noise MSE", title=title, yscale="log")
    ax.grid(alpha=.2)
axes[0].legend(frameon=False, fontsize=8)
fig.suptitle("Loss is not closed-loop task success", fontsize=11)
save_figure(fig, "loss_curves")
plt.close(fig)

evaluated = [(name, run) for name, run in ordered_runs if "evaluation" in run]
if evaluated:
    fig, ax = plt.subplots(figsize=(max(5, len(evaluated)*1.1), 4), constrained_layout=True)
    xx = np.arange(len(evaluated))
    for i, (name, run) in enumerate(evaluated):
        ev, tr = run["evaluation"], run["training"]
        rate = 100*ev["success_rate"]
        lo, hi = np.array(run["wilson_success_95ci"])*100
        ax.errorbar(i, rate, yerr=[[rate-lo], [hi-rate]], color=colors[tr["condition"]], fmt="o", capsize=4, ms=8)
        ax.annotate(f'{ev["successes"]}/{ev["episodes"]}', (i, rate), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=9)
    ax.set_xticks(xx, [f'{labels[r["training"]["condition"]]}\nseed {r["training"]["seed"]}' for _, r in evaluated], fontsize=9)
    ax.set(ylabel="Closed-loop success (%)", ylim=(-3, 110), title="50 frozen initial conditions per policy; Wilson 95% CI")
    ax.grid(axis="y", alpha=.2)
    fig.supxlabel("Larger lag seed 43: interrupted; no policy evaluation", fontsize=9)
    save_figure(fig, "closed_loop_success")
    plt.close(fig)
