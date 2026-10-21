# Phase 3.7：模型规模与公开 RGB 规划对照

研究者授权本轮诊断性选题验证。所有旧文件保留；旧 AGENTS/README 的停止位置是历史说明。
主报告见 [phase3_7_diagnostic.md](phase3_7_diagnostic.md)。Part C 必须先通过冻结的 Part A 门槛，不能自动运行。

新增结构：

```text
configs/phase3_7.yaml                # 同推理参数、两权重 revision、几何与 Part C 门槛
prompts/phase3_7/                    # 既有 prompt 的原样副本/哈希记录
diagnostics/phase3_7/
  inputs/{smoke,old16,new24}.jsonl    # 仅公开中性任务和 PNG 路径
  inputs/frozen_public.json          # 首次正式推理前冻结的输入/顺序/规则/代码
  images/                           # 24 张新模型输入；旧 16 张直接复用旧图片
  smoke/                            # 不评分的独立公开冒烟图片
  private/                          # 新几何、三分辨率标签、连通证据及全部生成尝试
outputs/phase3_7/
  smoke8b/                          # 唯一一次不评分 BF16 部署验证
  vlm8b_a/                          # 旧16+新24，各一次8B正式推理
  vlm4b_new/                        # 新24各一次；旧16保留原预测，不重跑
  rgb/                              # 从像素提取占据图、安全栅格、BFS/A* 路径/预测/计时
reports/phase3_7/                    # 源/权重校验、审计/测试、冻结、配对评估和研究判断
src/spatial_pilot/scale_*.py          # 新增源码，不改已有几何或推理基线
tests_phase3_7/                      # 图像管线、控制场景、隔离和运行证据测试
scripts/{download,freeze,run}_phase3_7.*
```

推理进程只读本轮公开清单/干净 PNG 及旧 16 张干净图；读防火墙拒绝标签、场景几何、QC、历史预测和 reports。
独立 CPU 评估器仅在 8B40、4B24、RGB80 条正式记录都结束后打开私有标签。4B 旧16预测以原文件哈希引用。
RGB 规划源码不导入 Shapely、生成器或 Oracle；颜色规则来自公开图例。地图边框和端点从像素检测，不提供隐藏坐标。
两种搜索使用同一占据图、圆盘膨胀及四邻接整段边规则。端到端时间包含图像读取、分割、膨胀、端点连接和搜索；共享预处理对每个算法各完整计时。
模型平均 elapsed 包含图像处理和生成；不能把 VLM 纯生成和栅格纯搜索时间当公平比较。

下列命令是流程记录，不应在已经存在的正式结果目录直接重跑。核心入口拒绝覆盖；正式预测没有重试选答。
全部在 /home/asus/EAI/spatial_intervention_pilot 下执行，不安装/升级任何包。

```bash
# 下载使用独立 .cache/phase3_7，不污染原缓存/环境；权重不入 Git
PYTHONPATH="$PWD/src" PYTHONNOUSERSITE=1 HF_HOME="$PWD/.cache/phase3_7/huggingface" HF_HUB_DISABLE_XET=1 .venv-vlm/bin/python scripts/download_phase3_7.py
bash scripts/run_phase3_7.sh prepare
# 独立公开 smoke PNG 及清单在第一次调用前已保存，不能用正式评分图挑选部署参数
bash scripts/run_phase3_7.sh smoke
PYTHONPATH="$PWD/src" PYTHONNOUSERSITE=1 .venv/bin/python -m pytest tests tests_vlm tests_phase3_5 tests_phase3_6 tests_phase3_7/test_protocol.py --basetemp=.cache/pytest-phase3_7-final-before --junitxml=reports/phase3_7/tests_before_final.xml
PYTHONPATH="$PWD/src" PYTHONNOUSERSITE=1 .venv/bin/python scripts/freeze_phase3_7.py
bash scripts/run_phase3_7.sh infer8b
bash scripts/run_phase3_7.sh infer4b
bash scripts/run_phase3_7.sh rgb
bash scripts/run_phase3_7.sh evaluate
PYTHONPATH="$PWD/src" PYTHONNOUSERSITE=1 .venv/bin/python -m pytest tests tests_vlm tests_phase3_5 tests_phase3_6 tests_phase3_7 --basetemp=.cache/pytest-phase3_7-after --junitxml=reports/phase3_7/tests_after.xml
PYTHONPATH="$PWD/src" PYTHONNOUSERSITE=1 .venv/bin/python scripts/verify_phase3_7_delivery.py
PYTHONPATH="$PWD/src" PYTHONNOUSERSITE=1 MPLCONFIGDIR="$PWD/.cache/phase3_7/matplotlib" .venv/bin/python scripts/report_phase3_7.py
```

RGB 规则 rgb-grid-v1：RGB 容差4，帧色 #182332、墙 #445060、矩形障碍 #DD9350、Start #2475C4、Goal #16805B；深色文字为注释，不当障碍。
从帧内像素范围和公开地图尺寸估计米/像素，圆盘半径使用公开0.25m，加固定2px安全余量覆盖像素单元和量化误差。
每2px一个栅格节点；四邻接边检查中间所有像素，端点短连接使用保守 supercover。失败保留为 unknown/pipeline_error，不用真值补图。
这是一套针对已知绘图风格的封闭颜色规则，并非一般视觉地图理解器。真值 Oracle 拥有真实坐标，只作标签参考，不作为公平图像方法性能。

Part C 预先规定门槛：8B 在新6个绕行例至少4个正确，且新12个负例至少10个正确；3/6未达最低门槛也停止。
这只是保守的后续实验运行规则，不是统计可靠性或显著改善的定义，不自动证明 H1/H2。
只有满足门槛后才考虑用户授权的探索性干预复查。无论门槛如何，本阶段结束后均停止等待复核。
