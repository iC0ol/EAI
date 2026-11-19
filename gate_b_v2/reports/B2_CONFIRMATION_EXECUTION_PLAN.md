# B2 v1.1 Confirmation 独立执行计划

**2026-11-19 · Confirmation COMPLETED。** 工作站通过独立审查与正式授权后完成了 Harvest、跨 Split 隔离核验和 450 条 Branch。以下为本次执行所使用的计划。 [Confirmation 收尾](b2_confirmation_20261118/B2_CONFIRMATION_CLOSEOUT.md) · [授权记录](B2_CONFIRMATION_AUTHORIZATION.md) · [冻结协议](../../research_spatial_action_round4_20261109/reports/B2_PROTOCOL_REVISION_20261116.md)

## 1. 授权前的工作站检查

在已验收的 RTX 3090 工作站使用现有 Python 3.9.13 隔离环境。核对 `cuda:0`、PyTorch `1.12.1+cu116`、CUDA 11.6、robomimic 0.2.0、robosuite 1.2.0 和 mujoco_py 2.0.2.13。冻结运行配置为 `H=16`、`To=2`、15 个未来动作、500 总步上限。以下命令读取 CLI 帮助并核验原机 Discovery 文件，使用 2026-11-18 实测的工作站路径。

```bash
cd "$(git rev-parse --show-toplevel)/gate_b_v2"
source scripts/gateb_env.sh
export GATEB_DISCOVERY_RUN="$PWD/runs/b2_discovery_20261117T153523"
export GATEB_PREFLIGHT_DIR="$PWD/runs/b2_preflight_third_revision"

git branch --show-current
git rev-parse HEAD
git status --short --branch --untracked-files=no
nvidia-smi
df -h "$PWD"
python -m gate_b_v2.cli b2-harvest --help
python -m gate_b_v2.cli b2 --help
python -m gate_b_v2.cli analyze --help
(cd "$GATEB_DISCOVERY_RUN" && sha256sum --check --quiet B2_DISCOVERY_SHA256SUMS.txt)
```

`GATEB_DISCOVERY_RUN` 指向工作站的原始 Discovery 运行目录。RTX 3090 工作站已用该目录中的 `B2_DISCOVERY_SHA256SUMS.txt` 实测，116 项全部通过。GitHub 公开发布目录 `reports/b2_discovery_20261117/` 使用自己的 `SHA256SUMS`，在发布目录内执行 `sha256sum --check SHA256SUMS` 校验公开文件。 [公开校验清单](b2_discovery_20261117/SHA256SUMS)

下列只读检查重新计算官方 Checkpoint、Dataset 和 Diffusion Policy 源树的 SHA256，并通过 `validate_preflight_gate()` 对照 B1 Full Runtime Manifest、冻结配置、当前 B2 源树及 PREFLIGHT。PREFLIGHT 须为 `PASS`，保留 seed `299999` 须真实触发 Stage Gate，几何和独立恢复验证通过。实际 Harvest 和 Branch 各自构建活体 Runtime Manifest 并重复检查锁定值。 [环境及配置锁](../src/gate_b_v2/locks.py) · [PREFLIGHT 门禁](../src/gate_b_v2/authorization.py)

```bash
python - <<'PY'
import json
import os
from pathlib import Path

from gate_b_v2.authorization import validate_preflight_gate
from gate_b_v2.b2_protocol import seed_blocks, seeds_for_block, selection_seed
from gate_b_v2.core import environment_fingerprint, sha256_file
from gate_b_v2.locks import load_fixed_project_config

root = Path.cwd()
preflight = Path(os.environ["GATEB_PREFLIGHT_DIR"])
discovery = Path(os.environ["GATEB_DISCOVERY_RUN"])
config = load_fixed_project_config(root)
paths = config["paths"]
recorded = json.loads((preflight / "environment_manifest.json").read_text())
live = environment_fingerprint(root / paths["dp_root"], root / paths["checkpoint"],
                               root / paths["dataset"], config["evaluation"]["device"])
for field in ("python", "torch", "torch_cuda", "cuda_available", "gpu_name",
              "robomimic", "robosuite", "mujoco_py"):
    if live.get(field) is None or live[field] != recorded[field]:
        raise SystemExit(f"BLOCKED — runtime differs for {field}")

gate = validate_preflight_gate(preflight, {**recorded, **live}, config=config, project_root=root)
pools = {split: set().union(*(seeds_for_block(b) for b in seed_blocks(config, split)))
         for split in ("discovery", "confirmation")}
if (pools["confirmation"] & pools["discovery"]
        or gate["summary"]["seed"] in pools["confirmation"]
        or seed_blocks(config, "confirmation") != ((310000, 100), (310100, 100))
        or selection_seed(config, "confirmation") != 20261117):
    raise SystemExit("BLOCKED — Confirmation seed lock differs")
print({key: gate["environment_fingerprint"][key]
       for key in ("checkpoint_sha256", "dataset_sha256", "dp_source_tree_sha256",
                   "config_fingerprint", "b1_full_manifest_sha256")})
print("Source tree SHA256", gate["source_tree_sha256"])
print("Implementation commit", gate["implementation_commit"])
print("PREFLIGHT Summary SHA256", gate["summary_sha256"])
print("Original Discovery analysis SHA256", sha256_file(discovery / "b2_discovery_analysis.json"))
PY
```

