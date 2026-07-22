---
name: whatsapp-engineer
description: Orquestrar resumos do WhatsApp para o agente OpenClaw usando o MCP whatsapp-profiles, transcricao local de audios e entrega em Telegram ou outros destinos. Use quando o usuario pedir para configurar, gerar, agendar ou publicar resumos de conversas, grupos, perfis, links, arquivos ou audios do WhatsApp em um grupo/topico do Telegram, WhatsApp ou outra plataforma.
---

# WhatsApp Engineer

## Overview

Use esta skill para fazer o OpenClaw agent parear WhatsApp por QR assistido, registrar/usar o MCP `whatsapp-profiles` embutido na propria skill, ler bases locais do `whatsapp-mcp-local-kit`, buscar historico antigo em `messages.db`, resumir mensagens e midias, transcrever audios quando necessario e publicar o resultado no destino escolhido pelo usuario: topico/grupo do Telegram, grupo/chat direto/canal do WhatsApp, canal do Discord ou outro destino manual/custom.

Esta skill e uma camada de orquestracao. Ela nao substitui o MCP de WhatsApp nem a skill de Telegram; a transcricao de audio fica nativa na propria skill via `scripts/transcribe_audio.py`.

## Quick Start

Skill path local atual:

```text
/home/openclaw/.openclaw/skills/whatsapp-engineer
```

Invocacao recomendada no OpenClaw:

```text
$whatsapp-engineer
```

Prompt direto com path:

```text
Use $whatsapp-engineer at /home/openclaw/.openclaw/skills/whatsapp-engineer to configure OpenClaw agent and test delivery.
```

1. Execute o wizard para criar ou atualizar a configuracao:

```bash
python3 ~/.openclaw/skills/whatsapp-engineer/scripts/configure.py
```

2. Para testar o payload de entrega Telegram sem enviar:

```bash
python3 ~/.openclaw/skills/whatsapp-engineer/scripts/test_delivery.py
```

3. Para enviar um teste real ao Telegram e medir o tempo da chamada:

```bash
python3 ~/.openclaw/skills/whatsapp-engineer/scripts/test_delivery.py --send
```

4. Para parear WhatsApp por QR pela propria skill, mantendo a sessao viva durante o scan:

```bash
python3 ~/.openclaw/skills/whatsapp-engineer/scripts/pair_whatsapp_qr.py --force
```

5. Leia o arquivo JSON gerado antes de rodar qualquer automacao.
6. Para historico antigo, registre primeiro o MCP embutido da propria skill:

```bash
python3 ~/.openclaw/skills/whatsapp-engineer/workspace/run.py setup-mcp \
  --profiles-config "$HOME/Documents/WhatsApp MCP Profiles/profiles.json" \
  --install \
  --register
```

7. Opcionalmente, se quiser apontar para o MCP externo do `whatsapp-mcp-local-kit`, configure:

```bash
python3 ~/.openclaw/skills/whatsapp-engineer/scripts/configure_history_mcp.py \
  --kit-dir ~/.openclaw/workspace/repos/whatsapp-mcp-local-kit \
  --profiles-config "$HOME/Documents/WhatsApp MCP Profiles/profiles.json"
```

8. Confirme que os perfis de WhatsApp estao sincronizados antes de gerar resumos.
9. Se houver audio, transcreva nativamente com `scripts/transcribe_audio.py`.
10. Entregue no destino configurado pelo usuario. Para Telegram, use a skill `telegram`; para Discord, use webhook ou bot adapter; para WhatsApp, use somente quando houver adaptador/tool de envio configurado.

## Multiple WhatsApp Numbers

Para analisar WhatsApp de funcionarios, use o modo perfis do `whatsapp-mcp-local-kit`: cada numero vira um perfil separado, com sessao e `messages.db` proprios. Leia `references/multiple-profiles.md` quando o usuario pedir para conectar mais de um numero, vendedor, funcionario, departamento ou projeto.

Regra operacional:

