#!/usr/bin/env python3
"""Unified WhatsApp Engineer connection flow: one QR for history + live DB sync."""
from __future__ import annotations
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / 'scripts'
STATE_DIR = Path.home() / '.openclaw' / 'state' / 'whatsapp-engineer'
DEFAULT_PROFILES_DIR = Path.home() / 'Documents' / 'WhatsApp MCP Profiles'
DEFAULT_KIT = Path.home() / '.openclaw' / 'workspace' / 'repos' / 'whatsapp-mcp-local-kit'

def run(script: str, args: list[str]) -> tuple[int, str, str]:
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args], text=True, capture_output=True)
    return p.returncode, p.stdout, p.stderr

def parse_json(stdout: str) -> dict:
    try:
        return json.loads(stdout)
    except Exception:
        return {'raw': stdout}

def profile_paths(profiles_dir: Path, project: str, slug: str) -> dict[str, Path]:
    profile_dir = profiles_dir / 'projetos' / project / slug
    return {
        'profile_dir': profile_dir,
        'bridge_dir': profile_dir / 'whatsapp-bridge',
        'store_dir': profile_dir / 'whatsapp-bridge' / 'store',
        'messages_db': profile_dir / 'whatsapp-bridge' / 'store' / 'messages.db',
        'session_db': profile_dir / 'whatsapp-bridge' / 'store' / 'whatsapp.db',
        'log_path': profile_dir / 'bridge.out.log',
        'err_path': profile_dir / 'bridge.err.log',
        'pid_path': profile_dir / '.bridge.pid',
    }

def slugify(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-') or 'principal'

def latest_qr(log_path: Path) -> str | None:
    if not log_path.exists():
        return None
    qr = None
    for line in log_path.read_text(encoding='utf-8', errors='ignore').splitlines():
        if 'QR_CODE_DATA:' in line:
            qr = line.split('QR_CODE_DATA:', 1)[1].strip()
    return qr

def db_stats(db: Path) -> dict:
    if not db.exists():
        return {'exists': False, 'messages': 0, 'chats': 0}
    import sqlite3
    try:
        with sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=2) as conn:
            cur = conn.cursor()
            first, last = cur.execute('select min(timestamp), max(timestamp) from messages').fetchone()
            return {'exists': True, 'messages': cur.execute('select count(*) from messages').fetchone()[0], 'chats': cur.execute('select count(*) from chats').fetchone()[0], 'first': first, 'last': last}
    except Exception as e:
        return {'exists': True, 'error': str(e), 'messages': 0, 'chats': 0}

def make_qr_png(qr_data: str, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    node = shutil.which('node')
    npm = shutil.which('npm')
    if not node or not npm:
        return {'ok': False, 'error': 'node/npm unavailable', 'qr_data': qr_data}
    node_dir = STATE_DIR / 'qr-node'
    node_dir.mkdir(parents=True, exist_ok=True)
    if not (node_dir / 'node_modules' / 'qrcode').exists():
        subprocess.run([npm, 'init', '-y'], cwd=node_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        subprocess.run([npm, 'install', 'qrcode'], cwd=node_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    js = """
const QRCode=require('qrcode');
QRCode.toFile(process.argv[2], process.argv[1], {type:'png', width:768, margin:2}, err=>{ if(err){console.error(err); process.exit(1)} });
"""
    subprocess.run([node, '-e', js, qr_data, str(out)], cwd=node_dir, check=True)
    return {'ok': True, 'path': str(out)}

def main() -> int:
    ap = argparse.ArgumentParser(description='Unified one-QR WhatsApp connection for whatsapp-engineer')
    ap.add_argument('--profiles-dir', default=str(DEFAULT_PROFILES_DIR))
    ap.add_argument('--project', default='Equipe')
    ap.add_argument('--name', default='Principal')
    ap.add_argument('--slug')
    ap.add_argument('--number', default='')
    ap.add_argument('--port', type=int, default=8101)
    ap.add_argument('--kit-dir', default=str(DEFAULT_KIT))
    ap.add_argument('--build-from-source', action='store_true', default=True)
    ap.add_argument('--skip-build', action='store_true')
    ap.add_argument('--wait-qr-seconds', type=int, default=20)
    args = ap.parse_args()

    profiles_dir = Path(args.profiles_dir).expanduser().resolve()
    slug = args.slug or slugify(args.name)
    paths = profile_paths(profiles_dir, args.project, slug)

    steps = {}
    if not args.skip_build:
        code, out, err = run('install_bridge.py', ['--profiles-dir', str(profiles_dir), '--kit-dir', args.kit_dir, '--build-from-source'])
        steps['bridge_install'] = {'code': code, 'stdout': parse_json(out), 'stderr': err[-1000:]}
        if code != 0:
            print(json.dumps({'ok': False, 'step': 'bridge_install', 'steps': steps}, ensure_ascii=False, indent=2)); return code

    code, out, err = run('sync_setup.py', ['--profiles-dir', str(profiles_dir), '--project', args.project, '--name', args.name, '--slug', slug, '--number', args.number, '--port', str(args.port), '--start'])
    steps['sync_setup_start'] = {'code': code, 'stdout': parse_json(out), 'stderr': err[-1000:]}
    if code != 0:
        print(json.dumps({'ok': False, 'step': 'sync_setup_start', 'steps': steps}, ensure_ascii=False, indent=2)); return code

    code, out, err = run('setup_embedded_mcp.py', ['--profiles-config', str(profiles_dir / 'profiles.json'), '--install', '--register'])
    steps['setup_mcp'] = {'code': code, 'stdout': parse_json(out), 'stderr': err[-1000:]}

    qr_data = None
    for _ in range(max(1, args.wait_qr_seconds)):
        qr_data = latest_qr(paths['log_path'])
        if qr_data:
            break
        if paths['session_db'].exists():
            break
        time.sleep(1)

    qr_info = None
    if qr_data:
        qr_info = make_qr_png(qr_data, STATE_DIR / 'qr' / f'unified-{slug}.png')

    result = {
        'ok': True,
        'mode': 'unified-one-qr',
        'profile': {'project': args.project, 'name': args.name, 'slug': slug, 'number': args.number, 'port': args.port},
        'paths': {k: str(v) for k, v in paths.items()},
        'session_exists': paths['session_db'].exists(),
        'db': db_stats(paths['messages_db']),
        'qr': qr_info,
        'qr_pending': bool(qr_data and not paths['session_db'].exists()),
        'steps': steps,
        'note': 'Use only this unified QR/session for whatsapp-engineer. Do not pair the native OpenClaw WhatsApp gateway for this workflow.',
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
