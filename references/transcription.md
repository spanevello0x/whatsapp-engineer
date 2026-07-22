# Native Audio Transcription

WhatsApp Engineer transcreve audio nativamente com `scripts/transcribe_audio.py`.

## Setup

Instalar dependencias em venv isolada:

```bash
python3 ~/.openclaw/workspace/skills/whatsapp-engineer/scripts/setup_transcription.py
```

O setup cria:

```text
~/.openclaw/state/whatsapp-engineer/transcription-venv
```

Ele instala `faster-whisper`. Isso pode baixar pacotes e modelos na primeira execucao.

## Transcrever Um Audio

Usando Python do ambiente atual:

```bash
python3 ~/.openclaw/workspace/skills/whatsapp-engineer/scripts/transcribe_audio.py audio.ogg --language pt --model tiny
```

Usando a venv isolada:

```bash
~/.openclaw/state/whatsapp-engineer/transcription-venv/bin/python \
  ~/.openclaw/workspace/skills/whatsapp-engineer/scripts/transcribe_audio.py \
  audio.ogg --language pt --model tiny
```

Saida texto:

```bash
python3 ~/.openclaw/workspace/skills/whatsapp-engineer/scripts/transcribe_audio.py audio.ogg --format text
```

## Config

Campos recomendados:

```json
{
  "audio": {
    "transcribe": true,
    "engine": "native-faster-whisper",
    "script": "~/.openclaw/workspace/skills/whatsapp-engineer/scripts/transcribe_audio.py",
    "language": "pt",
    "model": "tiny",
    "task": "transcribe"
  }
}
```

## Operational Rules

- Preferir `tiny` ou `base` em maquinas pequenas.
- Usar `language: auto` quando o idioma dos audios variar.
- Nao salvar audios privados na pasta da skill.
- Apagar arquivos temporarios depois da transcricao quando nao forem mais necessarios.
- A transcricao e local; ela nao envia audio para API externa.
