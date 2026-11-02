先读取运行原件与worker 2事件，核对工程恢复和证据链。

# render_repair 独立验收（DeepSeek）

## 1. 工程恢复与合规性

已读 `FINAL_REPORT`、`completion`、`review_gate`、`engineering_repairs`、`initial_attempt_completion`、`worker.py`、`context_binding.py`、`engineering_recovery_supervisor.py`、`worker_2/events.jsonl`、`entries.json`、`readback.json`，并查看了 `comparison.png`。

**合规，但不是完整协议 PASS。** worker1 在 `before_make_env` 因 PyOpenGL NULL opaque context `.address` 触发 ValueError，发生在任何 render/readPixels/实际 `make_env` 之前；初始 completion 保留，未重启原 supervisor。恢复 supervisor 另起进程，断言 worker1 已结束，使用剩余 worker 名额运行 worker2；`workers=2`、`make_env` 预留2/实际1、renders 6/12、readPixels 12/24、GPU 23.13/300s、ACT 0、env.step 0、optimizer 0。计数保守、未抹去失败进程，未超预算。

但 **worker2 是唯一有效渲染进程**，不是第二个独立复验进程；`independent_valid_worker_repetition=NOT_RUN`。因此只能接受 **PARTIAL / REPAIR_FAILED**，不能称双 worker 复验完成。一个工程修复（允许最多2）和一次 worker 恢复在范围内。

## 2. 证据可信与不完整

**可信**：
- 6 帧正常 raw、6 帧 sentinel 的计数与哈希；raw 到 flip/float/PNG 的边界关系由执行者 CPU 核对；`entries.json` 记录 `raw_to_saved_flip_exact=true`；三入口 state/XML/T hash 相同。
- baseline 三帧均无 current context；repair 三帧 current=target=ctx2；`mjr_render` 后 error 1286、`mjr_readPixels` 后 1282，sentinel 165 保留比例 1.0，正常 raw 的 165 比例约 6e-5–1.2e-3。
- 我看 `comparison.png`：上下两排均无法辨认机械臂/目标，仍是彩色条纹/噪点；修复没有产生健康图像。没有模型或成功率数据。

**不完整**：
- 只有一个有效 worker，无独立重复。
- 没有健康正常对照（无同状态健康 raw）。
- 没有 `GL_FRAMEBUFFER_BINDING`/`GL_READ_FRAMEBUFFER_BINDING`、FBO ID、attachment、`glIsFramebuffer`、纹理/renderbuffer 身份、尺寸/采样数；`glCheckFramebufferStatus` 33305 的对象不明。
- 没有 `MjrContext.con.free` 逐调用插桩；没有 old context free 的栈/对象身份；无法把 FBO 失效归到具体 `con.free`。
- 旧训练没有历史 RGB/GL，0/32 仍 UNKNOWN。

## 3. current 解除是否有实际触发链

**有直接链，但只覆盖 current 解除，不覆盖 FBO 失效。** events 零基索引：

- index24 `after_make_env`：current=ctx2，framebuffer=36053；index25 `before_Dataset` 仍 36053。
- index26 `free_enter`（旧 ctx1）：current 仍 ctx2，但 framebuffer 已为 **33305**；此时尚未 `eglDestroyContext`/`eglReleaseThread`。
- index27–28 `eglDestroyContext`；index29 `eglReleaseThread_enter` current=ctx2；index30 `eglReleaseThread_exit` current=**null**；index34 `after_Dataset` 仍 null；baseline 三帧均无 current。

所以：**`eglReleaseThread` 把当前 ctx2 解除，是当前 context 丢失的直接事件链**；但 **33305 出现在 free/release 之前**，不能归因于 release。它更可能来自 `MjrContext.con.free` 或 FBO 解绑，而这一点没有逐调用证据。报告把“当前解除”和“buffer 失效”分开是对的，但触发源仍未完全定位。

## 4. `glCheckFramebufferStatus` 究竟证明什么

