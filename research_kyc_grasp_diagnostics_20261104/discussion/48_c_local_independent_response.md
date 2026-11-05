**C-local原件验收**

- `c-local_result.json`/`stages/c-local.json`：22个实际item、2个真实collate（validation 10、train 12）、2个within-arm repeat（demo0/1 t0，`same_source_state/geometry/T/camera/seed/crop/raw/post_crop`全true、两collate均保存）、2个guard位置（c-local均未执行）；22 getitem/22 render/44 read；0 ACT/step/train。GPU 28.54238737700507s/135，累计339.8689732486382s。
- 22个item的`action_time_mask_exact`、`post_crop_is_actual_item_exact`、`normal_to_actual_crop_CPU_reconstruction_exact`均通过；2个batch的image/qpos/actions/is_pad/cam_extrinsics形状与逐item slice核验通过；48? ——C-local是22个readback（22帧），全部normal=sentinel、GL健康；事件132条对应22帧×6，未发现坏RGB/传播到item/collate。
- 我查看了`figures/c-local_actual_collate_RGB.png`全部22个实际batch RGB切片及`train_d0_t0_raw/actual_crop`图：机器人、桌面、绿方块清晰，无可见条纹/空帧；但**我未独立解析NPZ/batch数组**，该限制保留；图注/布尔不当作数组重算。
- repeat在相同state/相机/seed/crop下完全一致；动作/状态索引与生成XML身份边界按替代场景记录；`initial_generated_model.xml`非原demo XML，不能称原示教场景恢复。
- **限制**：`owner_aware_fix_installed=false`、`forced_GC_or_destructor=false`、无官方guard；目标释放窗口`NOT_REPRODUCED`，不能据此宣称自然故障未发生或已修复。C-local当前无坏RGB，但不解释旧0/32历史因果；B负例仍不能给出历史0/32唯一根因。

**结论**

**ACCEPT_C_LOCAL_AND_APPROVE_C_OFFICIAL**。只批准下一新c-official单次135 GPU秒/22 getitem、唯一添加实际官方两guard，其余不改；总900/科学截止2026-11-05 09:43:16.235501不延长，不新增ACT/step/train。C-official仍须新派发，不能把C-local当作官方guard或历史因果结论。

- `candidate_manifest.json`：`3179c07a0cf77758d4dff01d57ffebcca1af0c11bc4034a0753b32610f40b530`
- `PROTOCOL_CANDIDATE.md`：`8773f4b7733335898d2bed5803f0d7729798896892abe6bdefd604a1f71a8ed8`
