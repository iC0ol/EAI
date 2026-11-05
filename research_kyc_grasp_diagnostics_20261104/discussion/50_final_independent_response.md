**C-official原件**

`c-official` exit0、27.843600154388696s/135；总账本 **367.7125734030269s/900**（preflight34.5812+A75.4795+B201.2659+C-local28.5424+C-official27.8436）。22 item/2真实collate（10/12）、22 getitem/22 render/44 read、0新增ACT/step/train；`stages`/`scope_state` 计数一致，无追加。两官方guard `actual_guard_executed=true`，但 **guard-added resets=0**；阶段make_env自身有1次reset，不能把“0 guard reset”说成本阶段完全无reset。22条local/official对比全部 `same_source_state/actions/geometry/T/crop/post/item/raw`，两batch整个NPZ SHA相同；22帧readback全normal=sentinel、GL健康；目标释放窗口`NOT_REPRODUCED`，无owner修复/强制GC；图`c-official_actual_collate_RGB.png`我已看，22张清晰无显见条纹/空帧。**我未独立解码batch NPZ/raw数组**；上述均为原件记录/图/父审或执行端比较，不是我的全数组重算。

**1. 旧0/32是否定位具体原因：否。** A专家4/4阳性；B训练/dev各0/4；C-local/official在当前短样本无坏RGB、无guard reset、无目标释放、无owner错误；C未复现训练输入污染。官方guard/周期评估与本地差异是源码事实，但没有当前故障或历史逐帧证据连到旧4.57h；原demo XML仍缺。历史根因UNKNOWN。

**2. checkpoint训练相机任务阳性：无。** B 4个替代root训练相机0/4 success/reach/grasp，dev也0/4；最小EEF-cube距离0.112–0.344m>0.05，动作后cube最高约0.8199–0.8211m（初态约0.830–0.831m，未抬起）。A 4/4专家控制说明动作/判定/恢复链可用；B说明当前checkpoint在这四个替代场景无任务阳性。不是原32重跑或论文复现。

**3. 弱输出是学习、部署/数据还是相机：不能唯一区分。** B输入48 readback健康、8次restore exact、40实际输出确实执行；训练与dev双0，故不能仅归因开发相机分布。root3 train实际EEF X位移0.118657m（dev0.000735m），夹爪全程≤0，说明并非完全恒定/完全不看图，但仍不reach、不grasp。剩余假设至少包括：学习/prior不足、训练数据与单场景几何对应、历史训练输入污染（当前C未复现）、相机/视角、表示与优化；当前4 root不足以分离。

**4. 与0/32有合理因果关联的具体可复现工程错误：无。** C-local/official均无坏RGB、无故障传播到item/collate；6对保存raw和22 postcrop tensor支持当前健康；16组raw未保存只能靠runtime hash/health；两guard执行但未触发reset，不能证明guard修复。缺失本地FBO guard/周期评估是源码差异，不是当前复现故障或历史根因。

**5. 最小修复/是否需重训：没有证据支持具体修复或重训。** 当前链路健康、B仍无任务阳性；修复guard/重训都不能由本轮证据证明会改善；不授权训练或修代码。

**6. 是否继续KYC为F基础：当前checkpoint路线No-Go；F一般假设未被证明无效。** 当前checkpoint无任务阳性，不能作为F机制基线；优先选择已有官方权重、任务阳性可复验的基线，再谈准确标定与persistent/IID。Stage3仍PLAN_ONLY；不新增GPU、训练或排障。

`candidate_manifest.json`：`3179c07a0cf77758d4dff01d57ffebcca1af0c11bc4034a0753b32610f40b530`
`PROTOCOL_CANDIDATE.md`：`8773f4b7733335898d2bed5803f0d7729798896892abe6bdefd604a1f71a8ed8`
