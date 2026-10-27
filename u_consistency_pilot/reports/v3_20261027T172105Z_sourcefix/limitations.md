# 局限

- One initial flow training seed
- Endpoint inverse mapping can be nonunique
- PCA16 may discard conditional bias information
- F pretrained on original public distribution
- Nearest-action support is a proxy
- Official reset goals may be difficult in five control steps; uninformative pools retained

后验 d_F/d_G 和恒等式不构成因果分解。O 非部署评分或严格上界。没有 U1、Cube、额外容量 sweep 或测试后补采。完整精度逐 root / candidate 记录独立保存，未运行项用 null/NOT_RUN。


<!-- V3_REPRESENTATION_FINAL -->
PCA16保留训练latent方差比例为0.25040159095078707，低维历史可能丢失校正信息；失败不能排除所有条件偏差模型。源隔离使用185种精确初始状态家族作为保守代理（148/18/19分组），未声称识别了全部原始采集谱系。前序cache在G训练前作废，所有预算自原T0累计。λ敏感性、图表/视频、额外容量、多训练seed、闭环、U1和Cube均NOT_RUN。

额外实测限制：全部方法64test success均0；B2与B1选择完全相同。cal-fit过去动作特征近常量，cal-val标准化最大439σ，B3/B6残差预测明显失效；已验证存储参数的前向结果一致，没有测试后修改标准化/正则。此结果不能排除采用不同预登记表示/尺度的条件校准。工程早期计数的重建与GPU短上下文保守预留单列，未冒充全程无缺口的精确遥测。
