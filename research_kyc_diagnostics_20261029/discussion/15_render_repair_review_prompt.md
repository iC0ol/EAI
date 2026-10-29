继续真实会话，用户最新在主聊天明确说：“保存的RGB图像确有损坏，但还不能解释旧基线0/32——有问题就尝试的去解决，是什么原因检查一下然后想办法解决”。因此目前不是立即放弃排障/只筛新题。用户已授权当前故障定位与局部修复，仍禁止完整训练；原分工不变。

请你独立科学审核完整新微诊断协议：
/home/asus/EAI/research_kyc_diagnostics_20261029/render_repair/00_授权与范围.md
/home/asus/EAI/research_kyc_diagnostics_20261029/render_repair/01_渲染微诊断与最小修复任务书.md

先读完整文本及必要当前源码，指出设计是否会自己修好/扰动baseline、插桩能否辨识raw损坏/转换/保存、EGL context/GL查询的限制、sentinel残留误判、重复worker是否够、是否存在更直接廉价替代。不要只审批摘要。输出 APPROVE / APPROVE_WITH_REQUIRED_CHANGES / REJECT 和明确必要修订；尽量小而可执行，不自动要求更多样本。只读，不运行模型/渲染/修改文件。

Codex新只读观察：固定RoboSuite EGLGLContext.free先检查是否当前context才unbind，但随后无条件eglReleaseThread；MjSim.render不每次make_current。MjSim.free会gc.collect。它们仅提供机制线索，并没有证明触发本次坏图。需要事件链而不是根据函数名归因。原8输入坏图已逐数组核对，PNG与float变换无误，不重复假装没检查。

新协议最多2环境/worker、12底层renders、24readPixels、300GPU秒、0ACT/0env.step/0训练。第一worker3未修复+3证据支持的单一修复，第二worker同顺序复验，原环境/源码只读。候选是make_current或确认读错buffer或证实数组所有权，仅选一个而非顺次碰运气。新修复在新目录，必须与你审核通过后才让6.1-sol/max运行。

另：原执行结果已通过按Git对象上传并fast-forward到2d42000db84b59a82e18cb6b37940ca1131661d7，远端ls-remote已核实；这更新13/14当时公开同步未完成的时间状态。旧记录保留。
