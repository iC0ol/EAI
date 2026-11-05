**原件支持的内容**

- `roots/manifest.json`：4个替代root、20个root文件；`root_0..3` 的 XML/state/rng/control/physical_model 均有SHA；`first_absolute_command_error` 为 0 / 2.38e-7 / 0 / 0，均<1e-4；`source_demo_XML_available=false`，未冒充原始XML。
- 四份 `control.json` 均含 wrapper绝对目标、controller goal/origin/initial_joint、gripper actual；四份 `physical_model.json` 含 nq/nv/nu/nbody/ngeom/njnt 与 body/geom/jnt/actuator 指纹；root之间几何确有差异。
- `stages/gpu-preflight.json`/`scope_state.json`：exit0/EXITED，34.58120653964579s，quota90；counts为1 worker、4 make_env、8 resets、2 render、4 readPixels、0 ACT/env_steps/rollout/getitem/backward/optimizer。
- `results/gpu-preflight/events.jsonl`：实际2次`mjr_render`、4次`mjr_readPixels`，readback前后GL codes=[0]，owner/active objects为MEASURED_IN_OWNER_CONTEXT；cleanup有owned_release_DONE，结果`all_contexts_destroyed=true`、无fatal/cleanup_error。
- `preflight_strict_load.json`：strict=true、missing/unexpected均空、375 tensors、checkpoint SHA c904…、cached resnet f370…、optimizer未创建/未载入。
- 我实际查看了`preflight_train.png`/`preflight_dev.png`：均见机器人、绿色方块、桌面，未见条纹/空帧；仅这两帧，不等于全量健康。

**原件不支持的内容**

- `completion`明确`root_full_restore_control_path=DEFERRED_NOT_EXECUTED`：预检**未验证`roots.restore`及controller恢复路径**；A是第一次真实restore。
- 预检不能支持A/B行为、任务success/reach/grasp、C的crop/collate、历史0/32因果或论文复现；`science_clock_started=false`、`A_B_C_run=false`。
- 我**未独立解析NPZ或重算raw/sentinel数组**；readback相等/健康来自readbacks、events及PNG，不是我的数组复算。父审独立数组验收仍需保留。
- root是seed42..45的替代场景，不是原示教XML；不能称旧dev物理root或原场景恢复。

**预算与下一A**

`34.5812065396458 + 180 + 360 + 135 + 135 = 844.5812065396458 ≤ 900`，余55.4188秒；按指示不授权追加。A180覆盖4条专家430步/初始化，B360覆盖8×150步/40 ACT，C各135覆盖22 getitem；量级合理。A为首个科学RUN并启动8h；下一只执行A4专家，B仍须实际A4/4、控制/成功接口一致及expert_gate/新派发；C计划不变。

**必须保留的停止条件**

- A：restore/state/geometry/controller/RNG不精确、任一专家非阳性、`reward==1`与`_check_success`不一致、EEF控制偏差≥0.02m、done/非有限/超预算——停止，不进入B，不换root/不重试。
- B：仅在A 4/4及expert_gate后；8条/5 query/150步/40 ACT固定；个别成功不称论文复现；非有限/异常/超预算停止。
- C：不装owner修复、不强制析构；首故障后按预定split继续；GL/FBO单独不等于坏像素；无当前tensor污染不得追认历史；无额外render/getitem。
- 总900秒硬停，余量不得追加；预检通过不等于A/B/C行为或恢复control路径通过。

**结论**

**APPROVE_PREFLIGHT_AND_ALLOCATION**，仅接受本次预检并冻结 A180 / B360 / C-local135 / C-official135（含已用34.5812065396458，总844.5812065396458≤900）；不批准A/B/C行为或科学结论。

- `candidate_manifest.json`：`3179c07a0cf77758d4dff01d57ffebcca1af0c11bc4034a0753b32610f40b530`
- `PROTOCOL_CANDIDATE.md`：`8773f4b7733335898d2bed5803f0d7729798896892abe6bdefd604a1f71a8ed8`
