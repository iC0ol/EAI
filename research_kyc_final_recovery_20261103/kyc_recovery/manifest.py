"""Freeze a review candidate after the actual final CPU entry coverage."""
from .common import *
import ast
import difflib


def main():
    require(not (P/'recovery_state.json').exists(),'cannot rebuild after device execution')
    require(not list((P/'dispatch').glob('*.json')) if (P/'dispatch').exists() else True,
            'cannot rebuild after GPU/scientific dispatch')
    final=read(P/'cpu_preflight/final/result.json')
    require(final and final['status']=='CPU_IMPORT_READY' and final['final_entry_modules_verified'],
            'final actual CPU entry import failed/missing')
    require(all(sha(P/name)==digest for name,digest in final['final_code_hashes'].items()),
            'code changed since final real CPU coverage; do not hide with AST/mocks')
    old=W/'research_kyc_checkpoint_diagnostics_next'
    old_manifest=read(old/'candidate_manifest.json')
    sources=dict(old_manifest['sources'])
    sources.update({str(old/name):digest for name,digest in old_manifest['files'].items()})
    sources[str(R/'scripts/common.py')]=sha(R/'scripts/common.py')
    sources[str(D/'execution/root_plan.json')]='431b852e4aed785f72cbdc3fd8b59aefd981328c37f2098af5e8cea341a35416'
    sources[str(R/'results/dev_rollouts.jsonl')]=sha(R/'results/dev_rollouts.jsonl')
    for root in range(1000,1008):
        for name in ['model.xml','state.npy','rng.pt','manifest.json']:
            path=R/('root_states/dev/'+str(root))/name;sources[str(path)]=sha(path)
    for name,digest in sources.items():require(sha(Path(name))==digest,'read-only source differs: '+name)
    (P/'candidate_diffs').mkdir(exist_ok=True)
    for row in read(P/'copied_sources.json'):
        target=P/row['destination'];source=Path(row['source'])
        text=''.join(difflib.unified_diff(source.read_text().splitlines(True),target.read_text().splitlines(True),
                   fromfile=str(source),tofile=str(target),n=3))
        (P/'candidate_diffs'/(target.name+'.diff')).write_text(text)
    files=['run.py','PROTOCOL.md','AGENTS.md','00_本轮用户任务书_原文.md','01_有限恢复边界与阶段门.md',
           'preflight_scope_gate.json','orchestration/preflight_dispatch.json','sample_plan.json','call_plan.json',
           'root_plan.json','criteria_reference.md','references/stage1_v2_protocol.md','repair_ledger.json',
           'copied_sources.json','cpu_preflight/final/result.json','cpu_preflight/final/process.json',
           'cpu_preflight/cpu_budget_checks.json']
    files += [str(f.relative_to(P)) for f in sorted((P/'kyc_recovery').glob('*.py'))]
    files += [str(f.relative_to(P)) for f in sorted((P/'candidate_diffs').glob('*.diff'))]
    for name in files:
        if name.endswith('.py'):compile(ast.parse((P/name).read_text()),name,'exec')
    value=dict(state='CANDIDATE_CPU_IMPORT_READY_GPU_NOT_APPROVED',utc=utc(),recovery_id=RECOVERY_ID,
        protocol_sha256=sha(P/'PROTOCOL.md'),files={name:sha(P/name) for name in files},sources=sources,
        real_CPU_code_hashes=final['final_code_hashes'],GPU_seconds_cap=1800,counts_cap=CAPS,
        engineering_GPU_seconds_cap=180,stage1_GPU_seconds_cap=600,stage2='remaining_only',
        GPU_worker_hard_cap=5,planned_GPU_workers=4,each_phase_attempts=1,
        repair_rounds_used=2,repair_rounds_remaining=0,actual_GPU_workers=0,actual_GPU_seconds=0,
        actual_ACT=0,actual_render=0,actual_readPixels=0,actual_steps=0,ENGINEERING_READY=False,
        GPU_gate='requires new exact Codex and real DeepSeek review plus explicit phase dispatch',
        Stage2='requires actual Stage1 pass, dual phase acceptance, frozen closed-loop gate and explicit dispatch',
        Stage3='PLAN_ONLY')
    write(P/'candidate_manifest.json',value)
    print(json.dumps(dict(protocol_sha256=value['protocol_sha256'],candidate_manifest_sha256=sha(P/'candidate_manifest.json'),
        local_files=len(files),read_only_sources=len(sources),CPU_actual='PASSED',GPU='NOT_RUN')))


if __name__=='__main__':main()
