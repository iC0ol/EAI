请真实交叉验收18，并审核完整新任务 /home/asus/EAI/research_kyc_diagnostics_20261029/render_lifecycle/PROTOCOL.md。只读，不执行。

Codex已先冻结notes/04_Codex渲染修复独立验收.md并独立CPU重算artifacts/parent_render_repair_audit.json：6帧所有边界/PNG匹配、12raw哈希、76旧文件、来源与执行SHA保持、累计秒数23.132786匹配。实际看六图均坏。工程恢复在预算和允许局部错误修复范围内，完整度仍PARTIAL/仅1有效worker。

纠正你的18：自称零基索引却偏1，实际after_make_env23、before_Dataset24、旧free25、eglReleaseThread28→29，不是24/25/26/29→30。另“更可能con.free”无充分排名依据；0x8219只是当前draw绑定（可能是默认0），不能判目标offFBO被删。你提出的仅跳过release/恢复current很可能重复已经失败的绑定思路，不能恢复可能被误删资源。

新证据一手源码 https://raw.githubusercontent.com/google-deepmind/mujoco/3.3.0/src/render/render_context.c 的mjr_freeContext调用glDeleteRenderbuffers/Framebuffers等（1642起）；Khronos https://raw.githubusercontent.com/KhronosGroup/OpenGL-Refpages/main/gl4/glCheckFramebufferStatus.xml 明确GL_FRAMEBUFFER=draw，UNDEFINED可由无默认FBO。这支持测资源身份，不是已经证明误删除。

因此新协议只测试一个“在所属context释放con与EGL资源，并恢复之前仍活context”的原子生命周期修复，从新进程初始化前安装。新增≤2worker（基线/修复各1，不冒称同条件复验），每个早期1帧+三入口3帧，共8renders/16readPixels/300GPU秒，0ACT/step/训练；补con.free、真实bindings/glIsFBO、已绑定非零attachment等不自动bind的遥测。若早期坏要看异常是否早已发生，不能因早期坏就排除生命周期。确认无owner/错误restore/重复析构的CPU mock先过。不改旧代码/系统，Git父审独占。请完整读协议，给APPROVE或必要实质修订；勿新增泛泛实验范围。用户已明确解决故障，合格小修可派发，不需再次人类确认；完整训练仍禁止。
