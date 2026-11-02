先读取执行报告、计数与原始事件，再核对 owned_release/guard 的实际分支。

# render_controlled 独立验收

## 1. 原件与零基事件

我读取了 `FINAL_REPORT`、`completion`、`analysis`、两组 `fixture.json`/`guard_counts.json`、worker、`owned_release.py`、`telemetry.py`、`run_manifest`、`budget`、`integrity`，并抽查两组 `events.jsonl` 原始行；未运行程序、GL、模型或仿真。

关键零基位置（与 `analysis.json` 一致）：

- **baseline**：`29 controlled_A_release_enter`；`31 baseline_before_con_free`、`32 baseline_after_con_free`；A owner=`w1_ctx1`，current=B=`w1_ctx2`；A 对象正确记 `NOT_MEASURED_WRONG_CONTEXT`；B 的 3 FBO + 4 RBO 同 ID 由 true→false；`37–38 eglReleaseThread` 后 current=null；after 帧在无 current 下保存。
- **fix**：`29 controlled_A_release_enter`；`32–33 eglMakeCurrent` 绑定 A；`34 owner_bound_before_con_free`、`35 owner_bound_after_con_free`；A 对象在 A namespace 中 true→false；`36–43` 原 EGL free/release；`46 restore_native_return` 返回 true；`47 previous_restored`；`53 controlled_A_release_exit` 记录 A_live=false、B_live=true；`54–61` after 帧，current=B；B 的 3 FBO + 4 RBO 仍 true。
- **guard**：两条件 r1/r2 均 `first_entries=1, first_completed=1, con_free=1, destroy=1, skipped_DONE=1, skipped_RUNNING=0`；没有跳过首次析构，没有第二次实质 free。
- **fixture**：两条件均为 A 退休、B 活动、`A_sim_is_env_sim=false`、`B_sim_is_env_sim=true`，恰好 2 renderer/2 context，B 原 ID 一致。

## 2. 是否真正覆盖活 previous 恢复

**是，局部受控覆盖成立。** fix 不是“最终 cleanup 补恢复”：`previous_restored` 事件 47 发生在 `CONTROLLED_RELEASE_A` 内、after 帧之前；`restore_native_return` 46 返回 true；恢复后 current=B；B 原 FBO/RBO 仍有效；A 已销毁。baseline 则在同点释放 A 时 B 对象 true→false，after 无 current；两条件同一触发、同一 A/B 身份、同一 state/T/XML，只是释放事务不同。

这是 **同一释放窗口内的真实 live-other 恢复**，不是 CPU mock。fix 的成功不是由重建 B 或另建资源得到：B 的原始 ID 和对象在 before/after 都有效；没有 extra binding/rebuild 事件。

## 3. 有没有错认、跳首次、重建或只凭截图

- **跨 namespace**：baseline 只测 B active，A 明确 `NOT_MEASURED_WRONG_CONTEXT`；fix 在 A current 时测 A，恢复 B 后测 B；没有把 A/B 同名 ID 混用。
- **跳过首次**：guard 首 entry/首 completed 各一次，con.free/destroy 各一次；重复调用是 DONE skip；没有 RUNNING skip 或第二次 native free。
- **重建/泄漏**：fix 没有重建 FBO；A 被销毁；B 原对象保持；fixture 强引用最终清零；没有用保留资源换健康图。
- **只凭截图**：不是。before/after 都有 raw、flip/float/NPZ/PNG 五边界；before 像素 SHA 等于协议指定参考 `688297…`；fix after 与之逐像素相同；sentinel=raw；current/GL 错误/对象身份齐全。健康判定有读回和对象证据，不只靠图像。

## 4. baseline after “仍像场景”的解释

baseline after 无 current context；`normal_sentinel_equal=false`，sentinel 165 保留 100%；正常 raw 的 165 比例约 0.13%，与 sentinel 不同。after 的像素可能来自未初始化/陈旧缓冲，视觉上接近场景或翻转**不构成有效读回**；`GL_read_errors_clear=false`，current=null。不能把“看起来像”当健康，也不能据此推断具体内存来源。

## 5. unknown 非空 context 防护与合规

新 `owned_release.py` 已在准备阶段检查：

- `raw` 非零而 `key=None` 与 `raw==0`/key 状态矛盾，直接 `RuntimeError`；
- previous 非 live/未知、display/surface 非法、owner 缺失、绑定/释放/恢复异常均可见失败；
- 这些在任何 `bind_owner`/`con.free`/`egl.free` 之前；`one_shot` 把异常记为 ERROR，不重试。
CPU mock 30 项覆盖真实适配器 unknown、NULL 矛盾、live-other、owner=previous、异常路径；mock 不作为真实 GL 证据，但适配边界已补齐。**实际 GL 未触发 unknown 分支**；它只说明代码防护存在，不是本次故障原因。

预算/冻结/旧文件：2 worker、2 make_env、4 render、8 readPixels、19.29/180s、0 ACT/step/rollout/update；旧 295 文件与 7 脚本/7 源文件 SHA 不变；无 Git 写入。合规。

## 6. 局部修复能支持什么、不能支持什么

**支持**：在固定 sample0、同一 A/B 强引用 fixture、同一受控释放点下，按 owner context 释放 A 并真实恢复仍活 B，能保住 B 的原 FBO/RBO 与 after 图像；baseline 在同点破坏 B。这是**局部工程修复的因果证据**，比上一轮自然 GC 观察强。

**不能支持**：自然 GC 发生率/时序、多视角、长期/线程稳定性、旧 checkpoint 训练 0/32 历史因果；也不能证明 KYC 原论文或模型能力。旧 0/32 仍 **UNKNOWN**。

## 7. 旧 0/32、重训与 F

**旧 0/32：D / IMPLEMENTATION-LIMITED。** 当前只证明渲染生命周期机制与局部修复；没有历史训练 RGB/GL，不能把它写成旧 0/32 根因，不能给 A 类。

**是否值得完整重训：不建议自动重训。** 当前局部修复成立，但旧训练是否经历同类生命周期故障仍未知；完整 ACT 重训需人类另行批准，且应先做一份短小冻结模型诊断（不是现在自动运行），例如用固定 checkpoint/固定样本验证健康渲染下的 prior/posterior 与动作是否仍异常。该诊断只是建议，不是已授权执行。

**F 是否合格：不合格。** 即使渲染 bug 修复，当前是工程排障，不是论文机制；KYC/CamVLA/AnyCamVLA/MoVie 已覆盖大部分相机适应空间，persistent/IID 仍未被证明有独立残余。不把修 bug 包装成创新。

## 8. 最强反证

最强反证不是“图看起来健康”，而是：**fixture 是人为强持有/受控释放，不能证明自然 GC 或旧训练发生同样窗口**；A/B 是代理环境，不是旧训练上下文；因此局部 PASS 不能外推到旧 0/32 或生产。若有人据此直接重训、部署或宣称问题已解决，证据不足。另一个反证是 baseline after 视觉上像场景，但无 current/sentinel 100%；这说明外观不能替代读回，支持“不要只看图”的边界。

## 9. 结论

**render_controlled：执行合规，LOCAL_CONTROLLED_PASS（固定 fixture/受控释放）成立；旧 0/32 仍 D/IMPLEMENTATION-LIMITED，UNKNOWN。** 可接受该局部工程修复作为后续受控模型诊断的前置条件，但**不自动部署、不重训、不恢复 ACT/闭环**；下一份短小冻结模型诊断应另立协议并由人类批准，当前未运行。
