#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path.home() / ".openclaw" / "state" / "whatsapp-engineer" / "config.json"


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Config nao encontrado: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Config JSON invalido: {exc}") from exc


def telegram_payload(destination: dict[str, Any], text: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "chat_id": destination.get("chat_id"),
        "text": text,
        "disable_web_page_preview": True,
    }
    if destination.get("message_thread_id") not in (None, ""):
        payload["message_thread_id"] = destination["message_thread_id"]
    if destination.get("parse_mode"):
        payload["parse_mode"] = destination["parse_mode"]
    return {key: value for key, value in payload.items() if value not in (None, "")}


def post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, str, float]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            elapsed_ms = (time.perf_counter() - start) * 1000
            return response.status, body, elapsed_ms
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        elapsed_ms = (time.perf_counter() - start) * 1000
        return exc.code, body, elapsed_ms
    except urllib.error.URLError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return 0, str(exc), elapsed_ms


def main() -> int:
    parser = argparse.ArgumentParser(description="Test WhatsApp Engineer delivery target.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to config JSON.")
    parser.add_argument("--send", action="store_true", help="Actually send the test message.")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds.")
    parser.add_argument("--text", default="", help="Custom test message.")
    args = parser.parse_args()

    config = load_config(args.config)
    destination = config.get("destinations", {}).get("primary", {})
    destination_type = destination.get("type")

    if destination_type != "telegram":
        raise SystemExit(f"Destino primario nao e telegram: {destination_type!r}")

    text = args.text.strip() or (
        "<b>Teste WhatsApp Engineer</b>\n"
        f"Agente: {config.get('agent', {}).get('name', 'agent')}\n"
        f"Destino: Telegram {destination.get('target_kind', 'group')}\n"
        f"Horario UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n"
        "Status: teste de entrega."
    )
    payload = telegram_payload(destination, text)

    print("Payload de teste:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if not args.send:
        print("\nDry-run apenas. Use --send para enviar e medir o tempo da chamada.")
        return 0

    token_env = destination.get("token_env", "TELEGRAM_BOT_TOKEN")
    token = os.environ.get(token_env, "")
    if not token:
        raise SystemExit(f"Env var ausente: {token_env}")
    if not payload.get("chat_id"):
        raise SystemExit("chat_id ausente no destino Telegram.")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    status, body, elapsed_ms = post_json(url, payload, args.timeout)
    print(f"\nHTTP status: {status}")
    print(f"Tempo da chamada: {elapsed_ms:.0f} ms")

    try:
        parsed = json.loads(body)
        safe_body = {
            "ok": parsed.get("ok"),
            "error_code": parsed.get("error_code"),
            "description": parsed.get("description"),
            "message_id": parsed.get("result", {}).get("message_id") if isinstance(parsed.get("result"), dict) else None,
            "date": parsed.get("result", {}).get("date") if isinstance(parsed.get("result"), dict) else None,
        }
        print(json.dumps(safe_body, ensure_ascii=False, indent=2))
        return 0 if parsed.get("ok") else 1
    except json.JSONDecodeError:
        print(body[:1000])
        return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
