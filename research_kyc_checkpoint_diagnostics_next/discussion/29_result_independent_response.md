先读取授权、调度与实际运行原件，不读事后解释文件；随后用源码核对停止链。

# 冻结 checkpoint 诊断终止：独立原件验收

## 结论

**输入阶段在 import 时 TECHNICAL-BLOCKED；没有任何输入、健康图像、模型前向或科学结果。** 不能据此判断 checkpoint 无能力，也不能解释旧 0/32。F 当前无继续部署/闭环依据；不建议完整重训。

## 发生了什么（代码因果成立）

`input.log` 第2–8行是确定的 ImportError：

- `scripts/input_worker.py:2` 先 `from common import *`，把本目录 `scripts/common.py` 注册为 `sys.modules['common']`；
- `:38-39` 把 `reproduction/scripts` 插入 `sys.path` 后 `import experiment_lib`；
- `reproduction/scripts/experiment_lib.py:2` 执行 `from common import ROOT,...`，但解析到**已加载的本目录 common**；该文件没有 `ROOT`（本目录 `common.py` 只定义 `P/W/D/R/K` 等），于是 ImportError。

这是**Python 模块命名遮蔽**，不是 GL、CUDA、checkpoint 或策略问题。worker 在 `input_worker.py:56` 的 `InputRuntime` 安装、`:124` 的 `make_env` **之前**退出，因此 `run_state.json` 为 `workers=1, make_env=0, renders=0, readPixels=0, ACT=0`，GPU 3.93s，exit 1；`input_stop_integrity.json` 记录 `actual_inputs_NPZ=0`、`actual_frames_PNG=0`、`worker_input_result_exists=false`（这些是执行方哈希记录，我没有重算）。`stop_request.json` terminal，未重试，未启动模型。

## 预审遗漏

**我撤回 v2 “可静态执行”的判断。** 我读过 `input_worker.py` 的 `sys.path.insert/import experiment_lib`，但没有追踪 `experiment_lib` 内部的 `from common import ROOT` 与已加载 `common` 的冲突；`test_preparation.py` 只测 gates/metrics/mocks，从未真实 import `input_worker`/`experiment_lib`；`test_render_health.py` 也只 mock `input_runtime`。Codex 本轮聚焦 render gate，同样未覆盖真实 import 链。**CPU mock 不能替代 import smoke。**

最小修复必须是模块隔离，而不是给本目录 `common` 补一个 `ROOT`（那会让 `experiment_lib` 使用错误的 ROOT/DATA）。可用独立模块名/隔离 import 上下文加载 official `experiment_lib`，但任何修改都要重建 manifest、重新双审；**旧 RUN 已终止，剩余 596 秒不可重用**。

## 合规与科学边界

- 授权、dispatch、review_gate 的 SHA/run_id 一致；一个 worker、一次启动、无重试；GPU 3.93/600s；0 make_env/render/read/ACT/step/训练/rollout。**停止与计数合规**。
- **但不是实验完成**：没有 `input_result.json`、没有 NPZ/PNG、没有模型结果；不能填 0 成功率。证据状态是 **TECHNICAL-BLOCKED at import**，不是 MEASUREMENT-LIMITED，也不是 VALID-NEGATIVE。
- **不能解释历史 0/32**：旧训练是另一条已运行路径；本次 import 失败与旧结果无因果证据。
- **不能把软件失败当 checkpoint 无能力**：当前 checkpoint 的 prior/posterior、入口一致性、常数比较全部 **NOT_RUN**。

## 投入判断

- **当前 checkpoint：不继续部署，也不宣布无能力。** 没有科学信号。
- **闭环/完整重训：不批准。** F 的关键缺口仍完全未答：健康输入上的 prior 能力、persistent vs IID、自然标定误差频率、pose-jitter/重标定强基线。
- **若研究者仍要一次最低证据**：先做**纯 CPU import smoke**（新 manifest 下真实加载 input_worker/experiment_lib），通过后才允许一次 **input-only 4 状态健康门**；只有健康通过才谈 16 次冻结 forward。全部需新的 RUN 授权与预算，不能复用本次剩余额度，更不能训练/闭环。
- **机会成本**：KYC 已连续出现渲染、导入等工程阻塞，而论文时间有限。**优先重新寻找有公开匹配 checkpoint、数据、环境且任务阳性的已验证基线**，比继续扩大 KYC 工程排障更符合“尽快完成硕士小论文”。若仅做一次便宜的 import+input kill test，可以；但不应把它当成论文主线的默认继续。

**证据路径**：`logs/input.log:2-8`、`scripts/input_worker.py:2,38-39`、`reproduction/scripts/experiment_lib.py:2`、`run_state.json`、`stages/input.json`、`commands.jsonl`、`input_stop_integrity.json`。以上为只读核对；未运行任何代码。
