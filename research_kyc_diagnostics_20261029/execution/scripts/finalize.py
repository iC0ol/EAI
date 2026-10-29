"""Safe CPU-only emergency/normal completion without needing a live agent."""
from diag_common import *

def finalize(reason, state='STOPPED'):
    c=read(E/'counts.json',{})
    s=read(E/'status.json',{})
    gate=read(E/'stage1_gate.json',{})
    final={'utc':utc(),'state':state,'reason':reason,'counts':c,
           'gpu_allocation_seconds':s.get('gpu_allocation_seconds',0),
           'stage0':read(E/'stage0_gate.json',{'decision':'NOT_RUN'}),
           'stage1_gate':gate or {'decision':'NOT_RUN'},
           'formal_test':'NOT_RUN','training':'NOT_RUN; optimizer updates=0',
           'requires_codex_and_deepseek_review':True,'publication':'PENDING_EXECUTOR'}
    write(E/'completion.json',final)
    path=E/'FINAL_REPORT.md'
    if not path.exists():
        path.write_text('# KYC 有限排障执行回执\n\n'
                        f'状态：{state}。原因：{reason}。\n\n'
                        '该文件由独立监督器收尾生成，需研究者验收。已有原始结果保留，未运行内容为 NOT_RUN。\n\n'
                        f'固定前向尝试：{c.get("fixed_forward_attempts",0)}；闭环 query：{c.get("closed_query_attempts",0)}；'
                        f'闭环条数：{c.get("rollout_attempts",0)}；优化器更新：0。\n\n'
                        '正式 test、完整重训、新算法：NOT_RUN。\n')
    (E/'STATUS.md').write_text(f'# 执行状态\n\n{state}：{reason}\n\n见 completion.json、counts.json、stages/ 和 FINAL_REPORT.md。\n')
    return final

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--reason',required=True);p.add_argument('--state',default='STOPPED')
    a=p.parse_args();finalize(a.reason,a.state)
