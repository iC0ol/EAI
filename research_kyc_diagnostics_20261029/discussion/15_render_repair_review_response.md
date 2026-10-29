# 渲染微诊断协议审查

## 结论

**APPROVE_WITH_REQUIRED_CHANGES。**

协议方向正确：只查当前 RGB 损坏的进入路径，不把当前坏图追认成旧训练 0/32；12 次底层 render、24 次 readPixels、2 个 worker、300 GPU 秒、0 ACT/0 env.step/0 训练，范围足够小。先只读、后最小修复、第二 worker 复验，符合机会成本原则。

但协议在“插桩本身不扰动 baseline”“两个 worker 真正独立”“sentinel 与健康判定分离”“修复覆盖完整 render+readPixels 锁区”四处还不够明确，必须修订后才能执行。

## 源码事实

- `vendor/robosuite/robosuite/utils/binding_utils.py:165-170`：`read_pixels` 先 `np.empty((H,W,3), uint8)`，再 `mjr_readPixels`；若读取未写入，未初始化内容会成为噪点。这是可检验假说，不是已发生事实。
- 同文件 `:80-82`：`MjRenderContext.__init__` 调用一次 `gl_ctx.make_current()`。
- 同文件 `:1104-1141`：`MjSim.render` 在 `_MjSim_render_lock` 内执行 `render` + `read_pixels`，**没有逐次 make_current**。
- `egl_context.py:144-152`：`free()` 只在当前 context 是自己时才 unbind，但随后**无条件 `eglReleaseThread()`**。
- `binding_utils.py:1181-1188`：`MjSim.free()` 删除 render context/data/model 后 `gc.collect()`。

这些只支持“context 丢失/readPixels 未写入/数组所有权”三类机制线索；没有 GL status/error/current-context/readback 事件链，不能归因。

## 必改项

1. **§2 插桩不得持有对象引用。** 事件日志只能存 primitive、匿名 ID、weakref/地址代号；不得在全局日志中保存 `env`、`MjSim`、`MjRenderContext`、`EGLGLContext`、scene 或 numpy buffer 的强引用。否则会改变 `__del__`/`gc.collect`/`EGLGLContext.free` 时机，插桩本身可能“修好”或恶化 baseline。日志必须在 close/free 前释放。
2. **§2/§4 两个 worker 必须是独立 OS 进程。** 每个 worker 新 Python、新 EGL thread/context、新 env；不能在同一进程内复用第一个 worker 的 context，也不能让第一个 worker 的 `eglReleaseThread`/GC 影响第二个。记录 PID/start_ticks、context 匿名 ID、创建/释放顺序。否则“第二 worker 复验”不是独立复验。
3. **§2 sentinel 必须与健康判定分离。** 每帧最多一次 sentinel 预填的 readPixels，必须单独标注、单独保存；不得把 sentinel 输出当正常图像，也不得因 sentinel 残留直接判“未写入”。必须同时报告原始返回、context/GL 状态、正常对照和 sentinel 残留比例；无有效 context 时禁止只凭颜色模式宣判。原始 `readPixels 返回后、flip 前、flip 后、float tensor、保存数组` 必须是独立拷贝，不能共享同一 buffer。
4. **§3 make_current 修复必须覆盖完整 `render + read_pixels` 锁区。** 只在 `read_pixels` 前绑定、或只在 `render` 前绑定，都可能在中途再次丢失；修复应包住 `MjSim.render` 的整段 `_MjSim_render_lock`，且不改变 camera/state/参数。若 context 仍不匹配或修复后仍坏，停止，不换第二种猜测。
5. **§2 GL 查询顺序要写死。** `glGetError` 会清除错误标志；必须先读当前 context/ framebuffer status，再按固定顺序清空并记录 error，不能把“查询后无错误”当无故障。无有效 context 时跳过 GL 查询并标记，不得为查询自动 `make_current`。
6. **§1 预算计数要覆盖隐式调用。** `make_env`/初始化/`env.reset`/`free` 中的隐式 render/readPixels 也计；若初始化已消耗预算，按 §1 减计划并标 PARTIAL，不免费补。supervisor 必须在调用前持久计数，不能只靠日志事后统计。

## 设计是否会自己修好/扰动 baseline

- 基线阶段不调用 `make_current`、不重建 context、不复制/改写数组；只读日志和独立拷贝。方向正确。
- 但若日志持有对象、或 sentinel 预填影响 `np.empty` 的全局行为，可能改变 GC/context 生命周期；上述必改项 1、3 是为此。
- 两个独立进程可避免第一个 worker 的 `eglReleaseThread`/`gc.collect` 污染第二个；必改项 2。
- sentinel 只增加 readPixels、不增加 render，不会直接修好渲染；但若它改变了 buffer 初始化，必须把 sentinel 结果从健康判定中剥离。

## 重复 worker 是否够

两个 worker、每个 3 次未修复 + 3 次同一修复，足以判断**固定状态/固定构造顺序**下故障是否可重复、修复是否可重复；不足以证明所有视角、长时间训练或旧 0/32。协议已写“机制重复，不是独立任务样本”，正确。不要为统计功效增加 worker/样本。

## 更直接廉价的替代

没有明显更便宜且能保留“raw vs 转换 vs 保存 + context/readPixels”区分度的替代。单 worker 一次 render 只能看到现象，不能复验修复；当前 12 render/24 readPixels/300s 已接近最小。不要扩大。

## 科学边界

- 若 `make_current` 修复，只能证明**该固定状态/构造顺序下的局部直接机制**；触发源仍需事件链（某次 free/release/reset 前后 context 变化）才能归因；不能仅凭 `eglReleaseThread` 存在推断。
- 即使两个 worker 都复现并修复，也不能证明旧训练 RGB 健康或旧 0/32 根因；旧历史缺失，最后一项可能永远 UNKNOWN。
- 不能自动恢复原 32 前向/16 闭环；模型层检查另审。当前分类仍是 **D/IMPLEMENTATION-LIMITED**，本协议只是故障定位，不是论文结果。
- 新信息：原执行结果已按 Git 对象 fast-forward 到 `2d42000`，remote `ls-remote` 已核实；这更新此前“公开同步未完成”的状态，旧记录保留；最终发布仍以 remote SHA/tree 为准。

## 最终

**APPROVE_WITH_REQUIRED_CHANGES**：按上述 1–6 修订后方可派发；不增加样本/worker；不训练、不 ACT、不 env.step。修订后请再送核验，当前不是执行授权。
