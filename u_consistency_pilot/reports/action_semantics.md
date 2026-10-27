# 动作与时间语义：尚未验收

资源门阻塞，本报告区分研究者提供的目标接口与本机实测。没有用 DP 的 PushT 接口填补 LeWM 的空缺。

| 项目 | 研究者指定/要求 | 本机状态 |
|---|---|---|
| F | 冻结，strict load 无 missing/unexpected | NOT_RUN，未定位指定权重 |
| 历史与动作 | history=3，frame skip=5，input_dim=10，块形状 5×2 | 来自指令；非加载后打印 |
| 当前/后继索引 | 真实 5 步端点必须对应 F | NOT_RUN，无真实索引表 |
| flatten | 必须保留 5 个 2 维动作顺序 | NOT_VERIFIED，不假定 time-major 或坐标顺序 |
| 单位/绝对相对/裁剪/频率 | 需读取固定源码并实测 | NOT_VERIFIED |
| 图像和 latent | 固定编码/色序/latent 来源 | NOT_RUN |
| scaler | 匹配原训练数据或可信缓存 | NOT_RUN，不能用 dev/test 或小数据重估 |
| 状态分支 | 固定 seed 新建环境，完整前缀重放 | NOT_RUN；未调用 _set_state |
| 重复容忍 | 状态差 ≤1e-6，图像逐像素相同 | 配置中预先记录，未观测任何差值 |
| δ_J | max(1e-3,10×工程重复最大 J 差) | NOT_RUN，数值 null |
| J/success | 固定官方联合位置/周期角误差及阈值 | NOT_VERIFIED，τ 和 goal 尚未冻结 |

研究者指出 eval 使用 StandardScaler，train helper 使用 torch.std。本次没有本地匹配源码/样本进行比对，未声称量化成功。若同一组 n 个有限样本只差 ddof=0 与 ddof=1，则标准差比例为 sqrt(n/(n−1))；这只是代数关系，**不是本数据的观测差异**，不决定采用路径。mean/std、样本数、NaN、ddof 源码位置和实际差异全部未获得。

G 不允许读取 F 未预测的微步未来图像或把候选 A 当作输入；候选 A 仅允许进入指定的 b(H,A)。端点到动作块可能多解，不会仅因此判技术失败。当前也没有任何逆映射唯一性或 MSE 硬阈值结论。

在缺少权重、训练统计和可信接口时打印推测索引表会造成假验收，因此此处只登记未执行项。`replay_check.csv` 为仅表头的空结果表，没有把缺失数值填为零。
