#!/usr/bin/env python3
from __future__ import annotations
import json, os
from pathlib import Path
from settings import DEFAULT_SETTINGS, SETTINGS_PATH, save_settings, load_settings, ask, ask_bool, normalize_model, parse_telegram_topic_link

FIRST_RUN_FLAG = Path.home() / '.openclaw/state/whatsapp-engineer/.first-run-complete'

def main() -> int:
    settings = load_settings()
    print('Vou configurar a WhatsApp Engineer em 6 passos. ⚙️')
    print('')
    print('1. Definir onde vou entregar mensagens, resumos e transcrições.')
    print('2. Ajustar como a sincronia do WhatsApp vai funcionar.')
    print('3. Escolher como áudios serão baixados e transcritos.')
    print('4. Definir o formato das mensagens entregues.')
    print('5. Validar a regra de segurança: uma skill dona de um número.')
    print('6. Salvar tudo em settings.json e orientar a conexão via QR.')
    print('')
    print('Vou perguntar uma coisa por vez. Você pode aceitar os padrões quando quiser.')
    print('Nenhum token ou segredo será salvo aqui; segredos continuam em env/secret manager. 🔒\n')

    d=settings['delivery']; sync=settings['sync']; audio=settings['audio']; fmt=settings['formatting']; safety=settings['safety']

    print('Etapa 1/5 — Entrega 📨')
    d['type']=ask('Onde devo entregar os resumos/transcrições? telegram/discord/manual 📨', d.get('type','telegram')).lower()
    if d['type']=='telegram':
        print('\nPara entregar em tópico Telegram, você precisa de um grupo com tópicos ativados. 🧵')
        print('Passo a passo rápido:')
        print('1. Crie um grupo no Telegram para o agente, por exemplo: AGENT HUB.')
        print('2. Adicione o bot/agente no grupo.')
        print('3. Abra as configurações do grupo e ative Tópicos/Fórum, se ainda não estiver ativo.')
        print('4. Crie um tópico para WhatsApp, por exemplo: WhatsApp Engineer.')
        print('5. Envie qualquer mensagem dentro desse tópico.')
        print('6. Toque/segure na mensagem e escolha Copiar link.')
        print('7. Cole esse link aqui no wizard. A skill tenta descobrir o chat_id e o tópico automaticamente.\n')
        has_group = ask_bool('Você já criou um grupo no Telegram para este agente/bot? 👥', bool(d.get('chat_id')))
        if not has_group:
            print('Crie o grupo, adicione o bot/agente e depois volte para continuar. Se você já souber os IDs, pode continuar preenchendo manualmente. 🛠️')
        has_topic = ask_bool('Esse grupo já tem um tópico específico para WhatsApp Engineer? 🧵', bool(d.get('message_thread_id')))
        if not has_topic:
            print('Crie o tópico no grupo antes da operação final. Se quiser entregar no grupo principal sem tópico, deixe o message_thread_id vazio. 📌')
        link = ask('Cole aqui o link de uma mensagem do tópico Telegram, se tiver. 🔗', '')
        parsed_chat, parsed_thread = parse_telegram_topic_link(link)
        if parsed_chat:
            print(f'Consegui detectar automaticamente: chat_id={parsed_chat} e tópico={parsed_thread}. ✅')
        d['chat_id']=ask('Confirme o chat_id do Telegram. Se ficou vazio, peça ajuda ao suporte/administrador. 🧭', parsed_chat or d.get('chat_id',''))
        d['message_thread_id']=ask('Confirme o ID do tópico. Use vazio se for entregar no grupo principal sem tópico. 🧵', parsed_thread or d.get('message_thread_id',''))
    d['audio_template']=ask('Qual formato de entrega de áudio? clean/debug/custom 🎙️', d.get('audio_template','clean'))
    d['include_contact']=ask_bool('Incluir nome/número do contato? 👤', bool(d.get('include_contact',True)))
    d['include_origin']=ask_bool('Incluir origem, usando nome do grupo quando houver? 👥', bool(d.get('include_origin',True)))
    d['include_datetime']=ask_bool('Incluir data/hora em PT-BR? 🕒', bool(d.get('include_datetime',True)))

    print('\nEtapa 2/5 — Sincronia ⚡')
    sync['enabled']=ask_bool('Ativar sincronia near-real-time? ⚡', bool(sync.get('enabled',True)))
    sync['poll_interval_seconds']=int(ask('A cada quantos segundos o live-watch deve verificar novidades? 🔁', sync.get('poll_interval_seconds',3)) or 3)
    sync['media_download']=ask_bool('Baixar mídias automaticamente? 📎', bool(sync.get('media_download',True)))
    sync['audio_transcription']=ask_bool('Transcrever áudios automaticamente? 🎧', bool(sync.get('audio_transcription',True)))
    sync['delivery_debounce_seconds']=int(ask('Quantos segundos aguardar antes de entregar, para evitar duplicidade? ⏱️', sync.get('delivery_debounce_seconds',2)) or 2)

    print('\nEtapa 3/5 — Áudio e transcrição 🎙️')
    audio['model']=normalize_model(ask('Qual modelo de transcrição? tiny/base/small ou id completo 🧠', audio.get('model','Xenova/whisper-tiny')))
    audio['language']=ask('Qual idioma principal dos áudios? pt/portuguese/auto 🌎', audio.get('language','pt'))
    audio['task']=ask('A tarefa padrão é transcribe ou translate? 📝', audio.get('task','transcribe'))
    audio['auto_deliver_transcription']=ask_bool('Entregar transcrição automaticamente no destino configurado? 🚀', bool(audio.get('auto_deliver_transcription',True)))

    print('\nEtapa 4/5 — Formatação 🧾')
    fmt['timezone']=ask('Qual timezone usar na entrega? 🕒', fmt.get('timezone','UTC'))
    fmt['datetime_format']=ask('Formato de data/hora? pt-BR/iso 📅', fmt.get('datetime_format','pt-BR'))
    fmt['group_origin_prefix']=ask('Prefixo para origem de grupo? 👥', fmt.get('group_origin_prefix','grupo'))
    fmt['direct_origin_prefix']=ask('Prefixo para conversa direta? 💬', fmt.get('direct_origin_prefix','conversa direta com'))

    print('\nEtapa 5/5 — Segurança operacional 🔒')
    safety['single_number_owner']=ask_bool('Confirmar que esta skill será dona única do número WhatsApp? 🔒', bool(safety.get('single_number_owner',True)))
    safety['require_operator_for_qr']=ask_bool('Exigir operador pronto antes de gerar QR? 🧩', bool(safety.get('require_operator_for_qr',True)))
    safety['qr_valid_seconds']=int(ask('Por quantos segundos considerar o QR válido? ⏳', safety.get('qr_valid_seconds',60)) or 60)

    settings['delivery']=d; settings['sync']=sync; settings['audio']=audio; settings['formatting']=fmt; settings['safety']=safety
    save_settings(settings)
    FIRST_RUN_FLAG.parent.mkdir(parents=True, exist_ok=True)
    FIRST_RUN_FLAG.write_text('complete\n', encoding='utf-8')
    print(f'\n✅ Configuração inicial concluída. settings.json salvo em: {SETTINGS_PATH}')
    print('\nPróximos passos:')
    print('1. Rodar: run.py connect')
    print('2. Escanear o QR em até 45–60s')
    print('3. Validar: run.py status-v2')
    print('4. Testar áudio: run.py deliver-latest-audio --dry-run')
    return 0

if __name__=='__main__': raise SystemExit(main())
