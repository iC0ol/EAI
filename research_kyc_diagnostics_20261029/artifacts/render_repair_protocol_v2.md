# GPT-6.1-sol / max：定位并修复当前 RGB 损坏

版本 v2，2026-10-29，落实真实DeepSeek15六项修订。执行前须同时获得 Codex 与真实 DeepSeek 对本文件准确 SHA256 的通过记录。本任务来自用户新增“检查原因然后想办法解决”的授权，详见 00_授权与范围.md；不是重启已经结束的原诊断。

## 目标与边界

解释原 `execution/inputs/sample_00.npz` 等坏图在什么阶段产生，并在证据支持时实现、验证一个局部修复。分开回答：当前损坏能否复现、直接失效机制是否定位、最小修复是否有效、触发源是否定位、对旧训练 0/32 有何证据。最后一项可能始终 UNKNOWN。

主线程 `01a18138-0f15-76b2-b5cf-20e1722782a9`；执行模型 `gpt-6.1-sol`，reasoning=max。复用原执行聊天，但全新代码/运行记录/锁只写 `/home/asus/EAI/research_kyc_diagnostics_20261029/render_repair/`。不得运行原 execution/scripts/supervise.py 或修改任何旧产物。Git index 由主线程持有，执行者不 commit/push；提交原始代码与必要小型结果给主线程统一公开同步。

只读 runtime `/home/asus/EAI/research_expansion_20261029/reproduction/env/bin/python`，`PYTHONDONTWRITEBYTECODE=1`，新缓存/日志仅本目录。旧 KYC/RoboSuite/data/checkpoint 的版本和 SHA 继承原协议。无需加载 checkpoint、创建 ACT 或 optimizer；只复用 stats JSON、冻结 source state/camera、官方数据流和已有 helper。不得新安装、下载、变更系统或环境，不改旧源码。

## 0. 只读准备及新冻结清单

先读原执行 FINAL_REPORT、stage1.py/diag_common.py、三入口实际源码、父审 notes/03 与 DeepSeek13/14。父审已完成 PNG 与 float/uint8 原数组逐像素反解，不重复把保存图像编码作为未经检查的首要解释。

重点审查固定 RoboSuite：MjRenderContext 构造 make_current、MjSim.render 中 render/read_pixels、EGLGLContext.free 中 eglReleaseThread、环境 hard reset 与销毁/GC 生命周期。源码仅是线索，不能预判当前 context 丢失或旧训练损坏。先写因果图/候选列表、插桩范围、实际拟执行命令与内容 SHA，再运行。

从原 sample_plan 固定 **sample0：demo0/t0/train camera1**。读取同一 float32 source state、同一相机 T，保留 256×256、相同环境 seed0 和初始化顺序。每次渲染前还原物理 state 与 camera，核验 XML/state/camera hash，0 env.step。两个 worker 是机制重复，不是两个独立任务样本。

允许对新诊断代码使用窄作用域 wrapper/monkeypatch 进行日志采集和本进程临时修复；须保留原函数并在结束恢复。禁止全局修改第三方源码、驱动或原训练程序。

## 1. 预算与自动收尾

| 项目 | 总上限 |
|---|---:|
| 新 worker / make_env | 2 / 2；顺序，不并发 |
| 底层 RGB render 尝试 | 12，调用前持久计数；初始化隐式调用也计 |
| mjr_readPixels 尝试 | 24，调用前持久计数；诊断重复也计 |
| GPU 分配墙钟 | 300 秒，所有 worker 生命周期之和，含初始化、失败和退出 |
| ACT / optimizer / env.step / rollout | 全部 0 |
| CPU / RSS / VRAM / 新磁盘 | ≤3线程 /16GiB /12GiB /200MiB |
| 工程修复 | 最多2项新诊断脚本错误；每次保留错误与补丁，耗用照计 |

写独立 supervisor/进程锁和 PID/start_ticks、计数、deadline。首次运行前预算全部落盘，额度中断不影响300秒硬停止和 completion 写出。GPU总预算不可因为五小时检查延长。总派发后8小时结束，不重复启动已经 terminal 的 run。读取真实账户 resetsAt，复用 `6-1-sol-max` 于未来有效重置+120秒或最长5小时检查，完成即暂停并回传；不兑换额度重置券。

若初始化已经消耗渲染预算，减少后续计划并标 PARTIAL，不免费补齐。显式区分 env.step=0 与初始化/forward 内部引擎操作；不得隐瞒实际 renderer 调用。

## 2. 无修复基线：定位损坏进入路径的位置

复现原 stage1 的构造顺序 make_env→Dataset(id)→Evaluator→embedder，不创建 ACT。只能复用或复制纯输入 helper，避免 import 原脚本 main 的副作用。

在环境创建/重置、Dataset/Evaluator/embedder 构造、底层 render/read_pixels 入口/出口、可能的 EGL free/release 处保存有界事件日志：单调时钟、线程ID、当前 EGL context 与目标 context 的匿名标识、GL framebuffer status/error（有有效 context 才查询）、MuJoCo buffer字段、源 state/camera hash。记录异常，不为遥测自动 make_current 或重建 context，避免基线被插桩偷偷修好。GL error 查询会清除标志，应在报告中明确；context 指针仅留本地，公开记录用稳定代号。

日志仅存primitive、匿名代号或weakref，不存env/sim/context/scene/原始numpy buffer的强引用；包装器保留类的未绑定原函数，避免闭包持有旧实例。数值证据保存独立copy，不能替换原流水线buffer，不改全局np.empty，不主动gc.collect改变基线时机。释放临时引用后按原顺序close/free；记录插桩和拷贝仍可能改变分配/GC时序这一局限。

