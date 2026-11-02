# render_lifecycle v2 最终审查

## 结论

**APPROVE。**

v2 已准确落实 19 的 context 归属测量修订，未增加范围，也没有会必然造成假因果或超预算的实质阻碍。

## 逐项核对

1. **owner/current 隔离**：§4 第32行明确只有 `owner == current` 才能查询该 renderer 的 `offFBO/offFBO_r`、bindings、attachments；owner 不等于 current 时记 `NOT_MEASURED_WRONG_CONTEXT`，不把 current 的同名 ID 当 owner 对象。满足 19。
2. **baseline 限制**：baseline 在旧 owner 析构、新 context 当前时，只记录 owner/current 和**新 current 所属活动 renderer**的对象；不声称测到旧 owner 的销毁。满足“baseline 不能在错误 current 下填空”。
3. **fix 窗口**：fix 先绑定 owner，在 owner 当前时测 owner 对象；`con.free` 后、`gl_ctx.free` 前再测；`gl_ctx.free` 销毁 owner 后不再查；恢复 previous 后才测 previous 所属活动 renderer。ID 在 `con.free` 前以 primitive 保存。满足。
4. **验收逻辑**：§6 要求 baseline 的“另一个 context 当前 + 该 current 活动 renderer 的真实对象变化”，加 fix 中 owner-bound 前后变化、previous 恢复后对象有效；仅 0x8219 不够；缺对象身份/窗口则只报局部效果和因果缺项。满足。
5. **共享资源**：不预设共享；整数相同不等于同对象；记录资源所属 context。满足。
6. **预算**：2 worker、2 make_env、8 renders（每 worker 早期1+三入口3）、16 readPixels（每 render 正常+sentinel）、300 GPU 秒、0 ACT/0 env.step/0 训练；与 v1 相同，自洽。
7. **CPU mock**：覆盖 NULL、正常、重复/部分析构、owner 缺失、previous=owner/另一个 live/null、恢复失败/异常；不把 mock 当真实 GL 修复。满足。
8. **唯一修复**：只做 owner-context 内释放 + previous 恢复；不重建 FBO、不改 driver、不禁用 GC/不泄漏；失败停止，不追加第二修复。满足。
9. **健康对照**：早期 1 帧、同 state/T、三入口；baseline 坏、fix 正常且对象事件一致才支持局部生命周期；基线不复现则只标有效性证据不足；对象始终有效但 raw 坏则拒绝误删除解释。满足。
10. **历史边界**：旧训练 0/32 仍 UNKNOWN；当前成功不启动 ACT/rollout/训练。满足。

## 有限解释边界

- 即使 fix 后图像健康，只证明**固定 sample0、固定构造顺序**下的局部 owner-context 生命周期修复；不证明长期、多视角、多进程稳定性。
- baseline 只能在 current 活动 renderer 上测对象；旧 owner 对象在 baseline 不可测，不能补成“已证明旧 FBO 被删除”。fix 的 owner-bound 前后变化才是该机制的直接证据；缺窗口则因果未知。
- `0x8219` 可能来自 surfaceless 默认 FBO0，不能单独判 offFBO 被删；`glCheckFramebufferStatus` 不是全检查点 36053 门槛。
- 当前修复不解释旧训练 0/32，不恢复原 32 前向/16 闭环；旧训练 RGB/GL 历史仍缺失。
- 两个 worker 是 baseline/fix 条件，不是同条件独立复验；统计重复和长期稳定性未测。
- 本任务不训练、不 ACT、不 env.step、不改系统；当前 render_repair 仍是 **PARTIAL / REPAIR_FAILED，D/IMPLEMENTATION-LIMITED**。

## 批准范围

**APPROVE v2，可冻结准确 SHA 并派发给既有 gpt-6.1-sol/max**，仅执行 `render_lifecycle/` 的 2 worker/2 make_env/8 render/16 readPixels/300 GPU 秒、0 ACT/0 step/0 训练；不重启旧 terminal，不扩大样本。完整训练仍需人类另行批准。当前不是已执行结果，也不把修复候选写成已验证根因。
