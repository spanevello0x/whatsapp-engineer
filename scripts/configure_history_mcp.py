#!/usr/bin/env python3
"""Configure WhatsApp Engineer to use whatsapp-mcp-local-kit history profiles."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

STATE_CONFIG = Path.home() / ".openclaw" / "state" / "whatsapp-engineer" / "config.json"
DEFAULT_KIT = Path.home() / ".openclaw" / "workspace" / "repos" / "whatsapp-mcp-local-kit"
DEFAULT_PROFILES = Path.home() / "Documents" / "WhatsApp MCP Profiles" / "profiles.json"


def load_json(path: Path) -> dict:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return {"version": 1}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description="Wire whatsapp-mcp-local-kit history config into whatsapp-engineer.")
    parser.add_argument("--kit-dir", default=str(DEFAULT_KIT), help="Path to whatsapp-mcp-local-kit clone")
    parser.add_argument("--profiles-config", default=str(DEFAULT_PROFILES), help="Path to WhatsApp MCP Profiles/profiles.json")
    parser.add_argument("--config", default=str(STATE_CONFIG), help="whatsapp-engineer config.json")
    parser.add_argument("--register-openclaw-mcp", action="store_true", help="Run `openclaw mcp set whatsapp-profiles ...`")
    parser.add_argument("--uv", default=shutil.which("uv") or shutil.which("uvx") or "uv", help="uv/uvx executable for MCP stdio")
    args = parser.parse_args()

    kit_dir = Path(args.kit_dir).expanduser().resolve()
    mcp_dir = kit_dir / "profiles-mcp-server"
    mcp_main = mcp_dir / "main.py"
    profiles_config = Path(args.profiles_config).expanduser()
    cfg_path = Path(args.config).expanduser()

    checks = {
        "kit_dir_exists": kit_dir.exists(),
        "profiles_mcp_main_exists": mcp_main.exists(),
        "profiles_config_exists": profiles_config.exists(),
        "uv_found": bool(shutil.which(args.uv) or Path(args.uv).exists()),
    }

    cfg = load_json(cfg_path)
    cfg.setdefault("source", {})
    cfg["source"].setdefault("mcp", "whatsapp-profiles")
    cfg["source"]["history"] = {
        "kit_dir": str(kit_dir),
        "profiles_mcp_dir": str(mcp_dir),
        "profiles_config": str(profiles_config),
        "mcp_name": "whatsapp-profiles",
        "query_script": "~/.openclaw/workspace/skills/whatsapp-engineer/scripts/search_history.py",
    }
    save_json(cfg_path, cfg)

    mcp_payload = {
        "command": args.uv,
        "args": ["--directory", str(mcp_dir), "run", "main.py"],
        "env": {"WHATSAPP_MCP_PROFILES_CONFIG": str(profiles_config)},
    }

    registered = False
    if args.register_openclaw_mcp:
        if not checks["profiles_mcp_main_exists"]:
            print(json.dumps({"ok": False, "checks": checks, "error": "profiles-mcp-server/main.py not found"}, ensure_ascii=False, indent=2))
            return 2
        result = subprocess.run(["openclaw", "mcp", "set", "whatsapp-profiles", json.dumps(mcp_payload, ensure_ascii=False)], text=True, capture_output=True)
        registered = result.returncode == 0
        if result.returncode != 0:
            print(result.stdout, end="", file=sys.stderr)
            print(result.stderr, end="", file=sys.stderr)
            return result.returncode

    print(json.dumps({"ok": True, "config": str(cfg_path), "checks": checks, "mcp_payload": mcp_payload, "registered_openclaw_mcp": registered}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
