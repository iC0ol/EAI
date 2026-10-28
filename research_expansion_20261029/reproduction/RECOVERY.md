# 恢复与复核

本次触发dev地板停止规则后不得自行重训、增加rollout或启动新方法。以下入口用于检查、离线汇总以及**获后续授权后**的恢复，不构成继续实验授权。

先读取`STATUS.md`、`completion.json`、`status.json`、`run.json`、`queue.json`、`supervisor_identity.json`和阶段标记。核对`/proc/PID/stat`第22字段starttime与保存的start_ticks；检查`run.lock`持有者、日志时间与checkpoint哈希。PID相同但启动时间不同不能视为原作业，不得误杀。

本次真实提交命令是：

```bash
cd /home/asus/EAI/research_expansion_20261029/reproduction
python3 scripts/supervisor.py
```

实际通过`subprocess.Popen(..., start_new_session=True, stdin=DEVNULL)`提交，监督PID1944823、SID1944823；提交者SID不同。所有工作子进程由监督器独立创建进程组，CPU affinity限定0、1、2，OMP/MKL等最多3线程，workers0。

阶段实际命令、退出码和哈希在`stages/*.json`及`logs/events.jsonl`。监督器只读队列并跳过已有阶段，不自动重跑失败阶段；失败修复须新增唯一阶段名并保留旧标记。启动同一监督器受flock阻止。预算使用原始T0和已累计GPU秒，不因重启或检查顺延。

训练恢复命令为本次正式阶段命令：

```bash
/home/asus/EAI/research_expansion_20261029/reproduction/env/bin/python /home/asus/EAI/research_expansion_20261029/reproduction/scripts/run_experiment.py
```

它加载`C_latest.pt`中的model、optimizer、scheduler、Python/NumPy/CPU/CUDA RNG、完整sampler排列与游标，且不会越过冻结target更新数。当前已60003次更新，无剩余训练工作。`C_previous.pt`仅用于最新文件损坏时的人工核对，不能挑选效果更好的checkpoint。不得覆盖现有最终结果。

终止自己的作业时，监督器先写stop_request并向自己记录的子进程组发SIGUSR1，请求训练保存当前checkpoint；45秒后仅对同一组TERM，再10秒后KILL。GPU8h、RSS20GiB、设备显存20GiB、低可用内存60秒、磁盘或下载限额，以及T0+11h均有自动停止。五小时检查不是预算延长。

无模型、无仿真地重算交付：

```bash
/home/asus/EAI/research_expansion_20261029/reproduction/env/bin/python /home/asus/EAI/research_expansion_20261029/reproduction/scripts/statistics.py
/home/asus/EAI/research_expansion_20261029/reproduction/env/bin/python /home/asus/EAI/research_expansion_20261029/reproduction/scripts/offline_audit.py
python3 /home/asus/EAI/research_expansion_20261029/reproduction/scripts/summarize.py
```

这会更新时间字段与汇总hash；复核时优先读取已交付原件，避免不必要地重算。环境、runtime、权重、HDF5、缓存、镜像、root完整XML/RNG与全部日志不应公开提交；原创脚本、小型统计、阶段记录、报告与代表帧由主研究者审查后统一同步，不操作共享Git index。
