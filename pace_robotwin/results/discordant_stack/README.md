# 叠三块积木 · 26 个结果分歧场景的原始记录

从正式实验 `heldout/stack_blocks_three`（官方场景集 seed 1）的 100 个场景中，按原生成功标记选出分量更新和原版 PACE 结局不同的全部场景。每个场景保留两种方法各自的完整回合，共 **26 对、52 条记录**。场景序号是 `scene_NNN` 中的三位数，模拟器的 `scene_seed` 另列在索引中。[机器可读索引](https://raw.githubusercontent.com/iC0ol/EAI/pace-stack-discordant-seed1-v1/pace_robotwin/results/discordant_stack/index.json) · [下载完整 ZIP](https://github.com/iC0ol/EAI/releases/download/pace-stack-discordant-seed1-v1/pace-stack-discordant-seed1-v1.zip)

| 结果方向 | 场景数 | 场景序号 |
| --- | ---: | --- |
| [仅分量更新成功](component_only/) | 13 | 004、010、021、029、035、036、046、049、055、061、075、076、086 |
| [仅 PACE 成功](pace_only/) | 13 | 005、015、020、026、043、054、056、057、064、068、079、080、089 |

同一批独立场景另有 39 对共同成功、35 对共同失败。这个子集按最终结局选择，适合逐对比较轨迹。估算总体成功率时应使用全部 100 对。[完整实验报告](../../RESULTS.md) · [全组回合表](../episodes.jsonl) · [正式审计](../AUDIT.json)

## 给分析工具的入口

直接读取 `index.json` 的 `cases` 列表。每项含结果方向、场景序号、场景种子、指令、共同初态与首块哈希，以及 `methods.component` 和 `methods.pace` 的记录。用各方法的 `record_url` 可直接获取原始 JSON。索引内的文件路径既相对于本目录，也相对于 ZIP 解压后的根目录。Git 中可以浏览每条回合的三个 JSON 原件。ZIP 另包含同一场景的共享首帧和两条轨迹数组，原始文件的内容与工作站审计时一致。

| 原始文件 | 分析时可读取的内容 |
| --- | --- |
| 每个场景的 `initial.npz` | 两组共同使用的首帧与指令。三路 RGB 为 `cam_high`、`cam_left_wrist`、`cam_right_wrist`，形状为 3×240×320。另有本体指令 `state`、复位审计向量 `physics` 和语言 `prompt`。后续查询逐帧 RGB 未归档。 |
| 每种方法的 `record.json` | 成败、步数、查询数、初末成功判据几何和逐查询的 `query_log`。其中 `step` 是查询开始前已执行的控制步数，`h` 是选定的执行长度。分量更新的 `decision.arms.left/right` 保留几何门控、实际轴向修正及回退原因。 |
| 每种方法的 `chunks.npz` | 原始预测 `raw` 和建议动作 `proposed` 形状为 (Q, 50, 14)，逐步实际下发的 `issued` 为 (T, 14)，查询时的本体指令 `states` 为 (Q, 14)。Q 为该回合查询数，T 为实际执行步数。14 列按左臂 6 个关节、左夹爪、右臂 6 个关节、右夹爪排列。 |
| 每种方法的 `timing.json`、`sha256.json` | 前者保存整次尝试与含证据写盘的墙钟秒数，后者绑定本回合三个原始证据文件。其自身的 SHA-256 可用索引中的 `source_key` 在上一级正式审计的 `record_manifests` 中查到。 |

对齐两条轨迹时可从 `issued` 的控制步索引开始。两种方法在各自轨迹上重新查询，查询序号可以对应不同物理时刻。末次查询的实际执行长度还可能因成功或达到步数上限而缩短。

## 下载与核验

下载 ZIP 后，在其所在目录解压并核对 234 个原件的 SHA-256。压缩包本身的校验和也随源码公开。[ZIP 校验和](ARCHIVE.sha256) · [逐文件校验和](SHA256SUMS)

```bash
unzip -q pace-stack-discordant-seed1-v1.zip -d discordant_stack
(cd discordant_stack && sha256sum -c SHA256SUMS)
```

以下示例读取索引中第一对场景，打印两种方法的结局和实际下发动作的形状。可将 `cases[0]` 换成按 `group` 或 `scene_seed` 选中的场景。

```python
import json
from pathlib import Path
import numpy as np

root = Path("discordant_stack")
cases = json.loads((root / "index.json").read_text())["cases"]
case = cases[0]
for method, run in case["methods"].items():
    record = json.loads((root / run["record"]).read_text())
    with np.load(root / run["chunks"], allow_pickle=False) as trace:
        print(case["scene"], method, record["success"], trace["issued"].shape)
```
