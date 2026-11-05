import argparse,importlib
ROUTES={'cpu-preflight':'cpu_preflight','cpu-supervise':'cpu_supervisor','supervise':'supervisor','gpu-preflight':'preflight_worker','expert-a':'expert_worker','policy-b':'policy_worker','c-local':'reader_worker','c-official':'reader_worker'}
def resolve(mode):return importlib.import_module('kyc_grasp.'+ROUTES[mode])
def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=list(ROUTES));p.add_argument('--stage');a=p.parse_args()
    if a.mode in ['cpu-preflight','cpu-supervise']:resolve(a.mode).main()
    elif a.mode=='supervise':resolve(a.mode).main(a.stage)
    else:
        from .gates import worker_gate
        worker_gate(a.mode);resolve(a.mode).main(a.mode)
