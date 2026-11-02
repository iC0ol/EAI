# 最终审阅稿分歧处理

## 1. 事件索引更正

按 `results/worker_1_baseline/events.jsonl` 逐行零基核对：

- **31/32**：`baseline_before_con_free` / `baseline_after_con_free`，B 的 3 FBO + 4 RBO 由 true→false；
- **34/35**：`eglDestroyContext_enter` / `exit`，不是解绑；
- **37/38**：`eglReleaseThread_enter` / `exit`，38 出口 current=null，**这才是解绑**。

我 24 说“34/35 后解绑”不准确，撤回；原 23 的 **37/38** 才对。fix 的 **31/32 绑定、33/34 owner、46 restore、47 previous、52 exit、53–60 after、61 cleanup** 已核实正确。原回复不改。

## 2. 局部修复验收保持不变

**LOCAL_CONTROLLED_PASS 保持。** 证据链完整：

- baseline 31/32 中 A owner、B current；A 正确 `NOT_MEASURED_WRONG_CONTEXT`；B 原 3 FBO + 4 RBO 同 namespace/ID 由有效变无效；37/38 解绑；after 无有效 readback。
- fix 33/34 在 A current 下释放 A；46 native restore 返回 true；47 `previous_restored`；52 A 销毁、B 原对象有效；after 与 before 逐像素相同；正常=sentinel、GL 读回 codes=[0]；guard 首次未跳过、无二次 free、无资源重建。
- 2 worker/2 make_env/4 render/8 readPixels/19.29s/0 ACT/step/训练，旧文件与 SHA 未变；合规。

**限界不变**：整笔 owner 释放+previous 恢复事务未拆成两个子步骤；固定 sample0/人为共同 fixture/受控释放；未证明自然 GC 频率、多视角、长期/线程；baseline after 虽视觉像场景但无有效新读回，内存来源未知；旧训练 0/32 仍 UNKNOWN。这些限制不否定局部 PASS，但禁止升级为自然/生产修复或旧根因。

## 3. 自然窗口与健康模型诊断的逻辑分界

**接受。** 两者是**不同问题**：

- **自然窗口未出现**：明确记 `NOT_REPRODUCED`，不得宣称自然生命周期修复已验证，也不得把该输入的“健康”当作修复因果。
- **健康输入上的模型诊断**：只要按原 execution 源码冻结的准确入口、状态/相机和健康门（current/owner/对象、sentinel=raw、GL 错误、图像可辨认、参考像素）通过，就可以评估**已有冻结 checkpoint 在这些健康输入上的 prior/posterior/常数能力**；它不需要也不应强制制造自然 GC 窗口。
- **不能混用结论**：模型诊断通过只说明“该 checkpoint 在固定健康输入上有数值信号”，不证明旧训练一直健康、不证明自然 GC 修复、不证明 Lift 任务阳性。自然窗口 `NOT_REPRODUCED` 与模型健康门通过必须并列报告。

这个判据合理，避免了为机制复现而额外造 GC；唯一混杂是“健康输入路径可能与旧故障路径不同”，所以必须限定为健康输入能力诊断，并保留旧 0/32 独立 UNKNOWN。无需预算内替代实验。

## 4. 下一提示词：APPROVE_AS_REVIEW_DRAFT

更新后的 `03_下一阶段提示词_冻结模型诊断待批准.md` 已修正：

- §3 不再凭类名编造 `make_env→Dataset→Evaluator→embedder` 串行链，要求按原 execution 源码冻结真实调用顺序；无 fixture 强引用、强制析构或直接 render 旁路；自然窗口未出现记 `NOT_REPRODUCED`，但健康门通过可继续固定权重诊断。正确。
- §3 两 worker：第一个只做输入制备后退出；主审 CPU 看图/门后，第二个才 strict load 和前向；等待时不保留 GPU 进程，不预算外等待。正确。
- §4：16 次 = 12 基础（4 样本 × 官方 prior/自定义 prior/官方 posterior）+ sample0/1 各官方与自定义 prior 重复 4 次；sample4/5 无重复且不能借 sample0/1 噪声解释。正确，补上了此前自定义重复缺项。
- §4/§5：official/custom 同 raw；posterior 真动作仅诊断、不是部署；strict load；prior 重复噪声；常数地板；4 状态/2 demo 不包装显著、不证明任务能力；只暂停当前 checkpoint/当前诊断范围，不是 KYC/领域 No-Go。正确。
- 最终集成代码 SHA、阈值、停止门仍需双方冻结后再派发。正确。

**结论：APPROVE_AS_REVIEW_DRAFT。** 它不等于新运行、不等于完整训练批准、不等于最终代码通过；研究负责人批准后才执行。

## 5. 是否还有阻止交付的缺项

**没有阻止“作为审阅稿交付”的实质缺项。** 唯一必须保留的执行注记：自然窗口 `NOT_REPRODUCED` 与健康模型诊断必须分栏报告，不能互相背书；sample4/5 的入口差异不能借 sample0/1 重复噪声解释；最终代码 SHA/阈值/停止门另行双审。

## 6. 旧 0/32、重训与 F

- **旧 0/32：D / IMPLEMENTATION-LIMITED**，不是 A/B/C；当前局部机制不能追认历史。
- **完整重训：不建议现在做。** 先做上述冻结 checkpoint 健康输入诊断；任何恢复性训练需人类另行批准、独立预算与停止标准。
- **F：不合格。** 当前是工程修复，不是论文机制；KYC/CamVLA/AnyCamVLA/MoVie 已覆盖大部分相机适应空间；没有新的独立科学问题。

## 7. 本轮报告必须保留的限制

- 局部 PASS 只适用固定 sample0、共同 A/B fixture、受控释放点；未分离 owner 释放与 previous 恢复子步骤；未证明自然 GC、多视角、长期/线程安全。
- baseline after 视觉像场景不等于健康；无有效新 readback，内存来源未知。
- 旧训练 RGB/GL 历史缺失，旧 0/32 UNKNOWN；不自动部署、不恢复 ACT/rollout/训练。
- 下一提示词只是审阅稿；生成不等于授权。完成后停止主/子定时检查，等待研究负责人决定；CLI 累计费用不是真实账单。
