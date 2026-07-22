#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_faster_whisper() -> Any:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        message = (
            "Dependencia ausente: faster-whisper.\n"
            "Rode:\n"
            "  python3 ~/.openclaw/workspace/skills/whatsapp-engineer/scripts/setup_transcription.py\n"
            "Depois use o Python da venv gerada ou instale faster-whisper no ambiente atual."
        )
        raise SystemExit(message) from exc
    return WhisperModel


def normalize_language(language: str) -> str | None:
    language = language.strip()
    if not language or language.lower() == "auto":
        return None
    return language


def transcribe(args: argparse.Namespace) -> dict[str, Any]:
    audio_path = Path(args.audio).expanduser().resolve()
    if not audio_path.exists():
        raise SystemExit(f"Audio nao encontrado: {audio_path}")

    WhisperModel = load_faster_whisper()
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    segments_iter, info = model.transcribe(
        str(audio_path),
        language=normalize_language(args.language),
        task=args.task,
        beam_size=args.beam_size,
        vad_filter=args.vad_filter,
    )

    segments: list[dict[str, Any]] = []
    parts: list[str] = []
    for segment in segments_iter:
        text = segment.text.strip()
        if text:
            parts.append(text)
        segments.append(
            {
                "id": segment.id,
                "start": round(float(segment.start), 3),
                "end": round(float(segment.end), 3),
                "text": text,
            }
        )

    return {
        "audio_path": str(audio_path),
        "engine": "native-faster-whisper",
        "model": args.model,
        "task": args.task,
        "requested_language": args.language,
        "detected_language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
        "text": " ".join(parts).strip(),
        "segments": segments,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Native audio transcription for WhatsApp Engineer.")
    parser.add_argument("audio", help="Audio file path.")
    parser.add_argument("--model", default="tiny", help="Whisper model size/name. Example: tiny, base, small.")
    parser.add_argument("--language", default="pt", help="Language code or auto.")
    parser.add_argument("--task", choices=["transcribe", "translate"], default="transcribe", help="Whisper task.")
    parser.add_argument("--device", default="cpu", help="Device: cpu, cuda, auto.")
    parser.add_argument("--compute-type", default="int8", help="Compute type for faster-whisper.")
    parser.add_argument("--beam-size", type=int, default=5, help="Beam size.")
    parser.add_argument("--vad-filter", action="store_true", help="Enable VAD filtering.")
    parser.add_argument("--format", choices=["json", "text"], default="json", help="Output format.")
    args = parser.parse_args()

    result = transcribe(args)
    if args.format == "text":
        print(result["text"])
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
