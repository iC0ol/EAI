# KYC 当前RGB生命周期修复

[冻结协议](PROTOCOL.md)与[双方审核](review_gate.json)限定本轮实际执行。目标是比较原资源释放与在资源所属context中释放、随后恢复原context的一项修复。预算2worker、8renders、16readPixels、300GPU秒，0ACT/step/训练。

原失败证据见[父审](../notes/04_Codex渲染修复独立验收.md)。当前机制与旧训练0/32因果分开，工程修复不作为论文创新。状态见[STATUS](STATUS.md)，真实派发见dispatch.json（派发后生成）。
