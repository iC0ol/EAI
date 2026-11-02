# 冻结 checkpoint 诊断：本 RUN 终止报告

**TERMINAL_STOP_INPUT_IMPORT_COLLISION；模型阶段 NOT_RUN。** 已按正式 v2 RUN 启动唯一一次 input 监督器；其 worker 在导入 experiment_lib 时退出码1，未进入 make_env、渲染或模型。按冻结协议不修改代码、不修复、不重试，不使用第二个 worker 或剩余额度。这个失败不能评价 checkpoint 能力，也不能判断 F 的科学假设；旧0/32仍 UNKNOWN。

实际 RUN id：`kyc-frozen-84a848fd-a62d-4f61-8164-97044f315ae6`。协议 SHA256 `6ae547f65fc0b94a6954ae98d75fcf472a354b81d6e66f27abbd71b4b9ad883c`，manifest SHA256 `9d2171f112023395171a259423be4d3a3ec40a7d3a4442de0561108a28729aa1`。启动前已核对40个本地文件、39个来源及两审证据准确SHA；没有回退v1或重建prepare。正式派发为2026-11-03 04:29:37，原硬截止12:29:37未变；本轮已提前终止。

真实错误为 `ImportError: cannot import name 'ROOT' from 'common'`。input_worker顶层先载入诊断 scripts/common.py；随后虽然将 reproduction/scripts 插入 sys.path，experiment_lib 的 `from common import ROOT,atomic_json,utc` 仍命中已缓存的诊断 common 模块，该模块没有 ROOT。traceback实际指出诊断 common.py 路径，错误发生在 input_worker.py:39 / experiment_lib.py:2。原始CLI完整保留 logs/input.log，不公开原始终端文本；公开结构化错误见 input_stop_delivery.json。没有尝试别名、重命名、sys.modules改写或重启来绕过。

| 计数/结果 | 实际 |
| --- | ---: |
| 实验worker | 1（失败名额计入，未返还） |
| 整个worker分配时间，含导入/失败退出 | 3.926884102 秒 |
| make_env / native render / native readPixels / ACT | 0 / 0 / 0 / 0 |
| env.step / rollout / backward / optimizer | 全部0 |
| 新输入NPZ / 新PNG帧 | 0 / 0 |
| strict load / 16次模型清单 / CPU模型输出分析 | 全部 NOT_RUN |

这是按整个子进程寿命保守计入的GPU分配时间，不代表实际GPU运算耗时。input子配额210秒、总600秒等上限未扩大。预定12帧与输入健康/自然释放窗口均未执行；input_result.json未生成，因为错误在其try/finally结果写入区之前发生。不创建伪造的COMPLETE或12帧结果替代它；stages/input.json、run_state.json、stop_request.json与status.json保存了真实失败。

独立CPU监督器PID174477，实验worker PID174562/start_ticks300542757；worker退出码1。两个原PID/start_ticks已核实不存活，active_lease=null。监督器自身退出码没有单独采集，不冒称已记录exit0。GPU查询仅见启动前已有543637/python 296MiB；没有本任务GPU进程需要等待或清理。两次资源采样的RSS最大58,990,592 B、全设备显存609,222,656 B，不能当作连续峰值，尤其导入短于采样间隔。

执行后再次核对40个冻结本地文件、39个来源，以及521个旧证据文件size/mtime_ns/SHA，全部未变化。仅本目录新增日志与交付记录；没有改旧源码、数据、权重、runtime或系统，没有下载/安装。Git index归主审，本执行者没有add/commit/push。

子6-1-sol-max已通过应用工具暂停，并读回确认prompt/name/rrule/target等字段保留；主automation未改。见automation_closure.json。按既有人类及本目录AGENTS回传授权一次通知主审，回执保存input_terminal_return_receipt.json。当前RUN终止；没有input_gate与新RUN_MODEL，也不会启动模型。任何后续处理交研究负责人及两审重新决定，不由余量自动授权。

原件入口：input_stop_delivery.json、stages/input.json、run_state.json、commands.jsonl、resources.jsonl、stop_request.json、input_stop_integrity.json、execution_start_check.json；完整traceback在logs。公开仅runtime_allowlist.txt内原创代码与小记录，runtime_secret_scan.json及runtime_publication_manifest.json为当前v2交付清单；旧preparation清单仍是历史资料。
