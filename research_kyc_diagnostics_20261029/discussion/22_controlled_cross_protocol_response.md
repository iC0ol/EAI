# render_controlled v1 审查

## 1. 先纠正 21 的过强表述

我接受父审的纠正：render_lifecycle 的 fix 条件**没有经历目标释放窗口**，因此只能得到：

- **不能把 fix 健康图归因于 owner 安全释放或 live-previous 恢复**；
- 也**不能反过来说“健康更可能来自 GC”**——安装不同析构代码本身会改变分配/时序/排序，当前没有对照区分“GC 时序”“安装效应”“其他条件差异”。正确表述是：**健康图的因果未建立，条件差异未分解**。

父审的硬事实我核对一致：baseline 零基 29→30 是同一次原 `con.free` 前后，owner=`w1_ctx1`、current=`w1_ctx2`；ctx2 活动 renderer 的 3 FBO + 4 RBO 由 true→false；baseline 34→35 `eglReleaseThread` 后 current=null。fix 最后采图事件 56，owner 释放 59/75 均在 cleanup，`real_live_previous_restores=0`。计数 2 worker/2 make_env/8 render/16 readPixels/24.41s、0 ACT/step/更新，旧文件未变。**执行合规；因果 PARTIAL。**

## 2. CPU 适配边界修正

父审的 CPU 复现是有效的：`Telemetry.capture()` 在 raw context 非零、registry 无映射时返回 `key=None`；`release_owned` 只按 key 判 previous=null，不能区分“真正 null”与“非零未知”，于是返回 DONE、无 failure、当前 context 丢失。原 20 个 mock 的 `unknown` 字符串没有覆盖这个真实适配器形式。

render_controlled §3 已要求：raw current 非零但 key=None 必须在任何绑定/`con.free`/`egl.free` 前可见失败并停止；capture/owner/ids 前置异常可见；NULL 与 key 状态矛盾也拒绝。这是正确的必要修正。该分支未在本轮实 GL 触发，不是旧坏图已证原因；不能部署旧候选。

## 3. 新协议是否可执行、是否覆盖缺项

**APPROVE。**

关键设计成立：

- **同一受控触发**：两条件都显式强持有 make_env 的 A（退休 renderer，sim≠env.sim）与 B（活动 renderer，current=B）；在固定点、同一 `_MjSim_render_lock` 内，对 A 的同一 one-shot 析构入口调用一次。baseline 用原语义，fix 用 owner 安全释放并恢复 B。这不是自然 GC 碰运气，也不是弱引用 drop；两条件同一触发路径，只有释放事务不同。
- **归属测量**：baseline 只测 B 当前 namespace；fix 在 owner=A current 时测 A 对象、`con.free` 后/`gl_ctx.free` 前再测 A，随后恢复 B 并测 B；不把 A/B 的同名 ID 混同；不假定共享资源。
- **真实 live-previous 分支**：fix 要求 A≠previous=B、owner 绑定、真实 `previous_restored` 到 B、A 销毁、B 原对象仍有效；这正好补上 render_lifecycle 的 `previous_restores=0` 缺项。
- **health control**：before 必须与已确认健康的 `worker_1_baseline/early.png` 逐像素一致（SHA 688297…），before 不健康即 STOP；after 必须与 before bit equal；sentinel=raw；不以噪点熵或“图像看起来像”替代。
- **guard**：NEW/RUNNING/DONE/ERROR，只控制重复；首次调用必须执行原始/修复清理，不跳过首次 `con.free/gl_ctx.free`；fixture 移除 A 强引用后自然再析构只能跳过，记录 exactly-once；不泄漏、不禁 GC、不删除字段假装释放。
- **预算**：2 worker、2 make_env、4 renders（每条件 before/after）、8 readPixels（正常+sentinel）、180 GPU 秒、0 ACT/0 env.step/0 训练；比上一轮更小，自洽。
- **停止**：身份不清、恰有两个 renderer/context 条件不满足、before 不匹配、baseline after 不坏、fix 无真实 B 恢复、对象身份丢失、after 异常、任何门不满足 → PARTIAL/FAIL；不追加第三 worker/候选/图像。正确。

## 4. 仍然有限的外推

即使通过，只证明：

- **固定 fixture、固定 sample0、固定受控释放点**下，owner-context 释放 + 恢复 live B 能避免 B 资源失效；
- 不能证明自然 GC 的发生率/时序、多视角/长期/线程稳定性；
- 不能证明旧 checkpoint 训练 0/32 历史因果；旧训练 RGB/GL 仍 UNKNOWN；
- CPU mock 仍不能替代真实 GL；只有真实 `previous_restored`、B 对象有效、after=before 才可称局部受控 PASS；
- 不自动部署、不恢复 ACT/rollout/训练。

## 5. 结论

**render_controlled v1 APPROVE**，可冻结准确 SHA 并派发给既有 gpt-6.1-sol/max。无实质阻碍，不需增加样本或第三 worker；只需执行时严格遵守 §3 的 unknown-key 前置失败、§4 的同一 fixture/guard/参考像素、§5 的 live-previous 真实恢复门。旧 0/32 仍 UNKNOWN，Git 归主审。
