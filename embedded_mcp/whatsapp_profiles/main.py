from __future__ import annotations

import json
import os
import re
import socket
import sqlite3
import subprocess
from pathlib import Path
from typing import Any, Optional

import requests
from mcp.server.fastmcp import FastMCP


DEFAULT_PROFILES_DIR = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents" / "WhatsApp MCP Profiles"
CONFIG_PATH = Path(os.environ.get("WHATSAPP_MCP_PROFILES_CONFIG", str(DEFAULT_PROFILES_DIR / "profiles.json")))
LINK_RE = re.compile(r"https?://[^\s<>()\"']+")

mcp = FastMCP("whatsapp-profiles")


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"version": 1, "profiles_dir": str(CONFIG_PATH.parent), "profiles": []}
    raw = CONFIG_PATH.read_text(encoding="utf-8-sig")
    if not raw.strip():
        return {"version": 1, "profiles_dir": str(CONFIG_PATH.parent), "profiles": []}
    config = json.loads(raw)
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
            project_folder = profile.get("project_slug") or re.sub(r"[^a-z0-9]+", "-", str(profile.get("project") or "Geral").lower()).strip("-") or "geral"
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
            result = subprocess.run(
                ["tasklist", "/fi", f"PID eq {pid}", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return str(pid) in result.stdout
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except ValueError:
        return False


def db_stats(messages_db: str) -> dict[str, Any]:
    path = Path(messages_db)
    if not path.exists():
        return {"exists": False, "messages": 0, "chats": 0, "first": None, "last": None}
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1) as conn:
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


def profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    paths = profile_paths(profile)
    return {
        "slug": profile.get("slug"),
        "name": profile.get("name"),
        "description": profile.get("description"),
        "number": profile.get("number"),
        "port": profile.get("port"),
        "enabled": profile.get("enabled", True),
        "port_open": port_open(int(profile.get("port", 0) or 0)),
        "pid_alive": pid_alive(paths["pid_path"]),
        "paths": paths,
        "db": db_stats(paths["messages_db"]),
    }


def add_filters(where: list[str], params: list[Any], query: Optional[str], phone_number: Optional[str], chat_jid: Optional[str], after: Optional[str], before: Optional[str]) -> None:
    if query:
        pattern = f"%{query}%"
        where.append("""(
            lower(c.name) like lower(?)
            or lower(m.content) like lower(?)
            or lower(coalesce(m.filename, '')) like lower(?)
            or lower(m.sender) like lower(?)
            or lower(m.chat_jid) like lower(?)
        )""")
        params.extend([pattern, pattern, pattern, pattern, pattern])
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


def run_message_search(profile: dict[str, Any], query: Optional[str], phone_number: Optional[str], chat_jid: Optional[str], after: Optional[str], before: Optional[str], limit: int, page: int) -> dict[str, Any]:
    paths = profile_paths(profile)
    db = Path(paths["messages_db"])
    if not db.exists():
        return {"profile": profile_summary(profile), "items": [], "error": "messages.db not found"}

    limit = max(1, min(int(limit), 200))
    page = max(0, int(page))
    where: list[str] = []
    params: list[Any] = []
    add_filters(where, params, query, phone_number, chat_jid, after, before)
    where_sql = ("where " + " and ".join(where)) if where else ""
    params.extend([limit, page * limit])

    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1) as conn:
            cur = conn.cursor()
            rows = cur.execute(
                f"""
                select m.timestamp, m.sender, c.name, m.chat_jid, m.id, m.content,
                       m.is_from_me, m.media_type, m.filename, m.file_length
                from messages m
                join chats c on m.chat_jid = c.jid
                {where_sql}
                order by m.timestamp desc
                limit ? offset ?
                """,
                tuple(params),
            ).fetchall()
    except sqlite3.Error as exc:
        return {"profile": profile_summary(profile), "items": [], "error": str(exc)}

    return {
        "profile": profile_summary(profile),
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


def media_category(media_type: Optional[str], filename: Optional[str]) -> str:
    media_type = (media_type or "").lower()
    filename = (filename or "").lower()
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    if media_type == "image":
        return "fotos"
    if media_type == "video":
        return "videos"
    if media_type == "audio":
        return "audios"
    if media_type == "document":
        return "pdfs" if ext == "pdf" else "documentos"
    return "outros"


def local_media_path(paths: dict[str, str], chat_jid: str, filename: Optional[str]) -> Optional[str]:
    if not filename:
        return None
    safe_name = os.path.basename(filename)
    return str(Path(paths["store_dir"]) / chat_jid.replace(":", "_") / safe_name)


def run_asset_search(profile: dict[str, Any], query: Optional[str], phone_number: Optional[str], chat_jid: Optional[str], after: Optional[str], before: Optional[str], limit_per_category: int) -> dict[str, Any]:
    paths = profile_paths(profile)
    db = Path(paths["messages_db"])
    categories: dict[str, list[dict[str, Any]]] = {key: [] for key in ["fotos", "videos", "audios", "pdfs", "documentos", "links", "outros"]}
    counts = {key: 0 for key in categories}
    if not db.exists():
        return {"profile": profile_summary(profile), "counts": counts, "items": categories, "error": "messages.db not found"}

    limit_per_category = max(1, min(int(limit_per_category), 200))
    where: list[str] = []
    params: list[Any] = []
    add_filters(where, params, query, phone_number, chat_jid, after, before)
    base_where = ("where " + " and ".join(where)) if where else ""

    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1) as conn:
            cur = conn.cursor()
            media_where = (base_where + " and coalesce(m.media_type, '') <> ''") if base_where else "where coalesce(m.media_type, '') <> ''"
            media_rows = cur.execute(
                f"""
                select m.timestamp, m.sender, c.name, m.chat_jid, m.id, m.media_type,
                       m.filename, m.content, m.file_length
                from messages m
                join chats c on m.chat_jid = c.jid
                {media_where}
                order by m.timestamp desc
                """,
                tuple(params),
            ).fetchall()

            link_where = (base_where + " and m.content like '%http%'") if base_where else "where m.content like '%http%'"
            link_rows = cur.execute(
                f"""
                select m.timestamp, m.sender, c.name, m.chat_jid, m.id, m.content
                from messages m
                join chats c on m.chat_jid = c.jid
                {link_where}
                order by m.timestamp desc
                """,
                tuple(params),
            ).fetchall()
    except sqlite3.Error as exc:
        return {"profile": profile_summary(profile), "counts": counts, "items": categories, "error": str(exc)}

    for row in media_rows:
        category = media_category(row[5], row[6])
        counts[category] += 1
        if len(categories[category]) >= limit_per_category:
            continue
        path = local_media_path(paths, row[3], row[6])
        categories[category].append(
            {
                "timestamp": row[0],
                "sender": row[1],
                "chat_name": row[2],
                "chat_jid": row[3],
                "message_id": row[4],
                "media_type": row[5],
                "filename": row[6],
                "caption": row[7],
                "file_length": row[8],
                "downloaded": bool(path and Path(path).exists()),
                "local_path": path if path and Path(path).exists() else None,
            }
        )

    for row in link_rows:
        for link in LINK_RE.findall(row[5] or ""):
            counts["links"] += 1
            if len(categories["links"]) >= limit_per_category:
                continue
            categories["links"].append(
                {
                    "timestamp": row[0],
                    "sender": row[1],
                    "chat_name": row[2],
                    "chat_jid": row[3],
                    "message_id": row[4],
                    "url": link.rstrip(".,);]"),
                    "message_excerpt": (row[5] or "")[:500],
                }
            )

    return {"profile": profile_summary(profile), "counts": counts, "items": categories}


