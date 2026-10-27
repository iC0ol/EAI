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
