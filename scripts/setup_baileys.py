#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, subprocess
from pathlib import Path
SKILL_DIR = Path(__file__).resolve().parents[1]
STATE_DIR = Path.home()/'.openclaw/state/whatsapp-engineer/baileys'

def main():
    ap=argparse.ArgumentParser(description='Install Baileys runtime deps for whatsapp-engineer')
    ap.add_argument('--force', action='store_true')
    args=ap.parse_args()
    npm=shutil.which('npm')
    if not npm:
        print(json.dumps({'ok':False,'error':'npm not found'}, indent=2)); return 2
    need=args.force or not (SKILL_DIR/'node_modules/@whiskeysockets/baileys').exists() or not (SKILL_DIR/'node_modules/qrcode').exists()
    if need:
        subprocess.run([npm, 'install', '--omit=dev'], cwd=SKILL_DIR, check=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    print(json.dumps({'ok':True,'installed':need,'skill_dir':str(SKILL_DIR),'state_dir':str(STATE_DIR)}, indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
