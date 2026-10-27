# U v3 夜间运行交付

**NO-GO-CURRENT-SCOPE**。run_id `20261027T172105Z_sourcefix`。

1. 实际完成阶段：assets, decompress, semantics, prepare, train, cal_collect, cal_fit, score_dev, execute_dev, analyze_dev, seal_test, score_test, execute_test, analyze_test。cal: 32 roots/32 sources；dev: 16 roots/16 sources；test: 64 roots/64 sources。完整 test：True；IDM 各 split 来源数：{'train': 148, 'val': 18, 'audit': 19}。
2. U*=B2，对照=B0；mean R=0.490942499 / 0.50219452；mean J=15.2613241 / 15.3070404。R 改善（对照−U）=0.0112520208，95% CI=[0.0, 0.027098187140289803]；原 J 同方向差=0.0457163794，95% CI=[0.0, 0.12130536085772708]。完整精度及逐 root 差在 summary.json / CSV。
3. 候选误罚、强 G 和打乱标签证据：0 independent test roots have auditable harmful B1 flips. Paired intervention on frozen shared candidate pools is compared to dev-selected B0, with history/extra-label matched B4 and B6 controls. Real-domain residuals, F error, and d_G are recorded per candidate; no causal/off-manifold decomposition is identified. Benefit supported/unclipped selection counts: {'improved_roots': 3, 'U_supported_and_unclipped_improved_roots': 3, 'both_selected_supported_unclipped_improved_roots': 1}. Block-only improvement point: 0.018190047730830827.。初始基线状态：PASS。
4. 墙钟 6.1480 h；GPU 进程占用上界 3024.6752324481495 秒；下载预算计数 14089613322 B（包含早期 pip 不完整计量的保守预留）。实测 RSS 合计峰值 1977999360 B，采样任务 VRAM 峰值 759169024 B；磁盘分配峰值 67090026496 B；下载错误事件 229。后台占用、Torch 内部显存 watermark、前缀/积分步和全部修复见 budget.json / repairs.jsonl。监护前 CPU 准备峰值未完整采样，不冒充全程精确峰值。
5. 结论范围：单个冻结 LeWM、单一训练 seed、5 控制步共享候选选择。未做 U1、Cube、闭环、多任务或大模型训练；下一步仅为研究者复审当前证据。

| split | 独立 roots | 独立 sources | 有效候选记录 | 目标 roots |
|---|---:|---:|---:|---:|
| cal | 32 | 32 | 256 | 32 |
| dev | 16 | 16 | 128 | 16 |
| test | 64 | 64 | 512 | 64 |

停止/完成原因：COMPLETE。缺失项不填 0；上表的 0 只表示实际不存在的已执行记录。研究数值见逐 root 表，候选评分与真实结果在不同文件。
