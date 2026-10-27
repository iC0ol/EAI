# U v3 决定

**TECHNICAL-BLOCK-AFTER-REPAIR**

执行收尾原因：RuntimeError: STAGE_FAILED_decompress_EXIT_1 Traceback (most recent call last):
  File "$EAI/u_consistency_pilot/scripts/u_stage_v3.py", line 575, in <module>
    if __name__=='__main__':main()
                            ^^^^^^
  File "$EAI/u_consistency_pilot/scripts/u_stage_v3.py", line 572, in main
    try:mapping[STAGE]()
        ^^^^^^^^^^^^^^^^
  File "$EAI/u_consistency_pilot/scripts/u_stage_v3.py", line 81, in decompress
    b=reader.read(16*1024*1024)
      ^^^^^^^^^^^^^^^^^^^^^^^^^
zstd.ZstdError: zstd decompress error: Frame requires too much memory for decoding
。

NOT_RUN：RuntimeError: STAGE_FAILED_decompress_EXIT_1 Traceback (most recent call last):
  File "$EAI/u_consistency_pilot/scripts/u_stage_v3.py", line 575, in <module>
    if __name__=='__main__':main()
                            ^^^^^^
  File "$EAI/u_consistency_pilot/scripts/u_stage_v3.py", line 572, in main
    try:mapping[STAGE]()
        ^^^^^^^^^^^^^^^^
  File "$EAI/u_consistency_pilot/scripts/u_stage_v3.py", line 81, in decompress
    b=reader.read(16*1024*1024)
      ^^^^^^^^^^^^^^^^^^^^^^^^^
zstd.ZstdError: zstd decompress error: Frame requires too much memory for decoding


未完成有效比较；没有据此作算法负结论。

结论仅限预登记的单模型、单训练 seed、短时共享候选池选择。完整结果见 morning_report.md 与 summary.json；停止等待研究者复审，不自动继续 U1。
