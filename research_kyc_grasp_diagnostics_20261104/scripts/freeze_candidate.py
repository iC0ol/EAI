"""CPU-only packaging after real probe. No GPU authority and no Git operation."""
from pathlib import Path
import json,hashlib,datetime,re,xml.etree.ElementTree as ET
P=Path(__file__).resolve().parents[1];W=P.parent;R=W/'research_expansion_20261029/reproduction';K=R/'vendor/kyc/policy_robosuite'
def sha(f):
 h=hashlib.sha256()
 with Path(f).open('rb') as v:
  for b in iter(lambda:v.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def read(n):return json.loads((P/n).read_text())
def save(n,v):(P/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def clean(value):
 if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k!='module_id'}
 if isinstance(value,list):return [clean(v) for v in value]
 return value

def main():
 assert not (P/'scope_state.json').exists() and not (P/'science_clock.json').exists() and not (P/'roots/manifest.json').exists()
 assert not (P/'dispatch').exists() or not list((P/'dispatch').glob('*.json'))
 cpu=read('cpu_preflight/result.json');process=read('cpu_preflight/process.json');assert cpu['status']=='CPU_IMPORT_READY' and process['exit_code']==0
 assert cpu['device_audit']['CUDA_initialized_before'] is False and cpu['device_audit']['CUDA_initialized_after'] is False and not cpu['device_audit']['GL_modules_imported']
 for n,v in cpu['code_hashes'].items():assert sha(P/n)==v,('code differs from final actual CPU probe',n)
 paths=set()
 for base,suffixes in [(K,{'.py','.json'}),(R/'vendor/robosuite/robosuite',{'.py','.xml'})]:
  paths.update(f.resolve() for f in base.rglob('*') if f.is_file() and f.suffix in suffixes)
 for f in (R/'scripts').glob('*.py'):paths.add(f.resolve())
 explicit=['vendor/kyc/reproduce/paper_runs.yaml','vendor/kyc/script_robosuite_demos/gen_robosuite_format_demo.py','vendor/robosuite/robosuite/wrappers/action_wrapper.py','assets/liftrand_eef_delta.hdf5','checkpoints/C_latest.pt','cache/torch/hub/checkpoints/resnet18-f37072fd.pth','manifests/C_config.json','manifests/dataset_stats.json','manifests/frozen_roots.json','manifests/data_split.json','training_progress.json','checkpoint_manifest.json','results/semantics.json','results/semantics/expert_replays.jsonl','results/semantics/initial_restore_check.json','results/dev_summary.json','results/dev_rollouts.jsonl','logs/training_steps.jsonl','logs/training_events.jsonl','logs/validation.jsonl','results/semantics/canonical_initial_model.xml']
 for n in explicit:
  f=R/n
  if f.exists():paths.add(f.resolve())
 witness=R/'results/semantics/canonical_initial_model.xml';assets=[]
 if witness.exists():
  tree=ET.fromstring(witness.read_text())
  for element in tree.iter():
   file=element.get('file')
   if file:
    f=Path(file)
    if not f.is_absolute():f=witness.parent/f
    assert f.exists(),('referenced old Panda/Lift mesh/texture not resolvable',file)
    paths.add(f.resolve());assets.append(str(f.resolve()))
 sources={str(f):sha(f) for f in sorted(paths)}
 previous=json.loads((W/'research_kyc_final_recovery_20261103/candidate_manifest.json').read_text())['sources']
 matched={n:v for n,v in sources.items() if n in previous};assert all(v==previous[n] for n,v in matched.items()),'old previously pinned source changed'
 save('source_manifest.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sources=sources,all_older_paths_readonly=True,previously_frozen_intersection_checked=len(matched),previously_frozen_intersection_all_match=True,mesh_texture_dependency_witness='older canonical Panda/Lift XML only identifies assets; does not establish demo scene identity',asset_dependencies=sorted(set(assets))))
 report=clean(cpu);report['process']=process;report['source_count']=len(sources);report['source_bytes']=sum(Path(n).stat().st_size for n in sources);report['scope']='CPU preparation only, GPU pending exact dual review+RUN';report['CPU_attempts']=[dict(attempt=1,state='FAILED_CPU_TEST_FIXTURE',elapsed_seconds=14.2018291358836,archive='cpu_preflight_attempts/attempt_1'),dict(attempt=2,state='PASS_BEFORE_PARENT_FLOAT32_STEERING',elapsed_seconds=13.644495673011988,archive='cpu_preflight_attempts/attempt_2'),dict(attempt=3,state='PASS_OFFICIAL_FLOAT32_CONTRACT_BEFORE_PARENT_C_SPLIT_STEERING',elapsed_seconds=13.824397867079824,archive='cpu_preflight_attempts/attempt_3'),dict(attempt=4,state='PASS_C_SPLIT_RULE_BEFORE_REVIEW40',elapsed_seconds=14.127569741103798,archive='cpu_preflight_attempts/attempt_4'),dict(attempt=5,state='FINAL_LIMITED_REVIEW40_DELTA_CPU_CODE_COVERAGE',elapsed_seconds=process['elapsed_seconds'],archive='cpu_preflight')]
 report['protocol_sha256']=sha(P/'PROTOCOL_CANDIDATE.md');report['planned_trajectories']=12;report['planned_A_steps']=430;report['planned_B_steps']=1200;report['planned_ACT']=40;report['planned_C_getitems']=44
 save('CPU_PREPARATION_REPORT.json',report)
 text=f'''# CPU准备交付：GPU尚未批准\n\n**CPU_IMPORT_READY，仅CPU入口/资源/接口通过。** 最终同runtime/cwd/run.py实际进程exit0，{process['elapsed_seconds']:.6f}秒；真实上游loader、本地run_experiment/evaluate/validate_semantics、安全CLI分支和辅助模块均实际导入。当前{len(cpu['code_hashes'])}个Python源码与实际CPU快照SHA一致；安全入口/辅助身份记录共{len(cpu['final_entry_modules_verified'])}项。没有执行构造器、CUDA、GL、make_env、render、ACT、step、训练或真实optimizer。\n\n真实CPU读375项有限checkpoint张量、原args/stats、HDF5与四专家原始来源；四份reference_next_eef存在、形状/有限性通过且与HDF5 next_obs/robot0_eef_pos原值精确相等。固定demo0..3动作105/102/126/97，共430；原数据无逐demo XML，替代场景身份明确。CPU guard前后CUDA initialized=false、GL模块空、阻断设备尝试0；独立supervisor未观察到该CPU PID使用GPU，已退出。Torch数值线程3、interop1。\n\nCPU测试使用正式charge/CallGuard：40个**模拟**logical/internal ticket计数相符，ACT41、每rollout第6查询/151步、13轨迹/45getitem及预检禁用操作/optimizer/GPU门均拒绝；实际ACT/step为0。生产terminate函数确实SIGTERM了独立sleep子进程、exit-15，原PID失活。提取的真实wrapper函数在假CPU底层验证累计契约，绝不是物理阳性。官方eval原算术表达式在真实CPU Tensor上执行，与候选float32乘加bit equal，无新ACT；GPU时另断言policy返回等于内部捕获。\n\n五次CPU实际运行均留存：第一次预算测试夹具active_rollout为空，被正式guard正确拒绝；只把测试夹具改为带label，没有削弱正式guard，原traceback/前后源码/diff见repairs/CPU_fixture。第二次真实通过。父审随后要求执行float32/真实policy返回一致性，修改留diff，第三次实际通过官方算术契约。父审随后要求C validation故障后仍进入预定train split，追加后第四次真实通过。DeepSeek40及主审notes06又限定三项修订：目录缺失父目录创建且仍拒绝覆盖、四专家EEF源头断言、C原22槽位内demo0/1的t0重复。本次第五次是该限定修订后的唯一最终CPU覆盖。CPU确实执行两处生产mkdir语句，缺失父目录创建成功，重入被FileExistsError拒绝且已有marker未变；没有执行设备构造器。两组repeat的源状态/相机/seed约束已检查，未执行项实际调用比较函数输出NOT_RUN；没有执行真实C。上述均为准备阶段明确修订后的测试覆盖，不是GPU重跑。旧manifest/协议归档candidate_history/pre_review40，九个被改文件前后及diff见repairs/review40_delta。所有旧原件均保留；没有GPU额度消耗或科学时钟。\n\n候选新scope共用root恢复、base.step观测、严格加载、native/sentinel读回和ticket账本。A4+B8总12轨迹，B40 prior、C44实际getitem，取消旧20%门；详见协议与plan。C完整crop后item保存在实际collate的可索引数组中，代表pre-crop另存，防止大数组重复；两组t0重复沿用原末状态槽位与保存标记，within_arm_repeat只记录source/geometry/T/crop/raw/postcrop对比，早停缺项NOT_RUN且不追补。正式内秒额必须真实GPU预检后再双审冻结；预检候选≤90，总≤900。\n\n{len(sources)}个旧只读来源已锁SHA（含实际Panda/Lift XML引用的mesh/texture、官方/本地源码、数据/权重/日志），与前次已冻来源的交集{len(matched)}项全部匹配。当前源码/权重/数据/旧结果没有写入。原始cpu_preflight/result含Python对象身份id等，仅本地保存；公开报告已剔除module_id。公开只按public_allowlist，排除runtime/cache/tmp/原生地址/凭据/完整模型数据。\n\n**DEFERRED：** 实际4root生成/恢复、真实sim几何和控制器、GL初始化/健康读回、GPU模型strict-load、40 ACT/闭环、C实际crop/collate。CPU通过不能代替这些。全部GPU工程与科学阶段当前NOT_RUN；六问不作新增根因结论。准确候选manifest SHA见CANDIDATE_SHA256SUMS.txt；等待父审与真实DeepSeek准确SHA批准和新的phase dispatch，不自批，不Git操作，不更改automation。\n'''
 (P/'CPU_PREPARATION_REPORT.md').write_text(text)
 (P/'EXECUTOR_STATUS.md').write_text('CPU_IMPORT_READY / CANDIDATE_RETURN_PENDING / GPU_NOT_AUTHORIZED。最终代码真实CPU覆盖通过；所有GPU构造/渲染/ACT/A/B/C均NOT_RUN，等待精确SHA双审和新RUN。\n')
 files=[P/'run.py']+sorted((P/'kyc_grasp').glob('*.py'))
 for n in ['AGENTS.md','00_本轮用户任务书_原文.md','CPU_PREPARATION_AUTHORIZATION.json','SOURCE_AUDIT.md','PROTOCOL_CANDIDATE.md','STORAGE_AND_STOP_PLAN.md','CPU_PREPARATION_REPORT.md','CPU_PREPARATION_REPORT.json','EXECUTOR_STATUS.md','root_plan.json','rollout_plan.json','call_plan.json','sample_plan.json','phase_plan.json','source_manifest.json','cpu_preflight/result.json','cpu_preflight/process.json','cpu_preflight/started.json','scripts/freeze_candidate.py']:
  files.append(P/n)
 files+=sorted((P/'inputs').glob('*.npz'))
 # Repair metadata is bound; original raw CPU artifacts remain local evidence.
 files+=sorted(f for f in (P/'repairs').rglob('*') if f.is_file())
 manifest=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),state='CANDIDATE_CPU_IMPORT_READY_GPU_NOT_AUTHORIZED',scope_id=cpu['scope_id'],protocol_sha256=sha(P/'PROTOCOL_CANDIDATE.md'),files={str(f.relative_to(P)):sha(f) for f in sorted(set(files))},sources=sources,real_CPU_code_hashes=cpu['code_hashes'],GPU_seconds_cap=900,preflight_GPU_cap=90,actual_GPU_seconds=0,actual_GPU_workers=0,actual_ACT_steps_render=0,planned_A_rollouts=4,planned_B_rollouts=8,planned_ACT=40,planned_C_getitems=44,old_MAE_gate_applicable=False,authority='new exact dual-reviewed engineering/science/allocation and RUN_PHASE only')
 save('candidate_manifest.json',manifest)
 (P/'CANDIDATE_SHA256SUMS.txt').write_text(sha(P/'candidate_manifest.json')+'  candidate_manifest.json\n'+sha(P/'PROTOCOL_CANDIDATE.md')+'  PROTOCOL_CANDIDATE.md\n')
 public=[f for f in files if str(f.relative_to(P)) not in ['cpu_preflight/result.json']]
 public += [P/'candidate_manifest.json',P/'CANDIDATE_SHA256SUMS.txt']
 # Full raw CPU attempt trees/code snapshots/native object ids and runner logs are not public.
 public=sorted(set(f for f in public if not str(f.relative_to(P)).startswith('cpu_preflight/')))
 public_names=[str(f.relative_to(P)) for f in public]+['public_allowlist.txt','secret_scan.json','publication_manifest.json']
 (P/'public_allowlist.txt').write_text('\n'.join(sorted(public_names))+'\n')
 patterns=[r'AKIA[0-9A-Z]{16}',r'sk-[A-Za-z0-9_-]{24,}',r'-----BEGIN [A-Z ]*PRIVATE KEY-----',r'ya29\.[A-Za-z0-9_-]{20,}'];findings=[]
 for f in public:
  if f.suffix not in ['.npz']:
   text=f.read_text(errors='replace')
   for pattern in patterns:
    if re.search(pattern,text):findings.append(dict(file=str(f.relative_to(P)),pattern=pattern))
 save('secret_scan.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='explicit public allowlist only',scanned_files=len(public),findings=findings,excludes=['runtime','cache','tmp','local_only','raw CPU native object ids','DS CLI/raw/runner logs','credentials','full weights/dataset']))
 assert not findings,'secret-like data detected'
 public_evidence=public+[P/'public_allowlist.txt',P/'secret_scan.json']
 save('publication_manifest.json',dict(files={str(f.relative_to(P)):sha(f) for f in public_evidence},source_data_only_four_public_demo_subsets=True,public_allowlist_only=True,main_owns_git=True))
 print(json.dumps(dict(state=manifest['state'],code_files=len(cpu['code_hashes']),candidate_files=len(manifest['files']),sources=len(sources),public_files=len(public),protocol_sha256=manifest['protocol_sha256'],manifest_sha256=sha(P/'candidate_manifest.json'),directory_bytes=sum(f.stat().st_size for f in P.rglob('*') if f.is_file()),secret_findings=len(findings))))
if __name__=='__main__':main()
