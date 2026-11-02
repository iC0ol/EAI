先读执行原件与源码，重点核对 owner 绑定、previous 恢复和事件索引。

# render_lifecycle 独立验收（DeepSeek）

## 1. 执行合规与计数

已读 `PROTOCOL`、`FINAL_REPORT`、`completion`、`repair_choice`、`analysis`、`owned_release.py`、`telemetry.py`、`worker.py`、两个 worker 的 events/entries/readback、资源记录；未读新的父 notes/05 或 parent audit，未运行任何程序。

**执行合规 PASS（范围内）**：2 个独立 worker/2 次 make_env、8 次 `mjr_render`、16 次 `mjr_readPixels`、GPU 24.41/300s、0 ACT、0 env.step、0 rollout、0 optimizer、0 工程修复；worker1 exit0 后才启动 worker2，未重启旧 terminal；旧文件/源 SHA 未变。两个条件是 baseline/fix，不是同条件统计重复；这一点报告已诚实标注。

**但完整度是 PARTIAL，不是因果 PASS。** 修复条件没有在图像采集期间执行其目标析构窗口。

## 2. 当前故障机制：局部证据强，但只在 baseline 进程

`analysis.json` 的 baseline 对象对 `29→30`（`CONSTRUCT_DATASET`，零基）显示：

- 正在释放的 owner 是 `w1_ctx1`，真实 current 前后均为 `w1_ctx2`；
- 旧 owner 的 FBO/RBO 明确 `NOT_MEASURED_WRONG_CONTEXT`，没有在 ctx2 下拿 ctx1 的同名 ID 冒充证据；
- 测量的是 **ctx2 活动 renderer 的真实对象**：`offFBO=1`、`offFBO_r=2`、`shadowFBO=3` 的 `glIsFramebuffer` 由 true→false；`offColor=1`、`offColor_r=3`、`offDepthStencil=2`、`offDepthStencil_r=4` 的 `glIsRenderbuffer` 由 true→false；归属均为 `w1_ctx2`，ID 一致。

这是**活动 context 资源在错误 owner 的 `con.free` 窗口内失效**的直接对象证据，不是仅凭 `0x8219` 或 FBO 整数相等推断。随后 EGL release 使 current 变 null；baseline early 健康、后续三帧无 current 且损坏，链条自洽。

**仍需保留的未知**：为什么旧 `w1_ctx1` 会在 Dataset 构造时被析构（自然 GC/引用时机）没有栈/对象身份；这只解释当前进程的局部机制，不解释旧训练 0/32。

## 3. 健康图是否由修复产生：没有建立

这是最关键的反证：

- `fixed_owner_release_during_image_acquisition_indices=[]`；
- `fixed_image_acquisition_last_event_index=56`；
- fix 的旧 `w2_ctx1` 直到 `CLEANUP` 才析构（对象对 75→76），ctx2 也在 cleanup（59→60）；
- `previous_restorations=[]`，`real_GL_live_other_previous_restore_count=0`；
- `healthy_images_caused_by_fix = NOT_ESTABLISHED`。

fix 四帧健康且与 baseline early 逐像素相同，说明**该进程没有在采集期经历旧 owner 的错误释放**；健康更可能来自进程/GC/分配时序差异，而不是 `owned_release` 的 owner 绑定+previous 恢复。不能把 fix 图像健康归因于修复，也不能据此部署候选模块。

## 4. 真实 GL 活 previous 恢复未覆盖

fix 的两次 cleanup 都是 owner=current、previous 为 owner 自身或 null；没有“释放旧 owner 后恢复另一个仍活 previous”的真实 GL 调用。`previous_restorations=[]` 与 count=0 与报告一致。CPU mock 20/20 只验证控制流/异常路径，不能替代真实 EGL/GL 分支。**live-other 恢复仍是 CPU mock 假设，不是已测事实。**

## 5. 最关键缺项与最小因果验证

缺的不是更多截图，而是**在 fix 条件下强制触发同一个跨 context 析构窗口**：

- 新协议（另行冻结、2 worker/少量 render、0 ACT/step/训练）：
  1. 同一 sample0/state/T/构造顺序；baseline 与 fix 各一进程。
  2. 在早期健康帧之后、采集三入口之前，**显式、确定性地释放/析构旧 renderer（或捕获其弱引用并在固定点 drop/close）**，使 owner 与 current 的跨 context 条件真实发生；不要依赖自然 GC。
  3. baseline 预期 active ctx2 对象 true→false、后续坏图；fix 预期 owner-bound 释放后 previous 恢复，active ctx2 对象仍有效、图像健康。
  4. 记录 owner/current、owner 对象前后、previous 对象恢复前后、`previous_restored` 真实事件、raw/sentinel/PNG。
- **反驳条件**：强制 baseline 仍健康 → 当前对象丢失不是充分原因；fix 强制窗口后仍坏或 previous 恢复失败 → 该修复不足；fix 健康但 active 对象仍失效 → 图像健康另有原因；previous 未真实恢复 → 机制未覆盖。
- 健康对照：早期帧（已有）+ 强制窗口后 fix 健康；不能只用“fix 四图与 early 相同”当因果。

## 6. 分类

**执行 COMPLETE，因果验证 PARTIAL / LIVE_PREVIOUS_WINDOW_NOT_EXERCISED；当前证据 D/IMPLEMENTATION-LIMITED。** baseline 的错误 owner `con.free` 导致活动 context 资源失效有局部直接证据；fix 健康图**不**由修复因果产生；真实 GL 活 previous 恢复 **NOT_EXERCISED**；CPU mock 不能替代；旧训练 0/32 **UNKNOWN**。

**不建议部署候选修复、恢复 ACT/rollout 或训练。** 值得一次上述“强制同一析构窗口”的最小验证；若通过才谈该局部修复，若失败则停止，不追加第二修复。