- 1 numero de WhatsApp = 1 perfil.
- 1 funcionario normalmente = 1 perfil.
- Cada perfil pertence a um projeto, como `Vendedores`, `Financeiro` ou `Suporte`.
- O funcionario precisa autorizar o pareamento lendo o QR Code no WhatsApp dele.
- Quando gerar QR via CLI, use `scripts/pair_whatsapp_qr.py` e mantenha o processo aberto ate confirmar `Linked! WhatsApp is ready`.
- O OpenClaw agent analisa todos os perfis listados em `source.profiles`; se a lista estiver vazia, analisa todos os perfis habilitados.
- Nunca misture bancos, sessoes ou pastas entre funcionarios.

## Workflow

### 1. Load Configuration

Use o config em:

```text
~/.openclaw/state/whatsapp-engineer/config.json
```

Se o arquivo nao existir, execute `scripts/configure.py`. Para detalhes do schema, leia `references/config.md`.







## Entrega Polida De Transcrição

Para entrega ao tópico, preferir o fluxo polido em vez de despejar a saída crua do modelo:

```bash
python3 ~/.openclaw/skills/whatsapp-engineer/workspace/run.py deliver-latest-audio --dry-run
```

Esse fluxo gera entrega limpa por padrão: sem ID técnico, sem modelo e sem timestamp. Metadados técnicos aparecem apenas com `--debug`. Para maior qualidade, usar modelo melhor que tiny quando o runtime permitir, por exemplo `Xenova/whisper-small`.

A entrega não deve prometer tradução; o padrão é **transcrição**. Se o usuário pedir tradução, tratar como etapa separada.

## Transcrição De Áudio Dentro Da Skill

A skill inclui transcrição local via Node/Transformers, com ffmpeg empacotado por npm, sem depender de `python3-venv`, `apt` ou `ffmpeg` do sistema:

```bash
python3 /home/openclaw/.openclaw/skills/whatsapp-engineer/workspace/run.py transcribe-latest-audio
```

Por padrão usa `Xenova/whisper-tiny`, `@ffmpeg-installer/ffmpeg` para decodificar OGG/Opus e cache em:

```text
~/.openclaw/state/whatsapp-engineer/transformers-cache
```


### Backfill de mídia por message id

A skill tem comando para tentar rebaixar mídia por ID:

```bash
python3 /home/openclaw/.openclaw/skills/whatsapp-engineer/workspace/run.py download-media --message-id <id>
```

Limitação real do Baileys: se o worker não manteve o objeto criptográfico completo da mensagem em cache e o SQLite guardou apenas metadados, não é possível reconstruir/baixar mídia antiga só com `message_id`. Para garantir transcrição, o áudio precisa ser recebido depois do download de mídia estar ativo, preenchendo `local_path`.

A transcrição exige que o áudio tenha `local_path`, ou seja, que tenha sido recebido/baixado pela engine Baileys após a versão que habilitou download de mídia. Se a resposta for `no_downloaded_audio_found`, envie um novo áudio e rode novamente.

## Mídia E Áudio No Baileys V2

A engine Baileys salva metadados de mídia no SQLite e baixa arquivos recebidos em tempo real para:

```text
~/.openclaw/state/whatsapp-engineer/baileys/media/YYYY-MM-DD/<chat_jid>/<message_id>.<ext>
```

A busca `history-search-v2` retorna `local_path` quando o arquivo foi baixado. Mensagens históricas antigas podem ter apenas metadados se a mídia não estiver mais disponível para download no evento atual.

Áudios recebidos depois da v1.10.0 ficam prontos para serem enviados ao fluxo de transcrição da skill.

## Corte De Produção Para Baileys

Para finalizar a migração para a engine Baileys própria da skill, use apenas comandos do wrapper oficial:

```bash
python3 /home/openclaw/.openclaw/skills/whatsapp-engineer/workspace/run.py stop-engines --legacy-go
python3 /home/openclaw/.openclaw/skills/whatsapp-engineer/workspace/run.py connect
python3 /home/openclaw/.openclaw/skills/whatsapp-engineer/workspace/run.py status-v2
python3 /home/openclaw/.openclaw/skills/whatsapp-engineer/workspace/run.py history-search-v2 --year 2026 --limit 10
```

`stop-engines --legacy-go` deve ser usado antes do QR Baileys para evitar conflito com a antiga bridge Go/whatsmeow. Depois do scan, validar que `status-v2` mostra mensagens e chats no banco Baileys.

