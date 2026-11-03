**GPU预检：ACCEPT（限定工程状态）。**
- `stages/gpu-preflight.json`：exit 0、`EXITED`、16.88504482805729s、quota 180；`recovery_state` cumulative 16.885，`gpu_workers=1`、`make_env=1`，ACT/render/read/step 全 0，lease null；`call_ledger` 仅 workers+make_env；`model_events` 仅 cached ResNet，`network=false`。
- `strict_load`：strict=true，missing/unexpected=[]，checkpoint `c904…`，cached `f370…`，optimizer 未创建/未载入。
- `events` 48 条：两个 EGL context 均 `eglDestroyContext_exit=true`，无 render/read 事件；`resources` 峰值 RSS 2.20GB、VRAM 1.25GB、目录 23MB；无 fatal/terminal_stop/science_clock。日志有 200 demos、1000 poses、70.43M 参数，无错误。故 `ENGINEERING_READY_INPUT_AND_STRICT_LOAD` 成立。
- 限制：未做 render/read、ACT forward、BF16，不能称输入健康、模型能力或 SCIENTIFIC_MEASURED；两个 context 为构造/清理产物；`actual_GPU_path` 是自报，以账本/日志为准；我未复算 55/113 项，父审复算非我的操作。原始证据无矛盾。

**Stage1：APPROVE `STAGE1_WITH_PARENT_INPUT_GATE`。**
- 允许：先 `s1-input` 12 render/24 read、0 ACT、≤210s；整进程退出后父审真实 12 图/数组/GL/边界/文件集+源码 SHA+预算并签 `input_gate`；再以独立新 dispatch 运行 `s1-model` 固定 16 forward，S1≤600s、总≤1800s；首次 `s1-input` 派发写入 8h 科学时钟；四状态/两 demo、双常数、BF16、既有容差/筛选不变；无新修复、训练、重试。
- 条件：正式 `science_gate.json` 与新 dispatch 绑定上述精确 SHA，代码/manifest 未改；预检的 `close_input` 与 s1-input 的 manual cleanup 非完全同一函数，输入 worker 仍须独立通过真实 12 帧、GL/边界及退出检查；失败即停止。
- **Stage2 仍不放行**。本次 APPROVE 不是 Stage1 已运行成功或科学测量。

SHA：
- PROTOCOL.md：`3fd12394fd845a4c2df528119655af65ab1a830b55833f5aa278c0c8c004c460`
- candidate_manifest.json：`bd4233fbeca8898d0145c3411ae98901897fd24b974984c3b83195cea75843ed`
