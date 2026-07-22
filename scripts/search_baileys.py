#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3
from datetime import datetime, timezone
from pathlib import Path
STATE_DIR=Path.home()/'.openclaw/state/whatsapp-engineer/baileys'
DB=STATE_DIR/'messages.db'; STATUS=STATE_DIR/'status.json'

def db_stats(db:Path):
    if not db.exists(): return {'exists':False,'messages':0,'chats':0,'first':None,'last':None}
    try:
        con=sqlite3.connect(f'file:{db}?mode=ro', uri=True); cur=con.cursor()
        first,last=cur.execute('select min(timestamp), max(timestamp) from messages').fetchone()
        out={'exists':True,'messages':cur.execute('select count(*) from messages').fetchone()[0],'chats':cur.execute('select count(*) from chats').fetchone()[0],'first':first,'last':last}
        con.close(); return out
    except Exception as e: return {'exists':True,'messages':0,'chats':0,'first':None,'last':None,'error':str(e)}

def load_status():
    try: return json.loads(STATUS.read_text())
    except Exception: return {}

def main():
    ap=argparse.ArgumentParser(description='Search Baileys-owned whatsapp-engineer SQLite DB')
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--year', type=int); ap.add_argument('--after'); ap.add_argument('--before')
    ap.add_argument('--query'); ap.add_argument('--chat-name'); ap.add_argument('--chat-jid'); ap.add_argument('--phone-number')
    ap.add_argument('--limit', type=int, default=100); ap.add_argument('--page', type=int, default=0); ap.add_argument('--pretty', action='store_true', default=True)
    args=ap.parse_args()
    if args.year:
        args.after=args.after or f'{args.year:04d}-01-01'; args.before=args.before or f'{args.year+1:04d}-01-01'
    profile={'slug':'baileys-main','name':'Baileys Main','project':'WhatsApp Engineer','engine':'baileys','paths':{'messages_db':str(DB),'status':str(STATUS)},'db':db_stats(DB),'status':load_status()}
    if args.status:
        out={'profile':profile}
    else:
        items=[]
        if DB.exists():
            where=[]; params=[]
            if args.query:
                where.append("(lower(coalesce(c.name,'')) like lower(?) or lower(coalesce(m.content,'')) like lower(?) or lower(coalesce(m.sender,'')) like lower(?))"); params += [f'%{args.query}%']*3
            if args.chat_name: where.append("lower(coalesce(c.name,'')) like lower(?)"); params.append(f'%{args.chat_name}%')
            if args.chat_jid: where.append('m.chat_jid = ?'); params.append(args.chat_jid)
            if args.phone_number: where.append('(m.sender like ? or m.chat_jid like ?)'); params += [f'%{args.phone_number}%']*2
            if args.after: where.append('m.timestamp >= ?'); params.append(args.after)
            if args.before: where.append('m.timestamp < ?'); params.append(args.before)
            sql='where '+ ' and '.join(where) if where else ''
            limit=max(1,min(args.limit,1000)); offset=max(0,args.page)*limit; params += [limit, offset]
            con=sqlite3.connect(f'file:{DB}?mode=ro', uri=True); cur=con.cursor()
            rows=cur.execute(f'''select m.timestamp,m.sender,c.name,m.chat_jid,m.id,m.content,m.is_from_me,m.media_type,m.filename,m.file_length, m.local_path
              from messages m left join chats c on m.chat_jid=c.jid {sql} order by m.timestamp desc limit ? offset ?''', params).fetchall(); con.close()
            items=[{'timestamp':r[0],'sender':r[1],'chat_name':r[2],'chat_jid':r[3],'message_id':r[4],'content':r[5],'is_from_me':bool(r[6]),'media_type':r[7],'filename':r[8],'file_length':r[9], 'local_path': r[10] if len(r) > 10 else None} for r in rows]
        out={'generated_at':datetime.now(timezone.utc).isoformat(),'engine':'baileys','filters':vars(args),'results':[{'profile':profile,'items':items}]}
    print(json.dumps(out, ensure_ascii=False, indent=2 if args.pretty else None)); return 0
if __name__=='__main__': raise SystemExit(main())
