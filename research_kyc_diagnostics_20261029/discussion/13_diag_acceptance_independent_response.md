先读取执行原件与关键审计，随后查看两张 PNG，区分“实际看见”与执行者描述。

# KYC 有限排障独立验收（DeepSeek）

## 1. 实际读取与独立边界

已读：`FINAL_REPORT.md`、`stage0_report.md`、`stage0_gate.json`、`stage1_gate.json`、`completion.json`、`counts.json`、`stages/stage0.json`、`stages/stage1.json`、`code_manifest_stage1.json`、`scripts/stage1.py`、`diag_common.py`、`supervise.py`、`analyze_render.py`、`results/input_comparisons.json`、`render_audit.json`、`checkpoint_audit.json`、`normalization_audit.json`、`source_blob_audit.json`、`version_provenance_correction.json`、`schema_clarification.json`、`delivery_integrity.json`；查看了 `sample_00_entry_rgb.png`、`sample_04_entry_rgb.png`。

**实际看见**：两张都是三入口拼图；样本0左图有横向桌面状灰带、其余大面积彩色高频噪点；样本4左/中/右均为噪声与灰带交错，**没有任何一张能辨认出正常 Lift 的机器人、立方体或桌面场景**。这与执行者“严重像素损坏”的描述一致，但图片是从保存数组重建，不是重新渲染；我没有读 NPZ 二进制、没有重算数组、没有查看旧 expert/dev PNG，也没有 GL 状态/错误/context 遥测。因此“当前保存的 RGB 数组损坏”是事实；“渲染器/ framebuffer 机制”仍不是已证事实。

## 2. 执行合规性与计数

- `counts.json`：固定 ACT 前向 **0/32**、闭环 query **0/80**、rollout **0/16**、env.step **0/2400**、optimizer **0**；`stage1.py:376-380` 在 `prepare_inputs` 返回 `all_inputs_pass=false` 后直接写 `STOP_INPUT_DISCREPANCY` 并 return，**没有创建 ACT、没有跑模型**。计数与代码一致。
- Stage0：CPU、CUDA 未初始化，4.38s；Stage1：exit0，GPU 11.58s；总 GPU 远低于 3600s。Stage1 有 1 次 `make_env`、24 次显式 RGB 渲染、8 个来源状态/4 个 demo；符合 Stage1A 范围。
- `delivery_integrity.json`：6615 个旧文件无差异；`source_blob_audit` 48 个官方 blob 匹配；旧 checkpoint 未改；`completion` 记录 PARTIAL。**未发现超预算、重训、正式 test、test 标签泄漏或旧目录写入。**
- 公开同步：本地 `99a2147`/`2d42000` 保留，两次 HTTP408，remote 仍 `a03f16d`；报告如实写“未同步成功”。这是交付不完整，不是科学违规，也不是实验结果。

**结论：执行合规性 PASS（在授权 Stage0/Stage1A 范围内）；科学完整度 PARTIAL。**

## 3. H1–H4 的新证据

| 假设 | 新证据 | 能排除/不能排除 |
|---|---|---|
| H1 入口不一致 | 非 RGB 张量：state/qpos/cam_extrinsics/Plücker/action/mask 在所查比较中 **bit equal**；相机矩阵与给定 T 约 2e-16；RGB 三入口严重不一致 | 能排除“所有输入都错”；**不能**把 RGB 差异归因于适配预处理，因为三入口是分别渲染，未取得“同 raw RGB”。H1 仍未判定 |
| H2 posterior/prior | **完全未测**：0 次 ACT 前向，P/M/Q 均 null | 无任何 H2 证据 |
| H3 训练相机 vs 新相机 | **完全未测**：0 闭环；旧 0/32 仍是新相机池结果 | 无 H3 证据 |
| H4 采样/环境/历史渲染 | 当前 8 状态 24 次渲染出现 RGB 异常；无历史训练 RGB/framebuffer 日志；当前 MuJoCo3.3.0 满足 PR5 区间；sampler/RNG 差异仍在 | 当前渲染前提失败是事实；**历史训练是否同样损坏仍是 UNKNOWN**；不能把当前异常追认为旧 0/32 根因 |

## 4. 最强替代解释：诊断自身，而非训练渲染器

`analyze_render.py:10-23` 只读取已保存数组并拼接，没有重新渲染；因此 PNG 显示的损坏来自保存数组本身。但数组损坏可能由以下任一项造成，当前不能区分：

