# B2 v1.1 Snapshot 独立验证报告

**PASS · 2026-11-17 Asia/Shanghai · PREFLIGHT**

在原工作站使用 NVIDIA GeForce RTX 3090、`cuda:0`、PyTorch `1.12.1+cu116` / CUDA `11.6`、Python `3.9.13`、robomimic `0.2.0`、robosuite `1.2.0` 和 mujoco_py `2.0.2.13`。官方 Square-MH EMA checkpoint、影像数据集和 Diffusion Policy 源树指纹均通过 B1 Full 资产锁，渲染使用该工作站现有的 MuJoCo OSMesa 路径。 [环境指纹](preflight_third_revision/b2_preflight_environment.json)

实现提交 `2f1a495e495d926a91a317948c80184eccfc464d`。预检命令为 `python -m gate_b_v2.cli b2-preflight --run-dir runs/b2_preflight_third_revision --seed 299999`，退出码 0。固定 `h_source=8` 的源轨迹在第 **124** 个控制步首次进入 Stage Gate。采集使用 schema 3，`fallback_used=false`，`scientific_data=false`。 [PREFLIGHT 摘要](preflight_third_revision/b2_preflight_summary.json) · [证据文件与校验值](preflight_third_revision/PREFLIGHT_EVIDENCE_MANIFEST.json)

## Source Capture 与 Restore

首次进入 Stage Gate 时，从活体源环境分别读取恢复载荷和验证参考。验证参考包含 MuJoCo 数组、模型 XML 指纹、完整 `To=2` 策略输入、当前步原始 RGB 和低维输入、当场强制采样的观测、几何与控制器状态摘要。第二次读取在当步完成，期间没有环境步进。验证通过快照 SHA256、采集步、清单指纹与每键观测哈希绑定这批证据。 [逐状态验证 JSON](preflight_third_revision/b2_preflight_snapshot_validation.json)

| 检查项 | 实测 |
|---|---|
| 原始状态 SHA256 | `c9e856dd81ce235c818215601d7eb1e35dbc2292de24d554c1346bb67adc8e5f` |
| 恢复状态 SHA256 | `c9e856dd81ce235c818215601d7eb1e35dbc2292de24d554c1346bb67adc8e5f` |
| 原始与恢复状态的最大绝对误差 | **0**，上限 `1e-7` |
| 原始与快照载荷状态的最大绝对误差 | **0** |
| 状态数组表示 | 两侧均为 `<f8`、shape `[45]`、stride `[8]` |
| 原始与恢复 XML SHA256 | 两侧均为 `68b478b7e9bb3b6bd2bcba4c9b75078859b4c959f92a2ddd1cc8aad2ab636ac4` |
| 快照文件 SHA256 | `f918716d31e67aaf10ed626ec821653e7db1a51bac7e62d0f54a3fc57e3cc66e` |

状态哈希输入为固定小端 `float64`、C 顺序的数组字节及 dtype 和 shape，统一正负零的表示。数组数值比较保留原精度。下表中每列的 shape 和 dtype 在采集侧与恢复侧相同。新观测由恢复后的 robosuite 强制更新传感器并重新渲染两路相机。两帧原始观测历史的逐键哈希也全部匹配。 [逐键 shape、dtype、SHA256 和误差](preflight_third_revision/b2_preflight_snapshot_validation.json)

| Observation Key | 策略历史 shape / dtype | 历史 MAE / Max | 新观测 shape / dtype | 新观测 MAE | 新观测 Max |
|---|---|---:|---|---:|---:|
| `agentview_image` | `[2,3,84,84]` / `float32` | 0 / 0 | `[3,84,84]` / `float32` | `1.8525928e-7` | `3.9215684e-3` |
| `robot0_eye_in_hand_image` | `[2,3,84,84]` / `float32` | 0 / 0 | `[3,84,84]` / `float32` | `9.8928481e-5` | `3.9215684e-2` |
| `robot0_eef_pos` | `[2,3]` / `float32` | 0 / 0 | `[3]` / `float64` | `9.2518585e-18` | `2.7755576e-17` |
| `robot0_eef_quat` | `[2,4]` / `float32` | 0 / 0 | `[4]` / `float64` | `2.9488439e-8` | `1.0877850e-7` |
| `robot0_gripper_qpos` | `[2,2]` / `float32` | 0 / 0 | `[2]` / `float64` | 0 | 0 |

