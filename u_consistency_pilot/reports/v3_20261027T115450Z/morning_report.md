# U v3 夜间运行交付

**TECHNICAL-BLOCK-AFTER-REPAIR**。run_id `20261027T115450Z`。

1. 实际完成阶段：assets, decompress。cal: 0 roots/0 sources；dev: 0 roots/0 sources；test: 0 roots/0 sources。完整 test：False；IDM 各 split 来源数：NOT_RUN。
2. NOT_RUN：RuntimeError: STAGE_FAILED_semantics_EXIT_1 Traceback (most recent call last):
  File "$EAI/u_consistency_pilot/scripts/u_stage_v3.py", line 577, in <module>
    if __name__=='__main__':main()
                            ^^^^^^
  File "$EAI/u_consistency_pilot/scripts/u_stage_v3.py", line 574, in main
    try:mapping[STAGE]()
        ^^^^^^^^^^^^^^^^
  File "$EAI/u_consistency_pilot/scripts/u_stage_v3.py", line 170, in semantics
    data=H5Data();s=compute_action_scaler(data);F=FrozenF();relative=s['relative']
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "$EAI/u_consistency_pilot/scripts/u_stage_v3.py", line 108, in compute_action_scaler
    if not relative and not (amin.min()>=0 and amax.max()<=512.0001):raise RuntimeError('ACTION_UNITS_UNRESOLVED')
                                                                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
RuntimeError: ACTION_UNITS_UNRESOLVED

3. 候选误罚、强 G 和打乱标签证据：NOT_RUN；未完成有效比较，不能解释为算法负结果。初始基线状态：NOT_RUN。
4. 墙钟 5.1239 h；GPU 进程占用上界 183.595561303664 秒；下载预算计数 14089613322 B（包含早期 pip 不完整计量的保守预留）。实测 RSS 合计峰值 1625194496 B，采样任务 VRAM 峰值 759169024 B；磁盘分配峰值 66567041024 B；下载错误事件 2。后台占用、Torch 内部显存 watermark、前缀/积分步和全部修复见 budget.json / repairs.jsonl。监护前 CPU 准备峰值未完整采样，不冒充全程精确峰值。
5. 结论范围：单个冻结 LeWM、单一训练 seed、5 控制步共享候选选择。未做 U1、Cube、闭环、多任务或大模型训练；下一步仅为研究者复审当前证据。

| split | 独立 roots | 独立 sources | 有效候选记录 | 目标 roots |
|---|---:|---:|---:|---:|
| cal | 0 | 0 | 0 | 32 |
| dev | 0 | 0 | 0 | 16 |
| test | 0 | 0 | 0 | 64 |

停止/完成原因：RuntimeError: STAGE_FAILED_semantics_EXIT_1 Traceback (most recent call last):
  File "$EAI/u_consistency_pilot/scripts/u_stage_v3.py", line 577, in <module>
    if __name__=='__main__':main()
                            ^^^^^^
  File "$EAI/u_consistency_pilot/scripts/u_stage_v3.py", line 574, in main
    try:mapping[STAGE]()
        ^^^^^^^^^^^^^^^^
  File "$EAI/u_consistency_pilot/scripts/u_stage_v3.py", line 170, in semantics
    data=H5Data();s=compute_action_scaler(data);F=FrozenF();relative=s['relative']
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "$EAI/u_consistency_pilot/scripts/u_stage_v3.py", line 108, in compute_action_scaler
    if not relative and not (amin.min()>=0 and amax.max()<=512.0001):raise RuntimeError('ACTION_UNITS_UNRESOLVED')
                                                                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
RuntimeError: ACTION_UNITS_UNRESOLVED
。缺失项不填 0；上表的 0 只表示实际不存在的已执行记录。研究数值见逐 root 表，候选评分与真实结果在不同文件。
