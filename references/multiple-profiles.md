# Multiple WhatsApp Profiles

Use este guia quando o usuario quiser conectar e analisar mais de um numero de WhatsApp, como funcionarios, vendedores, financeiro, suporte ou departamentos.

## Mental Model

```text
1 numero de WhatsApp = 1 perfil
1 funcionario = normalmente 1 perfil
1 perfil = 1 whatsapp.db + 1 messages.db + 1 porta local
OpenClaw agent = consulta varios perfis via MCP whatsapp-profiles
```

O `whatsapp-mcp-local-kit` usa modo perfis. Cada perfil fica isolado por pasta, banco SQLite, sessao e porta. Isso evita misturar conversas de funcionarios diferentes.

## Setup Flow

1. Abrir o painel `WhatsApp MCP Tray`.
2. Criar ou escolher um projeto, por exemplo:

```text
Vendedores
Financeiro
Suporte
Administrativo
```

3. Criar um perfil para cada funcionario:

```text
Projeto: Vendedores
Perfil: vendedor-joao
Numero: +55...
Descricao: WhatsApp do Joao
```

4. Clicar em `Conectar QR` no perfil criado.
5. O funcionario deve abrir o WhatsApp dele e escanear o QR:

```text
WhatsApp > Aparelhos conectados > Conectar aparelho
```

Alternativa CLI pela skill, quando o operador estiver conduzindo o pareamento pelo OpenClaw agent:

```bash
python3 ~/.openclaw/workspace/skills/whatsapp-engineer/scripts/pair_whatsapp_qr.py --account default --force
```

O script grava o PNG em `~/.openclaw/state/whatsapp-engineer/qr/` e continua rodando ate o scan conectar ou expirar. Nao encerre o processo logo apos gerar o PNG; isso invalida a sessao do QR.

6. Aguardar a primeira sincronizacao inteligente.
7. Repetir para cada funcionario.

## Expected Local Structure

Exemplo:

```text
~/Documents/WhatsApp MCP Profiles/
  profiles.json
  projetos/
    Vendedores/
      vendedor-joao/
        whatsapp-bridge/store/whatsapp.db
        whatsapp-bridge/store/messages.db
      vendedor-maria/
        whatsapp-bridge/store/whatsapp.db
        whatsapp-bridge/store/messages.db
    Financeiro/
      financeiro-ana/
        whatsapp-bridge/store/whatsapp.db
        whatsapp-bridge/store/messages.db
```

## Configure OpenClaw agent

Rode o wizard:

```bash
python3 ~/.openclaw/workspace/skills/whatsapp-engineer/scripts/configure.py
```

Quando perguntar:

```text
Perfis WhatsApp separados por virgula, ou vazio para todos
```

Opcoes:

```text
vendedor-joao, vendedor-maria, financeiro-ana
```

ou vazio para todos os perfis habilitados.

Config resultante:

```json
{
  "source": {
    "mcp": "whatsapp-profiles",
    "profiles": ["vendedor-joao", "vendedor-maria", "financeiro-ana"],
    "chats": [],
    "default_period": "last_24h"
  }
}
```

## Analysis Behavior

Ao resumir varios perfis, agrupe por:

- projeto;
- perfil/funcionario;
- grupo ou chat;
- remetente;
- periodo.

Formato recomendado:

```text
Resumo WhatsApp - Vendedores
Periodo: ultimas 24h

vendedor-joao
- Principais pontos...
- Pendencias...
- Audios...

vendedor-maria
- Principais pontos...
- Pendencias...
- Audios...
```

## Safety Rules

- O funcionario precisa autorizar o pareamento por QR.
- Nao apague `whatsapp.db`, `messages.db`, logs ou pastas de perfil sem confirmacao explicita.
- Nao copie bancos SQLite para dentro da pasta da skill.
- Nao misture sessoes entre funcionarios.
- Para auditoria interna, deixe claro no resumo qual perfil/funcionario originou cada item.
- Se o usuario pedir "todos os funcionarios", primeiro use `list_profiles` e confirme quais perfis existem antes de publicar resumo em grupo.
