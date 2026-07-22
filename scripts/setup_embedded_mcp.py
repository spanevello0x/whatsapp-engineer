#!/usr/bin/env python3
"""Install/register the embedded whatsapp-profiles MCP shipped with this skill."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
MCP_DIR = SKILL_DIR / "embedded_mcp" / "whatsapp_profiles"
MCP_MAIN = MCP_DIR / "stdio_server.py"
STATE_DIR = Path.home() / ".openclaw" / "state" / "whatsapp-engineer"
DEFAULT_VENV = STATE_DIR / "mcp-venv"
DEFAULT_PROFILES = Path.home() / "Documents" / "WhatsApp MCP Profiles" / "profiles.json"
ENGINEER_CONFIG = STATE_DIR / "config.json"


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=check)


def venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def load_json(path: Path) -> dict:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return {"version": 1}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup embedded whatsapp-profiles MCP from inside whatsapp-engineer skill.")
    parser.add_argument("--profiles-config", default=str(DEFAULT_PROFILES), help="Path to WhatsApp MCP Profiles/profiles.json")
    parser.add_argument("--venv", default=str(DEFAULT_VENV), help="Where to create/use MCP Python venv")
    parser.add_argument("--mcp-name", default="whatsapp-profiles")
    parser.add_argument("--register", action="store_true", help="Register MCP with `openclaw mcp set`")
    parser.add_argument("--install", action="store_true", help="Deprecated no-op: embedded stdio MCP has no external Python dependencies")
    parser.add_argument("--skip-pip", action="store_true", help="Deprecated no-op")
    args = parser.parse_args()

    profiles_config = Path(args.profiles_config).expanduser().resolve()
    venv = Path(args.venv).expanduser().resolve()
    py = venv_python(venv)

    if not MCP_MAIN.exists():
        print(json.dumps({"ok": False, "error": f"embedded MCP main not found: {MCP_MAIN}"}, ensure_ascii=False, indent=2))
        return 2

    # Dependency-free server: no venv/pip required. Keep --install for backward-compatible CLI UX.
    installed = bool(args.install)
    command_python = Path(sys.executable)
    payload = {
        "command": str(command_python),
        "args": [str(MCP_MAIN)],
        "env": {"WHATSAPP_MCP_PROFILES_CONFIG": str(profiles_config)},
    }

    cfg = load_json(ENGINEER_CONFIG)
    cfg.setdefault("source", {})
    cfg["source"].setdefault("mcp", args.mcp_name)
    cfg["source"]["embedded_mcp"] = {
        "name": args.mcp_name,
        "main": str(MCP_MAIN),
        "venv": str(venv),
        "python": str(command_python),
        "profiles_config": str(profiles_config),
    }
    save_json(ENGINEER_CONFIG, cfg)

    registered = False
    if args.register:
        result = subprocess.run(["openclaw", "mcp", "set", args.mcp_name, json.dumps(payload, ensure_ascii=False)], text=True, capture_output=True)
        if result.returncode != 0:
            print(result.stdout, end="", file=sys.stderr)
            print(result.stderr, end="", file=sys.stderr)
            return result.returncode
        registered = True

    print(json.dumps({
        "ok": True,
        "installed": installed,
        "registered": registered,
        "mcp_name": args.mcp_name,
        "profiles_config_exists": profiles_config.exists(),
        "payload": payload,
        "engineer_config": str(ENGINEER_CONFIG),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
