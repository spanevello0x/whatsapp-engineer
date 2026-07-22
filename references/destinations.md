# Destinations

O destino de entrega deve ser definido pelo usuario no wizard ou no config. Nao assuma Telegram como destino unico.

## Telegram

Use a skill `telegram` para desenhar e executar chamadas diretas a Bot API por HTTPS.

Requisitos:

- Bot dentro do grupo/canal.
- `TELEGRAM_BOT_TOKEN` ou env equivalente configurada fora do arquivo JSON.
- `chat_id` do grupo/canal.
- `message_thread_id` se o grupo for forum/topico.

Payload base para `sendMessage`:

```json
{
  "chat_id": "-1001234567890",
  "message_thread_id": 123,
  "text": "<b>Resumo WhatsApp</b>...",
  "parse_mode": "HTML",
  "disable_web_page_preview": true
}
```

Se nao houver topico, omitir `message_thread_id`. Para grupo forum/topico, `message_thread_id` e obrigatorio para entregar no topico certo.

Para testar entrega e latencia:

```bash
python3 ~/.openclaw/workspace/skills/whatsapp-engineer/scripts/test_delivery.py
python3 ~/.openclaw/workspace/skills/whatsapp-engineer/scripts/test_delivery.py --send
```

O script mede o tempo da chamada HTTP ao Telegram Bot API. Esse tempo indica resposta da API, nao leitura pelos usuarios.

## WhatsApp

O kit `whatsapp-mcp-local-kit` expoe leitura, busca, inventario de midias e download por perfil. O MCP de perfis atual nao deve ser tratado como canal de envio ate existir uma tool explicita de envio, por exemplo:

```text
send_profile_message(profile_slug, chat_jid, text)
```

Antes de enviar para WhatsApp:

- exigir confirmacao explicita do usuario;
- confirmar perfil remetente;
- confirmar tipo do alvo: `group`, `direct`, `channel` ou `list`;
- confirmar JID do grupo/chat/canal destino;
- registrar que o destino e WhatsApp, nao Telegram.

## Discord

Use Discord quando o usuario escolher um canal/thread do Discord para receber o resumo.

Preferir webhook quando possivel:

```json
{
  "content": "**Resumo WhatsApp**\n..."
}
```

Regras:

- guardar o webhook URL em variavel de ambiente, nunca no config;
- para bot adapter, guardar bot token em variavel de ambiente e configurar `channel_id`;
- usar Markdown simples;
- dividir mensagens longas antes do limite da plataforma.

## Manual Or Custom Platforms

Quando o destino for `manual` ou `custom`, gere o resumo e informe que a publicacao ficou pendente ou delegada para outro conector. Para Slack, email, Notion ou outros destinos, manter adaptador separado e nao misturar tokens no config desta skill.
