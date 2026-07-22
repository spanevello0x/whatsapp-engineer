#!/usr/bin/env python3
"""Dependency-free MCP stdio server for whatsapp-mcp-local-kit profile history.

Implements a small MCP subset: initialize, tools/list and tools/call.
Data stays in whatsapp-mcp-local-kit profile folders; this server only reads
profiles.json and messages.db.
"""
from __future__ import annotations

import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

DEFAULT_PROFILES_DIR = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents" / "WhatsApp MCP Profiles"
CONFIG_PATH = Path(os.environ.get("WHATSAPP_MCP_PROFILES_CONFIG", str(DEFAULT_PROFILES_DIR / "profiles.json")))
LINK_RE = re.compile(r"https?://[^\s<>()\"']+")


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"version": 1, "profiles_dir": str(CONFIG_PATH.parent), "profiles": []}
    raw = CONFIG_PATH.read_text(encoding="utf-8-sig")
    config = json.loads(raw) if raw.strip() else {}
    redirected = Path(str(config.get("profiles_config", ""))) if config.get("profiles_config") else None
    if redirected and redirected != CONFIG_PATH and redirected.exists():
        raw = redirected.read_text(encoding="utf-8-sig")
        if raw.strip():
            config = json.loads(raw)
    config.setdefault("version", 1)
    config.setdefault("profiles_dir", str(CONFIG_PATH.parent))
    config.setdefault("profiles", [])
    return config


def profile_by_slug(slug: str) -> dict[str, Any]:
    for profile in load_config().get("profiles", []):
        if profile.get("slug") == slug:
            return profile
    raise ValueError(f"Profile not found: {slug}")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "geral"


def profile_paths(profile: dict[str, Any]) -> dict[str, str]:
    config = load_config()
    base_dir = Path(config.get("profiles_dir") or CONFIG_PATH.parent)
    if profile.get("profile_dir"):
        profile_dir = Path(str(profile["profile_dir"]))
    else:
        project_folder = profile.get("project_folder")
        if not project_folder:
            project_slug = profile.get("project_slug")
            for project in config.get("projects", []):
                if project.get("slug") == project_slug:
                    project_folder = project.get("folder_name") or project.get("project_folder") or project.get("slug")
                    break
        if not project_folder:
            project_folder = profile.get("project_slug") or _slug(str(profile.get("project") or "Geral"))
        profile_dir = base_dir / "projetos" / str(project_folder) / profile["slug"]
    bridge_dir = profile_dir / "whatsapp-bridge"
    store_dir = bridge_dir / "store"
    return {
        "profile_dir": str(profile_dir),
        "bridge_dir": str(bridge_dir),
        "store_dir": str(store_dir),
        "messages_db": str(store_dir / "messages.db"),
        "session_db": str(store_dir / "whatsapp.db"),
        "pid_path": str(profile_dir / ".bridge.pid"),
        "log_path": str(profile_dir / "bridge.out.log"),
    }


def port_open(port: int) -> bool:
    if not port:
        return False
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.5):
            return True
    except OSError:
        return False


def pid_alive(pid_path: str) -> bool:
    path = Path(pid_path)
    if not path.exists():
        return False
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
        if os.name == "nt":
            result = subprocess.run(["tasklist", "/fi", f"PID eq {pid}", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=3)
            return str(pid) in result.stdout
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def db_stats(messages_db: str) -> dict[str, Any]:
    path = Path(messages_db)
    if not path.exists():
        return {"exists": False, "messages": 0, "chats": 0, "first": None, "last": None}
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1) as conn:
            cur = conn.cursor()
            first, last = cur.execute("select min(timestamp), max(timestamp) from messages").fetchone()
            return {"exists": True, "messages": cur.execute("select count(*) from messages").fetchone()[0], "chats": cur.execute("select count(*) from chats").fetchone()[0], "first": first, "last": last}
    except sqlite3.Error as exc:
        return {"exists": True, "messages": 0, "chats": 0, "first": None, "last": None, "error": str(exc)}


def profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    paths = profile_paths(profile)
    return {
        "slug": profile.get("slug"), "name": profile.get("name"), "description": profile.get("description"),
        "number": profile.get("number"), "port": profile.get("port"), "enabled": profile.get("enabled", True),
        "port_open": port_open(int(profile.get("port", 0) or 0)), "pid_alive": pid_alive(paths["pid_path"]),
        "paths": paths, "db": db_stats(paths["messages_db"]),
    }


