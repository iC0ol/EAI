# U v3 夜间运行交付

**NO-GO-CURRENT-SCOPE**。run_id `20261027T172105Z_sourcefix`。

1. 实际完成阶段：assets, decompress, semantics, prepare, train, cal_collect, cal_fit, score_dev, execute_dev, analyze_dev, seal_test, score_test, execute_test, analyze_test。cal: 32 roots/32 sources；dev: 16 roots/16 sources；test: 64 roots/64 sources。完整 test：True；IDM 各 split 来源数：{'train': 148, 'val': 18, 'audit': 19}。
2. U*=B2，对照=B0；mean R=0.490942499 / 0.50219452；mean J=15.2613241 / 15.3070404。R 改善（对照−U）=0.0112520208，95% CI=[0.0, 0.027098187140289803]；原 J 同方向差=0.0457163794，95% CI=[0.0, 0.12130536085772708]。完整精度及逐 root 差在 summary.json / CSV。
3. dev/test 的有害 B1 排序翻转均为0；全部16/64池均有真实J范围。B2与B1在全部16dev及64test上选择相同，故相对B0的0.011252改善不是校正的独立收益。历史/额外标签匹配B4的test mean R=0.493103；B3=0.495324，标签打乱B6=0.486632，未支持校正机制。原始G拟合有效：flow val MSE=0.196096、常数=0.903122；相同历史下真实后继的信息增益=0.247446。B3 cal-val残差MSE=2.967919（未校正=0.0290372），已复算确认；近常量过去动作特征使cal-val标准化特征最大约439σ，属于本次固定线性表示/尺度的外推局限，未在看test后加floor或重训。
4. 墙钟 6.1480 h；GPU 进程占用上界 3024.6752324481495 秒；下载预算计数 14089613322 B（包含早期 pip 不完整计量的保守预留）。实测 RSS 合计峰值 1977999360 B，采样任务 VRAM 峰值 759169024 B；磁盘分配峰值 67090026496 B；下载错误事件 229。后台占用、Torch 内部显存 watermark、前缀/积分步和全部修复见 budget.json / repairs.jsonl。监护前 CPU 准备峰值未完整采样，不冒充全程精确峰值。
5. 结论范围：单个冻结 LeWM、单一训练 seed、5 控制步共享候选选择。未做 U1、Cube、闭环、多任务或大模型训练；下一步仅为研究者复审当前证据。

| split | 独立 roots | 独立 sources | 有效候选记录 | 目标 roots |
|---|---:|---:|---:|---:|
| cal | 32 | 32 | 256 | 32 |
| dev | 16 | 16 | 128 | 16 |
| test | 64 | 64 | 512 | 64 |

停止/完成原因：COMPLETE。缺失项不填 0；上表的 0 只表示实际不存在的已执行记录。研究数值见逐 root 表，候选评分与真实结果在不同文件。

交付复核：896个研究分支全部完成（4480候选控制步）；含工程、前缀、重试共54165控制步、544116积分步、1233次新建环境。80个dev/test root评分哈希、640个端点图像hash、选择/真实J/残差恒等式及5000次root bootstrap已独立复核。pipeline于北京时间2026-10-28 02:03:42完成，随后只作只读交付检查；见delivery_validation.json、counter_reconciliation.json。所有方法在64test上的success均为0；有限5步诊断不能说明闭环任务成功。

最终只读复核/报告封存时间：2026-10-27T18:11:46.381981+00:00；含该复核的累计墙钟6.282328328055555 h（原T0未重置）。五小时续查`u-v3-5`已删除；所有实验进程停止，等待研究者讨论。