@mcp.tool()
def list_profiles() -> list[dict[str, Any]]:
    """List configured WhatsApp profiles with local paths and database status."""
    return [profile_summary(profile) for profile in load_config().get("profiles", [])]


@mcp.tool()
def search_profile_messages(profile_slug: str, query: Optional[str] = None, phone_number: Optional[str] = None, chat_jid: Optional[str] = None, after: Optional[str] = None, before: Optional[str] = None, limit: int = 50, page: int = 0) -> dict[str, Any]:
    """Search messages inside one WhatsApp profile database."""
    return run_message_search(profile_by_slug(profile_slug), query, phone_number, chat_jid, after, before, limit, page)


@mcp.tool()
def search_all_profile_messages(query: Optional[str] = None, phone_number: Optional[str] = None, chat_jid: Optional[str] = None, after: Optional[str] = None, before: Optional[str] = None, limit_per_profile: int = 25) -> list[dict[str, Any]]:
    """Search messages across all enabled WhatsApp profile databases."""
    results = []
    for profile in load_config().get("profiles", []):
        if profile.get("enabled", True):
            results.append(run_message_search(profile, query, phone_number, chat_jid, after, before, limit_per_profile, 0))
    return results


@mcp.tool()
def list_profile_assets(profile_slug: str, query: Optional[str] = None, phone_number: Optional[str] = None, chat_jid: Optional[str] = None, after: Optional[str] = None, before: Optional[str] = None, limit_per_category: int = 50) -> dict[str, Any]:
    """List media files and links grouped by type inside one WhatsApp profile."""
    return run_asset_search(profile_by_slug(profile_slug), query, phone_number, chat_jid, after, before, limit_per_category)


@mcp.tool()
def list_all_profile_assets(query: Optional[str] = None, phone_number: Optional[str] = None, chat_jid: Optional[str] = None, after: Optional[str] = None, before: Optional[str] = None, limit_per_category: int = 25) -> list[dict[str, Any]]:
    """List media files and links grouped by type across all enabled WhatsApp profiles."""
    results = []
    for profile in load_config().get("profiles", []):
        if profile.get("enabled", True):
            results.append(run_asset_search(profile, query, phone_number, chat_jid, after, before, limit_per_category))
    return results


@mcp.tool()
def download_profile_media(profile_slug: str, message_id: str, chat_jid: str) -> dict[str, Any]:
    """Download one media file for a profile. Requires that profile bridge/port to be running."""
    profile = profile_by_slug(profile_slug)
    port = int(profile.get("port", 0) or 0)
    if not port_open(port):
        return {"success": False, "message": f"profile port {port} is closed; start the profile bridge first"}
    try:
        response = requests.post(
            f"http://127.0.0.1:{port}/api/download",
            json={"message_id": message_id, "chat_jid": chat_jid},
            timeout=60,
        )
        try:
            data = response.json()
        except ValueError:
            data = {"message": response.text}
        data["http_status"] = response.status_code
        data["profile"] = profile_summary(profile)
        return data
    except requests.RequestException as exc:
        return {"success": False, "message": str(exc), "profile": profile_summary(profile)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
