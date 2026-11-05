# Codex策略B独立验收（先于DeepSeek46）

结论：有效完成本轮8条固定闭环；训练相机0/4、开发相机0/4，reach/grasp各0/8。不是仅有MAE门失败，而是有完整150步行为负例。4个物理root相互独立、8是配对相机条件；不称原32重跑或KYC论文复现。A专家同root4/4阳性。

独立原件核验：1200行saved trajectory逐行计算原delta六维累积、底层绝对命令、实际EEF与物体距离/高度、reward==1判定；40个原NPZ块按原stats/FP32乘加重算，与1200执行delta逐位一致。40个实际官方policy返回与internal捕获在运行门逐位相同；qpos/cam_extrinsics内外SHA相同，image因官方ACTPolicy __call__ 的ImageNet normalize改变hash，不能误认部署错误。主审初版分析误断言全部输入hash相同，已只纠正CPU分析脚本并保存correction记录，实验无改动；按冻结存储计划未存完整9通道输入，不能声称重算其全部像素。

全部48原readback NPZ normal/sentinel逐位相同、保存PNG为raw上下翻转，96读的当前registered renderer/FBO36053/GL0均通过；已看16幅初终索引图，画面清晰可见，八个末帧夹爪均未到物体并未抬起。源文件SHA/逐轨迹重算及初终图在parent_policy_b_acceptance和contact_sheet。

最小真实EEF-物体距离：root0 train/dev0.20913/0.23594m；root1 0.21380/0.20158；root2 0.32824/0.34443；root3 0.11226/0.18465，均>0.05m。实际EEF按预测向下移约0.0684-0.1357m；目标跟踪误差中位0.00053-0.00413m，说明控制确实执行输出。多数轨迹XY变化小，root3 train却向X移动0.11866m（dev仅0.000735m），因此不能称完全恒定/完全不看图；仍未形成足够的朝物体运动与抓取，root3 train全部150步夹爪命令≤0。

8次restore的state/物理几何/controller与冻结root一致，观测属于这4个替代XML场景；来源demoXML缺失。B单worker201.26586915692315GPU秒，累计311.32658587163314；40ACT/1200step/8rollout/48render/96read，0训练，exit0，worker已失活，error/cleanup null。冻结预算未超、没有任何追加。

B结果削弱“只是开发相机分布”与“控制链完全不能动”的解释，也表明健康RGB本身没有恢复当前checkpoint任务阳性；但不排除训练数据/场景对应、训练污染、优化不足、prior学习等剩余假设，旧0/32历史根因仍未唯一定位。继续唯一既定C-local135秒/22getitem及随后另派发C-official比较，不训练、不修复/扩容；从实际训练tensor找证据后再做最终六问决策。

manifest3179c07a0cf77758d4dff01d57ffebcca1af0c11bc4034a0753b32610f40b530；protocol8773f4b7733335898d2bed5803f0d7729798896892abe6bdefd604a1f71a8ed8。09:43:16.235501科学截止不变。
