# 固定释放时点的 GL 生命周期修复：执行报告

执行结果为 **LOCAL_CONTROLLED_PASS_PENDING_REVIEW**。本次补齐了旧 render_lifecycle 缺少的同一释放窗口与真实活 previous 恢复证据；这是执行端的局部工程判断，等待主审独立核对原数组、代码、实际图像及真实 DeepSeek 质疑后验收。它不定位旧 checkpoint 的 0/32 根因，该项仍为 **UNKNOWN**。

本次严格执行已双审通过的 render_controlled v1，协议 SHA256 为 `0b39318295a299d9fc55327af7b24925b58036563819368154e39911f235fd8e`。唯一问题是：在固定 sample0、相同 A/B 强引用 fixture 和相同显式释放点下，按 owner context 释放旧 A 并恢复仍活的 B，是否保住 B 的原资源和图像。两个条件各一个独立进程，使用同一 make_env(0)、demo0/t0/camera1、state/T、256×256 与 RGB 转换路径。两组均先保存健康 before，再持有原 `_MjSim_render_lock` 调用 A 的共同 one-shot 析构入口，之后保存 after。显式持有和释放是两组共同的实验干预，**不是自然 GC 复现**。

| 已保存证据 | baseline（worker 1） | fix（worker 2） |
| --- | --- | --- |
| A/B fixture | 恰好两个原 renderer/context，A 已退休，current=B | 相同条件，独立进程 |
| before | 正常读回、sentinel=raw、精确匹配固定参考 | 同左，且像素完全一致 |
| A 的 con.free 窗口 | owner=A、current=B；只能测 B。B 的 3 个 FBO 与 4 个 RBO 同 ID 均 true→false | 先绑定 A；在 A namespace 中测得其 3 个 FBO 与 4 个 RBO 同 ID true→false |
| A 的 EGL 释放 | A 的 eglDestroyContext 实际成功一次；随后 eglReleaseThread 使 current=NULL | A 的 eglDestroyContext 实际成功一次；保留原 eglReleaseThread，随后原生 eglMakeCurrent 恢复 B |
| 释放后 B | context 仍存活，但资源已失效且未绑定 | 原 context 与原 FBO/RBO 保持有效，未重建 |
| after | 没有 current context；独立 sentinel 100% 保留 165，与正常缓冲不同 | current=B；正常与 sentinel 完全相同，读回观测无 GL 错误，与本组 before 逐像素一致 |

baseline 的决定性对象窗口为 events.jsonl 的 **0 起算事件 31→32**；A 对象明确记录 `NOT_MEASURED_WRONG_CONTEXT`，不能将 B namespace 的结果冒认为 A。fix 在 **33→34** 测 A 的释放，**46** 记录真实原生恢复返回 true，**47** 为 `previous_restored`，**52** 确认 A 已销毁、B 存活且其原对象有效。恢复发生在 `CONTROLLED_RELEASE_A`，早于 after 渲染及 B cleanup；不是在最终清理时补出恢复事件。两组在释放退出至 after 结束之间均无额外 context 绑定、renderer/context 构造或资源重建。

三张健康图的 RGB 像素 SHA256 均为 `688297023a217d9874c347fdd0a6821def4d0a57d6abc8899014c63860976c37`，等于协议指定、此前已查看的参考图。baseline after 的像素 SHA256 为 `b28bedaf38058a748bdb0246287a5304151de9af56b50ecf4775639bbe61cb4d`，54.22% 的通道值不同于 before。它视觉上仍像场景图，呈近似翻转；但它既不与 before 精确垂直翻转相等，也没有有效的新 GL 读回证据，不能据图像“看起来正常”判健康，更不能仅凭此确定具体内存来源。已实际查看 `montage.png`，保留了真实输出，没有增强或重绘像素。

CPU 后处理 `scripts/analyze.py` 的 **85 项核对通过**，包含 4 帧 × 5 个边界共 **20 个精确比较**：raw→flip 输入、flip 输入→输出、flip 输出→float32 RGB tensor、tensor→NPZ、NPZ→PNG。因此保存、翻转和转换链路忠实传递了各自实际缓冲。所有 state/T/XML 哈希在四帧一致；MuJoCo 读出的 state 为 float64，核对的是固定 f32 源状态按 float64 精确扩展后的值，没有改变物理状态。健康读回中的自然 165 值占 0.1297%，与 sentinel 原样保留不是一回事。

