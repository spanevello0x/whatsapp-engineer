#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path.home() / ".openclaw" / "state" / "whatsapp-engineer" / "config.json"


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    value = input(f"{prompt}{suffix}: ").strip()
    if value:
        return value
    return default or ""


def ask_bool(prompt: str, default: bool = True) -> bool:
    marker = "Y/n" if default else "y/N"
    value = input(f"{prompt} [{marker}]: ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes", "s", "sim", "1", "true"}


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def load_existing(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def build_config(existing: dict[str, Any]) -> dict[str, Any]:
    source = existing.get("source", {})
    audio = existing.get("audio", {})
    digest = existing.get("digest", {})
    destinations = existing.get("destinations", {})
    primary = destinations.get("primary", {})
    safety = existing.get("safety", {})

    print("\nWhatsApp Engineer wizard")
    print("Nao cole tokens aqui. Use apenas o nome da variavel de ambiente.\n")

    profiles = ask(
        "Perfis WhatsApp separados por virgula, ou vazio para todos",
        ", ".join(source.get("profiles", [])),
    )
    chats = ask(
        "Chats/grupos/JIDs separados por virgula, ou vazio para todos",
        ", ".join(source.get("chats", [])),
    )
    default_period = ask("Periodo padrao do resumo", source.get("default_period", "last_24h"))
    include_links = ask_bool("Incluir links e arquivos no resumo", digest.get("include_links", True))
    include_audio = ask_bool("Baixar/transcrever audios relevantes", audio.get("transcribe", True))
    audio_language = ask("Idioma dos audios (pt/en/es/auto)", audio.get("language", "pt"))
    audio_model = ask("Modelo nativo de transcricao (tiny/base/small)", audio.get("model", "tiny"))
    audio_task = ask("Tarefa de audio (transcribe/translate)", audio.get("task", "transcribe"))
    max_messages = ask("Maximo de mensagens por digest", str(digest.get("max_messages", 120)))

    destination_type = ask("Destino principal (telegram/whatsapp/discord/manual/custom)", primary.get("type", "telegram")).lower()
    destination: dict[str, Any] = {"type": destination_type}

    if destination_type == "telegram":
        destination["target_kind"] = ask("Alvo Telegram (topic/group/channel/private)", primary.get("target_kind", "topic"))
        destination["chat_id"] = ask("Telegram chat_id do grupo/canal/chat", str(primary.get("chat_id", "")))
        thread_default = primary.get("message_thread_id", "")
        thread = ask("message_thread_id do topico, vazio se grupo normal", str(thread_default))
        if thread:
            destination["message_thread_id"] = int(thread) if thread.isdigit() else thread
        destination["token_env"] = ask("Nome da env var com o token do bot", primary.get("token_env", "TELEGRAM_BOT_TOKEN"))
        destination["parse_mode"] = ask("parse_mode", primary.get("parse_mode", "HTML"))
    elif destination_type == "whatsapp":
        destination["target_kind"] = ask("Alvo WhatsApp (group/direct/channel/list)", primary.get("target_kind", "group"))
        destination["profile_slug"] = ask("Perfil remetente WhatsApp", primary.get("profile_slug", ""))
        destination["chat_jid"] = ask("JID do grupo/chat/canal destino", primary.get("chat_jid", ""))
        destination["send_adapter"] = ask("Nome do adaptador/tool de envio", primary.get("send_adapter", ""))
        destination["requires_send_adapter"] = True
        destination["require_confirmation"] = True
    elif destination_type == "discord":
        destination["target_kind"] = ask("Alvo Discord (channel/thread/webhook)", primary.get("target_kind", "channel"))
        destination["delivery_mode"] = ask("Modo Discord (webhook/bot)", primary.get("delivery_mode", "webhook"))
        if destination["delivery_mode"] == "webhook":
            destination["webhook_env"] = ask("Nome da env var com o webhook URL", primary.get("webhook_env", "DISCORD_WEBHOOK_URL"))
        else:
            destination["bot_token_env"] = ask("Nome da env var com o token do bot", primary.get("bot_token_env", "DISCORD_BOT_TOKEN"))
            destination["channel_id"] = ask("Discord channel_id", str(primary.get("channel_id", "")))
            thread_id = ask("Discord thread_id opcional", str(primary.get("thread_id", "")))
            if thread_id:
                destination["thread_id"] = thread_id
        destination["parse_mode"] = ask("Formato da mensagem (markdown/plain)", primary.get("parse_mode", "markdown"))
    else:
        destination["target_kind"] = ask("Tipo de alvo custom/manual", primary.get("target_kind", "manual"))
        destination["notes"] = ask("Notas do destino manual", primary.get("notes", ""))

    try:
        max_messages_int = max(1, int(max_messages))
    except ValueError:
        max_messages_int = 120

    return {
        "version": 1,
        "agent": {
            "name": ask("Nome do agente", existing.get("agent", {}).get("name", "agent")),
        },
        "source": {
            "mcp": "whatsapp-profiles",
            "profiles": split_csv(profiles),
            "chats": split_csv(chats),
            "default_period": default_period,
        },
        "audio": {
            "transcribe": include_audio,
            "engine": "native-faster-whisper",
            "script": "~/.openclaw/workspace/skills/whatsapp-engineer/scripts/transcribe_audio.py",
            "setup_script": "~/.openclaw/workspace/skills/whatsapp-engineer/scripts/setup_transcription.py",
            "language": audio_language,
            "model": audio_model,
            "task": audio_task if audio_task in {"transcribe", "translate"} else "transcribe",
        },
        "digest": {
            "include_links": include_links,
            "include_audio": include_audio,
            "max_messages": max_messages_int,
            "format": ask("Formato do resumo (executive/operational/brief)", digest.get("format", "operational")),
        },
        "destinations": {
            "primary": destination,
        },
        "safety": {
            "redact_phone_numbers": ask_bool("Mascarar telefones no resumo", safety.get("redact_phone_numbers", False)),
            "require_confirmation_for_whatsapp_send": True,
            "confirm_first_delivery": ask_bool("Confirmar a primeira entrega nesse destino", safety.get("confirm_first_delivery", True)),
            "never_store_tokens": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure WhatsApp Engineer.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to config JSON.")
    parser.add_argument("--print", action="store_true", help="Print generated config instead of writing it.")
    args = parser.parse_args()

    existing = load_existing(args.config)
    config = build_config(existing)
    rendered = json.dumps(config, ensure_ascii=False, indent=2)

    if args.print:
        print(rendered)
        return 0

    args.config.parent.mkdir(parents=True, exist_ok=True)
    args.config.write_text(rendered + "\n", encoding="utf-8")
    os.chmod(args.config, 0o600)

    print(f"\nConfig gravado em: {args.config}")
    print("Proximos passos:")
    print("- Validar que o MCP whatsapp-profiles responde list_profiles.")
    print("- Se Telegram for o destino, exportar a env var do token do bot.")
    print("- Confirmar chat_id/message_thread_id antes de publicar em grupo real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
