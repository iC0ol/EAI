# Codex 独立验收：当前渲染异常，历史失败未定位

2026-10-29，主线程在读取本轮DeepSeek13验收意见前形成。只读执行代码、日志、保存的NPZ/PNG，并独立CPU重算；没有新模型前向、新env或新渲染。机器结果见[独立重算](../artifacts/parent_execution_audit.json)，复核代码见[scripts/verify_execution_cpu.py](../scripts/verify_execution_cpu.py)。

**接受受控停止和D/IMPLEMENTATION-LIMITED；不接受把当前损坏追认成旧0/32根因。** 这次完整度为PARTIAL，B/C未运行；科学根因仍未回答完整。

## 核验结果

- 8个NPZ全部文件哈希与176数组哈希一致；从dataset_image反转换的uint8与NPZ原RGB及PNG逐像素一致。损坏已经存在于保存张量，不能仅由PNG拼图脚本解释。
- 我实际看过sample0/4三入口拼图及旧dev1000初始PNG：前两者为明显彩色高频噪点/条纹，旧图能辨认机械臂、白平面和绿色物体。其余6个样本只做数组核对，不声称逐图视觉检查。
- 所有8样本三入口物理state、qpos、零外参token及6通道ray逐元素一致；RGB每组都不完全一致。sample0 Dataset–Evaluator有65532/65536像素不同、平均绝对差84.2766/255；部分样本只有7–9像素变化，但相近坏图不等于健康图像。
- 复算stage1起止为11.579582秒，与supervisor单调时钟记录11.579576秒相符；Stage0记录先于Stage1。计数全0，与main中输入失败return发生在ACTPolicy创建之前、无prediction/rollout文件相符。此为多项软件记录相互印证，不冒称硬件逐调用追踪。
- 独立重算6615旧文件大小/mtime/SHA无变化；冻结执行脚本SHA无变化；原worker/supervisor PID/start_ticks均不再存活；协议准确SHA保持不变。
- source provenance最初误取父Git HEAD及schema简写有明确补充纠正，原件保留；不把错误字段静默重写。375 tensor条目有限与stats bit equal是Stage0证据，不等于本轮完成了模型strict load。strict load实际NOT_RUN。

## 代码与替代解释

`execution/scripts/stage1.py:114–199`在一个make_env内，依次调用官方Dataset、Evaluator、自定义render，各自重新渲染；直到完成8份采集才检查总体输入门。`main:370–379`在门失败时返回，因此停止早于任何模型实例化/forward。冻结计划允许最多8份输入采集；本次没有额外重试、没有耗尽上限的义务。

关键局限：三路原始RGB不同，**同raw图像的预处理等价性没有被隔离验证**。非RGB相同支持部分接口一致，但不证明完整H1被排除。应把结果称为“当前渲染前提失败”，不能称“预处理bug已找到”。固定共同crop的slice/resize验证同样不证明3D射线对应真实像素。

保存路径使用float/255与rint*255，独立反解一致；官方和适配render都有flipud.copy，torch转float/CUDA后再保存，未看到足以确认本次坏图由PNG编码或单纯float缩放造成的证据。仍不能排除诊断wrapper、环境重置后GL上下文生命周期、读像素失败或共享底层状态。仅靠条纹形态不能定位驱动或framebuffer leak。

只读源码线索：固定RoboSuite `utils/binding_utils.py:165–170`先`np.empty`分配RGB，再`mjr_readPixels`；`MjRenderContext.__init__`调用make_current，`MjSim.render:1138–1141`中未显式每次make_current。当前日志没有GL framebuffer/error/current-context或readPixels写入成功的遥测。因此“读像素未覆盖未初始化缓冲”是可检验替代假设，**不是已经证实的机制**；不得据此修改系统、驱动或重训。

上游train.py对framebuffer有检查而旧自定义训练没有，已确认为源码差异；但旧训练RGB历史未保存，本次诊断又是另一次进程，不能由当前坏图证明旧训练也是坏图。旧开发代表图正常是对简单历史外推的反证，也不能反向证明全部历史训练健康。

## 科学与投入决定

- H1：新证据是当前视觉采集/同状态重复渲染前提失败；同raw预处理、模型输出数值等价仍未测。
- H2：没有prior/posterior误差，不能计算open-loop地板、断言后验捷径或训练未学会。
- H3：没有训练池/新相机闭环，本轮不能判断视角泛化。
- H4：stats、checkpoint元信息、日志覆盖得到加强核验；历史渲染、精确采集XML及RNG流差异仍未定因果。

不建议现在投入新完整ACT训练或F新方法。若人类要继续KYC，应该只授权一次**先只读、后极小渲染对照**的独立任务，检查context/readPixels是否真正写入、单一raw RGB三路预处理、同进程健康可重复图像；仍不得先训练。没有已验证修复时，暂停F是机会成本决定，宜转向有精确匹配官方策略checkpoint、任务数据、动作语义和环境版本且可快速证明任务阳性的系统。后续任务文本只是提案，不能用本次剩余GPU预算自动启动。

## 公开同步

执行者有本地结果与收尾commit，但两次HTTP408后远端未更新；不是已公开交付。主线程已接回Git index并继续处理。发布成功需用remote SHA与文件tree核验，不能凭push输出里的“Everything up-to-date”判断（该输出与exit1/408并存）。最终状态以主线程publication记录为准。
