# 第08轮：针对07的事实纠错与保留争议

续接同一真实会话，只读，不运行任何模型、仿真或新实验。请优先读这两个遗漏文件：
/home/asus/EAI/research_expansion_20261029/reproduction/results/semantics/camera_raymap_checks.json
/home/asus/EAI/research_expansion_20261029/reproduction/scripts/validate_semantics.py
并读FINAL_REPORT.md（已于06:38生成）、../notes/04_复现结果独立审查.md。

07中P2声称因为semantics.json没有ray行，所以“已证实gate缺口、未做几何验收”。这忽略单独文件：单位方向/矩/正交性误差约1e-7、四像素解析ray/反投影、OpenGL与crop约定均已有记录。请撤回“完全没有做”的事实判断。但是Codex进一步检查代码发现，point=origin+同一解析ray，再用同一R/K投回去，属于代数自一致性；不是使用独立MuJoCo投影/实际像素位置的真值验收。应改为“已有解析验收，但独立渲染对应检查仍不足”，不能简单宣布P2完全排除或未做。

其他修正：
1. 07“整段z位移−0.084m”是目标平移增量的和，不是实测EEF位移。首动作跨root标准差X约6.9e-5、Y2.6e-5、Z1.2e-4m，不能所有维度笼统约1e-5。
2. 数据per-demo XML缺失、共享一个env状态恢复也是上游Dataset原路径，不是本轮相对上游新增的差异。10/10专家回放降低显著动力学不匹配疑虑；不能无因果证据把1–2mm cube size差列为已确认主因。
3. 0/32是在新camera pool，尚无same-checkpoint训练camera上的部署对照，因此不能断言“训练未学会”还是泛化失败。请使用“所需baseline验收未通过”。
4. 协议4/32只是最低工程排除地板，不是足以支持机制的论文质量门槛；回到研究资格必须有可信clean能力和复现差距解释。
5. “persistent/IID未见20pp差且区间宽”只能INCONCLUSIVE，允许因机会成本停止，但不是VALID-NEGATIVE，也不是两周自动重训授权。
6. MoVie冻结动力学适应视觉已有；相机隐变量/边缘化只是条件性设想，先有可信baseline+缺陷+simple pose-jitter/校准闭合失败再谈新机制。

请1000–1500中文字以内，明确哪些07结论撤回/改写、还不同意什么，并给出最终投入决定。不要为凑共识重复认可。此次实验已终止，所有正式标定任务对比仍NOT_RUN。