五个键的 MAE 均符合 `1e-3`。用原始控制步返回的观测直接比较恢复后的新观测，也得到同一组误差。几何与材质 RGBA 和相机视场角在重载前后一致。保留原生 MuJoCo 模型、用相同的采样时刻和关节状态重算时，两路 RGB 都逐值一致。经过 XML 重载，原生相机局部位置最多变动 `2.779e-6 m`，相机四元数、几何旋转与光源方向也有舍入差异。重载后两个相机分别有 1 和 247 个 RGB 通道值变化，误差按相同 `[0,1]` 格式测量。 [渲染对照](preflight_third_revision/b2_preflight_restore_diagnostics.json)

| 几何组 | 最大绝对误差 | 容差 |
|---|---:|---:|
| Clearance 与四方向余量 | 0 m | `1e-6 m` |
| `dx`、`dy`、`d_xy` | 0 m | `1e-6 m` |
| `z_gap`、孔底、销顶 | 0 m | `1e-6 m` |
| 孔和销半尺寸、厚度、外接半径 | 0 m | `1e-6 m` |
| Relative yaw，按最短环绕角差计算 | 0 rad | `1e-6 rad` |

碰撞几何指纹匹配。Live Geometry Audit 通过四条孔壁碰撞盒（46–49）、排除把手（50）、定位 peg（13）、局部坐标系与符号检查、倾斜区分和真实步进有限值检查。 [现场几何审计](preflight_third_revision/b2_geometry_audit.json)

控制器 51 个字段和夹爪 15 个字段的摘要全部匹配。审计列出控制器的模拟器引用以及夹爪的模型元数据和引用，没有遗漏未分类的可变字段。MuJoCo 当前模型的控制量、求解器 warm start、关节与笛卡尔施力数据恢复误差均为 0。 [控制器、夹爪及动力学输入证据](preflight_third_revision/b2_preflight_snapshot_validation.json)

## Deterministic Replay A/B

从捕获的源策略输入用固定种子 `424242` 生成 Probe Action。两次分别恢复快照和 RNG，再执行同一条动作。两次回放的规范化状态 SHA256 均为 `068c086f14464c98a52b28788a123be07ae0e0466635caf18ba56e14ab7138db`。状态最大绝对误差、五个策略观测键的 MAE、几何长度误差及偏航角误差均为 0。 [Replay A/B 明细](preflight_third_revision/b2_preflight_snapshot_validation.json)

## 上一轮哈希差异的根因

以保留的 schema 2 快照及同一种子现场复现。两个旧哈希使用同一个 `sha256_array`，数组 dtype、shape 和布局一致。载入快照后 `set_state_from_flattened` 精确复现 `912730e8…`。紧接着运行 `mj_forward()` 得到 `e8a27a6a…`，并在后续强制观测中保持。扁平数组中 20–23 四个分量因自由关节四元数归一化而改变。最大绝对误差为 `2.220446049250313e-16`，在 `1e-7` 内。 [旧版哈希与分步复现](preflight_third_revision/b2_preflight_restore_diagnostics.json)

Euler 子步先计算碰撞和相机变换，随后积分 `qpos`。上一轮 restore 在积分终点执行 `forward()`，使几何和观测移到另一采样时刻。源环境上直接做同一操作也复现了差异，`z_gap` 变化约 `1.557e-4 m`，`agentview_image` 的 MAE 约 `2.443e-3`。Schema 3 保留最后一个物理子步计算变换时的姿态，用它重算碰撞和相机变换，然后恢复积分终点数组。当前实现的状态数组逐值相同，几何与独立重渲染均通过各自的冻结容差。 [时序复现数据](preflight_third_revision/b2_preflight_restore_diagnostics.json)

**最终结果 PASS。** 验收覆盖保留种子 299999 的一个 Stage Gate 状态。未来 Discovery 与 Confirmation 各自的 30 个正式状态仍需逐一通过同样的验证。