本轮复核时，资产与运行时锁命中，B2 源树 SHA256 为 `e52aeb4a25a4f94e4684f622a0b806164caf20d339c05e8de114b3b261175378`，对应 PREFLIGHT 实现提交 `2f1a495e495d926a91a317948c80184eccfc464d`。在官方门禁上进行只读验证时，PREFLIGHT 通过，缺少 Confirmation 正式授权被拒绝。确认种子池和对应 CLI 入口均存在，271 项单元测试通过。 [工作站执行记录](WORKSTATION_EXECUTION_LOG.md)

## 2. 获得正式授权后的运行目录和门禁

独立审查和明确批准完成后，选取新的 Confirmation 目录，用原机证据建立同目录 PREFLIGHT。保留文件相对路径，让审批记录引用实际运行副本的哈希。以下命令使用本次复核过的原机证据文件名。

```bash
set -euo pipefail
export GATEB_CONFIRMATION_RUN="$PWD/runs/b2_confirmation_$(TZ=Asia/Shanghai date +%Y%m%dT%H%M%S)"
mkdir -- "$GATEB_CONFIRMATION_RUN"
for file in b2_preflight_summary.json b2_geometry_audit.json b2_preflight_snapshot_validation.json; do
  cp -- "$GATEB_PREFLIGHT_DIR/$file" "$GATEB_CONFIRMATION_RUN/$file"
  cmp -- "$GATEB_PREFLIGHT_DIR/$file" "$GATEB_CONFIRMATION_RUN/$file"
done
sha256sum "$GATEB_CONFIRMATION_RUN/b2_preflight_summary.json" \
  "$GATEB_DISCOVERY_RUN/b2_discovery_analysis.json"
```

研究者按模板签发新目录下的 `B2_CONFIRMATION_AUTHORIZATION.json`。其中 `implementation_commit` 取获批的 PREFLIGHT 实现提交，`discovery_run_dir` 指向上述原机 Discovery 目录，`discovery_analysis_sha256` 取该目录内的实际分析文件。GitHub 发布版分析绑定公开版运行清单，因而具有自己的 SHA256。 [Discovery 发布清单](b2_discovery_20261117/PUBLICATION_MANIFEST.json)

`validate_formal_authorization()` 在 Harvest 和 Branch 均分派到 `validate_confirmation_authorization()`。它依次检查当前目录的 PREFLIGHT、正式授权字段和哈希、Discovery 的运行清单和完整性，并要求 Discovery 快照验证全部通过、450 条有效 Branch、非空的 `B2_REPORT.md` 以及可继续的 Discovery 决策。任何门禁失败均为 **BLOCKED**。 [授权实现](../src/gate_b_v2/authorization.py)

签发文件后，可在启动模拟器前用同一门禁复核授权和 Discovery 证据。该命令使用第 1 节已核验的原机 Runtime Manifest。

```bash
python - <<'PY'
import json
import os
from pathlib import Path

from gate_b_v2.authorization import validate_formal_authorization

preflight = Path(os.environ["GATEB_PREFLIGHT_DIR"])
run = Path(os.environ["GATEB_CONFIRMATION_RUN"])
runtime = json.loads((preflight / "environment_manifest.json").read_text())
gate = validate_formal_authorization(run, "confirmation", runtime, project_root=Path.cwd())
print(gate["scope"], gate["discovery_decision"], gate["discovery_analysis_sha256"])
PY
```

## 3. Harvest 与候选选择 · 正式授权后

```bash
python -u -m gate_b_v2.cli b2-harvest --split confirmation --run-dir "$GATEB_CONFIRMATION_RUN"
```