1. **诊断上下文/生命周期**：同一 `env`、同一 EGL 上下文内连续做 Dataset/Evaluator/custom 三次渲染，未 `env.reset()`；`stage1.py:114-199` 无 GL status/error/context 遥测。官方训练也连续渲染，但官方有 framebuffer 检查（`train.py:102-106,163-166`），本诊断没有复制。可能是诊断暴露了上下文问题，不等于旧训练受损。
2. **路径/保存/转换**：Dataset 路径经过 `T.Resize(256)`（`EpisodicDataset`），Evaluator/custom 不过；三者都 `np.flipud(...).copy()`，理论上方向一致。`render_audit` 对样本3/4显示直接差异大、`flipud_meanabs` 约 0.01，说明部分图像可能是**上下翻转/方向差异**，而非随机噪声；这更像诊断数组/变换/路径问题，不能先判 framebuffer。`rgb_ds` 由 `ds_item['image'][0,:3]` 经 `np.rint(*255)` 重建（`stage1.py:136`），与 eval/custom 的重建方式不完全同路径；必须只读核对原始 `ds_item['image']`、`eval_image`、`custom_image` 的方向与 resize 前后值。
3. **渲染器/EGL 内部缓冲**：图像有彩色高频噪声，可能来自 framebuffer；但没有 GL 错误/状态，不能确认。当前渲染健康与否不能由这些数组证明。
4. **共享缓冲**：三条路径都 `.copy()` 后保存，代码上没有明显别名；但 `env.sim.render` 内部缓冲未验证，不能完全排除。
5. **旧训练根因**：旧 expert/dev PNG 可辨认（执行者报告；我未独立查看），只能说明旧评估帧可能正常，不能证明训练批次正常；无历史训练 RGB/GL 日志，故**不能定位旧 0/32 根因**。

**因此：当前 RGB 异常是真实的“输入前提失败”，但最可能首先是诊断/渲染上下文或数组路径问题；framebuffer 只是候选机制之一，不能预先选定。**

## 5. 决策：D，不是 A/B/C

- **不是 A**：没有确认的适配/预处理错误能解释 0/32；RGB 差异未隔离。
- **不是 B**：没有训练相机闭环阳性。
- **不是 C**：没有训练条件闭环；0/32 仍是新相机池，不能称普遍无能力。
- **是 D/IMPLEMENTATION-LIMITED**：当前输入前提失败，旧根因未知；正式 H2/H3、persistent/IID、moved-stale 全部 NOT_RUN。

**不建议完整重训**。当前没有可信修复或因果证据；重训可能重复同样输入问题。也不应使用剩余 GPU 预算自动重启。

## 6. 下一步最低成本方案

1. **只读追溯当前诊断脚本与保存数组**（0 GPU）：核对 `rgb_ds`、`eval_image`、`custom_image` 的原始形状/方向/resize 前后值；检查 `T.Resize` 是否只作用于 Dataset 路径；检查 `render_audit` 的 flip 近似是否由保存/变换造成。若能把差异归为诊断代码/数组路径，修诊断即可，不碰旧训练。
2. **仅当只读仍不能解释**，再另审一次**极小渲染微诊断**：同一状态、同一相机，重复渲染 N 次，保存 **raw pre-flip** 数组、GL framebuffer status/error/context 生命周期、图像 hash；不训练、不模型、不改旧 ray。该微诊断需单独协议与批准，不能把未用预算当自动授权。
3. 只有得到健康、可重复的 RGB，才谈 Stage1A 的 32 前向和 Stage1B；目前这些均未执行。
4. F 暂停；若恢复，仍先过可信 clean baseline、simple pose-jitter/重标定基线，再谈机制。KYC/CamVLA/AnyCamVLA/MoVie 已覆盖大部分相机适应空间，排障本身不是论文创新。

## 7. 给人类的最终五问

1. **根因是否定位？** 否。当前只确认“本轮 8 状态 24 次渲染的 RGB 保存数组严重异常”；旧训练 0/32 的根因未定位。
2. **是否有明确、低成本、可验证的修复？** 暂无已验证修复。最低成本是先只读核对诊断数组/方向/resize/上下文；若确认是诊断artifact，修诊断；若指向渲染器，再做一次独立 GL 微诊断。不能直接修旧训练。
3. **是否值得投入完整重训？** 不值得。没有可信 clean 输入或具体修复；重训会重复未知风险，且成本高。
4. **F 是否仍值得作为硕士论文候选？** 当前不作为论文候选，只保留条件性恢复资格；即使恢复，persistent/IID 只是窄诊断，KYC/CamVLA/AnyCamVLA/MoVie 已覆盖，需强简单基线后才谈新方法。
5. **下一候选优先找什么？** 有**公开且匹配的官方 policy checkpoint、数据、环境、任务阳性基线**的开源系统；能先复现已知成功，再做缺陷/机制；不要再从零训练一个未验证的基线。

## 8. 验收结论

**执行合规：PASS（授权范围）；科学证据：D/IMPLEMENTATION-LIMITED；完整度：PARTIAL；正式 H2/H3/误差对比：NOT_RUN；公开同步：未完成（网络408，remote未变）。**

不批准继续使用剩余 GPU，不批准重训，不批准把当前 RGB 异常写成旧训练根因或 KYC 科学阴性。下一步只读追溯诊断数组/渲染路径；若需运行，另立极小 GL 诊断协议并重新审查。
