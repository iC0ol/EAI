# 实际执行命令和复现入口

工作目录为 `/home/asus/EAI`。每条训练命令只有在对应前置审计和 gate 通过后才能运行。
本文件随实际执行更新；没有结果文件的训练不算完成。

## 部署和源码审查（已执行）

```bash
git status --short
git branch --show-current
git remote -v
nvidia-smi
free -h
df -h /home/asus/EAI
lscpu
git switch -c research/d-gate1
/usr/bin/python3 -m venv d_alignment_pilot/.venv
# 上一条失败：ensurepip 缺失。没有安装系统软件。
/home/asus/anaconda3/bin/python -m venv --clear d_alignment_pilot/.venv
env -u PYTHONPATH -u PYTHONHOME d_alignment_pilot/.venv/bin/python d_alignment_pilot/scripts/preservation.py
```

源码使用官方 codeload archive 下载到本项目的 `external/`；版本 SHA 见
`configs/versions.json`。没有建立新的 EAI workspace 或 worktree。
审查了 robomimic v0.5，但其 `lang_utils.py` 在 import 时下载 CLIP，故未将其用于
执行，也没有下载权重。实际选择 v0.4.0 的官方环境包装器。

```bash
PIP_CACHE_DIR=/home/asus/EAI/d_alignment_pilot/.cache/pip d_alignment_pilot/.venv/bin/python -m pip install --upgrade pip==25.3 setuptools==75.8.0 wheel==0.45.1
PIP_CACHE_DIR=/home/asus/EAI/d_alignment_pilot/.cache/pip d_alignment_pilot/.venv/bin/python -m pip install torch==2.2.2+cu121 torchvision==0.17.2+cu121 --index-url https://download.pytorch.org/whl/cu121
env -u PYTHONPATH -u PYTHONHOME PYTHONNOUSERSITE=1 PIP_CACHE_DIR=/home/asus/EAI/d_alignment_pilot/.cache/pip d_alignment_pilot/.venv/bin/python -m pip install --index-url https://pypi.org/simple -r d_alignment_pilot/requirements.in
```

最初默认的 Aliyun 索引下载停滞；终止本任务的 pip 进程后使用相同 pins 从 PyPI
重新执行。最初 pip 启动时继承了宿主 ROS PYTHONPATH，打印外部 ROS 元数据依赖
告警；后续一律清除继承路径。没有改动 ROS 或系统 Python。详见 `logs/`。

官方 HDF5 只下载 `v1.5/square/ph/low_dim_v15.hdf5`，未下载其他任务或图像全集。
初始下载 URL 使用 main；下载后验证其 SHA256 与已记录 revision 的官方文件一致。
正式复现脚本使用固定 revision URL：

```bash
curl -fL --retry 2 https://huggingface.co/datasets/robomimic/robomimic_datasets/resolve/74fa018461f479cd9fd15b924a16103012096203/v1.5/square/ph/low_dim_v15.hdf5 -o d_alignment_pilot/data/raw/square_ph_low_dim_v15.hdf5
sha256sum d_alignment_pilot/data/raw/square_ph_low_dim_v15.hdf5
```

部署初期曾在 h5py 尚未安装完成时尝试只读结构检查，返回 `ModuleNotFoundError`；
这不是数据检查通过，也不计为已完成 Step A。

## 数据、策略与最终结果

下列已执行（均有 `logs/` 记录）：

```bash
env -u PYTHONPATH -u PYTHONHOME PYTHONNOUSERSITE=1 d_alignment_pilot/.venv/bin/python -m pip freeze > d_alignment_pilot/requirements.lock
env -u PYTHONPATH -u PYTHONHOME PYTHONNOUSERSITE=1 d_alignment_pilot/.venv/bin/python -m pip check
bash d_alignment_pilot/scripts/run.sh scripts/audit_data.py
bash d_alignment_pilot/scripts/run.sh -m d_alignment.data
bash d_alignment_pilot/scripts/run.sh scripts/diagnose_observation_cache.py
bash d_alignment_pilot/scripts/run.sh scripts/finalize_observation_selection.py
bash d_alignment_pilot/scripts/run.sh -m pytest tests -q --junitxml=reports/gate1/tests.xml
bash d_alignment_pilot/scripts/run.sh scripts/freeze_eval.py
bash d_alignment_pilot/scripts/run.sh scripts/profile.py
bash d_alignment_pilot/scripts/run.sh scripts/diagnose_observation_cache.py
bash d_alignment_pilot/scripts/run.sh scripts/freeze_protocol.py
```

状态恢复差异出现后，在 0 optimizer updates 时排除缓存相对 pose，只选原始
同步状态分量，保留所有动作文件 SHA。先前 13 项测试和最终 14 项测试分别保存。
`profile.py` 只有一次前后向，没有 optimizer update，不计为策略训练。

干净复现时 `gate1.json` 已包含最终 16 维选择，因此不需要运行一次性的
`finalize_observation_selection.py`；该脚本只用于本次审计过程的可追溯修订。
先审计、准备数据、测试、冻结初态与协议，再训练。已存在的冻结文件不可覆盖。

训练前预登记提交：`fb74d1b0b16387feb127101fce67eddeec81ed40`。
冻结后只追加分析和报告代码，不改变模型、加载器、配置或协议。

```bash
bash d_alignment_pilot/scripts/run.sh -m d_alignment.train --condition clean --seed 42 > d_alignment_pilot/reports/gate1/logs/train_clean_seed42.txt 2>&1
bash d_alignment_pilot/scripts/run.sh scripts/validate_resets.py > d_alignment_pilot/reports/gate1/logs/validate_resets.txt 2>&1
```

其余策略训练和闭环评估命令只在实际执行后列出。
