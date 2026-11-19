# B2 v1.1 第三轮工程验收报告

**READY FOR INDEPENDENT REVIEW · 2026-11-17 Asia/Shanghai**

基线提交 `a58278fb8d7e9cb6700d72867b485fa25543de60`，实现提交 `2f1a495e495d926a91a317948c80184eccfc464d`，分支 `codex/b2-protocol-20261116`。本轮的工作站实例为 **PREFLIGHT**，独立审查是 Discovery 授权的前提。 [冻结协议](../../research_spatial_action_round4_20261109/reports/B2_PROTOCOL_REVISION_20261116.md)

## 三项修复

| 工程验收问题 | 修复与结果 |
|---|---|
| Snapshot 独立验证 | Stage Gate 首次进入时，从源环境分别采集恢复载荷与原始参考。Schema 3 使用原时刻重算碰撞与相机变换，再恢复积分终点。检查 MuJoCo 状态、XML、控制器和夹爪、`To=2` 历史及全部传感器重新采样。Replay A/B 独立保留。未来两个 Split 各自的 30 个状态全部进入此检查，任一失败会使 Split `BLOCKED`。 |
| 正式产物覆盖 | CLI 和 Branch Runner 均先检查已有的 run、episodes、snapshot validation、summary、status、analysis 及报告文件。空文件和残留 JSON 临时文件同样触发拒绝。Run Manifest 使用独占创建防止同目录重复启动。已完成的 Harvest 状态清单和快照作为只读输入。回归测试验证了两个 Split 的六类目标文件冲突时，目录内文件内容及时间戳原样保留。 |
| 异常混入统计 | B2 执行层严格处理成功谓词异常、非有限值、异常步进及恢复状态不一致。每行写入前检查步数、policy call 数、结束原因、成功字段、种子调度、几何和指纹。出错时保留此前有效行和失败位置，并写入 `BLOCKED`。分析要求 `COMPLETE`、30 个快照的独立证据及 450 条唯一合法记录。Confirmation 授权也检查 Discovery 验证证据。 |

Schema 1 和 2 继续由旧版接口恢复。正式 B2 要求 schema 3 的源参考。相对偏航采用最短环绕角差，以 `1e-6 rad` 作为独立角度容差。冻结协议、配置及 B0/B1 历史产物的 Git diff 为空。

## 工作站验证和测试

| 验证 | 结果 |
|---|---|
| 全量 `python -m compileall -q src tests` 和 `python -m pytest -q` | **271 passed**。现有 B0/B1、B2 授权、种子隔离和统计测试通过。新增 61 个用例，保留原有测试断言。SciPy 对既有合成常量输入发出 1 条警告。 |
| Live Geometry Audit | **PASS**。核对 4 条碰撞孔壁、销碰撞体、本地坐标系、符号、倾斜和现场步进有限值。 |
| 独立 Snapshot PREFLIGHT | **PASS**。RTX 3090、官方 Square-MH EMA checkpoint，seed `299999` 第 124 步触发 Stage Gate。原始与恢复状态 SHA256 一致，数值、长度和角度误差均为 0。 |
| To=2 历史、新观测和 Replay | **PASS**。历史逐键误差 0，新观测最大逐键 MAE 为 `9.89285e-5`，低于 `1e-3`。Replay A/B 状态、观测与几何误差为 0。控制器、夹爪和 MuJoCo 动力学输入检查通过。 |
| Source Archive Audit | **PASS**。干净解压，72 个文件逐字节核对，5 个 PREFLIGHT JSON 的证据哈希通过。抽取源码编译通过，pytest **270 passed、1 skipped**。跳过项需要归档外的 vendored Diffusion Policy 源树。 |

旧的 `912730e8…` 和 `e8a27a6a…` 来自同一种哈希方法。旧恢复过程中的 `mj_forward()` 改变四个四元数分量，最大差 `2.22e-16`。原采样时刻的几何与新的视图差异独立查明，并在本轮重测。 [Snapshot 详细报告](B2_SNAPSHOT_INDEPENDENT_VALIDATION_REPORT.md) · [工作站执行日志](WORKSTATION_EXECUTION_LOG.md)

## 源码归档和 GitHub CI

`gate_b_v2_source.tar.xz` 的 SHA256 为 `909086eedbdc9f71ca0e6bf232ae00d8011d8c0f1dff882eb0b41d566e9f1f0e`。README 和 GitHub Actions 固定同一校验值。CI 另外比对解包后的源码、测试、配置、脚本、工具和 PREFLIGHT JSON 与检出版本。 [源码归档](../../gate_b_v2_source.tar.xz)

GitHub Actions 在源码归档和验收证据提交 `86e7587ad578fb91cc3f3e3720b429398aa9571f` 上通过。Push 和 PR 两次运行的 `current-harness-tests` 与 `source-archive-audit` 均为 **success**。 [Push 运行 44037055112](https://github.com/iC0ol/EAI/actions/runs/44037055112) · [PR 运行 44037064333](https://github.com/iC0ol/EAI/actions/runs/44037064333)

## 修改文件

| 路径组 | 文件 |
|---|---|
| `gate_b_v2/src/gate_b_v2/` | `snapshot.py`、`env.py`、`harvest.py`、`runner.py`、`cli.py`、`b2_protocol.py`、`analysis.py`、`authorization.py` |
| `gate_b_v2/tests/` | `b2_test_data.py`、`test_b2_snapshot.py`、`test_b2_harvest.py`、`test_b2_branch.py`、`test_b2_protocol.py`、`test_b2_analysis.py`、`test_b2_authorization.py`、`test_env.py` |
| `gate_b_v2/reports/` | 本报告、`B2_SNAPSHOT_INDEPENDENT_VALIDATION_REPORT.md`、`WORKSTATION_EXECUTION_LOG.md`、`preflight_third_revision/` 中的公开 JSON 与证据清单 |
| 源码发布 | `gate_b_v2/README.md`、`.github/workflows/gate-b-v2-source-audit.yml`、`gate_b_v2_source.tar.xz` |

## 技术余项与授权

- 当前预检无技术 BLOCKER。XML 重载留下可复现的亚容差图像误差，原因和逐键实测已记录。 [RGB 隔离诊断](preflight_third_revision/b2_preflight_restore_diagnostics.json)
- Discovery 和 Confirmation 均未授权。实际工作站验收范围为几何审计与 seed 299999 的工程预检。正式 30 状态的覆盖率及 Branch 数据完整性等待独立审查和对应的研究者授权。
- 交付建议 **READY FOR INDEPENDENT REVIEW**。
