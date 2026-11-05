我**撤回42中“read事件 owner/active objects 均为 MEASURED_IN_OWNER_CONTEXT”这一不准确表述**。`results/gpu-preflight/readbacks.json` 原事件显示：read 事件 `owner_context=null`、`owner_objects=NOT_MEASURED_WRONG_CONTEXT`（read wrapper 未传 renderer）；真正被测量的是 `active_objects` 中已注册 renderer 在当前 `w1_ctx3` 内的 3 FBO/4 RBO，read/draw 绑定 object 1、FBO status 36053、GL errors=[0]。owner_objects 未测，不能写成已测；这不隐藏失败，预检健康结论仍由 active renderer、FBO/RBO、GL 错误和 readback 数组/PNG 支撑。

与 notes09 及父审 acceptance 核对无实质冲突：4 root/20 文件、HDF5 float64 初态精确、root1 首目标误差 2.384185791015625e-7（其余0）、2 render/4 read、12 context 注册/12 释放、375 strict-load、PID 失活、34.58120653964579s；父审独立确认 NPZ normal==sentinel、PNG 为 raw 上下翻转、两图实际查看正常。我的限制仅是我未独立解析 NPZ；父审已做，不冒充我的数组复算。

**无具体阻断。APPROVE_RUN_EXPERT_A_AND_ALLOCATION**，仅限：

- 冻结 A180 / B360 / C-local135 / C-official135，含预检实耗 **844.5812065396458≤900**；余 **55.4187934603542s** 不授权追加。
- 下一步仅新派发一次 A（≤180s）；A 正式派发启动 8h 科学时钟。A 是第一次真实 `roots.restore`/control 路径，失败即停，不归因 checkpoint；原 demo XML 未知，不称原场景恢复。
- B 仍须实际 A4/4、控制/成功接口一致及后续独立双审，另派发；C 也各自新派发。不得把本批准当 A/B/C 行为或任务成功。

- `candidate_manifest.json`：`3179c07a0cf77758d4dff01d57ffebcca1af0c11bc4034a0753b32610f40b530`
- `PROTOCOL_CANDIDATE.md`：`8773f4b7733335898d2bed5803f0d7729798896892abe6bdefd604a1f71a8ed8`
