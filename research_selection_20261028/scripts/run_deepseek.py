"""Run an explicitly authorized read-only DeepSeek consultation via Claude CLI."""
from pathlib import Path
import argparse, datetime, json, os, subprocess, uuid

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('turn')
p.add_argument('--resume', action='store_true')
p.add_argument('--timeout', type=int, default=1200)
a = p.parse_args()
if not a.turn.replace('_', '').isalnum():
    raise SystemExit('Invalid turn name')
session_file = ROOT / 'discussion/session.json'
if a.resume:
    session = json.loads(session_file.read_text())['session_id']
else:
    if session_file.exists():
        raise SystemExit('Session already exists; use --resume')
    session = str(uuid.uuid4())
    session_file.write_text(json.dumps({'session_id': session, 'original_session': '9be4870e-04f0-446c-9adf-24281ae34cf0', 'original_resume': 'NOT_FOUND', 'client': 'Claude Code 2.1.308', 'configured_model': 'deepseek-flash[1M]', 'context': 'new session with verified historical documents'}, ensure_ascii=False, indent=2)+'\n')
prompt = ROOT / 'discussion' / f'{a.turn}_prompt.md'
output = ROOT / 'discussion' / f'{a.turn}_raw.jsonl'
if output.exists():
    raise SystemExit('Refusing to overwrite raw communication')
args = ['claude', '-p', '--resume' if a.resume else '--session-id', session,
        '--tools', 'Read,Glob,Grep,WebSearch,WebFetch', '--allowedTools', 'Read,Glob,Grep,WebSearch,WebFetch',
        '--permission-mode', 'dontAsk', '--strict-mcp-config', '--output-format', 'stream-json', '--verbose']
now = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
meta = {'turn': a.turn, 'session_id': session, 'started_utc': now(), 'pid': os.getpid(), 'command': args, 'timeout_seconds': a.timeout}
meta_path = ROOT / 'discussion' / f'{a.turn}_metadata.json'
meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2)+'\n')
try:
    with output.open('w') as out, (ROOT / 'logs' / f'{a.turn}.stderr').open('w') as err:
        run = subprocess.run(args, input=prompt.read_text(), text=True, stdout=out, stderr=err, cwd=ROOT, timeout=a.timeout)
    meta['exit_code'] = run.returncode
except subprocess.TimeoutExpired:
    meta['exit_code'] = 'TIMEOUT'
meta['ended_utc'] = now()
texts, models = [], set()
for line in output.read_text().splitlines():
    try:
        event = json.loads(line)
    except ValueError:
        continue
    if event.get('type') == 'assistant':
        msg = event.get('message', {})
        if msg.get('model'): models.add(msg['model'])
        for part in msg.get('content', []):
            if part.get('type') == 'text': texts.append(part['text'])
    if event.get('type') == 'result':
        meta['result_status'] = event.get('subtype')
        meta['permission_denials'] = event.get('permission_denials', [])
        meta['model_usage'] = event.get('modelUsage', {})
meta['response_model_fields'] = sorted(models)
meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2)+'\n')
(ROOT / 'discussion' / f'{a.turn}_response.md').write_text('\n\n'.join(texts)+'\n')
print(json.dumps(meta, ensure_ascii=False))
