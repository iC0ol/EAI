**B原件审查**

- 8条均正常执行150步/5 query/40 ACT；4 train + 4 dev 的 success/reach/grasp 全为0；最小EEF-cube距离约0.112–0.344m（均>0.05m），cube最高约0.8199–0.8211m（未抬起）；终末EEF轨迹可见，未发生提前终止。
- 抽查 `review_packets/policy_raw_blocks.jsonl` 每root至少一块，并与对应`steps.jsonl`首步执行动作对齐：输出确实被执行；`policy_result` 40个实际模型输出、policy/internal各40、official policy return与internal逐位一致；`model_events` 120条与40×3一致。**我没有独立解析原NPZ**；raw block是带原件SHA的无损CPU转写，我的核对限于该转写与轨迹行。
- 8条`restore_state_geometry_controller_exact=true`；48个query readback全部normal=sentinel、GL健康；同root train/dev初态一致，输入健康/恢复可信。B不是“仅相机分布”：train与dev均0/4；也不能把输出称为完全常数——各root/相机有轻微变化（如root3 train首步x约1.26e-3），但总体近零、远小于专家动作且无reach，属弱输出，不足以归为单一相机原因或单一常数。缺demo XML，仍是替代场景；不能把B 0/8直接等同于旧0/32历史原因或论文结论。
- `stages/policy-b.json` exit0/EXITED、201.26586915692315s/360、累计311.32658587163314s；无`terminal_stop`、无C；B行为阴性不触发旧MAE门。

**结论**

**ACCEPT_B_BEHAVIORAL_RESULT_AND_APPROVE_C_LOCAL**。仅批准既定 C-local：≤135 GPU秒、22 getitem、0 ACT/step/训练、源码不改，使用新C-local派发；C-official仍需另一次新派发。科学截止2026-11-05 09:43:16.235501不延长，总900不追加轨迹。B阴性结果不说明检查点全局无能力，也不能反推旧0/32已定位。

- `candidate_manifest.json`：`3179c07a0cf77758d4dff01d57ffebcca1af0c11bc4034a0753b32610f40b530`
- `PROTOCOL_CANDIDATE.md`：`8773f4b7733335898d2bed5803f0d7729798896892abe6bdefd604a1f71a8ed8`
