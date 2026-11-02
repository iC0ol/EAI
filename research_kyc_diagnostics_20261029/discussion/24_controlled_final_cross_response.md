# 最终反驳与交付审查

## 1. 事件零基纠正

我 23 轮的 fix 索引确实偏 1，现按 `results/worker_2_fix/events.jsonl` 逐行更正：

- **31/32**：`eglMakeCurrent_enter` / `eglMakeCurrent_exit`，owner 绑定 enter/exit；
- **33/34**：`owner_bound_before_con_free` / `owner_bound_after_con_free`；
- **46**：真实 `restore_native_return`，返回 true；
- **47**：`previous_restored`；
- **52**：`controlled_A_release_exit`；
- **53–60**：after 采图（frame_before、render/read、frame_after）；
- **61**：cleanup 首次释放 B；**不是 after 采图**。

baseline **31/32** 仍是 `baseline_before_con_free` / `baseline_after_con_free`，此前正确。我 23 写的 34/35、53、54–61 不准确，撤回；不由 `analysis` 复述替代逐行核对。

## 2. 当前修复：LOCAL_CONTROLLED_PASS，限固定 fixture

**PASS（局部受控）有足够证据，但只能按限定范围接受。**

- baseline 31→32：owner=A、current=B；A 正确记 `NOT_MEASURED_WRONG_CONTEXT`；B 的 3 FBO + 4 RBO 同 namespace/ID 由 true→false；34/35 后解绑；after 无 current、sentinel 100% 165、无有效新读回。
- fix 31/32 绑定 A，33/34 在 A current 下测 A 对象 true→false；46 native restore true，47 `previous_restored`，52 A 销毁、B original objects 全部有效；53–60 after 与 before 逐像素相同；正常=sentinel，GL 读回 codes=[0]。
- guard：两条件首次 entry/done 各 1，con.free/context destroy 各 1，仅 DONE skip，无 RUNNING 跳过、无二次实质 free；没有重建 B 或保留资源换好图。
- 2 worker/2 make_env/4 render/8 readPixels/19.29s/0 ACT/step/训练；旧 295 文件、脚本/来源 SHA 未变。合规。
- unknown 非空/raw key=None 防护已在新 `owned_release.py` 前置于 bind/free，CPU mock 通过；实际 GL 未触发该分支，不能当本次原因。

**最强反证**：整笔 owner 释放 + previous 恢复事务没有被拆成两个子步骤，无法分别归因；fixture 人为强持有 A/B 并强制释放，不是自然 GC；旧训练历史缺失；baseline after 虽然视觉像场景，但无有效 readback，具体内存来源未知。这些都限制外推，但**不足以否定固定受控 fixture 下的 LOCAL_CONTROLLED_PASS**；若把它升级为自然/生产修复或旧 0/32 根因，则证据不足。

## 3. 旧 0/32、重训、F

- **旧 0/32：D / IMPLEMENTATION-LIMITED。** 当前只证明局部渲染生命周期机制；没有历史训练 RGB/GL，不能归为 A 类实现根因，也不是 B/C。
- **完整重训：不建议现在做。** 即使局部修复成立，旧 checkpoint 是否经历同窗口仍未知；完整 ACT 训练需人类另行批准。可先做一份短小、零更新、冻结 checkpoint 的输入/prior/posterior 诊断；该诊断是建议，不是执行授权。
- **F：不合格。** 当前是工程排障，不是论文机制；KYC/CamVLA/AnyCamVLA/MoVie 覆盖大部分相机适应空间，persistent/IID 残余未证明；不把修 bug 包装成创新。

## 4. 下一提示词：REVISE（可交付为审阅稿，不可执行）

`03_下一阶段提示词_冻结模型诊断待批准.md` 的总体目的（健康输入、strict load、prior/posterior/常数、16 forwards、0 step/训练）合理，但必须改三处才能作为下一阶段候选：

1. **§3 必须写死自然输入路径**：使用原 `make_env→EpisodicDataset→Evaluator→embedder` 顺序、无 fixture 强引用，实际经历自然 owner 释放窗口；若窗口未出现，报告 `NOT_REPRODUCED`，不得用直接 render 或受控 fixture 的健康图替代。现稿只说“不能靠复制受控fixture强引用掩盖自然释放”，不够明确。
2. **§4 的 prior 重复只有官方入口**：需改为 **2 官方 + 2 自定义** 重复（或明确“自定义噪声未测，1e-5～1e-3 差异不作噪声解释”）。否则 official/custom 入口差异可能被误归 H1。16 次预算内可分配：4 样本各 official/custom/posterior 3 次 =12，余 4 次为 2 官方 +2 自定义重复；或删去一个 posterior 重复，保持事前冻结。
3. **§5 “形成暂停KYC投入的证据”过宽**：4 状态/2 demo、单一 checkpoint 只能支持“暂停当前 checkpoint/当前范围投入”，不能写 KYC 或相机鲁棒性 No-Go；应改为“暂停当前冻结 checkpoint 与当前诊断范围，不构成 KYC/领域 No-Go”。

其余：strict load、same raw official/custom、posterior 真动作不作部署、常数地板、小样本不证明任务能力、最终集成代码/阈值/停止门双方冻结后再派发——这些正确，保留。

**结论：REVISE，不是 APPROVE_AS_REVIEW_DRAFT 直接通过；改完可再作为审阅稿交付，仍不是执行授权。**

## 5. 本轮报告必须保留的限制

- 局部 PASS 只适用固定 sample0、同一 A/B 强引用 fixture、受控释放点；不证明自然 GC 频率、多视角、长期/线程稳定性。
- 整体事务未分离 owner 释放与 previous 恢复的各自贡献；baseline after 视觉像场景但无有效读回，内存来源未知。
- 旧训练 RGB/GL 历史缺失，旧 0/32 仍 UNKNOWN；当前修复不自动部署、不恢复 ACT/rollout/训练。
- 下一提示词只是研究负责人审阅稿，生成不等于授权；完整训练需人类另行批准。CLI 累计费用不能当真实账单。