实际入口 `_cmd_b2_harvest()` 和 `harvest_split()` 都检查正式授权。源轨迹用 `h=8`，在每个控制步检查冻结的几何 Stage Gate，首次进入即采集独立快照。源种子用于环境重置，源 policy 种子为 `900000 + source_seed`。完整遍历 `310000–310099`，候选不足 30 时才完整遍历 `310100–310199`。采样按种子升序组织候选，以 `20261117` 无放回选出 30 个。候选数仍不足 30 时状态为 **BLOCKED**。候选选择随同上述 Harvest 命令完成。 [Harvest 实现](../src/gate_b_v2/harvest.py) · [Seed 与选择实现](../src/gate_b_v2/b2_protocol.py)

Harvest 产生 `b2_confirmation_harvest_manifest.json`、`b2_confirmation_candidates.json`、`b2_confirmation_state_manifest.jsonl`、`b2_confirmation_harvest_summary.json` 和 `snapshots/confirmation/`。核对 `COMPLETE`、选入数 30、随机选样和跨 Split 交集，再启动 Branch。

## 4. 跨目录隔离核验 · Harvest 完成后

代码自动要求在各自种子池内采集，验证状态身份、快照指纹和源参考。Branch 的自动交集检查读取同目录的另一个 Split 的入选清单。采用本计划的两个独立目录时，以下只读核验负责检查两边的候选池与正式状态池。任何交集、选样或哈希不符均为 **BLOCKED**。 [Branch Runner](../src/gate_b_v2/runner.py)

```bash
python - <<'PY'
import json
import os
from pathlib import Path

from gate_b_v2.b2_protocol import seed_blocks, seeds_for_block, selection_metadata, validate_state_manifest
from gate_b_v2.core import load_jsonl
from gate_b_v2.locks import load_b1_full_manifest, load_fixed_project_config, validate_b2_run_manifest
from gate_b_v2.snapshot import verify_snapshot_sha256

root = Path.cwd()
config = load_fixed_project_config(root)
b1_full = load_b1_full_manifest(root / config["paths"]["b1_full_manifest"])
folders = {"discovery": Path(os.environ["GATEB_DISCOVERY_RUN"]).resolve(),
           "confirmation": Path(os.environ["GATEB_CONFIRMATION_RUN"]).resolve()}
if folders["discovery"] == folders["confirmation"]:
    raise SystemExit("BLOCKED — splits must use separate run directories")
inventories = {}
for split, folder in folders.items():
    prefix = f"b2_{split}_"
    manifest = json.loads((folder / f"{prefix}harvest_manifest.json").read_text())
    validate_b2_run_manifest(manifest, split, b1_full)
    data = json.loads((folder / f"{prefix}candidates.json").read_text())
    summary = json.loads((folder / f"{prefix}harvest_summary.json").read_text())
    states = load_jsonl(folder / f"{prefix}state_manifest.jsonl")
    candidates = data["candidates"]
    selection = selection_metadata(candidates, split, config)
    allowed = set().union(*(seeds_for_block(b) for b in seed_blocks(config, split)))
    validate_state_manifest(states, split, config)
    if (summary.get("status") != "COMPLETE" or summary.get("selected_states") != 30
            or data["selection"] != selection
            or states != [candidates[i] for i in selection["selected_candidate_indices"]]):
        raise SystemExit(f"BLOCKED — selection or Harvest status differs for {split}")
    for row in candidates:
        if row["source_seed"] not in allowed or row["split"] != split:
            raise SystemExit(f"BLOCKED — out-of-split candidate for {split}")
        snapshot = (folder / row["snapshot_file"]).resolve()
        if not snapshot.is_relative_to(folder / "snapshots" / split):
            raise SystemExit(f"BLOCKED — snapshot location differs for {split}")
        verify_snapshot_sha256(snapshot, row["snapshot_sha256"])
    inventories[split] = candidates + states

for field in ("source_seed", "state_id", "snapshot_sha256"):
    discovery_ids = {row[field] for row in inventories["discovery"]}
    confirmation_ids = {row[field] for row in inventories["confirmation"]}
    if discovery_ids & confirmation_ids:
        raise SystemExit(f"BLOCKED — cross-split collision for {field}")
print("Both candidate and selected-state inventories are disjoint")
PY
```

## 5. 独立 Snapshot Validation 与 Branch · 授权且 Harvest 核验通过后

```bash
python -u -m gate_b_v2.cli b2 --split confirmation --run-dir "$GATEB_CONFIRMATION_RUN"
```

