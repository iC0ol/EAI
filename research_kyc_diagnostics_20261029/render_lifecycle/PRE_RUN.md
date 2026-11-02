# 执行前代码审计

CPU预检不import torch/MuJoCo/EGL、不创建context/env，覆盖NULL opaque、非NULL指针、重复/重入/部分清理、缺失或dead owner、previous为owner/另一个live/null/unknown、con/EGL/bind/restore异常、previous中途死亡，以及实际适配器的display/draw/read/context句柄恢复。另用无GL方法的mock确认wrong owner及stale current不会触发对象查询。cpu_mock.json保存实际结果；不把mock解释为真实GL有效。

GPU阶段冻结两个新exec条件，baseline原析构顺序与释放/吞异常语义保持，只插入con.free前后事件；fix通过owned_release.py在owner当前释放同一清理对象，再恢复previous display/surfaces/context，guard只保护部分/重复/异常路径。初始化前安装；不增加render-time绑定、不重建buffers、不关GC。原析构源码hash在每个worker落盘，完整原片段仅local_only。

测量顺序固定：EGL current/owner身份与生命周期→实际draw/read/RBO绑定→仅当前非零FBO的status/attachments→仅owner=current的glIsFramebuffer/glIsRenderbuffer及已绑定RBO尺寸→最多8次glGetError。默认FBO0单列，不把它的状态赋给offFBO。owner不同于current时NOT_MEASURED_WRONG_CONTEXT；另测current所属活动renderer。con.free前primitive IDs保留用于同owner释放后测量。前后context变化窗口丢弃对象归属值，不补数据。查询不会绑定FBO/context，也不创建对象；只有修复事务切换context。

registry只留primitive handle/liveness及weak renderer引用；事件不保存env、scene或原始buffer强引用。自然GC时序仍可能被日志分配/copy改变。旧对象可能在早期对照前被析构，须按事件链判断，不仅看图像时间。GL查询会消费/可能引入error，报完整区间，不称全程无错。

正常readPixels/np.empty不改；独立165 sentinel在同一原锁内返回前另读一次，经同一持久计数；raw/sentinel独立，比较preflip，不进入正常pipeline。每worker先make_env后早期1帧，再Dataset/Evaluator/embedder和三个入口，最多4render/8read，隐式调用挤占计划。正常raw、flip、tensor、NPZ/PNG分别存copy，并做共同raw RGB纯数值比较。没有ACT/optimizer实例。

独立supervisor先持flock，核对CPU通过/准确SHA和terminal防重复，再顺序exec worker1 baseline，只有其生命周期异常门通过才保存repair_choice并exec worker2 fix。记录worker1先结束后worker2创建；累计整个worker生命周期GPU秒，290秒请求终止留10秒释放余量，最晚300秒。全部失败计数不退回，无第三worker。Git由主线程独占。
