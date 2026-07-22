#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, shutil, socket, subprocess, sys
from pathlib import Path

DEFAULT_PROFILES = Path.home() / 'Documents' / 'WhatsApp MCP Profiles'
DEFAULT_KIT = Path.home() / '.openclaw' / 'workspace' / 'repos' / 'whatsapp-mcp-local-kit'

def slugify(s:str)->str:
    return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-') or 'perfil'

def load(path:Path)->dict:
    if path.exists() and path.read_text(encoding='utf-8-sig').strip():
        return json.loads(path.read_text(encoding='utf-8-sig'))
    return {'version':1,'profiles_dir':str(path.parent),'projects':[],'profiles':[]}

def save(path:Path,cfg:dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    path.chmod(0o600)

def port_open(port:int)->bool:
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=.4): return True
    except OSError: return False

def main():
    ap=argparse.ArgumentParser(description='Prepare WhatsApp history sync profile for whatsapp-engineer skill')
    ap.add_argument('--profiles-dir', default=str(DEFAULT_PROFILES))
    ap.add_argument('--kit-dir', default=str(DEFAULT_KIT))
    ap.add_argument('--project', default='Equipe')
    ap.add_argument('--name', default='Principal')
    ap.add_argument('--slug')
    ap.add_argument('--number', default='')
    ap.add_argument('--port', type=int, default=8101)
    ap.add_argument('--start', action='store_true', help='Try to start bridge if binary exists')
    args=ap.parse_args()
    profiles_dir=Path(args.profiles_dir).expanduser().resolve()
    cfg_path=profiles_dir/'profiles.json'
    cfg=load(cfg_path)
    cfg['profiles_dir']=str(profiles_dir)
    cfg.setdefault('projects',[]); cfg.setdefault('profiles',[])
    project_slug=slugify(args.project); project_folder=args.project
    if not any(p.get('slug')==project_slug for p in cfg['projects']):
        cfg['projects'].append({'slug':project_slug,'name':args.project,'folder_name':project_folder})
    slug=args.slug or slugify(args.name)
    profile={
        'slug':slug,'project':args.project,'project_slug':project_slug,'project_folder':project_folder,
        'name':args.name,'description':'Perfil historico criado pela skill whatsapp-engineer',
        'number':args.number,'port':args.port,'enabled':True,
    }
    old=[p for p in cfg['profiles'] if p.get('slug')!=slug]
    old.append(profile); cfg['profiles']=old
    profile_dir=profiles_dir/'projetos'/project_folder/slug
    bridge_dir=profile_dir/'whatsapp-bridge'
    store_dir=bridge_dir/'store'
    store_dir.mkdir(parents=True, exist_ok=True)
    save(cfg_path,cfg)
    bin_path=profiles_dir/'bin'/'whatsapp-bridge'
    kit_bridge=Path(args.kit_dir).expanduser()/'vendor/lharries-whatsapp-mcp/whatsapp-bridge'
    checks={
        'profiles_config': str(cfg_path),
        'profile_dir': str(profile_dir),
        'messages_db': str(store_dir/'messages.db'),
        'session_db': str(store_dir/'whatsapp.db'),
        'bridge_binary': str(bin_path),
        'bridge_binary_exists': bin_path.exists(),
        'kit_bridge_source_exists': kit_bridge.exists(),
        'go': shutil.which('go'),
        'gcc': shutil.which('gcc') or shutil.which('cc'),
        'port_open': port_open(args.port),
    }
    started=False; start_error=None
    if args.start:
        if not bin_path.exists(): start_error='bridge binary not found; build/install bridge first'
        elif port_open(args.port): start_error=f'port {args.port} already open'
        else:
            out=profile_dir/'bridge.out.log'; err=profile_dir/'bridge.err.log'; pid=profile_dir/'.bridge.pid'
            env=dict(**__import__('os').environ, WHATSAPP_MCP_PORT=str(args.port))
            proc=subprocess.Popen([str(bin_path)], cwd=str(bridge_dir), env=env, stdout=out.open('ab'), stderr=err.open('ab'))
            pid.write_text(str(proc.pid), encoding='ascii')
            started=True; checks['pid']=proc.pid
    print(json.dumps({'ok':True,'profile':profile,'checks':checks,'started':started,'start_error':start_error,'next': 'Build/start bridge to sync history; QR scan will be required for this historical profile if session_db does not exist.'}, ensure_ascii=False, indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
