# Config Reference

Config padrao:

```text
~/.openclaw/state/whatsapp-engineer/config.json
```

O wizard `scripts/configure.py` cria este arquivo. Ele nao salva tokens.

## Schema

```json
{
  "version": 1,
  "agent": {
    "name": "agent"
  },
  "source": {
    "mcp": "whatsapp-profiles",
    "profiles": ["vendedor-joao"],
    "chats": ["<GROUP_JID>"],
    "default_period": "last_24h"
  },
  "audio": {
    "transcribe": true,
    "engine": "native-faster-whisper",
    "script": "~/.openclaw/workspace/skills/whatsapp-engineer/scripts/transcribe_audio.py",
    "setup_script": "~/.openclaw/workspace/skills/whatsapp-engineer/scripts/setup_transcription.py",
    "language": "pt",
    "model": "tiny",
    "task": "transcribe"
  },
  "digest": {
    "include_links": true,
    "include_audio": true,
    "max_messages": 120,
    "format": "operational"
  },
  "destinations": {
    "primary": {
      "type": "telegram",
      "target_kind": "topic",
      "chat_id": "-1001234567890",
      "message_thread_id": 123,
      "token_env": "TELEGRAM_BOT_TOKEN",
      "parse_mode": "HTML"
    }
  },
  "safety": {
    "redact_phone_numbers": false,
    "require_confirmation_for_whatsapp_send": true,
    "never_store_tokens": true
  }
}
```

## Field Notes

- `source.profiles`: vazio significa todos os perfis habilitados no MCP.
- Para funcionarios, use um slug por numero/perfil, por exemplo `["vendedor-joao", "vendedor-maria", "financeiro-ana"]`.
- `source.chats`: vazio significa todos os chats encontrados pelo filtro do periodo.
- `source.default_period`: usar valores como `last_24h`, `today`, `yesterday`, `last_7d`, ou datas absolutas quando o usuario pedir.
- `destinations.primary.message_thread_id`: usar apenas em grupo forum/topico do Telegram.
- `destinations.primary.token_env`: nome da variavel de ambiente que contem o token do bot.
- `safety.never_store_tokens`: deve permanecer `true`.

## Destination Examples

Telegram topico:

```json
{
  "type": "telegram",
  "target_kind": "topic",
  "chat_id": "-1001234567890",
  "message_thread_id": 123,
  "token_env": "TELEGRAM_BOT_TOKEN",
  "parse_mode": "HTML"
}
```

WhatsApp grupo ou direto:

```json
{
  "type": "whatsapp",
  "target_kind": "group",
  "profile_slug": "agent-remetente",
  "chat_jid": "<GROUP_JID>",
  "send_adapter": "send_profile_message",
  "requires_send_adapter": true,
  "require_confirmation": true
}
```

Para chat direto no WhatsApp, use `target_kind: "direct"` e o JID do contato quando o adaptador de envio suportar isso.

Discord via webhook:

```json
{
  "type": "discord",
  "target_kind": "channel",
  "delivery_mode": "webhook",
  "webhook_env": "DISCORD_WEBHOOK_URL",
  "parse_mode": "markdown"
}
```

Custom/manual:

```json
{
  "type": "manual",
  "target_kind": "manual",
  "notes": "Gerar resumo e aguardar o usuario publicar."
}
```
