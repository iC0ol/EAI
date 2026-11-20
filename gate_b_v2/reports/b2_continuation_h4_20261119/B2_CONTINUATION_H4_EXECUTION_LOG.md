# B2 Continuation-h4 执行记录

运行标识 `b2_continuation_h4_20261119T170545`。实验入口提交 `da312b79e5f2997c7e53c84b95cdd7c96d7e27c8` 基于已发布的 B2 Confirmation `6d2165418c84b5300eb9a041df56ebf39218da4a`。工作站使用原隔离环境，输入来自核验通过的原 Confirmation 运行目录。 [诊断运行清单](b2_continuation_h4_run.json)

| 时间（Asia/Shanghai） | 操作与读回 |
|---|---|
| 2026-11-19 启动前 | 完整工程测试 299 项通过。诊断 `--check-source` 验证原始 111 项 SHA256、原授权及运行指纹、30 个快照引用和 450 个原分支。Launcher 通过 `bash -n`。 |
| 2026-11-19 17:05:45 | 使用 `nohup setsid bash` 启动独立 Launcher，PID 2656790。诊断 Worker PID 2656806。并行保存约每 30 秒的 GPU 读数。 |
| 2026-11-19 17:05:56 | Worker 复核原始数据和运行环境通过，进入原快照恢复验证。 |
| 2026-11-19 17:09:19 | 30/30 个原快照通过活体恢复验证。首条诊断 Branch 于 17:09:20 开始。 |
| 2026-11-19 17:13:54 | 前两条 Branch 已写入并通过读回，第 3 条运行。根据 164 次策略调用的实际用时预测次日约 06:55 结束。 |
| 2026-11-20 06:45:42 | 第 450 条记录写出，Worker 完成 450 条 Branch 完整性校验和原始证据 SHA256 重验，状态为 `COMPLETE`。 |
| 2026-11-20 06:45:44–06:45:45 | Worker 与 Launcher 先后以退出码 0 结束，GPU 监测保存 1,640 项样本。 |
| 2026-11-20 收尾 | 复核原始 111 项及诊断原始 10 项 SHA256，30 个快照、450 个配对键、实际行序和共享策略调用索引的噪声种子均匹配。使用独立计数和精确枚举复核总体、短首次交互和联合交互 p 值。 |
| 2026-11-20 发布验收 | 新增测试最初与已有测试同名，改用唯一文件名后重跑。完整回归与诊断测试 **305 项通过**，原冻结分析用例有一条已知的 SciPy 常量输入警告。公开输入复算与工作站分析一致。 |

工作站保管原 Runner 日志和原始快照文件。原始诊断 Branch、运行清单和活体验证的 SHA256 记录在完整性回执。公开版保留这些数据的字节和路径关系。 [完整性回执](b2_continuation_h4_integrity.json) · [发布清单](PUBLICATION_MANIFEST.json)

从本仓库的 Gate B 项目目录运行下列命令可复算已发布分析。脚本读取沿用的公开 Confirmation Branch，其 SHA256 与本次配对使用的原机文件一致。

```bash
source scripts/gateb_env.sh
python -B -m pytest -q tests diagnostics/continuation_h4
bash -n diagnostics/continuation_h4/launch_b2_continuation_h4.sh
python -B diagnostics/continuation_h4/analyze_b2_continuation_h4.py \
  --run-dir reports/b2_continuation_h4_20261119 \
  | cmp - reports/b2_continuation_h4_20261119/b2_continuation_h4_analysis.json
(cd reports/b2_continuation_h4_20261119 && sha256sum --check SHA256SUMS)
```

[冻结 B2 Confirmation 状态](../b2_confirmation_20261118/README.md) · [本次诊断报告](B2_CONTINUATION_H4_DIAGNOSTIC_REPORT.md)
