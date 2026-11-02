# render_lifecycle v2 完整协议最终审核

继续已真实接续的会话。19提出的context归属测量修订已逐项落实；请只审阅完整v2协议及必要的19记录，不重复扩展查新，不运行程序或修改文件。

协议绝对路径：/home/asus/EAI/research_kyc_diagnostics_20261029/render_lifecycle/PROTOCOL.md

修改要点：owner=current才查询owner资源；baseline只能查current所属活动renderer，旧owner项NOT_MEASURED_WRONG_CONTEXT；fix绑定owner后在con.free前/后、gl_ctx.free前测owner，销毁后不再查；previous恢复成功后测previous对象；ID在free前保存primitive，不拿清零字段冒充释放证据。验收明确baseline active-context变化+fix owner-bound变化，并对缺窗口保留因果未知。共享资源不预设，整数相同不是同对象。

保持2worker/2make_env/8render/16readPixels/300GPU秒、零ACT/step/训练；CPU mocks、早期健康对照、唯一所有权安全析构修复、失败停止均不变。用户已明确授权解决RGB；你和Codex审核后才真实派发gpt-6.1-sol/max。旧0/32仍UNKNOWN，不申请重训。

请核查是否准确满足19实质意见，是否有会导致假因果或超预算的实质阻碍。若满足，请明确完整协议v2 APPROVE并列其有限解释边界；若不满足，列最小必要修改。不要因无关措辞反复延长审查，也不要替代执行或虚构已成功。
