# Phase 3.6 基础空间能力控制实验

本目录属于研究者新授权的 Phase 3.6。历史 README/AGENTS 中的停止位置保留为历史记录；本轮只新增文件，完成后再次停止。
主报告为 [phase3_6_diagnostic.md](phase3_6_diagnostic.md)。不训练、不更换模型、不更新环境。

新增文件结构：

```text
configs/phase3_6.yaml                       # 模型参数沿用 3.5，独立几何与生成种子
prompts/phase3_6/                          # 原 poststate-reach-en-v1 的逐字节副本及版本记录
src/spatial_pilot/control_*.py              # 新场景、输入隔离、推理、独立评估与环境审计
scripts/run_phase3_6.sh, freeze_phase3_6.py
tests_phase3_6/                            # 33 项新增测试
diagnostics/phase3_6/
  inputs/                                 # 中性公开清单、固定顺序、推理冻结哈希
  images/                                 # 16 张干净 768×768 模型输入
  private/scenes/                         # 私有完整几何，仅生成器/评估使用
  private/private_labels.jsonl            # 三分辨率 Oracle 与独立拓扑证据
  private/generation_attempts.jsonl        # 所有实际生成尝试与失败记录
outputs/phase3_6/                          # 16 条一次性推理、原文、张量证据、session
reports/phase3_6/                          # 本目录：预览、私有 QC、测试/审计/评估/分析
```

“private”指对模型不可见；依照用户要求，这些非敏感研究产物仍同步到公开 GitHub。
scene_overview.png 含研究者用类别/ID；private_path_overview.png 和 private_qc/ 还含答案与路径。
这些图绝不可代替 diagnostics/phase3_6/images 作为模型输入。
紫色为 BFS 返回见证，绿色为另行检查的宽裕量参考路线；见证路径净空不等于最佳通道余量。

在新的空产物目录中重现的顺序如下。已有生成/推理/冻结/评估产物会拒绝覆盖，不能在正式数据上重试选答。
全部命令在 /home/asus/EAI/spatial_intervention_pilot 执行，无需安装或下载。

```bash
bash scripts/run_phase3_6.sh prepare
bash scripts/run_phase3_6.sh audit
PYTHONPATH="$PWD/src" PYTHONNOUSERSITE=1 .venv/bin/python -m pytest tests tests_vlm tests_phase3_5 tests_phase3_6 --basetemp=.cache/pytest-phase3_6-before --junitxml=reports/phase3_6/tests_before.xml
PYTHONPATH="$PWD/src" PYTHONNOUSERSITE=1 .venv/bin/python scripts/freeze_phase3_6.py
bash scripts/run_phase3_6.sh infer
bash scripts/run_phase3_6.sh evaluate
```

模型推理与评估为两个独立进程；只有全部 16 次推理成功结束后，评估器才打开私有标签。
输入读取防火墙拒绝历史数据、私有几何、QC、类别和旧预测。严格 JSON 错误原样保留，未知/错误计入完整分母。
最终环境审计使用 control_audit.audit(output_name='environment_after.json')，不重写旧审计。
历史 338 文件哈希、19/42 包版本、模型全部文件 SHA256，以及原有 113 项系统/机器人文件均进行前后核验；不声称审计了整个系统。
