#!/usr/bin/env python3
"""Official WhatsApp Engineer skill command wrapper.

Use this entrypoint instead of calling internal scripts directly.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / "scripts"
DEFAULT_PROFILES = Path.home() / "Documents" / "WhatsApp MCP Profiles" / "profiles.json"


def run_script(script: str, args: list[str]) -> int:
    path = SCRIPTS / script
    if not path.exists():
        print(f"[blocked] script not found: {path}", file=sys.stderr)
        return 2
    cmd = [sys.executable, str(path), *args]
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="whatsapp-engineer",
        description="Comando oficial da skill WhatsApp Engineer.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("first-run", help="Wizard inicial guiado da skill")

    p = sub.add_parser("settings", help="Mostra ou inicializa settings.json da skill")
    p.add_argument("--init", action="store_true")
    p.add_argument("--print", action="store_true", default=True)

    p = sub.add_parser("settings-wizard", help="Wizard de configurações da entrega e sincronia")

    p = sub.add_parser("stop-engines", help="Para engines WhatsApp da skill para evitar conflito")
    p.add_argument("--legacy-go", action="store_true")
    p.add_argument("--baileys", action="store_true")
    p.add_argument("--all", action="store_true")

    p = sub.add_parser("connect", help="Fluxo oficial: um QR/sessao para historico + mensagens novas via DB")
    p.add_argument("--profiles-dir", default=str(DEFAULT_PROFILES.parent))
    p.add_argument("--project", default="Equipe")
    p.add_argument("--name", default="Principal")
    p.add_argument("--slug")
    p.add_argument("--number", default="")
    p.add_argument("--port", type=int, default=8101)
    p.add_argument("--kit-dir", default=str(Path.home() / ".openclaw" / "workspace" / "repos" / "whatsapp-mcp-local-kit"))
    p.add_argument("--skip-build", action="store_true")
    p.add_argument("--wait-qr-seconds", type=int, default=20)

    p = sub.add_parser("status", help="Mostra perfis historicos e status da base SQLite")
    p.add_argument("--profiles-config", default=str(DEFAULT_PROFILES))
    p.add_argument("--pretty", action="store_true", default=True)

    p = sub.add_parser("status-v2", help="Status da engine Baileys da skill")
    p.add_argument("--pretty", action="store_true", default=True)

    p = sub.add_parser("admin-status", help="Status da API admin local da engine Baileys")

    p = sub.add_parser("admin-snapshot", help="Lista membros e pedidos pendentes de um grupo via worker Baileys")
    p.add_argument("--group-jid", required=True)
    p.add_argument("--no-members", action="store_true")
    p.add_argument("--no-pending", action="store_true")
    p.add_argument("--out")

    p = sub.add_parser("admin-request-update", help="Aprova/rejeita pedido pendente; dry-run por padrão")
    p.add_argument("--group-jid", required=True)
    p.add_argument("--participant", action="append", required=True)
    p.add_argument("--action", choices=["approve", "reject"], required=True)
    p.add_argument("--execute", action="store_true")

    p = sub.add_parser("admin-remove-member", help="Remove membro; dry-run por padrão")
    p.add_argument("--group-jid", required=True)
    p.add_argument("--participant", action="append", required=True)
    p.add_argument("--execute", action="store_true")

    p = sub.add_parser("history-search", help="Busca mensagens antigas nos messages.db dos perfis")
    p.add_argument("--profiles-config", default=str(DEFAULT_PROFILES))
    p.add_argument("--profile")
    p.add_argument("--year", type=int)
    p.add_argument("--after")
    p.add_argument("--before")
    p.add_argument("--query")
    p.add_argument("--phone-number")
    p.add_argument("--chat-jid")
    p.add_argument("--chat-name")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--page", type=int, default=0)
    p.add_argument("--pretty", action="store_true", default=True)

    p = sub.add_parser("download-media", help="Tenta baixar/rebaixar mídia Baileys por message id")
    p.add_argument("--message-id", required=True)

    p = sub.add_parser("deliver-latest-audio", help="Transcreve e prepara entrega polida do último áudio")
    p.add_argument("--model", default="Xenova/whisper-small")
    p.add_argument("--language", default="portuguese")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--mode", choices=["transcribe", "translate", "summary"], default="transcribe")

    p = sub.add_parser("transcribe-latest-audio", help="Transcreve o audio Baileys baixado mais recente")
    p.add_argument("audio", nargs="?")
    p.add_argument("--message-id")
    p.add_argument("--model", default="Xenova/whisper-tiny")
    p.add_argument("--language", default="portuguese")
    p.add_argument("--format", choices=["json", "text"], default="json")

    p = sub.add_parser("history-search-v2", help="Busca no SQLite da engine Baileys da skill")
    p.add_argument("--year", type=int)
    p.add_argument("--after")
    p.add_argument("--before")
    p.add_argument("--query")
    p.add_argument("--phone-number")
    p.add_argument("--chat-jid")
    p.add_argument("--chat-name")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--page", type=int, default=0)
    p.add_argument("--pretty", action="store_true", default=True)

    p = sub.add_parser("setup-mcp", help="Registra o MCP whatsapp-profiles embutido da skill")
    p.add_argument("--profiles-config", default=str(DEFAULT_PROFILES))
    p.add_argument("--register", action="store_true", default=True)
    p.add_argument("--install", action="store_true", default=True)

    p = sub.add_parser("bridge-install", help="Instala binario pre-compilado whatsapp-bridge para OpenClaw/MQC")
    p.add_argument("--profiles-dir", default=str(DEFAULT_PROFILES.parent))
    p.add_argument("--version", default="latest")
    p.add_argument("--url")
    p.add_argument("--sha256")
    p.add_argument("--force", action="store_true")
    p.add_argument("--build-from-source", action="store_true")
    p.add_argument("--kit-dir", default=str(Path.home() / ".openclaw" / "workspace" / "repos" / "whatsapp-mcp-local-kit"))

    p = sub.add_parser("sync-setup", help="Cria perfil/base local para sincronia historica")
    p.add_argument("--profiles-dir", default=str(DEFAULT_PROFILES.parent))
    p.add_argument("--project", default="Equipe")
    p.add_argument("--name", default="Principal")
    p.add_argument("--slug")
    p.add_argument("--number", default="")
    p.add_argument("--port", type=int, default=8101)
    p.add_argument("--start", action="store_true")

    p = sub.add_parser("test-delivery", help="Testa payload/entrega no destino configurado")
    p.add_argument("--send", action="store_true")

    p = sub.add_parser("pair-qr", help="Pareia WhatsApp por QR mantendo a sessao viva")
    p.add_argument("--force", action="store_true")
    p.add_argument("--build-from-source", action="store_true")
    p.add_argument("--kit-dir", default=str(Path.home() / ".openclaw" / "workspace" / "repos" / "whatsapp-mcp-local-kit"))
    p.add_argument("--scan-timeout-ms", default="240000")
    p.add_argument("--account", default="default")

    args = parser.parse_args()

    if args.command == "first-run":
        return run_script("first_run.py", [])

    if args.command == "settings":
        out = []
        if args.init:
            out.append("--init")
        if args.print:
            out.append("--print")
        return run_script("settings.py", out)

    if args.command == "settings-wizard":
        return run_script("settings.py", ["--wizard", "--print"])

    if args.command == "stop-engines":
        out = []
        if args.legacy_go:
            out.append("--legacy-go")
        if args.baileys:
            out.append("--baileys")
        if args.all:
            out.append("--all")
        return run_script("stop_engines.py", out)

    if args.command == "connect":
        out = ["--profiles-dir", args.profiles_dir, "--project", args.project, "--name", args.name, "--number", args.number, "--port", str(args.port), "--kit-dir", args.kit_dir, "--wait-qr-seconds", str(args.wait_qr_seconds)]
        if args.slug:
            out.extend(["--slug", args.slug])
        if args.skip_build:
            out.append("--skip-build")
        return run_script("connect_baileys.py", ["--install", "--wait-seconds", str(args.wait_qr_seconds)])

    if args.command == "status":
        out = ["--profiles-config", args.profiles_config, "--list-profiles"]
        if args.pretty:
            out.append("--pretty")
        return run_script("search_history.py", out)

    if args.command == "status-v2":
        return run_script("search_baileys.py", ["--status", "--pretty"])

    if args.command == "admin-status":
        return run_script("whatsapp_admin.py", ["status"])

    if args.command == "admin-snapshot":
        out = ["snapshot", "--group-jid", args.group_jid]
        if args.no_members:
            out.append("--no-members")
        if args.no_pending:
            out.append("--no-pending")
        if args.out:
            out.extend(["--out", args.out])
        return run_script("whatsapp_admin.py", out)

    if args.command == "admin-request-update":
        out = ["request-update", "--group-jid", args.group_jid, "--action", args.action]
        for participant in args.participant:
            out.extend(["--participant", participant])
        if args.execute:
            out.append("--execute")
        return run_script("whatsapp_admin.py", out)

    if args.command == "admin-remove-member":
        out = ["remove-member", "--group-jid", args.group_jid]
        for participant in args.participant:
            out.extend(["--participant", participant])
        if args.execute:
            out.append("--execute")
        return run_script("whatsapp_admin.py", out)

    if args.command == "download-media":
        return run_script("download_baileys_media.py", ["--message-id", args.message_id])

    if args.command == "deliver-latest-audio":
        out = ["--model", args.model, "--language", args.language]
        if args.dry_run:
            out.append("--dry-run")
        if args.debug:
            out.append("--debug")
        out.extend(["--mode", args.mode])
        return run_script("deliver_audio_transcription.py", out)

    if args.command == "transcribe-latest-audio":
        out = []
        if args.audio:
            out.append(args.audio)
        if args.message_id:
            out.extend(["--message-id", args.message_id])
        out.extend(["--model", args.model, "--language", args.language, "--format", args.format])
        return run_script("transcribe_baileys_audio.py", out)

    if args.command == "history-search-v2":
        out = ["--limit", str(args.limit), "--page", str(args.page)]
        for key in ["year", "after", "before", "query", "phone_number", "chat_jid", "chat_name"]:
            value = getattr(args, key)
            if value is not None:
                out.extend(["--" + key.replace("_", "-"), str(value)])
        if args.pretty:
            out.append("--pretty")
        return run_script("search_baileys.py", out)

    if args.command == "history-search":
        out = ["--profiles-config", args.profiles_config, "--limit", str(args.limit), "--page", str(args.page)]
        for key in ["profile", "year", "after", "before", "query", "phone_number", "chat_jid", "chat_name"]:
            value = getattr(args, key)
            if value is not None:
                out.extend(["--" + key.replace("_", "-"), str(value)])
        if args.pretty:
            out.append("--pretty")
        return run_script("search_history.py", out)

    if args.command == "setup-mcp":
        out = ["--profiles-config", args.profiles_config]
        if args.install:
            out.append("--install")
        if args.register:
            out.append("--register")
        return run_script("setup_embedded_mcp.py", out)

    if args.command == "bridge-install":
        out = ["--profiles-dir", args.profiles_dir, "--version", args.version]
        if args.url:
            out.extend(["--url", args.url])
        if args.sha256:
            out.extend(["--sha256", args.sha256])
        if args.force:
            out.append("--force")
        if args.build_from_source:
            out.append("--build-from-source")
        if args.kit_dir:
            out.extend(["--kit-dir", args.kit_dir])
        return run_script("install_bridge.py", out)

    if args.command == "sync-setup":
        out = ["--profiles-dir", args.profiles_dir, "--project", args.project, "--name", args.name, "--number", args.number, "--port", str(args.port)]
        if args.slug:
            out.extend(["--slug", args.slug])
        if args.start:
            out.append("--start")
        return run_script("sync_setup.py", out)

    if args.command == "test-delivery":
        return run_script("test_delivery.py", ["--send"] if args.send else [])

    if args.command == "pair-qr":
        # Legacy alias kept for compatibility. The official flow is now `connect`,
        # which uses the skill-owned bridge/session instead of native gateway QR.
        return run_script("connect_unified.py", ["--kit-dir", args.kit_dir])

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
