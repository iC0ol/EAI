"""Download named public papers only; no model, dataset, or code execution."""
from pathlib import Path
import concurrent.futures, datetime, hashlib, json, subprocess, urllib.request
ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'bid': 'https://arxiv.org/pdf/2408.17355',
    'median_te': 'https://arxiv.org/pdf/2609.27167v1',
    'chunk_ensembles': 'https://arxiv.org/pdf/2608.02547v1',
    'multimodal_failure': 'https://arxiv.org/pdf/2605.22493v1',
    'deminf': 'https://arxiv.org/pdf/2502.08623',
    'datamil': 'https://arxiv.org/pdf/2505.09603',
    'cupid': 'https://arxiv.org/pdf/2506.19121',
    'state_interfaces': 'https://arxiv.org/pdf/2608.03052v1',
    'adapt_body_WITHDRAWN': 'https://arxiv.org/pdf/2506.23944v1',
}
def fetch(item):
    name, url = item
    target = ROOT/'sources'/f'{name}.pdf'
    meta = {'name': name, 'url': url, 'retrieved_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        if not target.exists():
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (public research document review)'})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read(25_000_001)
            if len(data)>25_000_000 or not data.startswith(b'%PDF'): raise ValueError('Not a bounded PDF')
            target.write_bytes(data)
        subprocess.run(['/usr/bin/pdftotext','-layout',str(target),str(target.with_suffix('.txt'))],check=True,timeout=60)
        meta.update(status='FETCHED_TEXT_EXTRACTED', bytes=target.stat().st_size, sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    except Exception as e:
        meta.update(status='FAILED', error=str(e))
    return meta
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    rows = list(pool.map(fetch, SOURCES.items()))
(ROOT/'artifacts/paper_download_manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
for row in rows: print(json.dumps(row,ensure_ascii=False))
