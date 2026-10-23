# L-A 技术资格：Go，仅限在线代理分支

旧Gate0/R的Invalid / R-Fail / Engineering blocked结论保持不变。本轮从
89d89fbcd6458e50ae875746dd1adcdb032ec121创建独立research/m-gate0-live-screen，
协议58ac6095d3cad406748f4ecd50340112ce4af98f先提交，执行代码
60cf0ba510c306852e2dcfa262aa8bb53ec35bc5后提交，再开始任何L仿真。

L-A在S00 demo_191,t52与S03 demo_21,t165各独立创建环境并真实重放前缀两次，
共4条完整零扰动后缀。两对比较全部通过。native观测、全部动作、raw state、独立
kinematics物理位置、控制器目标/参考、gripper和推理历史的最大逐值差均为0；
fork state/controller/cache/observable/warmstart/actuator/gripper/随机流指纹一致。
所有success flags、ever/final、replan/noise表一致。原生quaternion测地角计算最大
4.2146848510894035e-8 rad，是相同浮点四元数的数值角度，远小于冻结1e-4 rad阈值。
详细原始比较见outputs/stage_A.json，未调阈值。

每支总episode均400控制步；S00前缀52+后缀348，S03前缀165+后缀235。
每控制步恰好25个2ms原生积分，未用额外step/forward修复缓存或solver。初始化固定
为已审计P1，未尝试其他reset路径。模型沿用原16D native观测与两帧历史；物理clone
只读观测用于审计，不改变模型输入或在线仿真状态。

本结果允许测量相同在线proxy fork上的后果。它不证明恢复了HDF5专家状态，亦不证明
原日志动作在proxy上仍最优。source_proxy_deviation.csv独立保留native与raw-qpos
物理偏差；source阈值从未作为本轮在线重复资格的替代，也未据此重判旧实验通过。

后续每个正式扰动分支必须与同状态名义分支的完整fork指纹完全一致。最终交付审计
另外检查同状态随机流表、动作增量、未clip首步、每支积分计数与原始trace SHA；
结果见outputs/final_audit.json。技术Go不自动开放B2/B3，它们仍受预登记科学门槛控制。