33305 = `GL_FRAMEBUFFER_UNDEFINED`，只证明**查询时当前绑定的 draw framebuffer 未定义**；它不证明：

- 检查的是 MuJoCo 的 `con.offFBO` 还是默认 framebuffer；
- 该 FBO 的 attachment 是否完整、尺寸/采样数是否匹配；
- `con.offFBO=1/offFBO_r=2` 这些 MuJoCo 字段对应的 GL 对象是否仍有效；
- `mjr_render` 内部绑定的是哪个 FBO。

缺少 `GL_DRAW_FRAMEBUFFER_BINDING`/`GL_READ_FRAMEBUFFER_BINDING`、FBO ID、`glIsFramebuffer`、attachment 类型/对象、`glCheckFramebufferStatus` 对具体绑定对象的重复查询，以及 `mjr_render` 前后绑定变化。**33305 不能单独证明 buffer 已损坏**；1286/1282 与 sentinel 1.0 更能说明 readback 失败，但仍不能定位具体对象。

## 5. 单次绑定失败如何解释

repair 三帧 current=target=ctx2 匹配，但 framebuffer 33305、`mjr_render` 1286、`mjr_readPixels` 1282、sentinel 全保留。说明：**context 绑定是必要条件，但不是充分条件；当前失败已下移到 FBO/read buffer 层**。它不证明 `make_current` 永远无用，也不证明旧 context free 链无关；只证明这一单一修复不足以恢复健康 readback。不能据此叠加第二种猜测。

## 6. 最小下一修复与可辨识设计

值得一次**control-first**的小范围修复，但不是再次盲试 `make_current`：

1. **健康对照**：新进程、`make_env` 后、构造 Dataset/Evaluator 之前，用同一 sample0 state/T 立即 render 一次；记录 raw、sentinel、`GL_FRAMEBUFFER_BINDING`/read binding、FBO ID/attachment/status、GL error。
   - 若 healthy：失效由 Dataset/Evaluator 构造或旧 context free 引入。
   - 若已坏：问题在 `make_env`/FBO 创建，不在旧 context free。
2. **补 `MjrContext.con.free` 与 `MjSim.add_render_context` 的逐调用事件**（弱引用/匿名 ID），确认旧 ctx1 的 `con.free` 是否在 33305 前解绑/销毁 FBO；不要仅凭 `eglReleaseThread` 函数名。
3. **只选一个修复**：
   - 若对照 healthy 且旧 con free 是触发：延迟/禁止对非当前旧 context 调用 `eglReleaseThread`，或在 free 后恢复当前 ctx；再看 FBO/raw。
   - 若对照已坏或 FBO 仍 33305：只做一次 FBO 重建/正确绑定候选，需先有 binding/attachment 证据。
4. **反驳条件**：`make_env` 后对照已坏 → 旧 context free 链不是唯一原因；修复 current 后 FBO 仍 33305/1282 → current 不是充分层；FBO binding 显示对象有效但 raw 仍坏 → 需查 read buffer/驱动，而不是继续改 context。
5. **健康标准**：人工可辨认机械臂/目标、raw 可复现、FBO/status 正常、sentinel 不残留；不能只看三入口相等或 context 匹配。

## 7. 最终分类

**PARTIAL / REPAIR_FAILED；证据分类 D / IMPLEMENTATION-LIMITED。** 当前故障在固定 sample0 复现；单次 context 绑定恢复 current，但**没有恢复健康 RGB**；current 解除有直接事件链，FBO/readback 失效源未定位；旧训练 0/32 仍 UNKNOWN。执行合规 PASS（未超预算、无 ACT/env.step/训练），但不是完整双 worker 协议；独立复验 NOT_RUN。

**建议**：允许一次上述 control-first 小修，不扩大样本、不训练、不改系统；若 control 已坏或修复后仍 33305/1282，停止并保留 D，不把当前机制追认为旧训练根因。公开同步状态按已核实 remote `2d42000` 更新，旧记录保留。
