# U v3 0A

PASS：真实 strict 加载、CUDA、编码、一步预测、headless PushT 与工程重复通过。

动作/原始时间索引和 scaler 见 semantics.json / action_scaler.json；每个块是五个二维控制动作。J 在每个被评价状态均和固定源码官方 success 比较；没有把 MSE 用作任务指标。

只绕过可选包的 __init__ 导入，未修改物理源码；HDF5 只读 adapter 保留原样本/时间语义，未转 Lance。框架原 4-observation clip 覆盖 20 microsteps；F 使用前三个 leaving blocks，最后未用 future block 不进入 G。

所有实验环境在 EAI/U 内，外部既有环境只读取并复制必要 torch 二进制；未升级原环境、系统 Python、CUDA、驱动或 ROS。工程重复是本机有限检查，不是全域确定性证明。