每组 r1/r2 的首次进入、首次完成、con.free 尝试与返回、成功 eglDestroyContext 均各一次；各有一次 DONE 重入跳过，RUNNING 重入为零。原 EGL 对象的析构可再次进入已清空 `_context` 的 free，它没有产生第二次原生 context 销毁。最终所有 context 已销毁、fixture 强引用数为零，无 fatal 记录；两个 worker 均退出码 0，监督器及 worker 的 PID/start_ticks 已核对为不存在。没有用保留 GPU 资源换取健康图。

候选仍是 owner-context 释放事务，本次必要的适配纠错是将非空 raw context、registry key=None 识别为 UNKNOWN，并在绑定/释放前拒绝；准备阶段异常纳入可见错误事务。共同 one-shot guard 不跳过首次释放。**30 项纯 CPU mock 通过**，包含真实适配器形式的 UNKNOWN、NULL 矛盾、正常活 previous、准备/绑定/释放/恢复异常、重复与重入；mock 本身不作为真实 EGL 修复证据。复制来源与最小差异见 `copied_sources.json` 和 `patches/`，旧模块未改。GPU 执行期间工程纠错为 0；启动前显存监控修订与冻结记录见 `prelaunch_revision.json`。

| 资源 / 调用 | 实际 | 上限 |
| --- | ---: | ---: |
| OS/Python worker / make_env | 2 / 2 | 2 / 2 |
| 底层 mjr_render / mjr_readPixels | 4 / 8（4 正常 + 4 sentinel） | 4 / 8 |
| GPU 分配时间，含初始化、导入、遥测和 cleanup | 19.285659 秒 | 180 秒；170 秒终止预留释放 |
| ACT / env.step / rollout / optimizer | 全部 0 | 全部 0 |
| 采样 RSS 峰值（监督器及自身子进程） | 1,346,560,000 B | 16 GiB |
| 采样全设备显存峰值（含已有进程，覆盖纯 EGL） | 991,952,896 B | 12 GiB |

资源每约两秒采样，所列为采样峰值，不能冒称连续峰值。纯 EGL 未出现在 compute-apps 归属显存计数中，因此用全设备 memory.used 作为保守补充。启动配置限制三核亲和性和数值库线程；未测量逐线程峰值。结束时 GPU 仅保留启动前已有 PID 543637/python 296 MiB，整卡用量回到 580 MiB。新增目录约 7.5 MB，最终精确大小见交付审计，远低于 150 MiB。295 个旧证据文件的大小、mtime_ns 与 SHA256 全部未变；冻结的七个脚本和七个源文件均未变。

本结果只支持 **固定 sample0、共同强引用 fixture、指定受控释放时点** 的局部修复。没有测自然 GC 发生率、多视角、长期运行或线程安全；没有复验旧三入口，也没有恢复 ACT/闭环或训练。它不是算法创新，不能追认旧 checkpoint 0/32 的因果解释，不能推出值得重训或研究方向已有科学收益。

主要复核入口为 `analysis.json`、`repair_choice.json`、两组 `events.jsonl` / `readback.json` / 原数组 / `guard_counts.json`、`run_manifest.json`、`commands.jsonl`、`resources.jsonl` 与 `integrity_after.json`。`scripts/analyze.py` 在终止 GPU 后新建，仅做 CPU 核对，哈希记录在 analysis 中。完整地址映射、XML、原析构文本和原始 CLI 保留于 local_only/logs，不纳入公开允许清单。

Git index 和公开同步由主审独占；执行端没有 stage、commit、push。原创实现和必要小结果将通过 `public_allowlist.txt` 与 `public_secret_scan.json` 交主审审查发布。专属自动检查按协议暂停并保存 `automation_closure.json`，单次回传回执保存为 `return_receipt.json`。本次 GPU 范围已终止，等待主审及研究负责人复核，后续实验需要新门控。