def add_filters(where: list[str], params: list[Any], query: Optional[str], phone_number: Optional[str], chat_jid: Optional[str], after: Optional[str], before: Optional[str]) -> None:
    if query:
        pattern = f"%{query}%"
        where.append("""(lower(c.name) like lower(?) or lower(m.content) like lower(?) or lower(coalesce(m.filename, '')) like lower(?) or lower(m.sender) like lower(?) or lower(m.chat_jid) like lower(?))""")
        params.extend([pattern] * 5)
    if phone_number:
        pattern = f"%{phone_number}%"
        where.append("(m.sender like ? or m.chat_jid like ?)")
        params.extend([pattern, pattern])
    if chat_jid:
        where.append("m.chat_jid = ?")
        params.append(chat_jid)
    if after:
        where.append("m.timestamp > ?")
        params.append(after)
    if before:
        where.append("m.timestamp < ?")
        params.append(before)


def run_message_search(profile: dict[str, Any], query=None, phone_number=None, chat_jid=None, after=None, before=None, limit=50, page=0) -> dict[str, Any]:
    paths = profile_paths(profile)
    db = Path(paths["messages_db"])
    if not db.exists():
        return {"profile": profile_summary(profile), "items": [], "error": "messages.db not found"}
    limit = max(1, min(int(limit), 200)); page = max(0, int(page))
    where: list[str] = []; params: list[Any] = []
    add_filters(where, params, query, phone_number, chat_jid, after, before)
    where_sql = ("where " + " and ".join(where)) if where else ""
    params.extend([limit, page * limit])
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1) as conn:
            rows = conn.cursor().execute(f"""
                select m.timestamp, m.sender, c.name, m.chat_jid, m.id, m.content,
                       m.is_from_me, m.media_type, m.filename, m.file_length
                from messages m join chats c on m.chat_jid = c.jid
                {where_sql} order by m.timestamp desc limit ? offset ?
            """, tuple(params)).fetchall()
    except sqlite3.Error as exc:
        return {"profile": profile_summary(profile), "items": [], "error": str(exc)}
    return {"profile": profile_summary(profile), "items": [{"timestamp": r[0], "sender": r[1], "chat_name": r[2], "chat_jid": r[3], "message_id": r[4], "content": r[5], "is_from_me": bool(r[6]), "media_type": r[7], "filename": r[8], "file_length": r[9]} for r in rows]}


def run_asset_search(profile: dict[str, Any], query=None, phone_number=None, chat_jid=None, after=None, before=None, limit_per_category=50) -> dict[str, Any]:
    # Keep this compact: reuse message search and extract link/media rows with same DB semantics.
    paths = profile_paths(profile); db = Path(paths["messages_db"])
    categories: dict[str, list[dict[str, Any]]] = {k: [] for k in ["fotos", "videos", "audios", "pdfs", "documentos", "links", "outros"]}
    counts = {k: 0 for k in categories}
    if not db.exists():
        return {"profile": profile_summary(profile), "counts": counts, "items": categories, "error": "messages.db not found"}
    limit_per_category = max(1, min(int(limit_per_category), 200))
    where: list[str] = []; params: list[Any] = []
    add_filters(where, params, query, phone_number, chat_jid, after, before)
    base_where = ("where " + " and ".join(where)) if where else ""
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1) as conn:
            cur = conn.cursor()
            media_where = (base_where + " and coalesce(m.media_type, '') <> ''") if base_where else "where coalesce(m.media_type, '') <> ''"
            media_rows = cur.execute(f"select m.timestamp,m.sender,c.name,m.chat_jid,m.id,m.media_type,m.filename,m.content,m.file_length from messages m join chats c on m.chat_jid=c.jid {media_where} order by m.timestamp desc", tuple(params)).fetchall()
            link_where = (base_where + " and m.content like '%http%'") if base_where else "where m.content like '%http%'"
            link_rows = cur.execute(f"select m.timestamp,m.sender,c.name,m.chat_jid,m.id,m.content from messages m join chats c on m.chat_jid=c.jid {link_where} order by m.timestamp desc", tuple(params)).fetchall()
    except sqlite3.Error as exc:
        return {"profile": profile_summary(profile), "counts": counts, "items": categories, "error": str(exc)}
    for r in media_rows:
        mt, fn = (r[5] or "").lower(), (r[6] or "").lower(); ext = fn.rsplit(".", 1)[-1] if "." in fn else ""
        cat = "fotos" if mt == "image" else "videos" if mt == "video" else "audios" if mt == "audio" else "pdfs" if mt == "document" and ext == "pdf" else "documentos" if mt == "document" else "outros"
        counts[cat] += 1
        if len(categories[cat]) < limit_per_category:
            categories[cat].append({"timestamp": r[0], "sender": r[1], "chat_name": r[2], "chat_jid": r[3], "message_id": r[4], "media_type": r[5], "filename": r[6], "caption": r[7], "file_length": r[8]})
    for r in link_rows:
        for link in LINK_RE.findall(r[5] or ""):
            counts["links"] += 1
            if len(categories["links"]) < limit_per_category:
                categories["links"].append({"timestamp": r[0], "sender": r[1], "chat_name": r[2], "chat_jid": r[3], "message_id": r[4], "url": link.rstrip(".,);]"), "message_excerpt": (r[5] or "")[:500]})
    return {"profile": profile_summary(profile), "counts": counts, "items": categories}


