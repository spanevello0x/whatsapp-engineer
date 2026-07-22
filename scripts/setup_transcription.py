#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import venv
from pathlib import Path


DEFAULT_VENV = Path.home() / ".openclaw" / "state" / "whatsapp-engineer" / "transcription-venv"


def bin_path(venv_dir: Path, name: str) -> Path:
    if sys.platform.startswith("win"):
        return venv_dir / "Scripts" / f"{name}.exe"
    return venv_dir / "bin" / name


def main() -> int:
    parser = argparse.ArgumentParser(description="Set up native transcription dependencies for WhatsApp Engineer.")
    parser.add_argument("--venv", type=Path, default=DEFAULT_VENV, help="Virtualenv path.")
    parser.add_argument("--upgrade", action="store_true", help="Upgrade installed packages.")
    args = parser.parse_args()

    args.venv.parent.mkdir(parents=True, exist_ok=True)
    if not args.venv.exists():
        print(f"Criando venv: {args.venv}")
        venv.EnvBuilder(with_pip=True).create(args.venv)

    python = bin_path(args.venv, "python")
    pip = [str(python), "-m", "pip"]
    install_cmd = pip + ["install"]
    if args.upgrade:
        install_cmd.append("--upgrade")
    install_cmd += ["faster-whisper>=1.1.0"]

    print("Instalando dependencias de transcricao nativa...")
    subprocess.check_call(pip + ["install", "--upgrade", "pip"])
    subprocess.check_call(install_cmd)
    print("\nOK.")
    print(f"Use este Python para transcrever: {python}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
