# 基线状态

**NOT_ASSESSED_RESOURCE_BLOCK**。初始 flow、2 层 MLP、历史/额外标签匹配的加强 G 均未训练或加载；常数动作、仅当前历史、加入真实后继、K=1/K=4 与共同配对采样均 NOT_RUN。没有训练曲线、验证误差、后继信息增益或采样误差可报告。

尚未进入 0B，没有按 episode 分组、拟合 PCA、重建 scaler 或访问 cal/dev/test。`split_manifest.csv` 和 `training_curves.csv` 未生成，以免被误解为有已执行样本。协议保存了样本上限和隔离要求，未执行的数量/指标为 null 或 NOT_RUN。

资源不足不等同于 BASELINE-UNSUPPORTED 的拟合失败证据。不能据本次审计评价 ACID 的数值结果、原论文方法是否有效、U 的剩余价值、flow 与 MLP 的优劣或任何校正机制。没有弱 G 结果可用于支持结论。
