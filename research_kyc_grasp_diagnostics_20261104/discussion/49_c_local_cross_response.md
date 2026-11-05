与48**无实质冲突**；需精确修正：

- C-local是**22帧/44 read**，不是48帧；`mjr_render/readPixels`测量事件为 **22帧×6=132**，这只是render/read测量事件数，**不是整份`events.jsonl`总条数**（另含context/生命周期记录）。我48中“132事件”应按此理解，不能当总事件数。
- 父审独立读取两完整batch，22×5 tensor哈希与HDF5 state/actions/time mask一致；6组保存raw独立重算flip/255/crop到实际batch，1个full pre/post代表9通道crop一致；其余16 raw只有runtime hash/health，**不能说全部raw被父审重算**。我本人**未解析NPZ/batch数组**，父审重算不是我的计算。

**原件支持**：22 actual items、2 collate（10/12）、22 render/44 read、0 ACT/step/train；20个不同image hash+2个预定相同repeat，完整9通道重复逐位一致；全部22 postcrop RGB已查看，无可见条纹/空帧，无GL/tensor fault；两repeat的state/geometry/T/camera/seed/crop一致；native目标释放窗口 **NOT_REPRODUCED**；两guard未执行、0 resets、无owner修复/强制GC。只能证明有限短采样健康，不能证明旧训练4.57h健康或恢复原demo XML；state/action索引关系已核，场景原身份未知。

**ACCEPT_C_LOCAL_AND_APPROVE_RUN_C_OFFICIAL**：仅新一次c-official≤135 GPU秒、22 getitem、22 render、44 read、0 ACT/step/train；唯一差异是实际执行官方两guard，其余不改；scope总900、截止2026-11-05 09:43:16.235501不延长。C-official后实验结束，不做训练/排障追加。

- `candidate_manifest.json`：`3179c07a0cf77758d4dff01d57ffebcca1af0c11bc4034a0753b32610f40b530`
- `PROTOCOL_CANDIDATE.md`：`8773f4b7733335898d2bed5803f0d7729798896892abe6bdefd604a1f71a8ed8`
