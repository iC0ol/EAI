import csv
import datetime
import json
from pathlib import Path

from m_direction.io import ROOT as M_ROOT, D_ROOT, sha256, array_hash, encode, git, stable_seed

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"outputs"
REPORT=ROOT/"reports"
LOCAL=ROOT/"local"
BASE="89d89fbcd6458e50ae875746dd1adcdb032ec121"


def read_json(p): return json.loads(Path(p).read_text())
def config(): return read_json(ROOT/"configs/protocol.json")
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write_json(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x") as f: json.dump(x,f,indent=2,ensure_ascii=False,default=encode,allow_nan=False);f.write("\n")


def write_csv(p,rows):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x",newline="") as f:
        w=csv.DictWriter(f,list(rows[0]),lineterminator="\n");w.writeheader()
        for r in rows:
            w.writerow({k:json.dumps(v,default=encode,separators=(",",":"),allow_nan=False) if isinstance(v,(list,dict)) or hasattr(v,"shape") else v for k,v in r.items()})


def read_csv(p):
    with Path(p).open() as f:return list(csv.DictReader(f))
