#!/usr/bin/env python3
"""Search WhatsApp MCP Local Kit profile SQLite history.

Reads the `whatsapp-mcp-local-kit` profiles.json layout directly, so the skill can
query old messages even when the MCP runtime is not attached to this agent.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_PROFILES_DIR = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents" / "WhatsApp MCP Profiles"
DEFAULT_CONFIG = Path(os.environ.get("WHATSAPP_MCP_PROFILES_CONFIG", str(DEFAULT_PROFILES_DIR / "profiles.json")))


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def load_profiles_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "profiles_dir": str(path.parent), "profiles": [], "missing": str(path)}
    raw = path.read_text(encoding="utf-8-sig")
    cfg = json.loads(raw) if raw.strip() else {}
    redirected = Path(str(cfg.get("profiles_config", ""))) if cfg.get("profiles_config") else None
    if redirected and redirected != path and redirected.exists():
        raw = redirected.read_text(encoding="utf-8-sig")
        cfg = json.loads(raw) if raw.strip() else cfg
        path = redirected
    cfg.setdefault("version", 1)
    cfg.setdefault("profiles_dir", str(path.parent))
    cfg.setdefault("profiles", [])
    cfg["_config_path"] = str(path)
    return cfg


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "geral"


def profile_paths(cfg: dict[str, Any], profile: dict[str, Any]) -> dict[str, str]:
    base_dir = Path(cfg.get("profiles_dir") or Path(str(cfg.get("_config_path", DEFAULT_CONFIG))).parent)
    if profile.get("profile_dir"):
        profile_dir = Path(str(profile["profile_dir"]))
    else:
        project_folder = profile.get("project_folder")
        if not project_folder:
            project_slug = profile.get("project_slug")
            for project in cfg.get("projects", []):
                if project.get("slug") == project_slug:
                    project_folder = project.get("folder_name") or project.get("project_folder") or project.get("slug")
                    break
        if not project_folder:
            project_folder = profile.get("project_slug") or slugify(str(profile.get("project") or "Geral"))
        profile_dir = base_dir / "projetos" / str(project_folder) / str(profile["slug"])
    bridge_dir = profile_dir / "whatsapp-bridge"
    store_dir = bridge_dir / "store"
    return {
        "profile_dir": str(profile_dir),
        "bridge_dir": str(bridge_dir),
        "store_dir": str(store_dir),
        "messages_db": str(store_dir / "messages.db"),
        "session_db": str(store_dir / "whatsapp.db"),
        "log_path": str(profile_dir / "bridge.out.log"),
    }


def db_stats(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {"exists": False, "messages": 0, "chats": 0, "first": None, "last": None}
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2) as conn:
            cur = conn.cursor()
            first, last = cur.execute("select min(timestamp), max(timestamp) from messages").fetchone()
            return {
                "exists": True,
                "messages": cur.execute("select count(*) from messages").fetchone()[0],
                "chats": cur.execute("select count(*) from chats").fetchone()[0],
                "first": first,
                "last": last,
            }
    except sqlite3.Error as exc:
        return {"exists": True, "messages": 0, "chats": 0, "first": None, "last": None, "error": str(exc)}


def profile_summary(cfg: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    paths = profile_paths(cfg, profile)
    return {
        "slug": profile.get("slug"),
        "name": profile.get("name"),
        "project": profile.get("project"),
        "description": profile.get("description"),
        "number": profile.get("number"),
        "enabled": profile.get("enabled", True),
        "paths": paths,
        "db": db_stats(Path(paths["messages_db"])),
    }


def add_filters(where: list[str], params: list[Any], args: argparse.Namespace) -> None:
    if args.query:
        pattern = f"%{args.query}%"
        where.append("""(
            lower(coalesce(c.name, '')) like lower(?)
            or lower(coalesce(m.content, '')) like lower(?)
            or lower(coalesce(m.filename, '')) like lower(?)
            or lower(coalesce(m.sender, '')) like lower(?)
            or lower(coalesce(m.chat_jid, '')) like lower(?)
        )""")
        params.extend([pattern] * 5)
    if args.phone_number:
        pattern = f"%{args.phone_number}%"
        where.append("(coalesce(m.sender, '') like ? or coalesce(m.chat_jid, '') like ?)")
        params.extend([pattern, pattern])
    if args.chat_jid:
        where.append("m.chat_jid = ?")
        params.append(args.chat_jid)
    if args.chat_name:
        where.append("lower(coalesce(c.name, '')) like lower(?)")
        params.append(f"%{args.chat_name}%")
    if args.after:
        where.append("m.timestamp >= ?")
        params.append(args.after)
    if args.before:
        where.append("m.timestamp < ?")
        params.append(args.before)


def search_profile(cfg: dict[str, Any], profile: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    summary = profile_summary(cfg, profile)
    db = Path(summary["paths"]["messages_db"])
    if not db.exists():
        return {"profile": summary, "items": [], "error": "messages.db not found"}

    where: list[str] = []
    params: list[Any] = []
    add_filters(where, params, args)
    where_sql = "where " + " and ".join(where) if where else ""
    limit = max(1, min(int(args.limit), 1000))
    offset = max(0, int(args.page)) * limit
    params.extend([limit, offset])
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=3) as conn:
            cur = conn.cursor()
            rows = cur.execute(
                f"""
                select m.timestamp, m.sender, c.name, m.chat_jid, m.id, m.content,
                       m.is_from_me, m.media_type, m.filename, m.file_length
                from messages m
                left join chats c on m.chat_jid = c.jid
                {where_sql}
                order by m.timestamp desc
                limit ? offset ?
                """,
                tuple(params),
            ).fetchall()
    except sqlite3.Error as exc:
        return {"profile": summary, "items": [], "error": str(exc)}

    return {
        "profile": summary,
        "items": [
            {
                "timestamp": row[0],
                "sender": row[1],
                "chat_name": row[2],
                "chat_jid": row[3],
                "message_id": row[4],
                "content": row[5],
                "is_from_me": bool(row[6]),
                "media_type": row[7],
                "filename": row[8],
                "file_length": row[9],
            }
            for row in rows
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Search old WhatsApp history from whatsapp-mcp-local-kit messages.db files.")
    parser.add_argument("--profiles-config", default=str(DEFAULT_CONFIG), help="Path to whatsapp-mcp-local-kit profiles.json")
    parser.add_argument("--list-profiles", action="store_true", help="Only list profiles and DB stats")
    parser.add_argument("--profile", help="Profile slug to search. Defaults to all enabled profiles.")
    parser.add_argument("--year", type=int, help="Shortcut for --after YEAR-01-01 --before YEAR+1-01-01")
    parser.add_argument("--after", help="Inclusive timestamp lower bound, e.g. 2026-01-01")
    parser.add_argument("--before", help="Exclusive timestamp upper bound, e.g. 2027-01-01")
    parser.add_argument("--query", help="Text/file/chat/sender search")
    parser.add_argument("--phone-number", help="Filter sender/chat JID by number fragment")
    parser.add_argument("--chat-jid", help="Exact chat JID")
    parser.add_argument("--chat-name", help="Chat/group name contains")
    parser.add_argument("--limit", type=int, default=50, help="Limit per profile, max 1000")
    parser.add_argument("--page", type=int, default=0)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if args.year:
        args.after = args.after or f"{args.year:04d}-01-01"
        args.before = args.before or f"{args.year + 1:04d}-01-01"

    cfg = load_profiles_config(Path(args.profiles_config).expanduser())
    profiles = cfg.get("profiles", [])
    if args.profile:
        profiles = [p for p in profiles if p.get("slug") == args.profile]
    elif not args.list_profiles:
        profiles = [p for p in profiles if p.get("enabled", True)]

    if args.list_profiles:
        output: Any = {
            "config_path": cfg.get("_config_path") or str(Path(args.profiles_config).expanduser()),
            "profiles_dir": cfg.get("profiles_dir"),
            "profiles": [profile_summary(cfg, p) for p in profiles],
        }
    else:
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "config_path": cfg.get("_config_path") or str(Path(args.profiles_config).expanduser()),
            "filters": {k: getattr(args, k) for k in ["profile", "year", "after", "before", "query", "phone_number", "chat_jid", "chat_name", "limit", "page"]},
            "results": [search_profile(cfg, p, args) for p in profiles],
        }

    print(json.dumps(output, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
