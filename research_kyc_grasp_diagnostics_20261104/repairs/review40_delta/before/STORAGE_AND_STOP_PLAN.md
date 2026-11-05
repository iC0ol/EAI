# 存储、终止与测量边界

目录150MiB包括真实DeepSeek raw、log、源代码、根快照、所有数组和结果，不能只算worker输出。B只保存40块动作、RGB/T和输入hash，不保存40份9通道输入。C所有实际item完整恢复自对应collate切片，不再重复44份item tensor；仅2个预定train代表另外保存完整pre-crop和post RGB，故障时最多追加每臂每split各1个真实链。

按未压缩float32上界，44个collate image共99MiB；AB/预检全部和C代表/首故障normal+sentinel最多74对，约27.75MiB；2个正常加最多4个故障pre/post RGB代表最多18MiB。主要数组最坏约144.75MiB，另有PNG/轨迹/XML/日志，故**不能承诺未压缩全量在150MiB内**。实际采用无损压缩并在CPU内存先得实际字节，再检查整个目录；不把压缩率当保证。save_npz在used+archive>146MiB前拒绝写，保留4MiB日志/清理；supervisor全目录150MiB/RSS/显存/时间独立终止。若不能容纳完整证据就PARTIAL停止，不扩输出预算、不删旧原件、也不伪称完整C。

GPU总900秒包含初始化、失败、清理；预检最多90，科学内部秒数必须真实预检后由双审另冻。每段提前15秒TERM、3秒后KILL；worker alarm/PDEATHSIG为独立后备；科学8h硬墙钟不延长。所有GPU phase一次，计数器在操作前记ATTEMPT，匹配policy/internal只扣一次；0训练/optimizer。CPU预算测试用独立内存账本和真实sleep子进程，不创建GPU账本。真实CPU失败与后续成功分别保存，不能抹去失败或称CPU通过等同GPU可用。
