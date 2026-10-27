# U v3 决定

**TECHNICAL-BLOCK-AFTER-REPAIR**

执行收尾原因：RuntimeError: STAGE_FAILED_semantics_EXIT_1 Traceback (most recent call last):
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
。

NOT_RUN：RuntimeError: STAGE_FAILED_semantics_EXIT_1 Traceback (most recent call last):
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


未完成有效比较；没有据此作算法负结论。

结论仅限预登记的单模型、单训练 seed、短时共享候选池选择。完整结果见 morning_report.md 与 summary.json；停止等待研究者复审，不自动继续 U1。
