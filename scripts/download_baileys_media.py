#!/usr/bin/env python3
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path
SKILL_DIR=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser(description='Backfill/download Baileys media by message id')
    ap.add_argument('--message-id', required=True)
    args=ap.parse_args()
    r=subprocess.run(['node','--experimental-sqlite',str(SKILL_DIR/'workspace/download_baileys_media.mjs'),'--message-id',args.message_id], cwd=SKILL_DIR, text=True)
    return r.returncode
if __name__=='__main__': raise SystemExit(main())
