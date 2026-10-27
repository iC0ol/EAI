# U v3 决定

**NO-GO-CURRENT-SCOPE**

执行收尾原因：COMPLETE。

U*=B2，对照=B0；mean R=0.490942499 / 0.50219452；mean J=15.2613241 / 15.3070404。R 改善（对照−U）=0.0112520208，95% CI=[0.0, 0.027098187140289803]；原 J 同方向差=0.0457163794，95% CI=[0.0, 0.12130536085772708]。完整精度及逐 root 差在 summary.json / CSV。

0 independent test roots have auditable harmful B1 flips. Paired intervention on frozen shared candidate pools is compared to dev-selected B0, with history/extra-label matched B4 and B6 controls. Real-domain residuals, F error, and d_G are recorded per candidate; no causal/off-manifold decomposition is identified. Benefit supported/unclipped selection counts: {'improved_roots': 3, 'U_supported_and_unclipped_improved_roots': 3, 'both_selected_supported_unclipped_improved_roots': 1}. Block-only improvement point: 0.018190047730830827.

结论仅限预登记的单模型、单训练 seed、短时共享候选池选择。完整结果见 morning_report.md 与 summary.json；停止等待研究者复审，不自动继续 U1。

补充解释：B2在全部64test上与B1选中项完全相同，没有可归于常数校正的新增选择收益；dev/test有害B1翻转均为0。NO-GO只排除本次已冻结候选/λ/短期诊断所要求的≥.05实用改善，不否定所有条件偏差模型。B3存在cal-val特征外推放大，详见delivery_validation.json；test未重用、未调参、未补样。
