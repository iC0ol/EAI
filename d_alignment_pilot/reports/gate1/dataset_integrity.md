# Gate 1 数据完整性

实际执行测试：**14 passed**，3.82 秒。机器可读结果 `tests.xml`，完整输出
`logs/tests.txt`。初始 23 维配置的 13 项检查也保留在
`tests_before_observation_selection.xml`；16 维最终输入有额外的原始值一致性检查。
这不表示训练或闭环成功，也不表示尚未执行的 lag 识别已通过。

| 项目 | 实际结果 |
|---|---|
| 原始 HDF5 | 官方 SHA256 精确匹配，200 episodes / 30,154 transitions |
| 官方 valid | 原 20 episodes，未写入、未污染 |
| 策略 train | 156 episodes |
| 同步 anchors | 8 episodes，未参与策略或归一化拟合 |
| 独立 lag test | 16 episodes，未参与策略或归一化拟合 |
| 训练污染 episode | 两个条件相同的 78/156，精确 50% |
| Mixed | ±1、±2、±4 各 13 条；其余 78 条 delta=0 |
| Larger | −4/+4 各 39 条；其余 78 条 delta=0 |
| 三组公共有效转移 | 每组 22,349 |
| 三组完整 16 步样本 | 每组 20,009 |
| split / corruption seeds | 20261022 / 731902 |
| 最终测试 | 50 个另行生成的初态，100000–100049，训练前冻结 |

共同训练区间 `[4,T−4)`；样本起点 `4 … T−20`，不使用任何 padding。
所有保留集互斥，并集精确覆盖原始 200 个 episodes。测试是正常仿真初态，不是
从训练或留出示教中复制的轨迹。原 valid 数据逐样本在三条件之间一致。

以独立 ramp 和所有真实 train episodes 检查：`C[t]=A[t+delta]`；delta=0
精确相等，公共窗口内 `C[t−delta]=A[t]` 精确相等。所有越界标签是 NaN，
没有跨 episode 索引、循环移位或端点复制。实际 loader 检查每条 episode 的
首尾样本及所有索引，不能采到 invalid edges。三个条件的 index 列表完全一致。

所选原始观测分量逐值与源文件 float32 表示一致；三组均直接读取同一个只读
源文件，没有为污染条件改变观测。选择 16 维同步状态的训练前修订详见时间
约定报告，没有改变任何污染 episode、delta 或动作文件字节。

| 派生 actions 文件 | SHA256 |
|---|---|
| clean | `0b639d054b21c3dadeffaee386b93615969c8c7bf7edb489a1b2abff4e2c8bb3` |
| mixed_small_lag | `92fe5215e8c3fce81a178bb19347580d6ba4e859da00356d552509696f9bf078` |
| larger_lag | `f57c4239919871cd16d030fcf58392fba93ba7fa4c7bf363a0df5d45ccf7d1fa` |

完整 episode/delta/seed/config/data hash 见 `data/manifests/injection_truth.json`；
训练只读 split、normalization 和派生 actions，不读 injection truth。
后续估计器若执行，必须使用隔离后的待估计输入，不得读取原文件 clean actions
或 injection truth。真值只用于生成与独立评分。

原始 HDF5、派生 HDF5、50 个含 XML 的初态均仅存本地且被 Git 忽略。Git 仅保存
小型 manifest、测试、代码、配置和统计证据。checkpoint 同样仅限本地路径和哈希。
另外执行 `validate_resets.py`，50 个互异初态经正式评估 reset_to 路径逐一复核，
所选状态分量均在 1e−5 容差内。该检查为 0 策略 episodes、0 action steps，
不计入闭环策略评估回合。明细见 `eval_reset_integrity.json`。
