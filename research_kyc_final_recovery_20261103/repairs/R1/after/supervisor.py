"""Two explicit stage invocations, one cumulative ledger; never run in prep."""
from .common import *
from .gates import gate, reserve
import argparse
import secrets
import signal
import subprocess
import sys


def resources():
    processes = {int(p.name): proc(int(p.name)) for p in Path('/proc').iterdir() if p.name.isdigit()}
    ids = {os.getpid()}
    for _ in range(10):
        found = {p for p, v in processes.items() if v and v['ppid'] in ids}
        if found <= ids:
            break
        ids |= found
    query = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                           capture_output=True, text=True, timeout=1)
    require(query.returncode == 0, 'GPU resource monitor failed')
    values = [int(line.strip())*2**20 for line in query.stdout.splitlines() if line.strip().isdigit()]
    require(values, 'GPU resource monitor empty')
    return dict(utc=utc(), rss=sum(v['rss'] for p, v in processes.items() if v and p in ids),
                total_device_vram=max(values),
                disk_bytes=sum(f.stat().st_size for f in P.rglob('*') if f.is_file()))


def terminate(child, identity):
    if child.poll() is not None:
        return
    require(active(identity), 'child PID identity changed; refuse unrelated signal')
    os.killpg(child.pid, signal.SIGTERM)
    try:
        child.wait(timeout=3)
    except subprocess.TimeoutExpired:
        require(active(identity), 'child identity changed before kill')
        os.killpg(child.pid, signal.SIGKILL)
        child.wait(timeout=1)


def main(stage):
    dispatch = gate(stage, full=True)  # no worker or GPU imports before approval
    with (P/'supervisor.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.sched_setaffinity(0, set(sorted(os.sched_getaffinity(0))[:3]))
        require(not (P/'stop_request.json').exists(), 'terminal stop; no retry')
        (P/'stages').mkdir(exist_ok=True)
        # Exclusive marker is never removed, including failed starts.
        write(P/('stages/'+stage+'_started.json'), dict(utc=utc(), run_id=dispatch['run_id'],
              identity=proc(os.getpid()), stage=stage), exclusive=True)
        if stage == 'input':
            state = dict(run_id=dispatch['run_id'], deadline_epoch=dispatch['deadline_epoch'],
                         counts={k: 0 for k in CAPS}, GPU_seconds=0., active_lease=None, stages={})
            write(P/'run_state.json', state, exclusive=True)
        else:
            state = read(P/'run_state.json')
            require(state['run_id'] == dispatch['run_id'] and state['active_lease'] is None
                    and state['counts']['workers'] == 1, 'model stage requires one exited input worker')
        remaining = 600-state['GPU_seconds']
        quota = min(210., remaining) if stage == 'input' else remaining
        require(quota >= (210 if stage == 'input' else 390), 'insufficient frozen phase budget')
        token = secrets.token_hex(24)
        started = time.monotonic(); epoch = time.time()
        lease = dict(stage=stage, token=token, supervisor_pid=os.getpid(),
                     held_GPU_seconds=quota, lease_recorded_before_launch=True, started_monotonic=started)
        state['active_lease'] = lease; write(P/'run_state.json', state)
        reserve('workers', stage, 'fresh_exec_'+stage)
        command = [str(R/'env/bin/python'), '-B', str(P/'scripts'/(stage+'_worker.py'))]
        environment = envvars(); environment['KYC_STAGE_TOKEN'] = token
        for key in ['__GL_SHADER_DISK_CACHE_PATH', 'CUDA_CACHE_PATH']:
            environment[key] = str(P/'cache/nvidia')
        environment['__GL_SHADER_DISK_CACHE'] = '0'
        child = None; identity = None; reason = None
        def interrupted(sig, frame):
            nonlocal reason
            reason = 'SUPERVISOR_SIGNAL_'+str(sig)
        for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGUSR1]:
            signal.signal(sig, interrupted)
        try:
            with (P/'logs'/(stage+'.log')).open('x') as log:
                child = subprocess.Popen(command, cwd=P, env=environment, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            identity = proc(child.pid)
            require(identity and identity['pid'] == child.pid, 'could not identify new worker')
            with (P/'counter.lock').open('a+') as counter:
                fcntl.flock(counter, fcntl.LOCK_EX)
                state = read(P/'run_state.json'); state['active_lease']['identity'] = identity
                write(P/'run_state.json', state)
            append(P/'commands.jsonl', dict(utc=utc(), event='FRESH_EXEC', stage=stage,
                   command=command, identity=identity, epoch=epoch, monotonic=started))
            last = -10
            while child.poll() is None:
                elapsed = time.monotonic()-started
                if elapsed >= quota-15:
                    reason = 'GPU_STOP_WITH_15S_RELEASE_MARGIN'
                if time.time() >= dispatch['deadline_epoch']-30:
                    reason = 'RUN_DEADLINE_RELEASE_RESERVE'
                if reason:
                    terminate(child, identity); break
                if elapsed-last >= 2:
                    resource = resources(); last = elapsed
                    append(P/'resources.jsonl', dict(resource, stage=stage, worker_elapsed=elapsed))
                    if resource['rss'] > 16*2**30 or resource['total_device_vram'] > 12*2**30 or resource['disk_bytes'] > 150*2**20:
                        reason = 'RESOURCE_CAP'
                time.sleep(.1)
            reason = reason or ('WORKER_EXITED' if child.returncode == 0 else 'WORKER_FAILED')
        except BaseException as exc:
            reason = reason or 'SUPERVISOR_'+type(exc).__name__
            raise
        finally:
            if child is not None and child.poll() is None:
                terminate(child, identity)
            elapsed = time.monotonic()-started
            with (P/'counter.lock').open('a+') as counter:
                fcntl.flock(counter, fcntl.LOCK_EX)
                state = read(P/'run_state.json')
                state['GPU_seconds'] += elapsed
                record = dict(utc=utc(), state='EXITED' if child is not None and child.poll() is not None else 'START_FAILED',
                    identity=identity, exit_code=child.returncode if child else None, reason=reason,
                    GPU_seconds=elapsed, cumulative_GPU_seconds=state['GPU_seconds'],
                    phase_allocation=quota, epoch=epoch, ended_epoch=time.time(),
                    counts_after_exit=state['counts'].copy())
                state['stages'][stage] = record; state['active_lease'] = None
                write(P/'run_state.json', state); write(P/('stages/'+stage+'.json'), record, exclusive=True)
            result = read(P/(stage+'_result.json'), {})
            success_state = 'COMPLETE_HEALTHY_PENDING_PARENT' if stage == 'input' else 'COMPLETE'
            okay = (record['exit_code'] == 0 and reason == 'WORKER_EXITED'
                    and elapsed <= quota and state['GPU_seconds'] <= 600
                    and result.get('state') == success_state and not active(identity))
            if not okay:
                write(P/'stop_request.json', dict(utc=utc(), stage=stage, reason=reason,
                      result_state=result.get('state'), terminal=True))
            write(P/'status.json', dict(utc=utc(), state='WAITING_PARENT_INPUT_GATE' if okay and stage == 'input'
                  else ('MODEL_FINISHED_PENDING_REVIEW' if okay else 'TERMINAL_STOP'), stage=stage,
                  counts=state['counts'], GPU_seconds=state['GPU_seconds'], worker_alive=False,
                  no_automatic_next_stage=True, no_new_training_rollout_authorization=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--stage', choices=['input', 'model'], required=True)
    main(parser.parse_args().stage)
