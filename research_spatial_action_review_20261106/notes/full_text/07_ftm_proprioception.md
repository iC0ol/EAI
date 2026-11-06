# FTM/FLA 2512.02902 + Proprioception 2608.03052

## 2512.02902 VLA Models Are More Generalizable Than You Think

- 作者：Weiqi Li 等 5 人；v2，2026-03-31
- 来源：<https://arxiv.org/abs/2512.02902>；本地全文 `papers/2512.02902__vla_more_generalizable.txt`
- 读取层级：方法 + Table（Fig. 1b 对应表）+ §4

关键（逐格核对）：
- Camera Viewpoints 列：π0.5 **Zero-Shot 48.5**；π0.5 One-Shot LoRA 90.3；π0.5 One-Shot FTM 87.2（4K 参数）；π0.5 One-Shot FLA 90.8（4.7M 参数）。π0 LoRA 83.6。
- 因此 48.5 是**零样本**，不是"π0.5 LoRA"；90.8 是 FLA（4.7M），不是 4K 的 FTM（87.2）。
- 方法性质：**测试时 one-shot 适配**，"requires only a single human demonstration per task to adapt to the new visual domain"（§4.1）。
- 解释：跨视角脆弱性主要在视觉表征，轻量重标定即可恢复大部分。

对本复审：
- 它不能直接反驳"训练期空间表征升级"，因为它解决的是"有目标域示范后的快速适配"。两者干预点、数据预算、部署假设都不同。
- 但它是一个必须设置的强对照：任何训练期方法若在同等目标数据下不如 4K 参数的 FTM，则其"表征"主张不成立。
- 上轮对数字的引用基本准确：4K FTM 87.1（摘要）/87.2（表），4.7M FLA 90.8，π0.5 LoRA 90.3；仅 87.1/87.2 为四舍五入差异。上轮的真正问题不是数字，而是把它当作"训练期表征升级"的反例。

## 2608.03052 How Should VLAs Use Proprioceptive State?

- 作者：Yiren Zhao 等 8 人；arXiv v1，2026-08-04
- 来源：<https://arxiv.org/abs/2608.03052>；本地全文 `papers/2608.03052__how_vla_use_proprioceptive_state.txt`
- 读取层级：引言 + 贡献 + 方法概览（未读全部 45 任务结果表）

关键：
- 固定 backbone、训练数据、动作表示、评估协议；只变 state 接口（5 种）、history 长度（1–96）、注入位置。
- 45 个原子任务（3 个 task family）+ 20 个复合任务。
- 结论包括："There is no task-agnostic best interface."；短 history 有益，长 raw history 可能有害；优选入口随 temporal budget 改变。
- 规模：flow-matching VLA + RoboCasa365，远超单卡 3090 硕士可复现范围。

对本复审：
- 这是"受控任务族研究"的最强范式先例，也是任何"哪类任务受益"研究的直接竞争。
- 它只研究 state，不研究空间观测精度；因此不覆盖"空间精度收益异质性"，但审稿人会说"这是同一问题换输入"。
