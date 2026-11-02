# render_controlled

**TERMINAL / LOCAL_CONTROLLED_PASS_PENDING_REVIEW**

固定 sample0 的两条件受控释放验证已结束：baseline 在 A 的释放窗口损坏当前 B 的原 3 FBO/4 RBO 并解绑；fix 在 A context 释放后真实恢复活 B，B 原对象有效，after 与健康 before 精确一致。

2 workers、2 make_env、4 native renders、8 native readPixels，19.285659 GPU 分配秒。0 ACT、0 env.step、0 rollout、0 optimizer。CPU mock 30/30；保存结果核对 85/85，20 个转换边界比较精确一致。295 个旧证据文件未变，执行进程均已退出。

这是执行端局部结论，等待主审独立数组/代码/实际看图及真实 DeepSeek 验收。非自然 GC 复现；没有长期、多视角或线程稳定性证明。旧 0/32 根因 UNKNOWN。Git index 及公开同步归主审，执行端不做 Git 写入。详见 FINAL_REPORT.md、analysis.json、integrity_after.json；自动检查与单次回传以 closure/receipt 原件为准。
