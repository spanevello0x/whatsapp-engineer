#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, signal, subprocess, sys, time
from pathlib import Path
SKILL_DIR=Path(__file__).resolve().parents[1]
STATE_DIR=Path.home()/'.openclaw/state/whatsapp-engineer/baileys'
PID=STATE_DIR/'worker.pid'; LOG=STATE_DIR/'worker.log'; STATUS=STATE_DIR/'status.json'; QR=STATE_DIR/'qr.png'; DB=STATE_DIR/'messages.db'; AUTH=STATE_DIR/'auth'
WORKER=str(SKILL_DIR/'workspace/baileys_worker.mjs')

def alive(pid:int)->bool:
    try: os.kill(pid,0); return True
    except OSError: return False

def read_json(p:Path):
    try: return json.loads(p.read_text())
    except Exception: return None

def worker_pids()->list[int]:
    try:
        out=subprocess.check_output(['pgrep','-f',WORKER], text=True)
    except Exception:
        return []
    me=os.getpid()
    pids=[]
    for line in out.splitlines():
        try: pid=int(line.strip())
        except ValueError: continue
        if pid and pid != me:
            pids.append(pid)
    return sorted(set(pids))

def stop_pid(pid:int, *, force:bool=False):
    if not pid or not alive(pid): return
    os.kill(pid, signal.SIGTERM); time.sleep(2)
    if force and alive(pid): os.kill(pid, signal.SIGKILL)

def main():
    ap=argparse.ArgumentParser(description='Start/status Baileys-owned WhatsApp session for whatsapp-engineer')
    ap.add_argument('--install', action='store_true')
    ap.add_argument('--force-restart', action='store_true')
    ap.add_argument('--wait-seconds', type=int, default=15)
    args=ap.parse_args()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if args.install:
        r=subprocess.run([sys.executable, str(SKILL_DIR/'scripts/setup_baileys.py')], text=True, capture_output=True)
        if r.returncode: print(r.stdout+r.stderr); return r.returncode
    if args.force_restart:
        for pid in worker_pids(): stop_pid(pid, force=True)
    if PID.exists():
        old=int(PID.read_text().strip() or '0')
        if old and alive(old):
            if args.force_restart:
                stop_pid(old, force=True)
            else:
                st=read_json(STATUS) or {}
                extra=[pid for pid in worker_pids() if pid != old]
                print(json.dumps({'ok':True,'already_running':True,'pid':old,'extra_worker_pids':extra,'status':st,'qr_path':str(QR),'db_path':str(DB)}, ensure_ascii=False, indent=2)); return 0
    env=dict(os.environ, WHATSAPP_ENGINEER_STATE_DIR=str(STATE_DIR), WHATSAPP_ENGINEER_AUTH_DIR=str(AUTH), WHATSAPP_ENGINEER_DB_PATH=str(DB), WHATSAPP_ENGINEER_QR_PATH=str(QR), WHATSAPP_ENGINEER_STATUS_PATH=str(STATUS))
    out=LOG.open('ab')
    proc=subprocess.Popen(['node','--experimental-sqlite', WORKER], cwd=SKILL_DIR, env=env, stdout=out, stderr=out)
    PID.write_text(str(proc.pid))
    st={}
    for _ in range(max(1,args.wait_seconds)):
        st=read_json(STATUS) or {}
        if st.get('state') in {'qr','open','history','error'}: break
        time.sleep(1)
    print(json.dumps({'ok':True,'pid':proc.pid,'status':st,'qr_path':str(QR),'db_path':str(DB),'log_path':str(LOG)}, ensure_ascii=False, indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
