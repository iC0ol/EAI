**原件支持的内容**

- `expert_result.json`：4 root全部 `success/reach/grasp=true`、`success_interfaces_agree=true`、`control_checks_pass=true`；`restore` 的 state/geometry/controller 均 exact；步数 105/102/126/97；`expert_EEF_deviation_max` 为 2.86e-4 / 9.48e-5 / 1.01e-4 / 1.48e-4 m，均<0.02m；最小EEF-cube距离 5.16–7.06mm；最大cube高度约0.944–0.948m。
- 四份 `A_root0..3_steps.jsonl` 行数与步数完整（105/102/126/97）；我查看了初始、首次夹持、首次成功及终末段：`delta`/`absolute_target`/实际EEF/夹爪qpos/高度/`reward==1`/`_check_success` 旁证一致。**约1.5cm的 `target_translation_tracking_error` 是实际EEF到累计目标的位置误差，不是专家对HDF5 `next_obs` 的偏差**；后者仅约1e-4m，不能用1.5cm误判专家回放失败。
- `expert_a_completion`：8帧初始/终末 readback 全部机器健康，normal=sentinel；`all_readback_machine_health_pass=true`。我查看了 `figures/expert_a_contact_sheet.png`：4 root初始/终末均见机器人、桌面、绿方块；终末夹持姿态可见，无明显条纹/空帧。**我没有独立解析NPZ或重算数组**；readback健康/PNG是视觉与元数据证据，不是我的数组复算。
- `stages/expert-a.json`：exit0、75.4795101750642s/180、累计110.06071671471s；phase为1 worker/1 make_env/5 resets/8 render/16 read/430 env_steps/4 rollouts/0 ACT；无训练/step越限。
- `science_clock.json`：deadline `1793842996.235501`（本地2026-11-05 09:43:16.235501），未延长。

**限制**

root为seed42..45替代场景；`not_original_demo_XML=true`，不是原示教XML或旧dev物理root；A阳性只证明这4个替代root上的动作累积、控制器、成功判据和专家回放阳性，**不证明策略任务行为**。B/C尚未执行。

**结论**

**APPROVE_EXPERT_A_CONTROLS_AND_NEXT_B**。A的匹配专家控制、恢复、动作/成功接口足够作为B的控制门；B只按原4 root train/dev配对8条、各150步/5 query/40 ACT、360 GPU秒执行；C仍各135秒且需新派发；科学截止不延长，0训练，无旧20% MAE门。B仍须expert_gate/独立双审及新精确SHA派发；本批准不宣称B/C任务成功。

- `candidate_manifest.json`：`3179c07a0cf77758d4dff01d57ffebcca1af0c11bc4034a0753b32610f40b530`
- `PROTOCOL_CANDIDATE.md`：`8773f4b7733335898d2bed5803f0d7729798896892abe6bdefd604a1f71a8ed8`
