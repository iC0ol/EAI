# 工作站 Agent：有限只读补证任务书

这是完整可复制的后续委托文本。**不是《基线复现与问题验证整夜执行提示词》；当前无候选取得那项资格。** 本轮已经完成文献/代码审查，以下只在出现新材料或研究者交给后续Agent时执行。现在不重复启动。

---

你在真实Linux工作站`/home/asus/EAI`工作。只完成一次有截止时间的只读补证，不运行机器人实验、仿真rollout、策略推理或训练，不安装实验环境，不下载权重或实验数据集，不修改旧实现/系统Python/驱动/CUDA/ROS，不创建或推送实验分支。

研究目标是第一篇硕士小论文。D/M/U、二维Spatial与导航恢复旧题已退出，不重启。本轮五个问题中仅A跨时间聚合、B数据覆盖、C本体状态依赖深入；A/B当前不投入，C仅保留补证。已知：medoid已有；DemInf有意避免逐时间步删数据；DataMIL已有15/30步片段选择；State-free有同相机同动作空间的缺陷结果；GAP已做阶段引导梯度抑制；NOSTRA已做可靠性切换。不要另命名新算法。

## 起点与目录

先读`/home/asus/EAI/research_selection_20261028/STATUS.md`、`README.md`、`01_联合审查主报告.md`及`notes/02_文献与源码阅读登记.md`。原任务书在同目录`00_原始任务书.md`。两轮讨论已经完成，不重做独立初筛。

新产物只能放在该研究目录下新建的`followup_YYYYMMDDTHHMMSS/`；不覆盖旧记录。先查有没有同一目标未完成的followup和进程；若有，核对其PID与命令后续接，不重复下载或计数。所有实验状态保持NOT_RUN。

## 固定预算

- 时区Asia/Shanghai；开始时记录实际T0与绝对截止时间T0+90分钟。最晚第70分钟停止检索，留20分钟汇总；可提前完成，不为用满预算扩题。
- GPU卡数0、GPUh0；不运行CUDA检查程序或模型forward。最多2个网络/解析并发任务、CPU线程2；单文件PDF≤25MB，总新增论文/源码/小型元数据≤100MB。已有缓存先验hash后复用。
- 新增磁盘≤2GiB，剩余磁盘至少20GiB；单任务RAM上限目标8GiB，发现超过即停该解析。不得解压大仓库或下载模型/数据。
- 网络每资源最多2次尝试，每次≤60秒；工具/文档抽取排障合计≤15分钟，最多2种已有工具组合。需要新凭据、付费、许可接受或更改系统时停该依赖，继续报告。

## 只查三个明确缺口

1. **GAP对应资产/语义**。固定原始commit为`2f605436c68eedf328c05520d52877604af730d3`，官方`https://github.com/GeWu-Lab/GAP`，论文`https://arxiv.org/abs/2602.12032v1`。只检查是否有新的作者提交、说明或匹配示范/权重的公开清单；只取元数据和代码文本，不取资产本体。核对`gap/gap.py`保留字、batch max与Algorithm1平均、`1−λρ`与Eq5`λ(1−ρ)`、train/valid重叠四项。不要修代码，更不能把修复包装为方法创新。新版本不自动覆盖旧版本记录。
2. **是否已有可用的匹配输入基线资产**。作者入口`https://statefreepolicy.github.io/`、`https://vsaxena.com/nostra/`。记录具体模型、数据版本、输入/动作接口、公开下载入口、许可、大小是否真的可知；没有就写未核实。禁止用“MetaWorld/DP开源”代替目标实验可复现。优先核验已有链接，不跨到另一个研究问题。
3. **两份缺失历史原件或一个会改变C判断的新直接证据**。缺失路径：`research_direction_audit_20261021/u_v3_review_20261028/U_v3实验结果独立审查_20261028.md`与`research_direction_audit_20261021/overnight_u_gate0_20261027/00_提示词问题审查与夜间执行修订.md`。本轮已在本机文件名和iC0ol/EAI main树搜索无果；只有新路径/提交线索才继续查。C的新证据须明确任务后果和最强简单对照，不接受Future Work或一个数学反例作为真实失败证据。

## 已存在且可用的只读命令

这些命令只用于必要的核验，不启动实验。工作目录为`/home/asus/EAI`。

```bash
git status --short
python3 research_selection_20261028/scripts/readonly_arithmetic_audit.py
```

第二条是本轮已有标准库脚本，只读取U旧JSON/CSV并重算归一化界与计数，不导入旧模型/模拟器。原始文件hash未变时无需重跑。下载PDF后用现有`/usr/bin/pdftotext -layout INPUT.pdf OUTPUT.txt`；INPUT/OUTPUT由实际取得的文件路径替换。不要采用DeepSeek环境中缺GLIBC的捆绑poppler，不为此更新系统库。

DeepSeek连接已验证：`/home/asus/.local/bin/claude` v2.1.308，经已配置DeepSeek Anthropic兼容端点，响应模型`deepseek-flash`。不要打印凭据。原指定session不存在；本轮真实session为`736077c1-8d4e-4df7-979f-1fc15f980a2a`。仅有新增实质证据需要反驳时才继续一次讨论，保留分歧，不能把未答复当同意。

如确需该调用，先在`discussion/`创建唯一、不覆盖的`04_readonly_delta_prompt.md`，写清新证据与一个具体争议，再使用已经存在的包装器：

```bash
python3 research_selection_20261028/scripts/run_deepseek.py 04_readonly_delta --resume --timeout 600
```

若该名字已存在，使用新的唯一名字并同时创建对应`NAME_prompt.md`。包装器拒绝覆盖raw记录；session不可用时不要自动串到最新聊天，不再次大规模发送旧全文。失败写明，继续单方报告。只开放Read/Glob/Grep/WebSearch/WebFetch，不给实验执行权限。客户端模型用量和费用字段不当正式账单。

## 资格决定与收尾

输出`asset_delta.md`、`source_manifest.json`、`decision.md`和一份简短`STATUS.md`，注明起止时间、实际新增字节数、访问失败、是否有未完成进程。资料下载和分析用正常独立子进程、超时、PID和日志记录；不需要长期GPU监督器。若Agent额度中断，先留检查点；后续查已有文件、hash和PID，不能从头重复。

只有新材料同时明确以下事项，才建议另写实验执行任务书：具体且未被简单对照解释的问题、匹配版本和数据来源、清晰输入/动作语义、同接口诊断、样本/精度依据、目标机可测预算。此时仍不启动实验；把可审查计划交给研究者。代码可修不等于方法值得做，方法未知也不等于必须无限补证。

没有新材料就记录“当前无合格候选，有限补证未改变决定”并结束。第二天只验收来源/版本/范围、真实讨论与停止理由；没有任何实验指标时填NOT_RUN，不填0。原始论文与完整第三方源码留本地；原创报告按当前EAI公开同步规则处理，不上传环境、缓存、模型、数据、凭据，不改写main或force-push。

---

复制范围到此。当前文件的保存不构成实验授权，也没有触发以上后续检索。
