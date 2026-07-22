#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3, subprocess, sys
from pathlib import Path
SKILL_DIR=Path(__file__).resolve().parents[1]
DB=Path.home()/'.openclaw/state/whatsapp-engineer/baileys/messages.db'

def get_raw(message_id: str):
    try:
        con=sqlite3.connect(f'file:{DB}?mode=ro', uri=True); cur=con.cursor()
        row=cur.execute("select raw_json from messages where id=?", (message_id,)).fetchone(); con.close()
        return json.loads(row[0]) if row and row[0] else None
    except Exception:
        return None

def latest_audio():
    if not DB.exists(): return None
    con=sqlite3.connect(f'file:{DB}?mode=ro', uri=True); cur=con.cursor()
    row=cur.execute("select m.timestamp,m.sender,m.chat_jid,m.id,m.local_path,m.file_length,c.name from messages m left join chats c on m.chat_jid=c.jid where m.media_type='audio' and m.local_path is not null and m.local_path <> '' order by m.timestamp desc limit 1").fetchone()
    con.close(); return row

def main():
    ap=argparse.ArgumentParser(description='Transcribe Baileys audio downloaded by whatsapp-engineer')
    ap.add_argument('audio', nargs='?', help='Audio path. Defaults to latest downloaded audio in Baileys DB.')
    ap.add_argument('--message-id')
    ap.add_argument('--model', default='Xenova/whisper-tiny')
    ap.add_argument('--language', default='portuguese')
    ap.add_argument('--format', choices=['json','text'], default='json')
    args=ap.parse_args()
    audio=args.audio
    meta=None
    if args.message_id:
        con=sqlite3.connect(f'file:{DB}?mode=ro', uri=True); cur=con.cursor()
        meta=cur.execute("select m.timestamp,m.sender,m.chat_jid,m.id,m.local_path,m.file_length,c.name from messages m left join chats c on m.chat_jid=c.jid where m.id=?", (args.message_id,)).fetchone(); con.close()
        if meta: audio=meta[4]
    if not audio:
        meta=latest_audio()
        if meta: audio=meta[4]
    if not audio:
        print(json.dumps({'ok':False,'error':'no_downloaded_audio_found','hint':'send a new audio after v1.10.0 so local_path is populated'}, ensure_ascii=False, indent=2)); return 2
    p=Path(audio)
    if not p.exists():
        print(json.dumps({'ok':False,'error':'audio_path_missing','audio':str(p)}, ensure_ascii=False, indent=2)); return 2
    cmd=['node','--experimental-sqlite', str(SKILL_DIR/'workspace/transcribe_audio_node.mjs'), str(p), '--model', args.model, '--language', args.language, '--format', args.format]
    r=subprocess.run(cmd, text=True, capture_output=True, cwd=SKILL_DIR)
    if r.returncode:
        print(json.dumps({'ok':False,'error':'transcription_failed','stderr':r.stderr[-4000:],'stdout':r.stdout[-1000:]}, ensure_ascii=False, indent=2)); return r.returncode
    if args.format=='json':
        try:
            out=json.loads(r.stdout); out['message']={'timestamp':meta[0], 'sender':meta[1], 'chat_jid':meta[2], 'id':meta[3], 'file_length':meta[5], 'chat_name': meta[6] if len(meta) > 6 else None, 'raw_json': get_raw(meta[3]) if meta else None} if meta else None; print(json.dumps(out, ensure_ascii=False, indent=2))
        except Exception: print(r.stdout)
    else: print(r.stdout.strip())
    return 0
if __name__=='__main__': raise SystemExit(main())
