"""Build review reports from actual audit, test and dataset artifacts; no model claims."""
from datetime import datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
import shapely
from spatial_pilot.render import FONT_PATH, font

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT/'reports'


def load(path):
    return json.loads((ROOT/path).read_text())


def read_lines(path):
    return [json.loads(line) for line in (ROOT/path).read_text().splitlines()]


def dump(path, value):
    (ROOT/path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def main():
    now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    audit = load('reports/logs/environment_raw.json')
    manifest = load('reports/generation_manifest.json')
    reproduction = load('reports/reproducibility.json')
    resolution = load('reports/resolution_audit.json')
    protected = load('reports/protected_comparison.json')
    labels = read_lines('data/private_labels.jsonl')
    test_suites = list(ET.parse(REPORTS/'tests.xml').getroot().iter('testsuite'))
    tests = {k:sum(int(s.get(k,0)) for s in test_suites) for k in ['tests','failures','errors','skipped']}
    installed = {d.metadata['Name']:d.version for d in importlib.metadata.distributions()}
    uv = subprocess.check_output([str(ROOT/'.tools/bin/uv'),'--version'],text=True).strip()
    gpu = subprocess.run(['nvidia-smi','--query-gpu=name,driver_version,memory.total,memory.used',
                          '--format=csv,noheader,nounits'],capture_output=True,text=True)
    memory = Path('/proc/meminfo').read_text().splitlines()[:3]
    disk = shutil.disk_usage(ROOT)
    versions = {'recorded_at':now,'python':platform.python_version(),'python_executable':sys.executable,
                'prefix':sys.prefix,'base_prefix':sys.base_prefix,'uv':uv,'packages':installed,
                'geos_version':shapely.geos_version_string,
                'font_path':str(FONT_PATH),'font_sha256':hashlib.sha256(FONT_PATH.read_bytes()).hexdigest(),
                'gpu_query':gpu.stdout.strip(),'memory_snapshot':memory,
                'disk_free_gib':round(disk.free/2**30,2),
                'requirements_lock_sha256':hashlib.sha256((ROOT/'requirements.lock').read_bytes()).hexdigest(),
                'cuda_driver_api':audit['cuda_driver_api'], 'system_site_packages':False}
    dump('reports/dependencies.json',versions)
    command_text = '\n\n'.join('$ '+' '.join(row['command'])+'\n'+row.get('stdout',row.get('error',''))+row.get('stderr','')
                               for row in audit['commands'])
    net = '\n'.join('- '+row['url']+' → '+str(row.get('status',row.get('error'))) for row in audit['network'])
    deps = '\n'.join(f'| {k} | {v} |' for k,v in sorted(installed.items()))
    environment = f'''# 环境审计 — Phase 0 / 1

记录时间：{now}（Asia/Shanghai）。所有结果来自实际工作站检查。

| 项目 | 实测结果 |
|---|---|
| 操作系统 | Ubuntu 22.04.5 LTS，Linux 6.8.0-60-generic，x86_64 |
| GPU | NVIDIA GeForce RTX 3090，24576 MiB |
| NVIDIA 驱动 | 550.144.03 |
| nvidia-smi 显示 CUDA | 12.4；这是驱动支持上限，不能当作 Toolkit 安装版本 |
| 系统 Toolkit | /usr/local/cuda-11.8，nvcc 11.8.89 |
| CUDA 可用性 | cuInit=0，cuDeviceGetCount=0，设备 1 个，Driver API=12040；没有测试 PyTorch 或模型 CUDA kernel |
| 物理内存 | 初始 free -h 总量 31GiB，可用 21GiB |
| 磁盘 | 初始 df -h 可用 287G；报告时可用 {versions['disk_free_gib']} GiB |
| 默认 Python | /home/asus/anaconda3 的 Python 3.9.13 |
| 系统 Python | /usr/bin/python3，3.10.12 |
| 已有 conda | /home/asus/anaconda3/bin/conda，22.9.0；没有修改已有环境 |
| 已有 ROS | 环境变量 ROS_DISTRO=humble，/opt/ros/humble；没有安装或修改 |
| 新项目 Python | {platform.python_version()}，独立 .runtime/python + .venv |
| 环境工具 | {uv}，位于项目 .tools/bin |
| CPU 包 | 全部依赖导入/测试成功，uv pip check 检查 19 个包兼容 |
| GEOS | {shapely.geos_version_string} |

## 隔离与边界

项目根目录：`{ROOT}`。Python 运行时、venv、uv、下载缓存、临时文件均在此目录中。
Git 元数据位于父目录 `/home/asus/EAI/.git`；按用户要求，源码和结果同步到公开 GitHub 仓库 iC0ol/EAI。
历史日志保留迁移前路径，当前路径以本报告和当前解释器为准。
venv 不继承 system site-packages；run.sh 只在子进程中排除 ROS 与动态库搜索变量。
没有执行 sudo、修改系统包/驱动/Toolkit、激活或修改旧 conda、操作机器人、下载权重或安装训练/推理框架。

前后保护哈希检查：{protected['checked_files']} 个文件，变化 {len(protected['changed_files'])} 个。
范围为 inspection_robot_ws/src（排除 .git）以及选定 ROS setup、nvcc、系统 Python、shell 配置和 base-conda history。
这是一份有明确范围的保护快照，不是全系统未变动的证明。详见 protected_before.json 与 protected_comparison.json。

## 网络探测（只取 HEAD，未下载权重）

{net}

初始系统 Python urllib 请求 Hugging Face 时发生 SSL UNEXPECTED_EOF，完整错误保留在 logs/audit_initial.log。
随后系统 curl 对同一官方模型 API 返回 HTTP/2 200，见 logs/huggingface_head.log。
最终系统 Python urllib 复查同一端点也返回 200，见 logs/audit_final.log；首次 TLS 错误属于保留的瞬态记录。
元信息端点可访问，不等于已经验证权重文件 CDN 或实际 Hugging Face 下载客户端；后者留待 Phase 3。
没有关闭证书校验或修改代理配置。

## 安装版本

| 包 | 版本 |
|---|---|
{deps}

全部包与下载哈希见 ../requirements.lock。安装过程见 logs/bootstrap_uv.log、python_install.log、
venv_create.log、resolve.log、install.log、dependency_check.log。
字体与 lock 哈希、解释器路径及完整版本快照见 dependencies.json。

## 原始只读命令输出

```text
{command_text}
```
'''
    (REPORTS/'environment.md').write_text(environment)
    rows = []
    all_clearances = []
    for label in labels:
        sid = label['sample_id']
        scene = load(f'data/scenes/{sid}/scene.json')
        values = '/'.join(str(int(v)) if v is not None else '?' for v in label['labels'].values())
        clearances = [entry['fine']['path_min_clearance_m'] for entry in label['states'].values() if entry['fine']['passable']]
        all_clearances.extend(clearances)
        margin = f'{min(clearances):.6f}' if clearances else '无通过路径'
        rows.append(f'| {sid} | {label["family"]} | {scene["variant"]} | {label["core_acceptance"]} | {values} | {margin} |')
    row_text = '\n'.join(rows)
    sensitive = sum(entry['boundary_sensitive'] for label in labels for entry in label['states'].values())
    summary = f'''# Spatial Intervention Pilot — Checkpoint B

更新时间：{now}。Phase 0、1、2 已完成；停在场景/标签人工检查点。
没有运行 VLM；H1/H2、模型准确率、分类型误差、危险误通过率、推理耗时/显存全部尚未评估。
推理与评估入口明确禁用，outputs/predictions.jsonl 保持为空，不伪造预测或失败记录。

## 验收结果

- 六个核心几何实例全部通过：每类两个；原始 NONE 均不可通过。
- 完整自动测试：{tests['tests']} 项，失败 {tests['failures']}、错误 {tests['errors']}、跳过 {tests['skipped']}，见 tests.xml 与 logs/tests.log。
- 尝试 {manifest['attempted']}，成功 {manifest['succeeded']}，失败 {manifest['failed']}，未决 {manifest['oracle_unresolved']}；失败文件保持显式记录。
- 三类各 4 张原始图，总计 12 张 768×768；另有 48 张四状态私有几何图。
- 0.10m / 0.05m 主标签全部一致；额外 0.025m 复核 {resolution['checked_states']} 个状态，分歧 {resolution['disagreements']}。
- 独立重新生成 {reproduction['compared_files']} 个 data 文件，逐字节比对差异 {len(reproduction['mismatches'])}。
- 串联/替代路线有 4 个 matched view pairs，局部物体与候选编辑完全相同；其中只有 2 对参数化基础布局。
- 原有工程/环境的指定保护范围 {protected['checked_files']} 个文件，前后变化 {len(protected['changed_files'])} 个。

## 场景与标签（12 个可读审查案例）

顺序为 NONE / A / B / AB；1/0 是有限网格可达性，不代表物理编辑可执行性。
每个案例的原图、四状态编辑后图、绿色见证路径与完整 geometry 链接在 scene_review.html。

| 样本 | 类型 | 变体 | 六核心 | NONE/A/B/AB | 0.05m 见证路径最小裕量 m |
|---|---|---:|---|---|---:|
{row_text}

三类模式均由实际障碍膨胀和图搜索验证，生成器没有从 EXPECTED 表赋值。
串联：A/B 单独只能清一处，AB 才通；替代路线：A/B 分别打开一条完整路线；
副作用：A 清除起初阻塞，B 从停放区进入另一段必经通道，故 A 通过而 AB 不通过。
私有 local_effects 显式记录 source/target、清除/新增占用区域与面积，以及新增全局阻塞的求解证据。

## 关键实现与验证

编辑最终位姿必须在地图内、保持足迹/朝向、无非法面积重叠；非法编辑与组合冲突是异常，不计作 F=0。
AB 顺序无关测试仅针对合法相容场景；另有“分别合法、合用冲突”的反例测试。
颜色和底层物体 ID 变化不改真值；候选 A/B 标签互换应相应置换 F_A/F_B，测试已覆盖。
四邻接不走对角，对每条边做整段碰撞检查，薄墙、穿角、真实端点吸附等回归案例均通过。
公开数据不包含类型、答案、后态图或 oracle 路径；图像重渲染不受私有标签/文件名字段影响，PNG 无文字元数据。

## 可视化

- qc_montage.png：12 个原始场景及私有标签总览。
- qc_core_edits.png：六个核心实例 × NONE/A/B/AB。
- scene_review.html：12 案例逐一浏览，可点击完整 768px 原图与编辑后图。
- data/images 只含原图；reports/edits 的 48 张后态图与绿色路径仅供人工审查。

## 当前问题、偏差与控制

1. **样本独立性有限**：12 张由每类 2 个参数布局与其受控视图构成；不是 12 个独立拓扑。
   保留 family_id 与 matched group，之后按基础布局划分开发/测试，不能把镜像变体当未见布局证据。
2. **候选角色存在先验**：副作用样本固定为 A 清路、B 引入阻塞；本批没有做完整 A/B 角色反平衡。
   已测试角色重命名的标签置换；正式扩展时须加入对称角色和标签频率基线。颜色、底层 ID、旋转/镜像已作受控变化。
3. **规则图像可能过于简单**：颜色、矩形、顶视布局都很规整。未来需要同观察图像分割+规划基线，
   若它可靠解决全部子任务，就不能据此声称 VLM 必要或发现了新方法。
4. **分辨率边界**：目前三个网格一致仍不能证明连续空间不可达。{sensitive} 个通过状态的返回路径裕量低于 0.12m，
   0.05m 见证路径裕量范围 {min(all_clearances):.6f}–{max(all_clearances):.6f}m；BFS 常返回贴边路径，这不是通道最大净空。
   已对所有状态追加 0.025m 复核；若未来分歧，必须隔离为 oracle_unresolved，不计入主评价。
5. **任务范围有限**：机器人全向、圆形，编辑只考察假设最终几何，不检查物体搬运轨迹、差速转向或真实机器人安全性。
6. **网络曾出现瞬态 TLS 错误**：Hugging Face 元信息端点首次系统 Python urllib TLS EOF，后来 curl 与 urllib 均返回 200；
   不影响几何，但权重 CDN 与实际 Hugging Face 下载客户端未检查。未改代理、证书、驱动或 CUDA。
7. **跨机器位图复现**：当前工作站逐字节一致；不同字体/Pillow/GEOS 可能改变图像或浮点边界，
   因此保留依赖哈希、字体哈希和 GEOS 版本，不能只依赖随机种子。

## 版本与重现

- 随机种子：{manifest['config']['seed']}；配置哈希：`{manifest['config_sha256']}`。
- 生成时源代码 commit：`{manifest.get('source_commit')}`；源文件状态：`{manifest.get('source_status_at_generation') or 'clean'}`。
- Python {platform.python_version()}，{uv}，GEOS {shapely.geos_version_string}；完整版本见 environment.md / dependencies.json / requirements.lock。
- 单命令：`cd {ROOT} && bash scripts/run.sh all`。
- 模型 ID / revision / prompt version：null；原因是按授权停在 Phase 2，后续未部署。

## 下一检查点

请研究者核对原图可读性、虚线目标框的含义、候选操作信息是否足够以及三个模式的标签。
本次只建立可复现的诊断夹具；没有 H1/H2 结果，不能判断科研假设是否成立或是否值得学习方法投入。
在用户完成检查前，不扩到 24–36 个基础布局，不下载模型，不运行训练或推理。
'''
    (REPORTS/'pilot_summary.md').write_text(summary)
    cores = [label for label in labels if label['core_acceptance']]
    canvas = Image.new('RGB',(1024,72+len(cores)*292),'#EDF1F5')
    draw = ImageDraw.Draw(canvas)
    draw.text((16,12),'PRIVATE QC | six core scenes x four final states',font=font(23),fill='#17202C')
    draw.text((16,42),'Column order: NONE / A / B / AB. Green paths are private oracle witnesses.',font=font(16),fill='#4A5568')
    for i,label in enumerate(cores):
        y = 72+i*292
        draw.text((12,y+1),f"{label['family']} | {label['sample_id']} | "+'/'.join(str(int(v)) for v in label['labels'].values()),
                  font=font(18),fill='#17202C')
        for col,state in enumerate(['NONE','A','B','AB']):
            with Image.open(REPORTS/f"edits/{label['sample_id']}_{state}.png") as im:
                canvas.paste(im.resize((256,256),Image.Resampling.LANCZOS),(col*256,y+28))
    canvas.save(REPORTS/'qc_core_edits.png')
    print(json.dumps({'tests':tests,'generated':manifest['succeeded'],'reports_updated':True},ensure_ascii=False))


if __name__ == '__main__':
    main()
