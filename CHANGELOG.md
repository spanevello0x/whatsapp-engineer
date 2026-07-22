# Changelog

## v1.14.4 - 2026-05-13

- Ajusta prompts do wizard para exibir uma pergunta por vez, com resposta em linha separada (`>`).
- Pergunta explicitamente se o usuário já criou grupo Telegram para o agente/bot.

## v1.14.3 - 2026-05-13

- Simplifica setup Telegram para usuários leigos: wizard ensina a copiar o link de uma mensagem do tópico e tenta detectar `chat_id`/`message_thread_id` automaticamente.
- Mantém confirmação manual dos IDs quando necessário.

## v1.14.2 - 2026-05-13

- `first-run` agora ensina como criar grupo/tópico Telegram antes de pedir `chat_id` e `message_thread_id`.
- Wizard pergunta se o agente já tem grupo e se já existe tópico específico para WhatsApp Engineer.

## v1.14.1 - 2026-05-13

- Melhora abertura do `first-run`: explica o workflow completo em 6 passos antes da primeira pergunta.
- Reforça que o wizard pergunta uma coisa por vez, permite aceitar padrões e não salva segredos.

## v1.14.0 - 2026-05-13

- Adiciona `first-run`, wizard inicial guiado da skill.
- Wizard conduz o operador uma pergunta por vez e salva `settings.json`.
- Cobre entrega, sincronia, áudio/transcrição, formatação PT-BR e segurança operacional.

## v1.13.0 - 2026-05-13

- Adiciona `settings.json` do usuário em `~/.openclaw/state/whatsapp-engineer/settings.json`.
- Adiciona comandos oficiais `settings` e `settings-wizard`.
- Remove hardcode operacional de entrega/sincronia do fluxo de áudio, lendo preferências de entrega, origem, data/hora, modelo e sincronia a partir de settings.
- Wizard segue regra MQC: uma pergunta por vez, com emoji, sem salvar segredos.

## v1.12.3 - 2026-05-13

- Formata entrega de áudio com contato, número real quando disponível, origem semântica (`conversa direta` ou `grupo <nome>`) e data/hora em PT-BR.
- Para grupos, a origem deve usar o nome do grupo a partir de `chat_name`/`@g.us`.

## v1.12.2 - 2026-05-13

- Entrega de áudio agora inclui remetente (`De`) e origem/conversa (`Origem`) por padrão.
- Mantém ID técnico, modelo e timestamp apenas em `--debug`.

## v1.12.1 - 2026-05-13

- Ajusta entrega de áudio: modo padrão não mostra ID técnico, modelo ou timestamp.
- Adiciona `--debug` para incluir metadados técnicos quando necessário.
- Reentrega formato limpo no tópico Telegram.

## v1.12.0 - 2026-05-13

- Adiciona `deliver-latest-audio` para preparar entrega polida de transcrição em vez de despejar saída crua do ASR.
- Aplica limpeza leve de erros comuns e reforça diferença entre transcrição e tradução.
- Recomenda modelo melhor que tiny para qualidade quando o runtime permitir.

## v1.11.3 - 2026-05-13

- Normaliza docs para path canônico de plataforma `~/.openclaw/skills/whatsapp-engineer`.
- Sincroniza versão de `skill.json` e `package.json`.
- Declara escopo avançado/single-number ownership para evitar uso concorrente com gateway nativo ou outra engine WhatsApp no mesmo número.
- Public release uses MIT license and removes private/customer-specific references.

## v1.11.2 - 2026-05-13

- Corrige transcrição Node/Transformers no runtime Node sem `AudioContext`: áudio é convertido para WAV/16k com `@ffmpeg-installer/ffmpeg` e lido via `wavefile`.
- Valida transcrição real de áudio WhatsApp baixado pelo Baileys e entrega no tópico Telegram.

## v1.11.1 - 2026-05-13

- Adiciona comando `download-media --message-id` para tentativa de backfill de mídia Baileys.
- Documenta limitação: mídia antiga sem objeto completo em cache não pode ser baixada apenas por metadados/ID.

## v1.11.0 - 2026-05-13

- Adiciona transcrição local dentro da skill via Node/Transformers (`@xenova/transformers`).
- Adiciona comando oficial `transcribe-latest-audio` no wrapper `workspace/run.py`.
- Evita dependencia de `python3-venv`, `apt` ou `ffmpeg` do sistema para o caminho principal de transcrição.

## v1.10.0 - 2026-05-13

