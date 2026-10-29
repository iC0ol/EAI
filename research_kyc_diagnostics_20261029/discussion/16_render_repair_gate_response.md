# v2 微诊断协议审查

## 结论

**APPROVE_WITH_REQUIRED_CHANGES。**

v2 已落实 15 的六项：日志无强引用、wrapper 用未绑定原方法；两个独立 OS/Python 进程且前一进程退出后再建；sentinel 独立保存、不参与健康；`make_current` 覆盖完整锁区并检查 render 后/read 前是否再丢 context；固定 GL 查询顺序并说明 error 清除；预算 hook 在 `make_env` 前覆盖隐式调用。方向、预算和科学边界正确，不增加样本、不训练、不 ACT、不 env.step。

仍有 **两处执行安全/可实现性** 需要写明，否则容易死锁或违反“不改全局 `np.empty`”。

## 必改项

1. **§3 写清 make_current 的安全插入点。** 不能在外层再次获取 `_MjSim_render_lock`（非重入会死锁）。应明确：在 `MjSim.render` 已持有锁的临界区内，包装 `MjRenderContext.render` 与 `read_pixels`：`render` 前 `make_current`，`render` 后、`read_pixels` 前检查 context 是否仍匹配；不匹配就保存并停止，不再绑定。或者用等价的“替换 `MjSim.render` 函数体”方式，但必须在同一把锁内、按原参数调用。不要只包装 `read_pixels`，也不要外层加锁。

2. **§2 写清 sentinel 的预填机制。** 协议禁止改全局 `np.empty`，但 `read_pixels` 内部自己 `np.empty`；要实现 sentinel，应窄包装 `binding_utils` 命名空间里的 `mujoco.mjr_readPixels`：在调用原函数前，把传入的 `rgb` ndarray 填已知模式，再调用原函数；不 patch 全局 `np.empty`，不改变 `read_pixels` 的正常分配。sentinel 数组单独保存、单独标记，不进入正常图像或健康判定。

3. **§2 写明 error 未清空的处理。** 最多 8 次 `glGetError` 后若仍有 error，记 `GL_ERROR_NOT_DRAINED` 并保留最后错误码，不能把“达到次数上限”写成无错误。GL 查询前必须有有效 current context；无 context 记 `NO_CURRENT_CONTEXT`，不绑定。

4. **§4 明确两 worker 的进程隔离记录。** 两个 PID/start_ticks、各自 context 创建/释放顺序、第一个进程 exit code 必须先于第二个启动；不能 fork 继承 CUDA/EGL。协议已有方向，建议写入交接检查项。

## 其他核对

- **是否自己修好/扰动 baseline**：基线不调用 `make_current`、不重建 context、不复制/改写数组；日志无强引用；sentinel 独立。设计上不会主动修复 baseline。仍需接受“插桩/拷贝改变分配与 GC 时序”的局限；v2 已写。
- **插桩能否辨识 raw/转换/保存**：五个边界独立拷贝、hash，sentinel 单独；可以区分。`readPixels` 返回后/flip 前/flip 后/float/save 的边界必须按 v2 保存；不要只存最终 PNG。
- **EGL/GL 限制**：`eglGetCurrentContext` 可读；`glGetError` 会清标志；`glCheckFramebufferStatus` 需有效 context/bound FBO；`mjr_readPixels` 本身无返回状态，必须靠 sentinel、context、error、正常对照组合，不能单凭颜色模式。v2 已覆盖。
- **sentinel 残留误判**：v2 明确单次残留不独立证明未写入；正确。健康判定仍以原始返回、context/error、正常对照和人工可辨认场景为主；不要把 sentinel 残留当唯一证据。
- **重复 worker**：两个独立进程、3 未修复 + 3 修复，足以判断固定状态/顺序下的可重复性；不足以证明所有视角/长期训练；v2 已写。不要再加样本。
- **更直接廉价替代**：没有既保留 raw/转换/保存区分、又能复验修复的更小方案；12 renders/24 readPixels/300s 已接近最小。不扩大。

## 科学边界

- 即使 `make_current` 修复成功，只证明该固定状态/构造顺序下的**局部直接机制**；触发源仍需事件链记录到某次 free/release/reset 前后 context 变化，不能仅凭 `eglReleaseThread` 存在归因。
- 当前坏图与旧训练 0/32 仍不能互证；旧训练 RGB/GL 历史缺失，最后一项可能永远 UNKNOWN。
- 不自动恢复原 32 前向/16 闭环；模型层检查另审；本轮仍不是论文结果，分类仍为 D/IMPLEMENTATION-LIMITED。
- 原执行结果已 fast-forward 到 `2d42000` 且 remote `ls-remote` 核实；这更新此前“未同步”的时间状态，旧记录保留，最终以 remote SHA/tree 为准。

**修订上述 1–4 后可执行；不增加范围，不重启原 execution，不训练。**
