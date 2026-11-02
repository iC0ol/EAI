# 交叉验收 18 与 render_lifecycle 协议审查

## 1. 先纠正 18 的事实

- **索引偏 1**：实际零基索引是 `23 after_make_env`、`24 before_Dataset`、`25 free_enter(旧ctx1)`、`28 eglReleaseThread_enter`、`29 exit`；我写的 24/25/26/29/30 是错的。撤回。
- **“更可能 con.free”没有充分排名依据**：`0x8219` 只是当前 draw 绑定（可能是 surfaceless 默认 FBO0），不能判定 `offFBO` 被删；`con.free` 是候选，不是已证原因。撤回排序。
- **“只跳过 release/恢复 current”很可能重复已经失败的绑定思路**：单次 `make_current` 已证明 context 匹配但 FBO/readback 仍坏；新协议改为“在所属 context 释放 con/EGL，再恢复 previous”，方向不同，但我接受不能只做 skip/restore。
- **当前机制与旧 0/32**：当前坏图、当前 context 解除、旧训练历史三者继续分开；旧训练仍 UNKNOWN。

## 2. render_repair 验收

**合规但有边界**：worker1 在 `make_env` 前因 NULL `.address` ValueError 失败；初始 completion 保留，恢复 supervisor 另进程使用剩余 worker，累计预算/名额未回收，worker1 退出后才启动 worker2。`workers=2`、`make_env` 预留2/实际1、renders 6/12、readPixels 12/24、GPU 23.13/300s、ACT 0、env.step 0、optimizer 0。一个工程修复在允许范围内。

**但不是完整双 worker 协议**：worker2 是唯一有效基线/修复进程，`independent_valid_worker_repetition=NOT_RUN`；不能称两份独立复验。结论 **PARTIAL / REPAIR_FAILED** 正确。

**可信证据**：6 帧 raw/flip/float/PNG 边界核验；12 个 raw 哈希；state/XML/T hash 相同；sentinel 1.0；修复前后六图均无法辨认 Lift；无 ACT/step/更新。**不完整**：无健康正常对照；无第二个有效 worker；无 `con.free` 逐调用；无 FBO 绑定/附着/资源身份；无历史训练 RGB/GL。

## 3. current 解除与 FBO

事件链：index23 `after_make_env` ctx2/36053；24 `before_Dataset` ctx2/36053；25 旧 ctx1 `free_enter` 时 current 仍 ctx2，但 draw 绑定已 33305；28 `eglReleaseThread` 入口 ctx2，29 出口 null；33 `after_Dataset` null。

因此：
- **current 解除有直接链**：旧 ctx1 的 `free` 调用 `eglReleaseThread`，把当前 ctx2 解除。
- **但 33305 出现在 release 之前**，所以不能归因于 release；它只说明当时当前 draw 绑定未定义。是 `con.free`、FBO 解绑、还是默认 FBO0，未测。
- **33305 本身**只证明“当前 GL_DRAW_FRAMEBUFFER 绑定未定义”；缺 `GL_DRAW_FRAMEBUFFER_BINDING`/`GL_READ_FRAMEBUFFER_BINDING`、FBO ID、`glIsFramebuffer`、attachment、尺寸/采样、`con.offFBO` 对应的真实 GL 对象。它不能证明 MuJoCo 的 offFBO 被删除。
- **单次 make_current**：current 匹配但 FBO 33305，`mjr_render` 1286、`mjr_readPixels` 1282，sentinel 全保留；说明 context 是必要条件、不是充分条件，失败已下移到 FBO/read buffer。不能据此说 `make_current` 永远无用，也不能证明旧 context free 无关。

## 4. render_lifecycle 协议

协议只测试一种修复：**renderer 的 GPU 资源在其所属 EGL context 中释放，释放后恢复先前仍存活的 context**；从新进程初始化前安装。它不是 make_current 补救、不是重建 FBO、不是禁用 GC/泄漏旧 renderer。这个方向与已记录的所有权/生命周期问题对应，**值得一次小范围修复**。

预算自洽：2 worker、2 make_env、8 renders（每 worker 早期1+三入口3）、16 readPixels（每 render 正常+sentinel）、300 GPU 秒、0 ACT/0 step/0 训练；worker1 基线、worker2 修复，不是同条件重复；CPU mock 覆盖 NULL/部分析构/owner 缺失/previous 为 owner/另一个活 context/null/恢复失败。这不扩大范围。

### 必须的实质修订

**§4 的 GL 对象测量必须按 context 归属隔离。** FBO/纹理/renderbuffer 名字是 per-context 的；在 ctx2 current 时对旧 ctx1 的 `offFBO/offFBO_r` 调 `glIsFramebuffer`/attachment，测的是 ctx2 的同名对象，不是 ctx1 的对象，会产生假证据。必须写死：

1. 只有 `owner == current` 时，才对该 owner 的 `offFBO/offFBO_r`、bindings、attachments 做 GL 查询；否则记 `NOT_MEASURED_WRONG_CONTEXT`，不得把结果写成对象有效/无效。
2. **baseline** 中 owner 正在被析构、current 是另一个 context；因此 baseline 只能记录 current/owner、active-context 的 draw/read binding 与 active renderer 对象；**不能声称 owner 的 FBO 在 con.free 前后被删除**。owner 对象有效性只能在 **fix 条件**（owner 被绑定后）前后测量，或在 owner 曾 current 的明确窗口测量。
3. fix 条件：绑定 owner → 测量 owner 对象 → `con.free`/`gl_ctx.free` → 测量 owner 对象（若仍可）→ 恢复 previous → 测量 previous 对象；owner 缺失/恢复失败即停。
4. §6 的“支持资源误释放”应改为：baseline 的 **event + active-context 变化**，加 fix 条件中 **owner-bound before/after 对象变化**；不能要求 baseline 在错误 current 下测 owner 对象。

这是测量正确性修订，不是新实验范围。若不改，协议可能把“ctx2 的同名 ID”误当 ctx1 对象，得出错误因果。

### 解释边界

- 早期对照（make_env 后、Dataset/Evaluator 前）若健康、后续 baseline 坏，支持构造/旧 free 触发；若早期已坏，不能仅凭此排除生命周期，但也不能把 fix 后健康单独当因果，必须看 owner-bound 对象事件。
- 若对象始终有效而 raw 仍坏，拒绝“误删除资源”解释，停止，不追加 FBO/驱动候选。
- 即使 fix 成功，只证明该固定 state/顺序的局部生命周期修复；旧训练 0/32 仍 UNKNOWN，不恢复 ACT/rollout/训练。

## 5. 结论

**render_repair：PARTIAL / REPAIR_FAILED，D/IMPLEMENTATION-LIMITED；执行合规 PASS（预算内，一个有效 worker，无越权）；完整双 worker 复验 NOT_RUN。**

**render_lifecycle 协议：APPROVE_WITH_REQUIRED_CHANGES。** 只需补上 §4/§6 的 per-context 对象测量隔离（owner=current 才能查；baseline 不得在错误 current 下测 owner FBO；owner 对象变化只在 fix 条件报告），并保留早期对照/反证条件。修订后可派发；不增加样本、不训练、不改系统。
