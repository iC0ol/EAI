# v2 代码交叉审核

## 1. 漏洞确认与修正

Codex 指出的 v1 缺口成立：v1 `mjr_render_after` 只记录并排空 GL error，不检查；随后成功 readback 可把旧错误掩盖为健康。父审 `parent_code_probe_v1.json` 已用纯 CPU 复现。

v2 已修正：

- `input_runtime.py:80-88`：`mjr_render` **before/after** 都要求原锁持有且 `healthy_event` 通过；before 失败不调用 native，after 失败立即停止。
- `input_runtime.py:95-101`：`mjr_readPixels` **before/after** 同样检查；错误码 `[1286,0]` 不再被后续成功 read 掩盖。
- `test_render_health.py` 5 个 CPU 用例覆盖健康 render、render before/after error、read before/after error；未增加 render/read 调用、GC、资源重建或锁改动，预算不变。
- 静态未见新的必败路径；真实健康 readback、strict load、缓存 ResNet、BF16 数值仍只能运行时验证，均为失败即停门，不作为已通过结果。

## 2. 对两个 SHA 的审批

**APPROVE** 以下两项作为本轮有限实验的最终协议/代码审核：

- `PROTOCOL.md`：`6ae547f65fc0b94a6954ae98d75fcf472a354b81d6e66f27abbd71b4b9ad883c`
- `candidate_manifest.json`：`9d2171f112023395171a259423be4d3a3ec40a7d3a4442de0561108a28729aa1`

我**未独立重算 SHA**；以上为 manifest/父审值。正式 RUN 前主线程仍须按实际文件复核；任一文件变更则本次审批失效。**批准不等于 RUN，也不等于运行结果。**

## 3. 剩余运行时边界

- 输入 stage 210s（195s 终止+15s 释放），模型至少 390s，累计 600s；2 worker、12 render、24 read、16 ACT、0 step/rollout/optimizer。
- 自然 A 释放窗口未出现只记 `NOT_REPRODUCED`；health gate 通过可继续固定权重诊断，但不得把健康输入当自然生命周期修复证据。
- strict load、缓存 ResNet、`NoOptimizer`/torch proxy、BF16 重复噪声、sample4/5 单次 1e-5、方向/夹爪退化门、20% 仅投资门，均按现有代码失败即停；CPU mock 不等于真实 EGL/模型验证。
- 旧 0/32 仍 UNKNOWN；不授予训练、闭环、扩容或 F 方法研发。