def tool_list_profiles(**_: Any) -> Any:
    return [profile_summary(p) for p in load_config().get("profiles", [])]

def tool_search_profile_messages(profile_slug: str, **kw: Any) -> Any:
    return run_message_search(profile_by_slug(profile_slug), **kw)

def tool_search_all_profile_messages(**kw: Any) -> Any:
    return [run_message_search(p, **kw) for p in load_config().get("profiles", []) if p.get("enabled", True)]

def tool_list_profile_assets(profile_slug: str, **kw: Any) -> Any:
    return run_asset_search(profile_by_slug(profile_slug), **kw)

def tool_list_all_profile_assets(**kw: Any) -> Any:
    return [run_asset_search(p, **kw) for p in load_config().get("profiles", []) if p.get("enabled", True)]

def tool_download_profile_media(profile_slug: str, message_id: str, chat_jid: str) -> Any:
    return {"success": False, "message": "download requires the whatsapp-mcp-local-kit bridge HTTP endpoint; this embedded dependency-free MCP exposes SQLite history search only", "profile": profile_summary(profile_by_slug(profile_slug)), "message_id": message_id, "chat_jid": chat_jid}

TOOLS = {
    "list_profiles": (tool_list_profiles, "List configured WhatsApp profiles with local paths and database status.", {}),
    "search_profile_messages": (tool_search_profile_messages, "Search messages inside one WhatsApp profile database.", {"profile_slug": {"type": "string"}}),
    "search_all_profile_messages": (tool_search_all_profile_messages, "Search messages across all enabled WhatsApp profile databases.", {}),
    "list_profile_assets": (tool_list_profile_assets, "List media files and links grouped by type inside one WhatsApp profile.", {"profile_slug": {"type": "string"}}),
    "list_all_profile_assets": (tool_list_all_profile_assets, "List media files and links grouped by type across all enabled WhatsApp profiles.", {}),
    "download_profile_media": (tool_download_profile_media, "Stub for compatibility; media download requires bridge HTTP endpoint.", {"profile_slug": {"type": "string"}, "message_id": {"type": "string"}, "chat_jid": {"type": "string"}}),
}
COMMON_PROPS = {"query": {"type": "string"}, "phone_number": {"type": "string"}, "chat_jid": {"type": "string"}, "after": {"type": "string"}, "before": {"type": "string"}, "limit": {"type": "integer"}, "page": {"type": "integer"}, "limit_per_category": {"type": "integer"}}


def respond(msg_id: Any, result: Any = None, error: Any = None) -> None:
    out = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None: out["error"] = error
    else: out["result"] = result
    print(json.dumps(out, ensure_ascii=False), flush=True)


def tool_schema(name: str, desc: str, props: dict[str, Any]) -> dict[str, Any]:
    merged = dict(COMMON_PROPS); merged.update(props)
    return {"name": name, "description": desc, "inputSchema": {"type": "object", "properties": merged, "required": list(props.keys())}}


def handle(req: dict[str, Any]) -> None:
    msg_id = req.get("id"); method = req.get("method")
    if msg_id is None: return
    try:
        if method == "initialize":
            respond(msg_id, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "whatsapp-profiles", "version": "1.0.0-embedded"}})
        elif method == "tools/list":
            respond(msg_id, {"tools": [tool_schema(n, d, p) for n, (_, d, p) in TOOLS.items()]})
        elif method == "tools/call":
            params = req.get("params") or {}; name = params.get("name"); args = params.get("arguments") or {}
            if name not in TOOLS: raise ValueError(f"Unknown tool: {name}")
            fn = TOOLS[name][0]
            result = fn(**args)
            respond(msg_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}], "isError": False})
        else:
            respond(msg_id, error={"code": -32601, "message": f"Method not found: {method}"})
    except Exception as exc:
        respond(msg_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try: handle(json.loads(line))
        except Exception as exc:
            print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}), flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
