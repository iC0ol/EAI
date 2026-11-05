**一、撤回 38 的错误判断**

我确认：我在 38 中称“`env.reset` 不重建 `MjRenderContext`”，这是错误的，我撤回该说法。`base.py:83-84,104` 显示 `hard_reset=True` 是默认值，`:136` 显示 `deterministic_reset=False`；`:261-284` 在默认路径下调用 `_load_model`/`_initialize_sim`，`:239-253` 创建新的 `MjSim`，随后 `:319-340` 在新 sim 没有 offscreen context 时创建 `MjRenderContextOffscreen`。`parent_initial_source_data_audit.json:14-42` 的 HDF5 `env_kwargs` 没有覆盖 `hard_reset`/`deterministic_reset`，因此默认 `env.reset()` **会重建 model/sim/render context**。我此前的判断未被代码支持。

但仍保留两点：官方 `train.py:102-105,163-166` 只检查当前绑定的 `GL_FRAMEBUFFER`，未绑定、未查询 `offFBO`，也没有 `glGetError`，且只在 epoch 边界调用 `env.reset()`；它不能证明所有读回健康，也不能保证消除历史故障。更关键的是，默认 hard reset 会重新随机化 LiftRand 几何；C 的 guard 路径因此不是只做“FBO 修复”，而是同时换 model/sim/context/场景，健康和几何变化会混淆。`reset_from_xml_string` 走 deterministic 路径（`base.py:614-633`），与官方 guard 的 `env.reset()` 不同；A/B 应使用前者，并记录 XML/state/T/geometry。

**二、与 notes/01、02 的交叉**

- 同意：旧 20% MAE 门不适用于本轮；A4+B8、各≤150 步、真实 `reset_root`、A 通过前 policy 前向为 0、C 两臂真实 `getItem→crop→default_collate` 张量证据、12 条轨迹上限、900s 硬上限；旧 dev1000 初始 PNG 主审记录正常，已知坏图主要来自后续诊断路径，历史因果严格限定；论文 60.6% 是多 seed/多 checkpoint/1500 rollout 汇总，不能泛化到本轮 4 root。
- 同意 notes/01：A 完整使用 105/102/126/97 共 430 个原始动作，不增补/平滑；B 为 8 条 ×≤150 步/5 块，总 1200 步/40 ACT；A/B 使用同一成功判据，并同时记录 `reward==1` 与 `_check_success`；A 失败或两者不一致即停止 B 归因；eef_delta 按原 wrapper 累加，不改旋转语义；初态 model/state 精确匹配优先于 RGB；不同相机不要求同图。
- 同意 notes/02 的两项追加：A 必须用本轮真实 `reset_from_xml_string`+state+`set_init_action`，不能引用旧直接 `set_state` 回放；C 只复现坏 raw 不够，必须证明坏图进入 crop 后、`default_collate` 后、模型前的 image。
- 我加严两点：①官方 guard 的 hard reset 可能改变 LiftRand 几何，C 必须保存 model/geometry/XML/state/T 摘要，不能把图像变好直接归因于 FBO 修复；②训练实际是单个 `make_env(0)` 环境服务 200 个 demo，HDF5 无逐 demo XML，且 demo 状态来自不同生成场景；训练图像与该示教原始物理场景是否匹配仍是未解混淆，C 应检查 model/cube geometry 与 state 的对应，不只查 FBO。否则“训练输入污染”可能来自场景错配，而非 RGB 损坏。

**三、交给执行者的必需代码条件**

1. 冻结 demo0..3、`make_env(42+i)`、`states[0]` 的 XML/state/controller 初始目标/RNG 及 SHA；明确 `per_demo_XML_present=false`，不得称原示教场景完全重建。
2. A 与 B 共用同一个 `reset_root`（`reset_from_xml_string`+state+forward+`set_init_action`+RNG+相机）；A 阶段 0 ACT/policy 前向；任一专家失败或成功判据不一致，停止 B 归因，不筛 root。
3. B 仅 4 个替代 root × train 相机 i+1 与旧 dev 1000+i 的 **T**；8 条、≤150 步/5 块；不得称旧 dev 物理 root；逐条记录 success/reach/grasp、EEF/物体/夹爪、delta 与底层绝对目标、reward、预测与实际执行前缀；不得事后挑 root/相机。
4. C 两臂：无 guard 的原本地生命周期、官方 guard 路径；固定输入/RNG；真实 `EpisodicDataset`（`transform='crop'`）→raw/crop 参数/crop 后 tensor→`default_collate` 后模型前 image；记录 XML/geometry/state/T/FBO/EGL；不得强制析构/释放，未触发记 NOT_REPRODUCED。
5. 900s 整轮硬上限，含预检/初始化/失败/清理；0 训练/backward/optimizer；CPU≤3、RSS≤16GiB、整卡 VRAM≤12GiB、输出≤150MiB；单 GPU；失败即停，不扩预算。
6. 上述为候选必须满足的条件；在未见集成候选、真实 CPU 预检及精确 SHA 双审前，**不批准任何 GPU/RUN**。本意见不重复整篇源码审查，也不把论文 60.6% 当作本轮四 root 的预期或门槛。
