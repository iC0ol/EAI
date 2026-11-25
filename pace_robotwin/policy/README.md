# PACE 的 π₀.₅ 推理服务

官方权重使用 Hugging Face 发布版本 `17ef545270cf26ed81169893b60f845f80ce6557`。其清单指定 OpenPI-PACE `ba9876639cb7a4bf0c7db00ec39eeb9c8efd8b12`，本服务按该版本检出。两个任务各使用独立的第 30,000 步 EMA 权重和原始归一化统计，共用发布的 PaliGemma 分词器。[权重发布](https://huggingface.co/niejunnan25/pi05-robotwin/tree/17ef545270cf26ed81169893b60f845f80ce6557) · [OpenPI-PACE 源码](https://github.com/niejunnan25/Openpi-PACE/tree/ba9876639cb7a4bf0c7db00ec39eeb9c8efd8b12)

## 安装与校验

在 `/home/asus/EAI` 执行以下命令。`install.sh` 将 CPython 3.11.14、`uv`、锁定的 OpenPI 依赖和下载缓存放入 `pace_robotwin/runtime/policy`。下载脚本仅获取 `stack_blocks_three`、`place_phone_stand`、分词器和发布清单及条款。中断后重跑同一命令，已校验文件保留，未完成文件从 `.partial` 续传。

```bash
bash pace_robotwin/policy/install.sh
python3 pace_robotwin/policy/fetch_checkpoints.py --jobs 6
python3 pace_robotwin/policy/fetch_checkpoints.py --verify-only
```

每个参数分片、归一化统计和分词器都按固定发布清单核对大小与 SHA256。清单 SHA256 为 `2337bd9e7244fc3f6d51b0b830a9cdfc8d6e683decf2c398a431bc5800696c41`。依赖锁 SHA256 为 `5e3a9a0a12d9a6048afea5591f4520c98585499cbd4a8343dcabfe2aaed94e3d`。

## 启动与调用

```bash
bash pace_robotwin/policy/serve.sh --task stack_blocks_three --port 8000
```

服务使用本机 `127.0.0.1` 的官方 WebSocket 协议、JAX CUDA、Orbax 权重加载以及原版模型和变换。启动器禁用 XLA 显存预分配，单张 24 GiB 显卡按需分配。Orbax 读取的主机侧并发上限为 6 GB，模型仍以原版 `bfloat16` 加载。切换任务时停止当前进程，再为另一个任务启动服务。

使用原版 `WebsocketClientPolicy` 和 `pace.rollout.encode_observation`。请求包括 `state`（14 维关节与夹爪向量）、`images`（`cam_high`、`cam_left_wrist`、`cam_right_wrist` 三幅 CHW `uint8` RGB 图像）和 `prompt`（任务指令）。关节顺序为左臂 6 维、左夹爪、右臂 6 维、右夹爪。D435 三路的分辨率为 `3 × 240 × 320`。

```python
client = WebsocketClientPolicy("127.0.0.1", 8000)
reply = client.infer({
    **encode_observation(env.get_obs(), env.get_instruction()),
    "episode_seed": int(scene_seed),
    "query_index": int(query_index),
})
assert (reply["episode_seed"], reply["query_index"]) == (scene_seed, query_index)
actions = reply["actions"]
```

每次查询用批大小 1、10 个流匹配步骤得到一个 `50 × 14` 绝对关节与夹爪动作块，保留原版返回精度。`episode_seed` 为场景种子，`query_index` 从 0 开始。包装层从该种子按 OpenPI 原有的 `jax.random.split` 递推到查询前的键，再调用一次官方策略。两字段均省略时沿用原版服务的全局种子 0 随机流。连接元数据包含任务、配置、权重版本、归一化哈希、`candidate_count` 和 `denoising_steps`。

## 预热与计时

```bash
pace_robotwin/runtime/policy/venv/bin/python -B pace_robotwin/policy/probe_policy.py \
  --task stack_blocks_three --port 8000
```

探针对独立的合成观测测量首次查询和预热后的查询，检查动作形状、有限值、同种子逐位复现以及显式种子 0 与原版随机流前两次查询的一致性。工程耗时与正式回合分开记录。`server_timing.infer_ms` 计量已解包请求到 CPU 可用动作块之间的服务器耗时。`policy_timing.infer_ms` 是原版对 JAX 模型调用的计时，热态会包含异步派发。客户端以 `time.perf_counter()` 测量 `.infer()` 往返，其中包含服务器耗时、消息传输、编解包。
