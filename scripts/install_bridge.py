#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, platform, stat, subprocess, sys, tarfile, urllib.request
from pathlib import Path

DEFAULT_PROFILES = Path.home() / 'Documents' / 'WhatsApp MCP Profiles'
DEFAULT_REPO = 'spanevello0x/whatsapp-engineer'
STATE_DIR = Path.home() / '.openclaw' / 'state' / 'whatsapp-engineer'
DEFAULT_KIT = Path.home() / '.openclaw' / 'workspace' / 'repos' / 'whatsapp-mcp-local-kit'
GO_VERSION = '1.23.4'
ZIG_VERSION = '0.13.0'

def asset_name() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system != 'linux':
        raise SystemExit(f'[blocked] unsupported OS for prebuilt bridge: {system}. Expected linux in OpenClaw/MQC.')
    if machine in ('x86_64','amd64'):
        return 'whatsapp-bridge-linux-amd64'
    raise SystemExit(f'[blocked] unsupported architecture for prebuilt bridge: {machine}.')

def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={'User-Agent':'whatsapp-engineer-skill'})
    with urllib.request.urlopen(req, timeout=120) as r, dest.open('wb') as f:
        while True:
            chunk = r.read(1024*1024)
            if not chunk: break
            f.write(chunk)

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()



def ensure_go(toolchain: Path) -> Path:
    go_bin = toolchain / 'go' / 'bin' / 'go'
    if go_bin.exists():
        return go_bin
    arch = 'amd64' if platform.machine().lower() in ('x86_64','amd64') else None
    if not arch:
        raise SystemExit('[blocked] unsupported arch for Go bootstrap')
    url = f'https://go.dev/dl/go{GO_VERSION}.linux-{arch}.tar.gz'
    archive = toolchain / f'go{GO_VERSION}.linux-{arch}.tar.gz'
    toolchain.mkdir(parents=True, exist_ok=True)
    download(url, archive)
    with tarfile.open(archive, 'r:gz') as tf:
        tf.extractall(toolchain)
    return go_bin

def ensure_zig(toolchain: Path) -> Path:
    zig_bin = toolchain / f'zig-linux-x86_64-{ZIG_VERSION}' / 'zig'
    if zig_bin.exists():
        return zig_bin
    if platform.machine().lower() not in ('x86_64','amd64'):
        raise SystemExit('[blocked] unsupported arch for Zig bootstrap')
    url = f'https://ziglang.org/download/{ZIG_VERSION}/zig-linux-x86_64-{ZIG_VERSION}.tar.xz'
    archive = toolchain / f'zig-linux-x86_64-{ZIG_VERSION}.tar.xz'
    toolchain.mkdir(parents=True, exist_ok=True)
    download(url, archive)
    with tarfile.open(archive, 'r:xz') as tf:
        tf.extractall(toolchain)
    return zig_bin

def build_from_source(kit_dir: Path, out: Path, toolchain: Path) -> dict:
    bridge_src = kit_dir / 'vendor' / 'lharries-whatsapp-mcp' / 'whatsapp-bridge'
    if not bridge_src.exists():
        raise SystemExit(f'[blocked] bridge source not found: {bridge_src}')
    go = ensure_go(toolchain)
    zig = ensure_zig(toolchain)
    out.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({
        'CGO_ENABLED': '1',
        'GOOS': 'linux',
        'GOARCH': 'amd64',
        'CC': f'{zig} cc -target x86_64-linux-gnu',
        'PATH': f"{go.parent}:{env.get('PATH','')}",
    })
    subprocess.run([str(go), 'mod', 'download'], cwd=str(bridge_src), env=env, check=True)
    subprocess.run([str(go), 'build', '-ldflags=-s -w', '-o', str(out), '.'], cwd=str(bridge_src), env=env, check=True)
    out.chmod(out.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return {'go': str(go), 'zig': str(zig), 'source': str(bridge_src)}

def main() -> int:
    ap=argparse.ArgumentParser(description='Install prebuilt whatsapp-bridge binary for whatsapp-engineer history sync')
    ap.add_argument('--profiles-dir', default=str(DEFAULT_PROFILES))
    ap.add_argument('--repo', default=os.environ.get('WHATSAPP_ENGINEER_BRIDGE_REPO', DEFAULT_REPO))
    ap.add_argument('--version', default=os.environ.get('WHATSAPP_ENGINEER_BRIDGE_VERSION', 'latest'), help='Release tag like v1.6.0, or latest')
    ap.add_argument('--url', default=os.environ.get('WHATSAPP_ENGINEER_BRIDGE_URL'), help='Override direct binary URL')
    ap.add_argument('--sha256', default=os.environ.get('WHATSAPP_ENGINEER_BRIDGE_SHA256'), help='Expected sha256 hex')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--build-from-source', action='store_true', help='Bootstrap Go+Zig in state dir and compile bridge without system Go/GCC')
    ap.add_argument('--kit-dir', default=str(DEFAULT_KIT))
    ap.add_argument('--toolchain-dir', default=str(STATE_DIR / 'toolchain'))
    args=ap.parse_args()
    profiles_dir=Path(args.profiles_dir).expanduser().resolve()
    out=profiles_dir/'bin'/'whatsapp-bridge'
    name=asset_name()
    if out.exists() and not args.force:
        print(json.dumps({'ok': True, 'installed': False, 'reason':'already_exists', 'bridge_binary': str(out), 'sha256': sha256(out)}, ensure_ascii=False, indent=2))
        return 0
    build_info = None
    url = None
    if args.build_from_source:
        build_info = build_from_source(Path(args.kit_dir).expanduser().resolve(), out, Path(args.toolchain_dir).expanduser().resolve())
        got = sha256(out)
    else:
        if args.url:
            url=args.url
            checksum_url=None
        else:
            base = f'https://github.com/{args.repo}/releases'
            rel = 'latest/download' if args.version == 'latest' else f'download/{args.version}'
            url=f'{base}/{rel}/{name}'
            checksum_url=f'{url}.sha256'
        tmp=out.with_suffix('.download')
        download(url, tmp)
        got=sha256(tmp)
        expected=args.sha256
        if not expected and checksum_url:
            try:
                sum_path=tmp.with_suffix('.sha256')
                download(checksum_url, sum_path)
                expected=sum_path.read_text(encoding='utf-8').split()[0].strip()
            except Exception:
                expected=None
        if expected and got.lower()!=expected.lower():
            tmp.unlink(missing_ok=True)
            print(json.dumps({'ok':False,'error':'sha256_mismatch','expected':expected,'got':got,'url':url}, ensure_ascii=False, indent=2))
            return 3
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp.replace(out)
        out.chmod(out.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(json.dumps({'ok': True, 'installed': True, 'bridge_binary': str(out), 'asset': name, 'url': url, 'build_info': build_info, 'sha256': got}, ensure_ascii=False, indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
