我先做独立审查，不读 Codex 结论。先读取交接文件、任务书和候选材料。

**审查声明**：我没有读取 `notes/03_Codex候选独立审查.md`；本轮没有启动进程、GL、模型，也没有写文件或改代码。以下是静态读码和现有产物核验；SHA 依据 `artifacts/parent_candidate_hash_audit.json`（protocol `3fd123…`、manifest `bd4233…`，`bad_local/bad_source/bad_final_cpu` 为空，55 个本地文件/113 个来源），我本人未重新计算。

## 1. CPU 预检

**真实隔离与同入口成立，但最终覆盖是 import-only。**
- `cpu_preflight/final/process.json`：同一解释器、同一 `run.py cpu-preflight`、同 cwd、`-B`，exit 0、15.688s；`final/result.json` 的 provenance 显示 8 个上游模块均来自只读真实路径，`sys_modules_same_object=true`；`common` 是 `reproduction/scripts/common.py`，`kyc_recovery.common` 是独立对象；`loader.py:24-54` 只验证并拒绝错误身份，不删缓存、不补字段。R1 的旧 common 冲突确实被隔离。
- R2 diff 只做一件事：放行 resolved 的 `os.dev/null` 的 `open`；remove/rename/其他写仍走 `write_path` 拒绝。范围与报告一致。
- 局限陈述基本正确：`ENGINEERING_READY=false`、`GPU_pending`、9 个最终模块 `native_entry_execution=DEFERRED`、builders/model_runtime `constructor_execution=DEFERRED`、CUDA 前后 false、GL 未导入。**但需要补一句**：`cpu_preflight.py:61-82` 的最终覆盖只 import 了 ROUTES 模块、builders、model_runtime；`input_runtime/telemetry/owned_release/lc_common` 只在函数内 lazy import，实际未被 import；constructors/gates/supervisor 未执行。因此“真实入口导入链”只覆盖到模块顶层，不能表述为完整链路已测；GPU 预检会首次 import 这四个模块。
- R1/R2 已 2/2、剩余 0（`repair_ledger.json`）；supervisor 失败会写 `terminal_stop` 且 `repair_rounds_remaining=0`（`supervisor.py:96`）。最终 CPU 覆盖是无修改测试重复，不是 R3，我接受；不得第三轮修复。

## 2. 一个 worker 两条路径：我撤回上轮断言

**就构造/清理层面，当前代码没有阻断，上轮“一个 worker 不能覆盖两路径”不成立。**
- `gpu_preflight.py:16-24` 明确顺序：`input_setup()` → `close_input()` → `empty_cache` → `ModelRuntime` → `model_setup()` → `close_model()`；`builders.py:27-63/66-71/74-110/113-116`。
- `close_input` 在 `builders.py:71` 强制所有登记 GL context 已销毁；`model_setup` 不依赖 env，只 import `models`/`detr_vae`、构造 `ACTPolicy`（其中 `build` 调 `model.cuda()`，`detr_vae.py:189`）、`load_state_dict(strict=True)`（`builders.py:101`）。输入路径的全局 patch（`MujocoEnv.step`、`mjr_render/readPixels`、EGL telemetry）对模型路径不是依赖，且 `ModelRuntime` 的 guard 在 input 关闭后安装（`model_runtime.py:8-35`）。源码未发现确定性阻断。
- 但这**不是 S1 合并**：S1 input/model 仍是两个独立 worker；preflight 只覆盖 constructors/cleanup，不覆盖 Dataset `__getitem__`、render/read、BF16 forward。另有一处措辞不一致：`input_worker.py:176-205` 使用自己的 manual cleanup，不是 `builders.close_input`；协议“调用同一 close_input”应改为“preflight 用 close_input，S1 input 用等价 manual cleanup”，否则不精确。
- 静态阅读不称 GPU 成功；180s 是否足够由实际 supervisor 记录决定。

## 3. 计数、停止、旧源与 SHA

