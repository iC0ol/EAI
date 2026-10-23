# 原始输出与读取约定

全部测量对象均为online replay surrogate；源日志动作只用作log-action proxy。
`all160_allocations_actual.csv`保留全部冻结槽位。未运行Y为空，不得当作失败0。
`all12_states_actual.csv`保留全部原状态；`episode_summary.csv`以来源为汇总单位。
`signed_outcomes.csv`保持每个±分支，DeltaY=Y_nominal−Y_perturbed：−1表示改善。
`sign_asymmetries.csv`和`improvements.csv`仅在存在对应记录时产生，不作正负平均。

每支`outputs/branches/*.json`保存协议/执行SHA、数据/权重SHA、代码SHA、实际计步、
fork指纹、物体/task/contact坐标、首步控制器回执、源/代理偏差、每次replan噪声种子及
输入历史hash、ever/final success、CPU/GPU成本。全部尝试先进入append-only ledger。

本地`local/traces/*.npz`含完整prefix/suffix原始数值；不提交NPZ。相同数值以无损浮点
十进制JSON逐行导出到`outputs/raw_trajectories/*.csv.gz`，公开同步。`trace_index.csv`
同时列出本地NPZ与公开CSV.GZ的SHA、每个数组的shape/dtype。每个CSV行：
phase、control_step、array、values_json；同一array各行按原数组第0轴顺序恢复，
用索引中的dtype重建即可逐值比较NPZ。gzip mtime固定0以便稳定哈希。

`branch_costs.csv`逐支保留wall/process CPU、prefix成本、suffix simulation成本、
inference wall/CPU及CUDA Event累计区间、显存峰值。CUDA Event区间不是设备独占
核时或100% GPU利用时长；process CPU也不能与wall相加。stage wall包含该stage
加载模型，execution elapsed从A启动到最终stage完成；分支计时则从reservation后开始。

- `prefix_states` / `suffix_sim_states`：flattened [time,qpos23,qvel21]，含初始采样。
- `prefix_obs` / `suffix_observations`：原native16D；[nut world pos3, xyzw quat4,
  EEF site pos3, EEF body xyzw quat4, gripper qpos2]。从不以同步几何替换模型输入。
- `*_physical_obs`：同16D语义，来自独立MjData raw-qpos kinematics，仅作审计。
- `*_received_actions`：实际composite controller收到的7D，动作行对应该索引开始的控制步。
- `suffix_after_clip_actions`：冻结控制器自身的normalized clip结果。每步回执均断言
  实际arm scale等于此结果乘[.05,.05,.05,.5,.5,.5]；公开原始数组保留clip前后值，
  不声称另外保存了每步完整receipt字典。首步完整receipt另存branch JSON。
- `*_controller`：[goal_pos3, goal_ori9, ref_pos3, ref_ori9]，均为该状态采样时的控制器值。
- `*_gripper`：current_action补齐2维，另1维为原长度；补齐仅为日志，不修改控制。
- `suffix_success` / `suffix_ncon`：对应索引开始的控制步执行后官方task flag/原生接触数。
  ncon不是接触法向，不用于代替contact frame。接触frame来自fork最后原生solver的
  接触力和法向，可能较积分后data.time早一个物理子步；没有额外forward刷新。
- `replan_histories`：每次推理实际native输入，两帧×16D。control_step列为replan序号，
  branch JSON的absolute_step_before给出真实控制索引。
- `initial_noise`：同一次DDIM采样初始noise [1,16,7]；由独立generator副本生成并核对hash。

状态/观测数组control_step表示采样时刻；动作/flag数组control_step表示转移起点。
首个suffix状态是t，首个flag描述t→t+1；不要把flag误当分叉前已成功。
完整episode终点固定400步，前缀t计入；suffix长度400−t，20Hz控制，25×2ms积分。

`source_proxy_deviation.csv`将native缓存误差与独立raw-qpos物理偏差分别列出。
前者包含原native观测时效语义；后者也不能用来声称源HDF5被精确恢复。
旧Gate0/R的源状态阈值与结论保持不变。本轮的重复一致性阈值只比较在线分支彼此。

`fixed_baselines.json`仅在B2许可并完成时产生；若提前停止，baseline_evaluation记录
not fitted，不构造矩阵、不填随机分数，也不把缺失contact或未收敛模型算作被击败。
图中灰色为未测量，不是0。统计不给160条相关后缀套独立样本显著性或狭窄置信区间。
