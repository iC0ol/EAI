"""Shared CLI: no scientific mode can run without its separate exact gate."""
import argparse
import importlib

ROUTES={'cpu-preflight':'cpu_preflight','gpu-preflight':'gpu_preflight','s1-input':'input_worker',
        's1-model':'model_worker','s2-closed':'closed_worker','supervise':'supervisor','cpu-analyze':'analyze'}


def resolve(mode):
    return importlib.import_module('kyc_recovery.'+ROUTES[mode])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=list(ROUTES))
    parser.add_argument('--stage')
    args=parser.parse_args()
    if args.mode=='cpu-preflight':
        resolve(args.mode).main()
    elif args.mode=='supervise':
        resolve(args.mode).main(args.stage)
    elif args.mode=='cpu-analyze':
        resolve(args.mode).main()
    else:
        from .gates import worker_gate
        worker_gate(args.mode)
        resolve(args.mode).main()
