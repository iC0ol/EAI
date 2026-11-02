先读取协议、manifest、判据交叉处理与执行计划，再逐个读脚本，最后对照旧适配器/官方代码。

# 最终协议与代码独立审核

## 1. 事件索引纠正

按 `results/worker_1_baseline/events.jsonl` 零基核对：

- **31/32**：`baseline_before_con_free` / `baseline_after_con_free`，B 的 3 FBO + 4 RBO 由 true→false；
- **34/35**：`eglDestroyContext_enter` / `exit`；
- **37/38**：`eglReleaseThread_enter` / `exit`，38 出口 current=null，**这才是解绑**。

我 24 的“34/35 后解绑”不正确，撤回；31/32 是 con.free 资源变化，37/38 是解绑。fix 的 **31/32 绑定、33/34 owner、46 restore、47 previous、52 exit、53–60 after、61 cleanup** 已核实正确。原回复不改。

## 2. 局部修复验收：保持 LOCAL_CONTROLLED_PASS

**保持。** baseline 31/32 中 owner=A、current=B；A 明确 `NOT_MEASURED_WRONG_CONTEXT`，B 的 3 FBO + 4 RBO 同 namespace/ID 由有效变无效；37/38 解绑；after 无有效 readback。fix 33/34 在 A current 下释放 A，46 native restore true，47 `previous_restored`，52 A 销毁、B 原对象有效；after=before；正常=sentinel；guard 首次未跳过、无二次 free、无重建。**局部受控 PASS 成立。**

限界：整笔 owner 释放+previous 恢复未拆子步骤；固定 sample0/受控 fixture；未证明自然 GC、多视角、长期/线程；baseline after 虽像场景但无有效读回；旧 0/32 UNKNOWN。

## 3. 协议与代码：APPROVE（两个候选 SHA）

**APPROVE** 以下两项作为本轮代码双审候选：

- `PROTOCOL.md` SHA256 `ddbfbc0b4ad45fd3d380a2984c9ef0591d461429817af8c6b9cd9dc2da428381`
- `candidate_manifest.json` SHA256 `dcf61668dc0d5789c313d9afd759b99a8c610a43b8a9fbd16f2405470c670ee7`

**限制**：我未运行 `sha256sum`，无法独立重算两个 SHA；以上值来自 manifest/PREPARATION_REPORT。正式派发前主线程仍需按实际文件复核 SHA；若任一文件被改，manifest 与候选审核失效。

## 4. 静态审查：未发现阻塞性假通过

已实际阅读：`PROTOCOL.md`、`candidate_manifest.json`、PREPARATION_REPORT、notes/02、`sample_plan.json`、`call_plan.json`、`source_map.json`、`common.py`、`gates.py`、`runtime_safety.py`、`input_runtime.py`、`input_worker.py`、`call_guard.py`、`model_worker.py`、`metrics.py`、`analyze.py`、`supervisor.py`；未读完整 CPU tests/patches，未执行任何程序。

关键点核对：

- **自然 A 释放的安装/注册时点**：`input_worker.py:30-46` 在 `make_env` 前安装 `InputRuntime`；`input_runtime.py:30-58` 包装 `EGLGLContext.__init__`/`MjRenderContext.__init__`/`__del__`，弱注册，无 HELD、无强制析构、无额外 `gc.collect`；`input_worker.py:124-138` 保持旧 `make_env→Dataset→Evaluator→embedder` 顺序；`input_runtime.py:59-72` 只做 EGL 事件，不主动绑定；`input_worker.py:210-235` 只按原 `ds.env=None; env.close` 清理。**符合要求。**
- **raw/sentinel 同锁/计数**：`input_runtime.py:73-123` 在 `mjr_render`/`mjr_readPixels` 入口 reserve；`read_pixels` 要求 `_MjSim_render_lock.locked()`；正常 `np.empty` 不变，sentinel 独立 `np.full`，同锁内；`input_worker.py:102-110` 校验边界。**符合。**
- **完整同 raw 预处理与 Dataset 输出**：`input_worker.py:163-188` 用 Dataset 第一次 raw 的 `common_rgb`，official 使用旧 AST `official_eval_data`，custom 用 `lib.policy_input`；同时比较 actual Dataset `image/qpos/cam_extrinsics` 与 pure official；`all(checks)` 才保存。**符合。**
- **frame 保存/strict load/NoOptimizer/缓存**：`input_worker.py:95-110` 保存五边界；`model_worker.py:79-92` strict load、375 项、有限值；`model_worker.py:18-33` 仅 `builder_module.torch` proxy + `NoOptimizer`，不改 vendor；`model_worker.py:15-17` 只接受已缓存 ResNet URL；`model_worker.py:94-99` eval/inference、requires_grad False。**静态可执行；strict load/缓存适配只能在真实验证。**
- **内部 forward 票据**：`call_guard.py:12-49` `policy_enter` 先 reserve 再校验 branch/keys/batch；`internal_enter` 只允许一次内部 forward，额外/重入会再 reserve 并 raise；`model_worker.py:45-69` policy/internal wrapper；`model_worker.py:157` 要求 16/16 且 active None。**不漏不双计；若异常也消耗票据。**
- **两 worker / 父审门**：`supervisor.py:42-68` input 初始化 run_state/lease；`gates.py:46-92` `input_gate` 要求 actual images/CPU originals、RUN_MODEL、input worker EXITED/identity inactive、counts=12/24/1/1、GPU≤210；`gates.py:114-134` worker lease/token/PDEATHSIG；`supervisor.py:93-137` 15s margin、累计 600、8h deadline、stop。**模型阶段不可绕过；等待无 GPU worker。**
- **预算**：input 210（195 stop+15 release），model `600-实际`、至少390、距截止15s；总2 worker、1 make_env实际/2上限、12/24、16 ACT、0 step/rollout/optimizer。**自洽。**
- **无新训练/rollout/下载/旧路径写入**：`runtime_safety.py:19-33` audit hook 限定 P 内写入；`:47-56` 缓存只读；`model_worker.py:35-44` 禁止 backward/grad/hub；`gates`/manifest; **静态符合。**
- **metrics 落实 notes/02**：`metrics.py:9-23` 同 mask/单位；`:50-59` 四状态等权、pooled/mean-state RMS；`:71-88` 0/1 噪声公式、4/5 单次1e-5、不借噪声；`:91-116` 双常数同时击败、20%只投资、3/4且覆盖两 demo、7维、方向/夹爪退化；`analyze.py:18-51` first/repeat分离、posterior不重复计能力；`:72-88` 局限。**符合。**
- **未知非空 context**：`owned_release.py` 已前置 raw/key 一致性、live/display/surface/owner 检查；manifest SHA 与 render_controlled 一致；CPU mock 只作软件路径，不能替代真实 EGL。**静态正确。**

