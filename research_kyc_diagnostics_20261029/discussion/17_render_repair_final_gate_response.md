# v3 最终审查

## 结论

**APPROVE。**

v3 已解决 16 的实质阻碍：

- **锁与插点**：明确保持 `MjSim.render` 原持锁逻辑，窄包装未绑定的 `MjRenderContext.render`；wrapper 自身不加锁，绑定后调用原函数，并在 render 后/read 前检查 context；不匹配即保存停止，不重复绑定。避免了外层重复获取非重入 `_MjSim_render_lock` 的死锁。
- **sentinel**：正常 `read_pixels`/`np.empty` 完全不变；正常原始读回并复制 raw 后，独立 `np.full((256,256,3),165,uint8)`，用同一 viewport/con、`depth=None` 再调一次原 `mjr_readPixels`；独立计数、独立保存，不进入正常 pipeline/健康判定；不 patch 全局 `np.empty`、不填正常 rgb。该方案能测同帧 readback 是否覆盖，且不污染 baseline。
- **预算**：每 render 最多 2 次 readPixels（正常 + sentinel），12 renders/24 readPixels 自洽；sentinel 经同一持久计数 hook，不能绕过。
- **GL**：固定查询顺序，明确 `glGetError` 会清标志、查询本身可能产生 error；8 次仍未 `NO_ERROR` 记 `GL_ERROR_NOT_DRAINED` 与最后错误码，不把次数耗尽当健康。
- **进程隔离**：两个独立 OS/Python 进程，先退出再启动；记录 worker1 退出码/退出时间并断言早于 worker2 创建；不 fork 继承 CUDA/EGL。
- **日志**：primitive/匿名 ID/weakref，不持 env/sim/context/scene/buffer 强引用；保留未绑定原方法；记录拷贝/分配可能改变 GC 时序。
- **科学边界**：当前修复只证明固定状态/顺序下的局部机制；触发源需事件链；旧训练 0/32 仍不能追认；不恢复原 32 前向/16 闭环；不训练、不 ACT、不 env.step。

## 两条非阻塞实现注记

1. **sentinel 对照方向**：sentinel 是原始 readback，应与**同帧 pre-flip raw 拷贝**比较残留，不要与 flip 后或保存 PNG 比较；否则上下翻转会被误读为残留/覆盖。
2. **sentinel 时序**：sentinel 应在该次 `read_pixels` 返回前、原 `MjSim.render` 锁仍持有时完成；v3 §3 已写，执行时在代码审计中明确。额外 `np.full` 的分配/GC 扰动已作为限制保留，不因此重试或改 sentinel 值。

这两点不改变范围，不需要再改协议文本即可执行；若执行者选择在代码注释/审计中写明即可。

## 范围与授权

批准执行：**2 个独立 worker、≤12 底层 render、≤24 readPixels、≤300 GPU 秒、0 ACT/0 env.step/0 rollout/0 optimizer**；仅写 `render_repair/`，不重启原 `execution/`，不改旧源码/环境/驱动。用户已明确授权本次故障定位与局部修复；本批准不包含完整训练、模型前向或正式 test。

## 最终分类与状态

- 当前证据分类仍为 **D / IMPLEMENTATION-LIMITED**；本微诊断不是论文结果，也不把旧 0/32 改写成已定位。
- 原执行结果已 fast-forward 到 `2d42000` 且 remote `ls-remote` 已核实；此前“未同步”状态据此更新，最终发布以 remote SHA/tree 为准，旧记录保留。

**APPROVE；可冻结 v3 SHA 并派发给现有 gpt-6.1-sol/max 在全新 `render_repair/` 单独运行。**
