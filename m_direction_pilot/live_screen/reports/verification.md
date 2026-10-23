# 交付检查

8项执行前测试全部通过，另2项交付测试全部通过。首次合成优化失败的原日志仍保留，
解析Jacobian修复发生在执行代码提交和任何新仿真之前，未改科学规则。

交付测试将108个公开CSV.GZ中的全部17类数组（总1836个数组）按索引shape/dtype
恢复，与本地原始NPZ逐值完全比较；通过。公开轨迹合计46530082 bytes，NPZ继续
保留在local/traces/，通过trace_index.csv的两组SHA对应，不上传运行时/权重/HDF5。
两张静态科学图均已实际打开检查，标签与缺失值可读。

final_audit核对全部108次reservation/finish/result SHA、raw NPZ SHA、执行源码SHA、
实际前后缀/积分计数、每次noise/history实值hash，以及正式分支相对名义分支的
fork/controller/cache/history/RNG/geometry与噪声表。首步动作回执未clip、增量正确。
108次全部完整，0次重试、无部分积分；Y与原始每步success flags一致。

12原状态和160原计划完整保留，4个held-out状态/52个槽位未运行，Y为空。L-B1/B2
各完成全部计划后才作科学判断；L-B2方向信息仅1来源，因此continue=false。
PSD强预警为false，不伪造强拒绝；world/object/task/contact基线未拟合，不算作被击败。

历史113个M文件、原HDF5/权重/config/normalizer/requirements及相关upstream SHA
均通过；5个旧分支引用不变。全部新交付位于live_screen/。无新模型、训练、Gate1、
额外状态/噪声/radius/task、旧源状态修复或阈值放宽。最终seal清单不哈希自身，Git提交
绑定该清单与交付文件。实验结束后不再进行新的推理或仿真。
