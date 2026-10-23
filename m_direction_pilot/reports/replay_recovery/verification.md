# 最终核验

预检6项通过（3.986s）；仅一次0积分API/kinematics环境构建/重置检查，未执行专家动作。
停机后交付检查5项通过（0.068s），完全只读，无新环境实例或积分；原始日志分别在
logs/preflight_tests.txt和logs/delivery_tests.txt。106条raw_control_boundaries导出行另与
原始NPZ逐项核验：qpos/qvel/native16D一致，源缺失warmstart/contact字段仍为空。

当日再次导入审计确认MuJoCo3.2.3、robosuite1.5.1、robomimic0.4.0、Torch2.2.2+cu121，
使用原D独立Python3.9环境；版本及模块路径在runtime_audit.json。导出/版本审计未创建
环境、未加载策略、未推进物理或执行推理。

0..52的PNG已实际打开检查：三面板、坐标单位、冻结阈值、观测与物理曲线和接触力标签
可读，无裁切或遮挡；SVG同时保留。源码摘录和Matplotlib SVG的空白按新报告目录的
局部.gitattributes保留，旧文件没有格式化。

封存前校验旧M全部56个文件、旧P0原始NPZ、原HDF5/两份checkpoint/依赖锁/固定源码，
并检查旧分支ref未变。所有本轮变更限于三个授权目录；local/replay_recovery原始遥测只在
本地保留，以SHA和字节数索引，不提交环境、cache、权重、原始HDF5或原始NPZ。

没有把“重复前缀一致”当成“源状态重建通过”，没有把未执行suffix填写为失败，
没有事后放宽阈值或替换来源。预登记与执行均先于任何新仿真step。最终提交SHA由交付消息提供。
