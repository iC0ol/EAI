# 26轮意见处理：供最终协议冻结，不是RUN门

Codex已读真实DeepSeek26。保留notes/01原稿不改；以下为最终代码审查前的修订候选，后续须由DeepSeek完整审查协议和实现准确SHA。仍无任何模型输出。

1. **能力用词**采纳。只称四个已见训练状态的动作生成信号，不能证明广泛部署能力、视觉因果依赖、泛化或Lift成功。posterior每状态一次仅作动作条件诊断，不能作为prior必须失败/必须优于的门。

2. **两个常数**：原稿“整体误差更低者”在不拼接样本/坐标且要求policy更低时，数学上等价于同时优于两个常数，方向是更严格的policy要求，不会使policy伪阳性。为避免标签选择措辞误导，最终改为显式**同时满足mean与median两个固定比较**；主报告MAE锚点预登记为30×7训练采样加权median，mean作为同等需要击败的竞争基线；RMSE分别报两者，不更换任何policy。不得把常数逐样本/维度拼接。

3. **闭环计划的候选信号门**：全部健康/strict-load/入口/重复门通过；四状态等权规范化xyz MAE≤0.8×median且≤0.8×mean；至少3/4状态的xyz MAE分别同时优于两常数，覆盖两个demo；规范化7维MAE≤median且≤mean。20%是投资筛选规则，非科学阈值，连续结果和demo/state/chunk分解都报告。

4. **方向与夹爪退化否决**采纳但精确定义。只用官方prior首次输出，参考同一median。每步专家xyz范数>1e-6米者计余弦；预测范数≤1e-6者余弦记0并列计数，不删除失败预测。先sample平均再有有效项sample等权，cosine不低于median（比较松弛1e-8仅数值舍入）；另报告逐轴符号一致。夹爪按raw第7维sign（零单列且与±1不符），valid-step正确率不低于median。相邻有效步sign是否改变作为transition指示，其与专家指示的Hamming错误率不高于median；无专家transition时只能说未增加误转换，不证明时序能力。任一明确退化则INCONCLUSIVE，不提交积极闭环建议；不把这些诊断当任务成功率。

5. **重复与入口容差**：采纳事前经验公式但加硬上限，避免噪声把所有差异豁免。sample0/1分别计算本状态official repeat和custom repeat相对首次的规范化maxabs，若任一>1e-3则NUMERIC_UNSTABLE；否则本状态两入口tol=max(1e-5,2×max(该状态两重复差))，报bit_equal/maxabs/逐元素原件。公式与1e-3上限都在输出前冻结，禁止事后扩张。sample4/5没有重复，不引用0/1噪声；pair bit_equal或maxabs≤预登记1e-5只称“该次入口吻合”，不声称本状态重复稳定；>1e-5则NUMERICAL_OR_ENTRY_INCONCLUSIVE。实际BF16 precision沿旧部署代码固定，不能称bit-consistency。该规则不会因为没在sample4/5重复就把完全相同输出判失败，也不外推噪声分布。

6. **停止与No-Go**：若健康、一致、稳定但官方prior的xyz和7维整体误差均分别不优于两冻结常数，且无明确可修原因，建议暂停当前checkpoint及F复现路径；是机会成本的投入No-Go，不是领域科学否定。弱收益、混合或地板近零为INCONCLUSIVE，默认不优先延长当前路线，不自动补样本/训练。若某个常数一项胜、另一项负则如实混合，不强行二分。所有范围外下一步仅计划。

7. **算术与预算**：能力误差用首次输出、valid mask、float64计算，规范化与raw单位分开，posterior及repeat不重复计能力均值。主MAE四状态等权；RMSE同时写明pooled RMS与mean-of-state-RMS，不能名字含混。旧CPU常数/数据SHA核验见artifacts/parent_reference_baselines.json，未新拟合常数，四目标与旧已核验NPZ逐位相同。2worker顺序和16/12/24/600原预算均保持，不加调用来解决统计不足。
