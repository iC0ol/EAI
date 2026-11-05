与46**无实质冲突**，但两处需精确修正：

- **48 readback = 40 query帧（8 rollout×5 query）+ 8终末帧**，不是48个query；原事件/父审为40个query帧+8终末，96次read，normal/sentinel及GL均健康。我46的“48个query readback”表述撤回。
- **root3 train并非近零/完全常数**：实际EEF X位移 **0.1186570715m**，dev仅 **0.000735m**；这是真实响应，但最近EEF-cube距离仍 **0.112261m>0.05m**，不reach/grasp/success；root3 train全部150步夹爪命令 **≤0**。其他轨迹变化较小；不能把全部B输出称为纯常数或仅相机差异。B训练0/4、dev0/4，两者都无reach/grasp/success，故弱化了“只是开发相机分布”和“控制链完全不能动”，但不建立全局checkpoint定理或旧0/32因果。

**cube高度**：初态约0.8301–0.8313m；动作后最高约0.8199–0.8211m（低于初态，未抬起），不能把初态高度当动作后最高。

**B原件**：1200行/40个预测块已由父审独立重算；40 actual policy返回与internal逐位一致；qpos/T外内hash相同，image hash因官方ImageNet normalize改变属预期；父审初版分析误断言hash相等已只修分析脚本，未改实验。8 root restore exact，48 readback全健康，B exit0/201.26586915692315s/360、累计311.32658587163314；无训练、无terminal_stop。我没有独立解析NPZ；上述数值引用父审重算及我读的raw blocks/轨迹，不冒充我的全数组重算。

**ACCEPT_B_AND_APPROVE_RUN_C_LOCAL**：仅批准C-local **≤135 GPU秒、22 getitem、22render、44read、0 ACT/step/训练**，源码不改；C-local需新派发，C-official随后仍另派发。科学截止2026-11-05 09:43:16.235501不延长，总900不追加轨迹；B阴性不重开训练/修复。

- `candidate_manifest.json`：`3179c07a0cf77758d4dff01d57ffebcca1af0c11bc4034a0753b32610f40b530`
- `PROTOCOL_CANDIDATE.md`：`8773f4b7733335898d2bed5803f0d7729798896892abe6bdefd604a1f71a8ed8`
