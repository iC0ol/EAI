# 生命周期结果交叉质疑及确定性释放协议完整审查

请继续真实会话，先读父审 /home/asus/EAI/research_kyc_diagnostics_20261029/notes/05_Codex生命周期结果独立验收.md 及 artifacts/parent_render_lifecycle_audit.json，再完整读新 render_controlled/PROTOCOL.md（v1）。只读，不执行程序/GL/模型或修改文件。

交叉点：
1. 双方一致确认基线29→30错误owner con.free窗口内当前ctx2的3FBO+4RBO失效，34→35解绑；fix采图最后56，释放59/75仅cleanup，恢复live-other事件0。但你21的“健康更可能来自GC”“fix健康图不由修复因果产生”过强。只能说没有经历目标释放窗口，不能将健康图归因于owner释放/previous恢复；安装不同析构代码本身可能改变分配/时序，不能无对照排除所有安装效应或排序。请纠正精确边界。
2. 父审独立纯CPU复现真实适配器的遗漏：raw context非零、registry key=None被当NULL，release_owned返回DONE且无failure，原20mock中的unknown字符串没有覆盖这种形式。当前实GL未触发，不能认作旧故障原因；后续同一候选需在任何绑定/释放前拒绝unknown，并把capture/owner/ids前置异常可见化。请直接核对源码和父审复现逻辑。
3. 新协议明确两条件一致持有旧renderer、在固定点显式一次释放（common one-shot guard防止随后再析构double-free），这是受控触发，与旧自然GC实验区分；不用弱引用drop碰运气、不调用gc.collect、不泄漏。2worker/2make_env/4render/8readPixels/180GPU秒，比上次更小；每条件before/after单一路径，0模型/step/训练。before须匹配已确认健康的固定参考像素。fix必须实际恢复仍活B、其原资源保持有效、after=before，才能局部受控PASS。基线不复现只代表本fixture证据不足，不能自动否定已有原进程机制。

请完整评估具体协议的可执行性、相同触发/归属测量、guard不会跳过首次free、CPU边界修正、预算与停止。若无实质阻碍，明确APPROVE完整v1并限定外推；若有，列最小必要修订。用户已要求继续解决RGB，不需再次人类批准已有范围内这项明确小验证，但需你与Codex审核完成后才派发gpt-6.1-sol/max。旧目录只读、Git主审、旧0/32未知；不自动部署训练或恢复模型预算。