`_cmd_b2()` 使用既有运行目录并进入 `run_b2(split="confirmation")`。Runner 检查正式授权、PREFLIGHT、已完成 Harvest、冻结运行时与输出冲突，创建 `b2_confirmation_run.json`。随后在第一条 Branch 前对全部 30 个 schema 3 快照检查 SHA256、采集源参考、恢复状态、观测、几何及确定性 Replay，并写出 `b2_confirmation_snapshot_validation.json`。任一失败写出 **BLOCKED** 状态；全部 `PASS` 才进入 Branch。

每个快照按随机化 Horizon 顺序运行 5 个首次提交 × 3 次重复，同一 `state_id` 与 repeat 的各 Horizon 使用共同的 policy-noise 种子调度。每次 Branch 前重验文件 SHA256，恢复物理状态和观测历史，重置策略。首次 Horizon 后使用 `h=15` 续跑，按冻结的终止条件和最终成功谓词记录结果。 [Snapshot 实现](../src/gate_b_v2/snapshot.py) · [Branch 实现](../src/gate_b_v2/runner.py)

## 6. 完整性、统计分析与最终报告 · Branch 完成后

完整性验证在写入每条 Branch 时及最后汇总时自动执行。以下只读命令使用分析入口所调用的 `_b2_inputs()` 再核对运行清单、30 个状态、逐状态快照证据、`COMPLETE` 和 450 条合法且唯一的记录。

```bash
python - <<'PY'
import os
from pathlib import Path

from gate_b_v2.analysis import _b2_inputs
from gate_b_v2.locks import load_fixed_project_config

root = Path.cwd()
run = Path(os.environ["GATEB_CONFIRMATION_RUN"])
records, states, validation, *_ = _b2_inputs(run, "confirmation", load_fixed_project_config(root), root)
print(f"{len(states)} states, {len(records)} validated branches, snapshot pass={validation['all_passed']}")
PY
python -m gate_b_v2.cli analyze --run-dir "$GATEB_CONFIRMATION_RUN"
```

分析入口使用冻结配置。它同时生成 `b2_confirmation_analysis.json`、`b2_confirmation_report.md` 和 `ANALYSIS.md`。核验所用输入为 `b2_confirmation_episodes.jsonl`、`b2_confirmation_state_manifest.jsonl`、`b2_confirmation_run.json`、`b2_confirmation_snapshot_validation.json` 和 `b2_confirmation_status.json`。运行结束另核对 `b2_confirmation_summary.json` 的记录数量和完整性字段。 [分析及报告实现](../src/gate_b_v2/analysis.py) · [CLI](../src/gate_b_v2/cli.py)

工作站在授权前以 CLI 帮助、单元测试和只读门禁检查核实路径。完成后对原始运行目录执行了上述完整性与冻结分析核验。 [正式产物](b2_confirmation_20261118/README.md)

## 7. 预注册的 Confirmation 判定

独立单位为物理状态。沿用 `Δ_s = 0.5 × (p_s(1) + p_s(2)) − p_s(15)`、`E = predicted Δ(c10) − predicted Δ(c90)`、5,000 次状态聚类 bootstrap 与 100,000 次置换。按冻结规则依次判定。

| 条件 | 结果 |
|---|---|
| E 点估计 ≥ 0.08 且 95% CI 下界 > 0 | `CONFIRMATION_SUPPORTS_B2_MECHANISM` |
| 95% CI 上界 < 0.08 | `CONFIRMATION_NO_PRACTICALLY_MEANINGFUL_EFFECT` |
| 其他情况 | `CONFIRMATION_INCONCLUSIVE` |

Discovery 的结论用于决定是否进入独立 Confirmation。Gate C 的授权状态为 **NOT AUTHORIZED**。 [冻结判定规则](../../research_spatial_action_round4_20261109/reports/B2_PROTOCOL_REVISION_20261116.md#73-discovery-and-confirmation-decision)

## 8. 资源估算

同机 Discovery 用时 9 小时 06 分 25 秒，其中 Harvest 约 1 小时 25 分，Branch 阶段约 7 小时 42 分。主种子块足够时，按 **9–12 小时**估算 Confirmation。触发扩展时，按额外 100 个源轨迹预估增加 **2–3.5 小时**。实际用时取决于达到 Stage Gate 的步数、快照验证和 GPU 负载。 [Discovery 时间记录](b2_discovery_20261117/B2_DISCOVERY_CLOSEOUT.md)

Discovery 原机目录约 30 MB，90 个快照合计约 26 MB，单个最大约 0.30 MiB。按最多 200 次源轨迹估算，快照约 60 MiB 的保守容量，加上清单、JSONL、诊断和报告，可按 **100–150 MiB** 预留每次独立运行的输出空间。官方 checkpoint、dataset 和源树沿用工作站上的锁定资产。