**没有必须拒绝的问题。**
- 计数：`common.py:17-19` CAPS；`gates.py:73-94` project/charge；`97-103` 先在锁内记账再操作。preflight 只允许 `make_env=1`；ACT/render/read/step 的 project 返回 None → raise，不能偷跑。worker cap 5、PHASES 4、planned 4、每 phase 1；`supervisor.py:44-47` 用 stages/lease/lock 拒绝重试；manifest 的 `actual_GPU_workers/seconds/ACT/render` 全为 0，未虚报。
- 停止：`supervisor.py:71-80` quota−15s TERM、3s 后 KILL；`gates.py:119-123` PDEATHSIG + lease−5s alarm；wall deadline−30s；资源 cap；失败 `terminal_stop`（`supervisor.py:95-96`）；child 被 wait，正常路径无 orphan；审查等待无 GPU。
- 旧源/SHA：`gates.py:23-24` full 重验 113 个来源；`runtime_safety.py:19-37` 写保护；旧源在 P 外，写被拒；每 phase 入口重验 manifest + CPU final hashes（`gates.py:32-34`）。
- 仅报告限制：① `supervisor.terminate` 在 poll→proc 之间若 child 恰好退出/身份读取失败会 raise，极端情况下 finally 的记账/结果写入可能被跳过（fail-closed，不会超 1800，但需日志兜底）；② audit 允许 P 内写，因此“冻结”靠 phase 入口 SHA，不是写保护；③ `cli.py:25-27` 与 `gpu_preflight.py:7` 双调 `worker_gate`，冗余 full hash，不影响语义；④ `gpu_preflight_result.json` 未自绑定两个 evidence 文件/counts 的 SHA，父审需看 `stages/gpu-preflight.json` 与 `results/*.json`；⑤ 失败路径 finally 中 `close_*` 若再抛，可能来不及写 result，依赖日志。

## 4. Stage1 / Stage2

- **Stage1 设计符合授权**：`call_plan.json` 16 次；input 4×3=12 render/24 read（`input_runtime.py:92-131`）；`sample_plan` 0/1/4/5、两条 demo；模型 16 次；旧 `constants` 不拟合；0.8×/3-of-4/7 维/方向夹爪门；重复容差；BF16；无训练。健康输入先于模型：`input_gate`（`gates.py:54-70`）绑定实际看图/原始文件/进程记录，`s1-model` gate 在 `gates.py:41` 强制。
- 报告限制（不改阈值）：`analyze.py:15-37` 读 constants/stats/inputs 时未在分析阶段重验 SHA，证据绑定依赖 input_gate/manifest；`gate('s2-closed')` 未重新调用 `input_gate`（`gates.py:42-46`），依赖 analysis/stage2_gate 复核。应写入验收，而非视为已证。
- **Stage2 不自动批准**：`root_plan.json` 16 条/8 roots 配对；`closed_worker.py` 每 query 一次 render、5 query/150 step、80/2400/80/160 上限；旧 `clean_RGB`/旧 0/32 动作只作 descriptive，不再 assert（`closed_worker.py:61-66`），符合删除错误对照；success/reach/grasp 原谓词；`stage2_gate` 需 analysis+model_result+root_plan 精确 SHA 且双审（`gates.py:42-46`）。我**不批准 Stage2**；须 S1 实际输出双审后另派发，8 root 不是 16 独立任务。Stage3 仍 PLAN_ONLY。

## 5. 结论

**APPROVE GPU_PREFLIGHT_ONLY**，严格针对 protocol `3fd123…` / manifest `bd4233…`：一次受监督 `gpu-preflight`，180s/1800s 账本，不得改代码或 manifest；必须存在绑定同一 SHA 的 `engineering_gate.json` 与新 `dispatch/gpu-preflight.json`（`gates.py:5-31,114-124`）。不批准 Stage1/Stage2，不称 GPU 实际成功。

**必须修改（阻断）**：未发现源码级必须修改项；若 formal gate 缺失或任何文件变更，gates 会拒绝，这是正确的。**仅报告限制**：上述 CPU lazy-import 缺口、`input_worker` cleanup 措辞、preflight result 证据绑定、`terminate` 极端竞态、audit 的 P 内写范围、双 `worker_gate`，以及 Stage1 analyze / Stage2 gate 的证据绑定缺口。CPU lazy-import 是主要残余风险；若主审要零风险，可在不写文件、不占 GPU 的前提下用同一解释器 import 那四个模块——这是测试重复而非 R3，不改变本 SHA，也不是我批准 GPU 预检的前置条件。

若 preflight 失败：封存，不第三轮修复，不第二次预检。
