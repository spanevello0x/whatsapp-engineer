#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, signal, time
from pathlib import Path
GO_PROFILE = Path.home()/'Documents/WhatsApp MCP Profiles/projetos/Equipe/principal'
BAILEYS_STATE = Path.home()/'.openclaw/state/whatsapp-engineer/baileys'

def alive(pid:int)->bool:
    try: os.kill(pid, 0); return True
    except OSError: return False

def stop_pid(pid:int, timeout=5):
    if not pid or not alive(pid): return {'pid':pid,'stopped':False,'reason':'not_running'}
    try: os.kill(pid, signal.SIGTERM)
    except ProcessLookupError: return {'pid':pid,'stopped':False,'reason':'not_running'}
    for _ in range(timeout*10):
        if not alive(pid): return {'pid':pid,'stopped':True,'signal':'TERM'}
        time.sleep(.1)
    try: os.kill(pid, signal.SIGKILL)
    except ProcessLookupError: pass
    return {'pid':pid,'stopped':True,'signal':'KILL'}

def read_pid(path:Path):
    try: return int(path.read_text().strip())
    except Exception: return None

def main():
    ap=argparse.ArgumentParser(description='Stop whatsapp-engineer engines safely')
    ap.add_argument('--legacy-go', action='store_true', help='Stop legacy Go/whatsmeow bridge')
    ap.add_argument('--baileys', action='store_true', help='Stop Baileys worker')
    ap.add_argument('--all', action='store_true')
    args=ap.parse_args()
    if not (args.legacy_go or args.baileys or args.all): args.all=True
    out={'ok':True,'stopped':{}}
    if args.legacy_go or args.all:
        pid=read_pid(GO_PROFILE/'.bridge.pid')
        out['stopped']['legacy_go']=stop_pid(pid) if pid else {'pid':None,'stopped':False,'reason':'pid_missing'}
    if args.baileys or args.all:
        pid=read_pid(BAILEYS_STATE/'worker.pid')
        out['stopped']['baileys']=stop_pid(pid) if pid else {'pid':None,'stopped':False,'reason':'pid_missing'}
    print(json.dumps(out, ensure_ascii=False, indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
