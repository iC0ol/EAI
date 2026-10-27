# preflight

NOT_RUN / 阶段未完成：RuntimeError: STAGE_FAILED_decompress_EXIT_1 Traceback (most recent call last):
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
。没有据此作科学否定。