## Regra Operacional Do QR Baileys

Para o fluxo Baileys v2, o QR deve ser tratado como efemero:

- gerar QR somente quando o operador estiver pronto para escanear;
- enviar o QR imediatamente apos a geracao;
- considerar janela util de 45-60 segundos;
- se passar desse tempo, descartar e gerar outro QR;
- nunca reutilizar QR antigo salvo em disco;
- em rodada real, avisar explicitamente: `QR valido agora`.

Antes de uma rodada real de QR Baileys, fazer corte controlado para evitar conflito:

1. parar a engine ativa anterior do mesmo numero;
2. iniciar `run.py connect`;
3. enviar o QR assim que `status.state == qr`;
4. validar `status-v2` depois do scan;
5. validar `history-search-v2 --year 2026`.



## Escopo Avançado / Single-Number Ownership

Esta skill embute uma engine WhatsApp própria. Ela é modo avançado e deve ser isolada por número:

- uma skill/engine dona de um número por vez;
- não rodar junto com gateway WhatsApp nativo para o mesmo número;
- não rodar junto com outra engine WhatsApp para o mesmo número;
- usar com clareza operacional em VPS/container dedicado ou ambiente controlado.

Para marketplace público/curado, marcar como `advanced`, `developer` ou equivalente, não como skill genérica para usuário leigo.

## Path Canônico De Instalação

Para OpenClaw/QuickClaw em plataforma, o path canônico da skill é:

```text
~/.openclaw/skills/whatsapp-engineer
```

Durante desenvolvimento local, este repositório também pode existir em:

```text
/home/openclaw/.openclaw/workspace/skills/whatsapp-engineer
```

Docs e comandos de produção devem preferir o path canônico `~/.openclaw/skills/whatsapp-engineer`.



## First Run Wizard

No primeiro uso, a skill deve guiar o operador com uma pergunta por vez, exibindo cada prompt separado em uma linha com `>` para resposta:

```bash
python3 ~/.openclaw/skills/whatsapp-engineer/workspace/run.py first-run
```

Abertura:

```text
Vou configurar a WhatsApp Engineer em 6 passos. ⚙️

1. Definir onde vou entregar mensagens, resumos e transcrições.
2. Ajustar como a sincronia do WhatsApp vai funcionar.
3. Escolher como áudios serão baixados e transcritos.
4. Definir o formato das mensagens entregues.
5. Validar a regra de segurança: uma skill dona de um número.
6. Salvar tudo em settings.json e orientar a conexão via QR.

Vou perguntar uma coisa por vez. Você pode aceitar os padrões quando quiser.
Nenhum token ou segredo será salvo aqui; segredos continuam em env/secret manager. 🔒
```


### Entrega Telegram no first-run

Quando o destino for Telegram, o wizard ensina antes de pedir IDs:

1. criar um grupo para o agente;
2. adicionar o bot/agente no grupo;
3. ativar Tópicos/Fórum nas configurações do grupo;
4. criar um tópico para WhatsApp Engineer;
5. copiar o link de uma mensagem dentro do tópico;
6. colar o link no wizard para a skill tentar detectar `chat_id` e `message_thread_id` automaticamente.

O usuário leigo não precisa calcular manualmente os IDs se tiver o link do tópico. Antes de confirmar `chat_id` e `message_thread_id`, o wizard pergunta:

- se o agente já tem grupo Telegram;
- se o grupo já tem tópico específico para WhatsApp Engineer.

Sequência do wizard:

1. Entrega 📨
   - canal de entrega;
   - chat_id;
   - message_thread_id;
   - formato de áudio;
   - incluir contato;
   - incluir origem/grupo;
   - incluir data/hora.
2. Sincronia ⚡
   - ativar near-real-time;
   - intervalo do live-watch;
   - baixar mídia;
   - transcrever áudio;
   - debounce de entrega.
3. Áudio e transcrição 🎙️
   - modelo;
   - idioma;
   - tarefa transcribe/translate;
   - entrega automática.
4. Formatação 🧾
   - timezone;
   - formato de data;
   - prefixo para grupo;
   - prefixo para conversa direta.
