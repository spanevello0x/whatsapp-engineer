#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os
from pathlib import Path
from typing import Any

STATE_DIR = Path.home() / '.openclaw' / 'state' / 'whatsapp-engineer'
SETTINGS_PATH = STATE_DIR / 'settings.json'
LEGACY_CONFIG = STATE_DIR / 'config.json'

DEFAULT_SETTINGS: dict[str, Any] = {
    'version': 1,
    'mode': 'baileys-owned-session',
    'delivery': {
        'type': 'telegram',
        'chat_id': '',
        'message_thread_id': '',
        'parse_mode': 'plain',
        'audio_template': 'clean',
        'include_contact': True,
        'include_origin': True,
        'include_datetime': True,
        'include_debug_metadata': False,
    },
    'sync': {
        'enabled': True,
        'mode': 'near_real_time',
        'poll_interval_seconds': 3,
        'media_download': True,
        'audio_transcription': True,
        'delivery_debounce_seconds': 2,
    },
    'audio': {
        'model': 'Xenova/whisper-tiny',
        'language': 'portuguese',
        'task': 'transcribe',
        'auto_deliver_transcription': True,
    },
    'formatting': {
        'timezone': 'UTC',
        'datetime_format': 'pt-BR',
        'group_origin_prefix': 'grupo',
        'direct_origin_prefix': 'conversa direta com',
    },
    'safety': {
        'single_number_owner': True,
        'require_operator_for_qr': True,
        'qr_valid_seconds': 60,
        'never_store_tokens': True,
    },
}

def deep_merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}

def normalize_model(value: str) -> str:
    aliases = {'tiny': 'Xenova/whisper-tiny', 'base': 'Xenova/whisper-base', 'small': 'Xenova/whisper-small'}
    return aliases.get(str(value), str(value))

def from_legacy() -> dict[str, Any]:
    cfg = load_json(LEGACY_CONFIG)
    primary = (cfg.get('destinations') or {}).get('primary') or (cfg.get('delivery') or {}).get('destination') or {}
    audio = cfg.get('audio') or {}
    out: dict[str, Any] = {}
    if primary:
        out['delivery'] = {
            'type': primary.get('type', 'telegram'),
            'chat_id': str(primary.get('chat_id') or ''),
            'message_thread_id': str(primary.get('message_thread_id') or ''),
            'parse_mode': 'plain',
        }
    if audio:
        out['audio'] = {
            'model': normalize_model(audio.get('model', DEFAULT_SETTINGS['audio']['model'])),
            'language': audio.get('language', DEFAULT_SETTINGS['audio']['language']),
            'task': audio.get('task', DEFAULT_SETTINGS['audio']['task']),
        }
    return out

def normalize_settings(settings: dict[str, Any]) -> dict[str, Any]:
    settings.setdefault('audio', {})
    settings['audio']['model'] = normalize_model(settings['audio'].get('model', DEFAULT_SETTINGS['audio']['model']))
    return settings

def load_settings(path: Path = SETTINGS_PATH) -> dict[str, Any]:
    if path.exists():
        return normalize_settings(deep_merge(DEFAULT_SETTINGS, load_json(path)))
    return normalize_settings(deep_merge(DEFAULT_SETTINGS, from_legacy()))

def save_settings(settings: dict[str, Any], path: Path = SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.chmod(path, 0o600)

def parse_telegram_topic_link(value: str) -> tuple[str, str]:
    import re
    text=(value or '').strip()
    m=re.search(r't\.me/c/(\d+)/(\d+)', text)
    if not m:
        return '', ''
    return '-100'+m.group(1), m.group(2)

def ask(prompt: str, default: Any = '') -> str:
    suffix = f' [{default}]' if default not in (None, '') else ''
    print(f'\n{prompt}{suffix}')
    value = input('> ').strip()
    return value if value else str(default or '')

def ask_bool(prompt: str, default: bool) -> bool:
    marker = 'S/n' if default else 's/N'
    print(f'\n{prompt} [{marker}]')
    value = input('> ').strip().lower()
    if not value:
        return default
    return value in {'s', 'sim', 'y', 'yes', '1', 'true'}

def wizard(settings: dict[str, Any]) -> dict[str, Any]:
    print('Vou configurar a entrega e a sincronia da WhatsApp Engineer. Vou perguntar uma coisa por vez e salvar tudo em settings.json. ⚙️\n')
    d = settings['delivery']; sync = settings['sync']; audio = settings['audio']; fmt = settings['formatting']
    d['type'] = ask('Qual canal de entrega? 📨', d.get('type', 'telegram')).lower()
    if d['type'] == 'telegram':
        d['chat_id'] = ask('Qual chat_id do Telegram? 🧭', d.get('chat_id', ''))
        d['message_thread_id'] = ask('Qual message_thread_id do tópico? Use vazio se não tiver tópico. 🧵', d.get('message_thread_id', ''))
    d['audio_template'] = ask('Qual template de áudio? clean/debug/custom 🎙️', d.get('audio_template', 'clean'))
    d['include_contact'] = ask_bool('Incluir nome/número do contato na entrega? 👤', bool(d.get('include_contact', True)))
    d['include_origin'] = ask_bool('Incluir origem da mensagem, incluindo nome do grupo quando houver? 👥', bool(d.get('include_origin', True)))
    d['include_datetime'] = ask_bool('Incluir data/hora em formato PT-BR? 🕒', bool(d.get('include_datetime', True)))
    sync['enabled'] = ask_bool('Ativar sincronia near-real-time? ⚡', bool(sync.get('enabled', True)))
    sync['poll_interval_seconds'] = int(ask('Intervalo do live-watch em segundos? 🔁', sync.get('poll_interval_seconds', 3)) or 3)
    sync['media_download'] = ask_bool('Baixar mídias automaticamente? 📎', bool(sync.get('media_download', True)))
    sync['audio_transcription'] = ask_bool('Transcrever áudios automaticamente? 🎧', bool(sync.get('audio_transcription', True)))
    audio['model'] = normalize_model(ask('Modelo de transcrição? 🧠', audio.get('model', 'Xenova/whisper-tiny')))
    audio['language'] = ask('Idioma dos áudios? 🌎', audio.get('language', 'portuguese'))
    fmt['timezone'] = ask('Timezone para exibir data/hora? 🕒', fmt.get('timezone', 'UTC'))
    settings['delivery'] = d; settings['sync'] = sync; settings['audio'] = audio; settings['formatting'] = fmt
    return settings

def main() -> int:
    ap = argparse.ArgumentParser(description='Manage whatsapp-engineer settings.json')
    ap.add_argument('--path', type=Path, default=SETTINGS_PATH)
    ap.add_argument('--wizard', action='store_true')
    ap.add_argument('--init', action='store_true')
    ap.add_argument('--print', action='store_true')
    args = ap.parse_args()
    settings = load_settings(args.path)
    if args.wizard:
        settings = wizard(settings)
        save_settings(settings, args.path)
        print(f'\nsettings.json salvo em: {args.path}')
    elif args.init:
        save_settings(settings, args.path)
        print(f'settings.json salvo em: {args.path}')
    if args.print or not (args.wizard or args.init):
        print(json.dumps(settings, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
