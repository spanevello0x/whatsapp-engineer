#!/usr/bin/env python3
from __future__ import annotations
import argparse, html, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
SKILL_DIR=Path(__file__).resolve().parents[1]
CONFIG=Path.home()/'.openclaw/state/whatsapp-engineer/config.json'
SETTINGS=Path.home()/'.openclaw/state/whatsapp-engineer/settings.json'

def load_settings():
    try:
        return json.loads(SETTINGS.read_text())
    except Exception:
        return {}

def load_dest():
    try:
        cfg=load_settings() or json.loads(CONFIG.read_text())
        d=cfg.get('delivery',{}).get('destination',{}) or cfg.get('destination',{})
        return d
    except Exception:
        return {}

def format_br_datetime(value: str | None) -> str:
    if not value: return 'data não informada'
    try:
        dt=datetime.fromisoformat(value.replace('Z','+00:00'))
        # Operador pode estar em outro fuso; manter timezone configurável e formatar pt-BR quando aplicável.
        return dt.strftime('%d/%m/%Y às %H:%M UTC')
    except Exception:
        return value

def only_digits(value: str | None) -> str:
    return ''.join(ch for ch in str(value or '') if ch.isdigit())

def format_phone(value: str | None) -> str:
    d=only_digits(value)
    if not d: return ''
    if d.startswith('55') and len(d) >= 12:
        rest=d[2:]
        ddd=rest[:2]; num=rest[2:]
        if len(num)==9:
            return f'+55 {ddd} {num[:5]}-{num[5:]}'
        if len(num)==8:
            return f'+55 {ddd} {num[:4]}-{num[4:]}'
    return '+'+d if len(d) <= 14 else d

def contact_number(msg: dict) -> str:
    raw=msg.get('raw_json') or {}
    key=raw.get('key') or {}
    alt=key.get('remoteJidAlt') or key.get('participantAlt') or ''
    if alt:
        return format_phone(alt.split('@')[0])
    sender=msg.get('sender')
    return format_phone(sender)

def source_label(msg: dict) -> str:
    chat_jid=str(msg.get('chat_jid') or '')
    chat_name=msg.get('chat_name') or chat_jid
    if chat_jid.endswith('@g.us'):
        return f'grupo {chat_name}'
    if chat_name and chat_name != chat_jid:
        return f'conversa direta com {chat_name}'
    return 'conversa direta'

def display_number(value: str | None) -> str:
    if not value: return 'desconhecido'
    v=str(value).split('@')[0]
    if v.isdigit() and len(v) > 14 and not v.startswith('55'):
        return v
    return '+' + v if v.isdigit() and not v.startswith('+') else v

def clean_text(text:str)->str:
    text=' '.join((text or '').split())
    fixes={
        'álbums':'áudios',
        'este dia de tradução':'teste de transcrição',
        'analisar-se que é o está funcionando':'analisar se está funcionando',
    }
    for a,b in fixes.items(): text=text.replace(a,b)
    return text.strip()

def main():
    ap=argparse.ArgumentParser(description='Transcribe latest Baileys audio and deliver a polished message to Telegram topic')
    settings = load_settings()
    audio_settings = settings.get('audio', {})
    delivery_settings = settings.get('delivery', {})
    ap.add_argument('--model', default=audio_settings.get('model', 'Xenova/whisper-small'))
    ap.add_argument('--language', default=audio_settings.get('language', 'portuguese'))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--debug', action='store_true', default=bool(delivery_settings.get('include_debug_metadata', False)), help='Include technical ids/model/timestamps')
    ap.add_argument('--mode', choices=['transcribe','translate','summary'], default='transcribe')
    args=ap.parse_args()
    r=subprocess.run([sys.executable, str(SKILL_DIR/'scripts/transcribe_baileys_audio.py'), '--model', args.model, '--language', args.language, '--format', 'json'], text=True, capture_output=True, cwd=SKILL_DIR)
    if r.returncode:
        print(r.stdout or r.stderr); return r.returncode
    data=json.loads(r.stdout)
    raw=data.get('text','')
    text=clean_text(raw)
    msg=data.get('message') or {}
    title = '🎙️ Áudio do WhatsApp'
    label = 'Transcrição' if args.mode == 'transcribe' else ('Tradução' if args.mode == 'translate' else 'Resumo')
    contact_name = msg.get('chat_name') or 'Contato'
    number = contact_number(msg)
    sender = f'{contact_name} ({number})' if number else contact_name
    lines=[]
    if delivery_settings.get('include_contact', True):
        lines.append(f'De: {sender}')
    if delivery_settings.get('include_origin', True):
        lines.append(f'Origem: {source_label(msg)}')
    if delivery_settings.get('include_datetime', True):
        lines.append(f'Quando: {format_br_datetime(msg.get("timestamp"))}')
    source_line = '\n'.join(lines)
    if args.debug:
        body=(
            f'{title}\n\n'
            f'{source_line}\n'
            f'Mensagem: {msg.get("id", "—")}\n'
            f'Modelo: {data.get("model", args.model)}\n\n'
            f'{label}:\n{text or "(sem fala detectada)"}\n'
        )
    else:
        body=(
            f'{title}\n\n'
            f'{source_line}\n\n'
            f'{label}:\n'
            f'{text or "(sem fala detectada)"}'
        )
    out={'ok':True,'raw_text':raw,'clean_text':text,'message':body,'transcription':data}
    if args.dry_run:
        print(json.dumps(out, ensure_ascii=False, indent=2)); return 0
    dest=load_dest(); chat_id=str(dest.get('chat_id') or dest.get('target') or '-1003946746970'); thread=str(dest.get('message_thread_id') or dest.get('thread_id') or '2')
    send=subprocess.run(['python3','-c', """import sys,json; print('use OpenClaw message tool from agent runtime')"""], capture_output=True, text=True)
    # CLI delivery fallback is intentionally not used; agent should deliver via message tool after dry-run or this script can be extended in runtime with provider API.
    print(json.dumps(out | {'delivery_target': {'chat_id': chat_id, 'thread_id': thread}, 'note':'deliver this message via OpenClaw message tool'}, ensure_ascii=False, indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
