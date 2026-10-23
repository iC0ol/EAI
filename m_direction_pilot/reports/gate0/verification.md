# 交付核验

2026-10-23，全部实验停机后执行，无新增模拟步。

```text
bash m_direction_pilot/scripts/run.sh -m unittest discover -s m_direction_pilot/tests -p 'test_*.py' -v
```

实际13项测试通过，0.423s，exit0；原始输出见logs/final_tests.txt。涵盖原9项保护，
并增加缺失Y不转成失败、真实停机之后零推理/零suffix、12状态/6来源/144分支完整分母、
原始trace哈希、预登记不变和执行时9个源文件哈希未变。没有重跑A或B。

expert_prefix_fidelity.png已实际打开检查，两个面板无遮挡/截断，单位、两条比较曲线与
冻结位置/姿态阈值清楚。SVG一并提供。表中观测误差与直接qpos误差明确区分。

Git whitespace检查对CSV接受标准CRLF，对Matplotlib生成SVG路径保留其空白，
规则仅作用于这两类生成文件，未改动已冻结CSV的任何字节。代码和报告继续严格检查。
git diff --cached --check通过；相对冻结base的所有改动都在m_direction_pilot/。main、
research/d-gate1、research/d-gate1-q2的ref记录于final_audit.json，均保持原SHA。
检查没有把原始HDF5、checkpoint、运行环境、缓存、NPZ、凭据加入Git。

sha256_manifest.json在最终报告、图像和测试日志之后封存，覆盖所有M源码/配置/紧凑结果/
报告，并索引本地原始trace。它不包含自身哈希，避免自引用。
最终Git提交SHA由交付消息提供；协议SHA与真实实验执行SHA已写入每条实际分支记录。
