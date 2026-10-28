# 扩展轮第二轮交叉质疑：新增强反证和首夜执行约束

已读 05。拟只保留 F 为条件性问题验证，C1/G 不开实验。请实读下面新增原文/代码并反驳，不能继续使用“CamVLA未测误差”的判断。

## 新增证据与需更正处

1. **CamVLA 附录 B 已做 Extrinsic Noise Robustness**。本地 sources/camvla.txt 行 798–818（arxiv2607.05396），Figure 5：0°参考、1–20°每1°、25–45°每5°，随机3D轴；**每次 planning step 独立重采样，明确不是整段固定偏差**。0°64%、1°63.3%、5°58.7%，到12°仍接近无噪baselineπ0 36%。相对动作变换消除 translation项。Table5 sparseview下predicted vsGT 51.4vs52.3、34.0vs40.0、21.2vs26.3，论文认为视觉representation shift更主要。请撤回“未知/带噪本身未覆盖”的宽泛创新描述。

2. KYC源码已核查：repo ripl/CamPoseOpensource commit e0647105a0f3946581d253c55dc9fd1218fa0974；本地sources/kyc_train.py,kyc_utils.py,kyc_eval.py,kyc_paper_runs.txt。官方lift ACT配置是20001 epochs（通用论文30k不适合直接套此任务），200训练demo+10val，batch70，__len__是demo数，每个getitem随机t并即时渲染；每epoch非一个梯度步，CPU4核可能瓶颈。默认num_workers=0。setup.sh会下载全folder+两套环境依赖且未锁版本，不能照跑。只有渲染、camera/action语义和吞吐gate通过才上长训练。

3. KYC Delta EEF与CamVLA camera-frame delta公式不同。KYC先把动作相邻**绝对目标pose**相减，部署再累加，不能错当当前eef-relative OSC delta。cam2world、OpenGL→OpenCV、crop与raymap同步、绝对/相对旋转的左右乘都要验收。纯外参输入误差时冻结图像/物理state；真实相机移动时另外渲染，不能混算。

4. 你的“IDP下降不是条件失配、主因是稀有模式质量低”过于因果化。TableII只是分解下降由恢复模式承担，作者解释不是排除条件失配的独立因果证据。C1仍因直接COT覆盖+资产/价值降级，但结论应是未证实这个因果，不能证伪。G也不能用全量200任务太大直接推出任何单任务不能验证；降级主因是学习新意与具体资源协议均未建立，而非简单把全量成本强加给首夜。

## 拟冻结的验证问题

“在 KYC 官方 LiftRand / ACT 的同任务、同训练来源上，输入外参的整段持续旋转偏差，是否比同幅度、每决策独立旋转噪声更破坏成功；该影响是否足以抵消显式几何相对 RGB-only 的收益？”这是验证问题，尚无新方法资格。用已验证的世界camera pose加误差生成输入raymap，观察进入policy同接口；校准准确作为合法同接口阳性参照，RGB-only在metadata扰动下严格不变作为阴性检查。计划再单独测试真实相机移动+正确/陈旧metadata，区分视觉OOD与标定错误。不能换旧二维空间规则题。

首夜倾向先 U=official RGB随机视角，C=official Plucker，单个matched train seed；最多20001 epochs按相同梯度步收敛/截止，低成本吞吐pilot后冻结可完成步数，若是截断只称预算诊断。固定最终checkpoint不看test择优；32 dev roots做工程有效性，50独立test state-camera roots做paired检验，training seed方差未知。0/5/10°误差，固定axis按root合法随机、persistent vsIID same-marginal；另10°真实相机azimuth位移+correct/stale metadata。两模型相同数据/随机化/crop/action控制，只差camera conditioning；C增加的分支参数是原方法固有差异，不能谎称参数完全相同。

预算12h墙钟，8 GPUh，先资产/准备<=90min（若可恢复下载/编译有客观进展可到2h但不加总），GPU<=1/20GiB，RAM<=20GiB，CPU<=3 threads workers0，下载<=12GiB（只取单lift数据+必要依赖/ResNet权重），额外磁盘<=45GiB，剩余>=60GiB；留至少1h评估与汇总。无条件改算法/加任务/新VLA。若仅两模型未完成就报告PARTIAL/IMPLEMENTATION-LIMITED，不解释科学否定。pose-jitter训练是下一阶段必须强基线：若时间不足首夜先不训，不能因此声称新方法必要。若没有这两个可信baseline，最多做可复核接口诊断，不能POTENTIAL-GO。

请检查该范围是否有比“只是给已知噪声换相关性”更有用的可验证问题，指出当前足以或不足以启动限定复现的理由、必须前置的强反例、统计/语义漏洞。最多纠正当前F，不再扩新候选。请查第三直接方法AnyCamVLA或ViewVLA/RayViT的全文与代码，若persistent drift已做指出原文；不要求为了创新自造更多条件。只读讨论。
