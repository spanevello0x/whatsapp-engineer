#!/usr/bin/env python3
"""Cliente local da API admin do worker Baileys da skill WhatsApp Engineer.

Seguro por padrão: comandos de escrita só fazem dry-run, salvo com --execute.
O worker ainda bloqueia execução real se não tiver sido iniciado com
WHATSAPP_ENGINEER_ADMIN_ALLOW_WRITES=1.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

STATE_DIR = Path(os.environ.get("WHATSAPP_ENGINEER_STATE_DIR", Path.home() / ".openclaw/state/whatsapp-engineer/baileys"))
STATUS_PATH = Path(os.environ.get("WHATSAPP_ENGINEER_STATUS_PATH", STATE_DIR / "status.json"))
TOKEN_PATH = Path(os.environ.get("WHATSAPP_ENGINEER_ADMIN_TOKEN_PATH", STATE_DIR / "admin-token"))


def load_status() -> dict[str, Any]:
    if not STATUS_PATH.exists():
        return {}
    return json.loads(STATUS_PATH.read_text(encoding="utf-8"))


def load_token(status: dict[str, Any]) -> str:
    token_path = Path(status.get("admin_api", {}).get("token_path") or TOKEN_PATH)
    if not token_path.exists():
        raise SystemExit(f"[blocked] admin token not found: {token_path}")
    return token_path.read_text(encoding="utf-8").strip()


def admin_base(status: dict[str, Any]) -> str:
    api = status.get("admin_api", {})
    host = api.get("host") or os.environ.get("WHATSAPP_ENGINEER_ADMIN_HOST", "127.0.0.1")
    port = int(api.get("port") or os.environ.get("WHATSAPP_ENGINEER_ADMIN_PORT", "18791"))
    return f"http://{host}:{port}"


def call(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    status = load_status()
    token = load_token(status)
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        admin_base(status) + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"[error] HTTP {exc.code}: {body}") from exc


def print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Cliente local da API admin WhatsApp Engineer")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Status da API admin")

    p = sub.add_parser("snapshot", help="Lista membros e pedidos pendentes de um grupo")
    p.add_argument("--group-jid", required=True)
    p.add_argument("--no-members", action="store_true")
    p.add_argument("--no-pending", action="store_true")
    p.add_argument("--out")

    p = sub.add_parser("request-update", help="Aprova/rejeita pedido pendente")
    p.add_argument("--group-jid", required=True)
    p.add_argument("--participant", action="append", required=True)
    p.add_argument("--action", choices=["approve", "reject"], required=True)
    p.add_argument("--execute", action="store_true")

    p = sub.add_parser("remove-member", help="Remove participante do grupo")
    p.add_argument("--group-jid", required=True)
    p.add_argument("--participant", action="append", required=True)
    p.add_argument("--execute", action="store_true")

    args = parser.parse_args()

    if args.command == "status":
        print_json(call("GET", "/admin/status"))
        return 0

    if args.command == "snapshot":
        result = call("POST", "/admin/group-snapshot", {
            "groupJid": args.group_jid,
            "includeMembers": not args.no_members,
            "includePending": not args.no_pending,
        })
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print_json(result)
        return 0

    if args.command == "request-update":
        print_json(call("POST", "/admin/group-request-update", {
            "groupJid": args.group_jid,
            "participants": args.participant,
            "action": args.action,
            "dryRun": not args.execute,
            "execute": args.execute,
        }))
        return 0

    if args.command == "remove-member":
        print_json(call("POST", "/admin/group-participants-update", {
            "groupJid": args.group_jid,
            "participants": args.participant,
            "action": "remove",
            "dryRun": not args.execute,
            "execute": args.execute,
        }))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
