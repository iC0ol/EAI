# 固定时点的资源释放验证

[协议v1](PROTOCOL.md)已获Codex和真实DeepSeek22通过；[准确SHA与预算](review_gate.json)。尚未派发：共享五小时额度已用90%，按2026-11-02 14:24:36 reset后两分钟续办。既有执行线程和子检查只有真实派发后才重新启用。当前没有新GPU作业。

目标是补上render_lifecycle未经历的活previous恢复窗口，并拒绝unknown非空context；不是重跑原terminal或追加训练。