- Baileys v2 agora baixa mídia/áudio recebido em tempo real para `~/.openclaw/state/whatsapp-engineer/baileys/media/`.
- Adiciona coluna `local_path` ao SQLite Baileys e retorno em `history-search-v2`.
- Prepara áudios novos para o fluxo de transcrição da skill.

## v1.9.0 - 2026-05-13

- Adiciona comando oficial `stop-engines` para parar engine legada Go/whatsmeow ou Baileys antes de cortes controlados.
- Valida corte real para Baileys: QR escaneado, worker aberto, sync historico populando SQLite Baileys.
- Documenta sequencia de producao: `stop-engines --legacy-go`, `connect`, `status-v2`, `history-search-v2`.

## v1.8.1 - 2026-05-13

- Documenta regra operacional do QR Baileys: gerar somente com operador pronto, enviar imediatamente, janela util de 45-60s, descartar QR antigo.
- Documenta corte controlado antes de rodada real Baileys para evitar conflito com outra engine do mesmo numero.

## v1.8.0 - 2026-05-13

- Inicia migração de produção para engine Baileys própria dentro da skill.
- Adiciona `workspace/baileys_worker.mjs` com `syncFullHistory: true`, QR PNG, auth local e persistência SQLite via `node:sqlite`.
- Adiciona `setup_baileys.py`, `connect_baileys.py`, `search_baileys.py` e comandos `status-v2`/`history-search-v2`.
- `run.py connect` passa a apontar para Baileys v2; fluxo Go/whatsmeow fica legado/fallback.

## v1.7.0 - 2026-05-13

- Adiciona comando oficial `connect` para fluxo de um QR/sessao unica da propria skill.
- `connect` instala/compila bridge, cria perfil historico, inicia sync, registra MCP embutido e gera QR PNG quando necessario.
- `pair-qr` vira alias legado para o fluxo unificado, evitando pareamento separado pelo gateway nativo do OpenClaw.

## v1.6.0 - 2026-05-13

- Adiciona `bridge-install --build-from-source` para baixar Go+Zig em `~/.openclaw/state/whatsapp-engineer/toolchain` e compilar `whatsapp-bridge` sem depender de Go/GCC do sistema.
- Mantem suporte opcional a download de binario pre-compilado por URL/release quando existir.
- Atualiza fluxo recomendado: instalar/compilar bridge, criar perfil/sync e iniciar pela propria skill.

## v1.5.0 - 2026-05-13

- Adiciona `sync-setup` no wrapper oficial `workspace/run.py`.
- Cria estrutura de perfil historico (`profiles.json`, projeto, perfil, store) pela propria skill.
- Reporta prechecks da bridge: binario, fonte do kit, Go/GCC e porta.

## v1.4.0 - 2026-05-13

- Adiciona `workspace/run.py` como comando operacional oficial da skill.
- Padroniza setup MCP, status, busca historica, teste de entrega e QR para rodarem pelo wrapper da skill.
- Atualiza README/SKILL para evitar chamadas diretas a scripts internos em operacao normal.

## v1.3.0 - 2026-05-13

- Embute o MCP `whatsapp-profiles` dentro da propria skill em `embedded_mcp/whatsapp_profiles/stdio_server.py`.
- Adiciona `scripts/setup_embedded_mcp.py` para registrar o MCP embutido no OpenClaw.
- Remove dependencia obrigatoria de `uv`, `pip` ou `mcp[cli]` para busca historica SQLite.
- Mantem dados sensiveis fora do Git: `profiles.json`, `messages.db`, `whatsapp.db`, logs, QR Codes e midias continuam externos.

## v1.2.0 - 2026-05-13

- Integra o fluxo de historico antigo com `whatsapp-mcp-local-kit`.
- Adiciona `scripts/configure_history_mcp.py` para apontar a skill ao kit/perfis e registrar opcionalmente o MCP `whatsapp-profiles`.
- Adiciona `scripts/search_history.py` para consultar diretamente os `messages.db` dos perfis quando o MCP nao estiver anexado ao runtime.
- Documenta busca por ano, chat/grupo, perfil, telefone e palavra-chave.

## v1.1.0 - 2026-05-13

- Adiciona pareamento QR pela propria skill com `scripts/pair_whatsapp_qr.py`.
- Mantem a sessao de login viva enquanto o usuario escaneia o QR, evitando QR aparentemente expirado.
- Salva QR temporario em `~/.openclaw/state/whatsapp-engineer/qr/`, fora da pasta versionada da skill.
- Documenta o fluxo de pareamento e a validacao dos scripts.

## v1.0.0

- Skill inicial para configurar resumos de WhatsApp, transcricao nativa de audio e entrega Telegram/Discord/WhatsApp/manual.