## 5. 只能正式运行才知的风险（不阻塞一次有限诊断）

以下均为**失败即停**的运行时门，不是静态假通过：

1. `input_worker.py:112-114` sample0 与参考像素逐像素一致；实际 `T.Resize(256)` 是否 no-op、Dataset 与 `lib.render` 是否同像素，只有真实采图能确认；不一致即 STOP。
2. `input_runtime.py:125-137` current/owner/3FBO+4RBO/GL errors/raw=sentinel；真实 EGL 生成的对象身份与 readback 才能确认。
3. `model_worker.py:79-92` 375 项 strict load、`ck['args']==args`、stats bit-equal；只有真实 checkpoint 加载能确认。
4. `model_worker.py:15-17` 缓存 ResNet URL 适配是否命中；未命中即停。
5. `model_worker.py:18-33` `NoOptimizer`/proxy 与 `torch.optim.AdamW.step` 赋值在目标 torch 2.6 是否按预期；失败即停。
6. BF16 实际输出重复差是否 <1e-3；sample0/1 重复门、sample4/5 单次1e-5 门；真实数值才能确认。
7. 210/390 秒与 600 秒累计、`nvidia-smi` 监控、8h 截止是否足够；真实吞吐才能确认，不预判成功。
8. 自然 A 释放窗口是否出现；未出现只记 `NOT_REPRODUCED`，健康门通过仍可做固定权重诊断；二者分开报告。

## 6. 下一提示词：APPROVE_AS_REVIEW_DRAFT

**APPROVE_AS_REVIEW_DRAFT。** 更新稿已正确处理：

- 只暂停当前 checkpoint/当前诊断，不是 KYC/领域 No-Go；
- 16 = 12 基础 + sample0/1 各官方/自定义重复4；sample4/5 无重复、不借噪声；
- 两个 worker：输入制备→父审 CPU/图像门→模型 strict load；等待无 GPU；
- 自然窗口未出现记 NOT_REPRODUCED，不强制 GC；健康门通过可做固定权重诊断，但模型结果不能反证自然生命周期；
- official/custom 同 raw；prior 无标签；posterior 真动作仅诊断；常数/方向/夹爪/20%投资门/小样本局限均落实。

**但这不是新运行、完整训练或最终代码通过。** 正式 RUN 仍需主线程派发；准确 code/SHA 仍需按本回复第3节复核。

## 7. 旧 0/32、重训、F

- **旧 0/32：D / IMPLEMENTATION-LIMITED**，不是 A/B/C；当前局部机制不追认历史。
- **完整重训：不建议现在做**；先完成健康输入冻结 checkpoint 诊断；任何恢复性训练需人类另行批准。
- **F：不合格**；当前是工程/基线诊断，不是论文机制；KYC/CamVLA/AnyCamVLA/MoVie 已覆盖大部分相机适应，persistent/IID 残余未证；不把修复或 4 状态诊断包装成创新。

## 8. 本轮报告必须保留的限制

- 局部 PASS 只适用固定 sample0、共同 A/B fixture、受控释放点；未分离 owner 释放与 previous 恢复子步骤；未证明自然 GC/多视角/长期/线程。
- baseline after 视觉像场景不等于健康；无有效 readback，内存来源未知。
- 旧训练 RGB/GL 历史缺失，旧 0/32 UNKNOWN；不自动部署、不恢复 ACT/rollout/训练。
- 4 状态/2 demo 只描述训练内信号，不证明泛化、视觉因果或 Lift 成功；20% 是投资门，不是科学阈值。
- CPU mock、本回复的静态审查和两个 SHA 的引用都不能替代真实 EGL/strict load/模型输出；未执行内容均为 NOT_RUN。
