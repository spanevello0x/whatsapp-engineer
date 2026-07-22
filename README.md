# WhatsApp Engineer

Skill avançada para OpenClaw que ajuda terceiros a monitorar WhatsApp localmente com perfis separados, histórico em SQLite, MCP `whatsapp-profiles`, download/transcrição de mídia e entrega de resumos operacionais.

> Escopo: leitura, busca, resumo, transcrição e entrega controlada. Escrita/admin em WhatsApp é modo avançado, bloqueado por padrão e exige confirmação explícita.

## O que faz

- Pareia um número WhatsApp por QR em ambiente controlado.
- Mantém engine Baileys própria para leitura/sincronia local.
- Guarda histórico em SQLite local fora do Git.
- Expõe busca histórica via MCP `whatsapp-profiles`.
- Lista mensagens, links, documentos, imagens, vídeos e áudios.
- Transcreve áudios localmente quando mídia baixada está disponível.
- Gera resumos operacionais por período/perfil/chat.
- Entrega resultado em destino configurado: Telegram, Discord, manual ou adaptador próprio.

## Para quem é

- Times que precisam acompanhar WhatsApp de suporte, vendas ou operação.
- Agentes OpenClaw que precisam consultar histórico local sem expor bancos na nuvem.
- Desenvolvedores que querem uma base para criar monitoramento privado por perfil.

Não é skill para usuário leigo. Use em VPS/container ou máquina dedicada, com consentimento de quem pareia o número.

## Instalação rápida

```bash
git clone https://github.com/spanevello0x/whatsapp-engineer.git ~/.openclaw/skills/whatsapp-engineer
cd ~/.openclaw/skills/whatsapp-engineer
npm install
python3 workspace/run.py status
```

Configuração guiada:

```bash
python3 scripts/configure.py
```

Pareamento por QR:

```bash
python3 workspace/run.py connect --project Equipe --name Principal --number PHONE_E164
```

Depois do scan, valide:

```bash
python3 workspace/run.py status-v2
python3 workspace/run.py history-search-v2 --limit 10
```

## MCP embutido

O servidor MCP fica em:

```text
embedded_mcp/whatsapp_profiles/
```

Ele lê `profiles.json` e os bancos `messages.db` dos perfis. Dados reais não ficam no repositório.

Registrar MCP:

```bash
python3 workspace/run.py setup-mcp \
  --profiles-config "$HOME/Documents/WhatsApp MCP Profiles/profiles.json" \
  --install \
  --register
```

## Onde ficam dados sensíveis

Nunca versionar:

- QR codes;
- sessões WhatsApp;
- `messages.db`, `whatsapp.db` ou qualquer SQLite real;
- mídias baixadas;
- logs;
- tokens de Telegram/Discord/OpenClaw;
- exports de contatos ou conversas.

Por padrão, estado local fica em:

```text
~/.openclaw/state/whatsapp-engineer/
```

## Segurança operacional

- Um número = uma engine dona por vez.
- Não rode junto com outro Baileys/gateway usando o mesmo número.
- Escrita/admin exige `--execute` e flags explícitas.
- Confirme destino antes do primeiro envio real.
- Use variáveis de ambiente para tokens; a skill salva só o nome da variável.
- Respeite consentimento, privacidade e legislação aplicável.

## Exemplo de config

```json
{
  "version": 1,
  "agent": { "name": "agent" },
  "source": {
    "mcp": "whatsapp-profiles",
    "profiles": ["vendas-principal"],
    "chats": [],
    "default_period": "last_24h"
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
    "redact_phone_numbers": true,
    "require_confirmation_for_whatsapp_send": true,
    "confirm_first_delivery": true,
    "never_store_tokens": true
  }
}
```

## Estrutura

```text
embedded_mcp/whatsapp_profiles/  # MCP local para consultar perfis SQLite
scripts/                         # setup, QR, busca, transcrição, entrega
workspace/run.py                 # wrapper operacional principal
workspace/*.mjs                  # worker Baileys e helpers Node
references/                      # docs de configuração e operação
```

## Licença

MIT. Use como base, adapte com cuidado e nunca publique dados pessoais.
