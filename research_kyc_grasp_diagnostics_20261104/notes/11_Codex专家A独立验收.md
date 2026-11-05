# Codex专家A独立验收（先于DeepSeek44）

APPROVE_EXPERT_A_CONTROLS。原4条105/102/126/97共430行全部逐行CPU重算：delta与原专家动作逐位一致、实际base绝对命令按原六维累积逐位相符、夹爪不累积；真实EEF/物体距离、reach、reward==1和原Lift高度成功一致。4/4均reach/grasp/success，8幅初终图已作原NPZ正常/独立sentinel逐位比对和PNG翻转检验；全部16读GL事件FBO36053/GL0。联系表亲自看图：四个终帧均清晰可见方块抬起，初帧均正常，不只依赖success字符串。grasp为原接口与contact记录，未假称另跑物理。

四条每步EEF对原next_obs最大偏差分别0.0002859515、0.0000947643、0.0001011335、0.0001481846m，均远低于原0.02m；实际目标跟踪误差中位约0.015m，须区别源头轨迹偏差。最小EEF-物体距离5.16-7.06mm，最大方块高度0.94397-0.94770m。四次恢复state/物理模型/controller相同，root文件未改；新A/B可匹配，仍不能称原demo XML完全重建。

真实A单次75.4795101750642 GPU秒，累计110.06071671471；4rollout/430step/8render/16read、0ACT/训练，worker失活，清理无错。结果说明这四个已固定替代root的原专家控制/判定链工作；不证明checkpoint、不定位历史0/32。

下一B的行为资格门已达到，待真实DeepSeek独立/交叉后只派发既定8配对/150步/40ACT/360秒，不能扩样本；不适用旧MAE门。manifest3179c07a0cf77758d4dff01d57ffebcca1af0c11bc4034a0753b32610f40b530；protocol8773f4b7733335898d2bed5803f0d7729798896892abe6bdefd604a1f71a8ed8。科学09:43:16.235501截止不变。
