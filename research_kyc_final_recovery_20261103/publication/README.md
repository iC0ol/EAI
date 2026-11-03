# 公开证据说明

原始科学小结果完整公开：4个固定输入NPZ、12张RGB及读回/保存边界、16个ACT输出NPZ与JSON、严格加载、调用/资源/阶段账本、专家与两常数、完整分析和父审独立重算。它们仅为本轮固定样本，不是完整训练数据集。

CPU/GPU模块来源证据中的 `module_id` 是CPython进程地址；为遵守不公开原生地址的协议，这些原件保留本地，公开副本位于 `redacted/`。仅替换这些地址及长十六进制原生指针字符串，路径、hash、sys.modules同一对象判断、错误/预算/科学数值不改变。小整数GL对象编号不是原生指针，保留以核查FBO/RBO事件。[export_map.json](export_map.json) 精确记录原路径、原件SHA、导出SHA及删减字段。manifest引用原件hash而非导出hash，不把两者混称同一原件。

运行日志的公开副本在 `runtime_logs/`，原log的hash和指针替换数在导出清单。DeepSeek真实响应与原prompt保留；[deepseek_receipts.json](deepseek_receipts.json) 记录每轮时间、退出码、返回模型字段、原始CLI/metadata及公开响应hash。原CLI、会话档、累计计费信息和凭据不公开。第32轮上下文满失败未被当作批准，32b起为真实续接的新会话。

执行代码/修复差异/冻结前协议原文保持原字节，不为了当前状态重写。原代码含只读运行环境路径，这不是环境本体；Python环境、权重、完整数据、XML、cache、local_only、私钥与API凭据全部排除。

[final_public_allowlist.txt](../final_public_allowlist.txt) 是唯一staging集合；[final_publication_manifest.json](../final_publication_manifest.json) 绑定稳定证据。STATUS、completion、clocks及本目录远程/自动检查关闭回执属于可变交付记录，不纳入稳定证据hash，避免自引用；它们由Git提交记录绑定。清单/扫描/manifest自身也不参与自身hash。秘密扫描是本次内容检查，不能视为对任意未来文件的安全保证。

未被公开的原件仍在本地原路径，不删除旧结果。[remote_verification.json](remote_verification.json) 记录实际远程SHA与校验结果。