固定遥测顺序：读取当前/目标EGL context→有效context时读取framebuffer status→随后最多8次glGetError，遇GL_NO_ERROR即停并完整记录→被观测的原调用→同序后测。无有效context则GL项null+NO_CURRENT_CONTEXT。error属于包含查询的整个区间，可能由查询产生，不能把清空后NO_ERROR当调用之前无错；不得为了查询绑定context。预算hook在make_env前安装，覆盖初始化/reset/free的隐式mjr_render与mjr_readPixels；sentinel也经过同一持久计数器。

三个入口 Dataset/id、Evaluator、自定义各1次 render，捕获 **readPixels 返回后、flip 前、flip 后、float tensor、保存数组** 的独立拷贝和哈希。原始路径不能悄悄改 flip 或 float 转换。对每帧最多再做1次 **sentinel 预填缓冲的 readPixels**，不额外 render，记录哪些字节仍保留已知模式，并保存返还状态。单个 sentinel 残留不能独立证明未写入，须结合原始返回、context/error 和正常对照解释；无有效 context 时禁止通过颜色模式单独宣判。

sentinel数组/调用明确单独标记，独立保存，永不流入正常图像或健康判定；正常pipeline五个边界各自copy，记录不共享原buffer。另报sentinel残留比例及正常对照。不可为获得理想结果改变sentinel值或重试。

先区分：raw即坏、转换后才坏、保存后才坏；若当前不能复现坏图，只报告 NOT_REPRODUCED，记录与旧执行顺序/状态的差异，不能声称已修复。

## 3. 证据驱动的最小修复

第一 worker 的后三次 render 只在基线存在明确异常时使用。候选修复须由遥测支持，最多采用一种语义变化：

- 当前 EGL context 与目标不一致或不存在：在原渲染锁内、render+read_pixels 之前显式绑定该环境的 `gl_ctx.make_current()`，其他参数及物理状态不变。
- 若 context 正确，但确认读错 framebuffer/buffer：只恢复同一 renderer 的正确 offscreen buffer 选择；必须先指出记录中具体错误值及上游期望，禁止试各种 driver/env/config。
- 若 raw 健康而数组后续被复用/改写：只在证实的边界复制数组，保留真实所有权/共享内存证据。

选择前写 `repair_choice.json`，引用支持证据、反对证据和唯一改动。没有支持某项的遥测则不盲试；无法在预算内判定就保存未决证据。若首个修复无效，不自动换第二种猜测堆叠。

make_current候选必须覆盖MjSim.render原来完整的`_MjSim_render_lock`区间：在锁内绑定、按原参数render与read_pixels，不能只包装read_pixels，也不能在外层重复获取同一个非重入锁而死锁。在绑定后、render后/read前记录context是否仍匹配；不匹配就保存并停止，不偷偷再次绑定。锁只能保证原渲染临界区，不能保证同线程GC/free永不发生，仍须靠事件记录确认。

同一个 source state/camera 的三个入口再各渲染一次，保存完整前后对照。健康要求不止入口相等：人工检查可辨认机械臂/场景/目标，且 readback/status 正常，无异常条纹或噪点；共同 raw 输入另走三种纯预处理，逐元素比较，不能把三张独立坏图相等当成功。

## 4. 独立 worker 复核与解释限制

若第一 worker 得到明确修复，则启动第二个全新 **OS/Python进程**，重复相同 **3次未修复→3次同一修复** 顺序，合计≤12 renders。第一个进程必须退出并释放资源，再创建第二个；不使用fork继承已初始化CUDA/EGL，不在同一进程换env充作独立worker。记录两个PID/start_ticks和匿名context创建/释放顺序。不按第一次好坏换 state/camera/seed/顺序，不需要模型推理。若预算剩余不足或基线不再复现则明确 PARTIAL/NOT_REPRODUCED，不偷偷增加 worker。

若绑定 context 后恢复，要区分“读图前 context 不正确、绑定可恢复”的直接机制与“哪个生命周期事件使它失效”的触发源。只有事件链记录到某次 free/release/reset 前后变化才能归因该触发源；不要仅从源码 `eglReleaseThread` 存在推断。即使两次复现成功，也只证明该固定状态/构造顺序下的局部修复，不能证明所有视角/长时间训练健康。

旧训练RGB/GL历史缺失。当前修复不得把旧0/32改写成已定位，不能自动恢复原32前向或16闭环额度。先将渲染证据交 Codex/DeepSeek 验收，再由双方制定是否需要模型层下一检查；本任务不授权其执行。

## 5. 交付与异步回传

保存 STATUS、status/completion、运行命令/退出码、进程记录、代码 hash、逐次预算计数、原始 tensor/PNG、匿名化 context/GL/readback日志、repair_choice、最小可复用修复模块与 CPU分析脚本、修复前后表。保留失败，不覆盖原诊断。无执行数据用 null+NOT_RUN，0模型调用不能写成0成功率。

父线程会独立看图、核对数字与代码，再让真实 DeepSeek 反驳。公开只包含原创代码和必要小型结果，不公开runtime、第三方权重/全量数据、完整XML、原始CLI和凭据；原始context地址仅本地。本轮 Git 写入由父线程负责，执行者不改 Git index。

完成/预算停止后暂停自己的现有检查，按主聊天人类回传授权，一次性通过 send_message_to_thread 告知主线程真实状态、原件位置、计数、直接机制/触发源/历史因果各自已知程度、修复是否复验，并保存回执。不能在任务结束后自动重启或继续训练。