5. Segurança operacional 🔒
   - single-number ownership;
   - exigir operador antes do QR;
   - validade do QR.

Saída:

```text
~/.openclaw/state/whatsapp-engineer/settings.json
~/.openclaw/state/whatsapp-engineer/.first-run-complete
```

O wizard não salva tokens nem segredos.

## Settings Do Usuário

A skill não deve hardcodar entrega ou sincronia. Preferências do usuário ficam em:

```text
~/.openclaw/state/whatsapp-engineer/settings.json
```

Comandos oficiais:

```bash
python3 ~/.openclaw/skills/whatsapp-engineer/workspace/run.py settings --init
python3 ~/.openclaw/skills/whatsapp-engineer/workspace/run.py settings
python3 ~/.openclaw/skills/whatsapp-engineer/workspace/run.py settings-wizard
```

O wizard pergunta uma coisa por vez e salva campos como:

- canal de entrega;
- `chat_id` e `message_thread_id`;
- formato da entrega de áudio;
- se inclui contato/origem/data;
- sincronia near-real-time;
- intervalo do live-watch;
- download de mídia;
- transcrição automática;
- modelo/idioma de transcrição;
- timezone/formato PT-BR.

Nenhum token deve ser salvo nesse arquivo. Segredos continuam em variáveis de ambiente/secret manager.

## Engine Baileys V2

A arquitetura de produção recomendada agora é Baileys dentro da própria skill, não o gateway WhatsApp nativo e não a bridge Go/whatsmeow como caminho principal.

Comandos oficiais:

```bash
python3 ~/.openclaw/skills/whatsapp-engineer/workspace/run.py connect
python3 ~/.openclaw/skills/whatsapp-engineer/workspace/run.py status-v2
python3 ~/.openclaw/skills/whatsapp-engineer/workspace/run.py history-search-v2 --year 2026 --limit 100
```

Estado da engine Baileys:

```text
~/.openclaw/state/whatsapp-engineer/baileys/
  auth/
  messages.db
  qr.png
  status.json
  worker.log
```

Regra de produção: use uma única engine por número. Para evitar logout cruzado, não rode o gateway WhatsApp nativo e a sessão Baileys da skill conectados ao mesmo número ao mesmo tempo.

O fluxo Go/whatsmeow fica legado/fallback até a migração Baileys estar totalmente validada.

### 2. Read WhatsApp

Para mensagens novas em tempo real, o gateway WhatsApp nativo do OpenClaw pode receber mensagens, mas ele nao expoe busca historica.

Para historico antigo, use o `whatsapp-mcp-local-kit` em modo perfis. Preferencialmente use o MCP `whatsapp-profiles` embutido na skill quando ele estiver registrado/anexado ao agente:

- `list_profiles` para descobrir perfis e status de DB.
- `search_profile_messages` para um perfil especifico.
- `search_all_profile_messages` para varios perfis.
- `list_profile_assets` e `list_all_profile_assets` para links, documentos, imagens, videos e audios.
- `download_profile_media` para baixar midia fisica quando necessario.

O MCP le `messages.db` local mesmo com a bridge fechada. Downloads de midia exigem que a bridge do perfil esteja aberta.

O MCP embutido fica em `embedded_mcp/whatsapp_profiles/stdio_server.py` e nao depende de `pip`, `uv` ou pacote externo para pesquisar mensagens/assets em SQLite. A tool `download_profile_media` fica limitada quando a bridge HTTP do kit nao estiver aberta.

Se o MCP nao estiver configurado/anexado neste runtime, use a leitura direta da skill:

```bash
python3 ~/.openclaw/skills/whatsapp-engineer/workspace/run.py status
python3 ~/.openclaw/skills/whatsapp-engineer/workspace/run.py connect --project Equipe --name Principal --number PHONE_E164
python3 ~/.openclaw/skills/whatsapp-engineer/workspace/run.py history-search --year 2026 --limit 100
```

Use `--chat-name`, `--chat-jid`, `--profile`, `--query`, `--phone-number`, `--after` e `--before` para reduzir o volume antes de resumir.

### 3. Handle Audio

Quando o resumo exigir audio:

1. Liste audios com `list_profile_assets` ou `list_all_profile_assets`.
2. Baixe o audio com `download_profile_media` se `local_path` estiver vazio.
3. Transcreva o arquivo usando `scripts/transcribe_audio.py`.
4. Inclua no resumo apenas o trecho relevante, horario, remetente, chat e confianca quando disponivel.

Setup opcional para dependencias nativas:

```bash
python3 ~/.openclaw/skills/whatsapp-engineer/scripts/setup_transcription.py
```

Transcricao direta:

```bash
python3 ~/.openclaw/skills/whatsapp-engineer/scripts/transcribe_audio.py caminho/do/audio.ogg --language pt --model tiny
```

### 4. Build Digest

Use `references/digest-format.md` para montar a resposta. O resumo deve priorizar:

- principais pontos;
- decisoes;
- pendencias com responsavel e prazo;
- riscos ou bloqueios;
- audios importantes;
- links e arquivos acionaveis;
- origem: perfil, chat/grupo e periodo.

### 5. Deliver

Use `references/destinations.md`.

Destinos suportados no config:

- Telegram: grupo, canal ou topico/forum via `chat_id` e `message_thread_id` opcional.
- WhatsApp: grupo, chat direto, lista/canal ou outro `chat_jid`, desde que exista tool/adaptador de envio.
- Discord: canal via webhook ou bot adapter.
- Manual/custom: gerar o resumo e deixar a publicacao pendente ou delegar para outro conector.

Regras gerais:

- nunca grave bot tokens, webhook URLs ou credenciais no config;
- use nomes de variaveis de ambiente para segredos;
- divida mensagens longas conforme o limite da plataforma;
- confirme o destino antes da primeira publicacao em grupo real.

Para WhatsApp como destino:

- usar somente se houver adaptador de envio configurado;
- confirmar com o usuario antes de qualquer envio;
- observar que o MCP `whatsapp-profiles` atual do kit e focado em leitura/download e nao expoe envio por perfil.

## Safety Rules

- Nunca publique mensagens privadas, audios ou telefones em grupo amplo sem checar o destino.
- Nunca salve tokens, QR Codes, sessoes, `.db`, logs reais ou midias privadas dentro da pasta da skill.
- Para envio em WhatsApp, exigir confirmacao explicita.
- Para Telegram, confirmar o `chat_id` e `message_thread_id` quando houver topicos.
- Se a consulta retornar muitos dados, reduza por periodo, chat ou perfil antes de resumir.
- O tempo de entrega Telegram medido pela skill e o tempo da chamada HTTP ao Bot API; ele nao garante o momento exato em que todos os usuarios visualizaram a mensagem.

## Resources

- `scripts/configure.py`: wizard interativo para criar `config.json`.
- `scripts/configure_history_mcp.py`: configura paths do `whatsapp-mcp-local-kit` e opcionalmente registra o MCP `whatsapp-profiles`.
- `scripts/pair_whatsapp_qr.py`: gera QR de pareamento e mantem a sessao viva enquanto o usuario escaneia.
- `scripts/search_history.py`: consulta historico antigo direto dos `messages.db` dos perfis.
- `scripts/setup_embedded_mcp.py`: registra o MCP `whatsapp-profiles` embutido na skill.
- `embedded_mcp/whatsapp_profiles/stdio_server.py`: servidor MCP stdio local, sem dependencias externas, para historico SQLite.
- `workspace/run.py`: entrada operacional oficial da skill; use este wrapper para comandos em vez de chamar scripts internos diretamente.
- `scripts/test_delivery.py`: gera payload de teste Telegram e, com `--send`, envia e mede latencia.
- `scripts/setup_transcription.py`: instala `faster-whisper` em venv isolada para transcricao nativa.
- `scripts/transcribe_audio.py`: transcreve audios localmente dentro da skill.
- `references/config.md`: schema e exemplos de configuracao.
- `references/digest-format.md`: formato recomendado do resumo.
- `references/destinations.md`: regras de entrega em Telegram, WhatsApp e outros destinos.
- `references/multiple-profiles.md`: como conectar e analisar varios numeros de funcionarios.
- `references/transcription.md`: setup e uso da transcricao nativa.
- `references/prd.html`: PRD completo em HTML para produto, wizard, destinos e criterios de aceite.
