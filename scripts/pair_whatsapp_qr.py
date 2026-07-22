#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path.home() / ".openclaw" / "state" / "whatsapp-engineer"
DEFAULT_RUNTIME_DIR = Path.home() / ".openclaw" / "plugin-runtime-deps" / "openclaw-2026.4.26-67e811bb8931"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate WhatsApp QR and keep the login session alive until scanned.")
    parser.add_argument("--account", default="default", help="OpenClaw WhatsApp account id/profile to pair.")
    parser.add_argument("--qr-timeout-ms", type=int, default=30_000, help="Timeout waiting for QR generation.")
    parser.add_argument("--scan-timeout-ms", type=int, default=180_000, help="How long to keep the QR session alive for scanning.")
    parser.add_argument("--force", action="store_true", help="Force a fresh QR/login attempt.")
    parser.add_argument("--out", type=Path, default=None, help="Output PNG path. Defaults to state dir.")
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR, help="OpenClaw plugin runtime dependency dir.")
    args = parser.parse_args()

    api_path = args.runtime_dir / "dist" / "extensions" / "whatsapp" / "login-qr-api.js"
    if not api_path.exists():
        print(json.dumps({"event": "error", "message": f"WhatsApp QR runtime not found: {api_path}"}), flush=True)
        return 1

    output = args.out
    if output is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = STATE_DIR / "qr" / f"whatsapp-pair-{args.account}-{stamp}.png"
    output.parent.mkdir(parents=True, exist_ok=True)

    node_code = f"""
import {{ startWebLoginWithQr, waitForWebLogin }} from {json.dumps(str(api_path))};
const accountId = {json.dumps(args.account)};
const started = await startWebLoginWithQr({{
  accountId,
  force: {str(bool(args.force)).lower()},
  timeoutMs: {int(args.qr_timeout_ms)},
  verbose: false
}});
if (!started.qrDataUrl) {{
  console.log(JSON.stringify({{ event: 'done', ok: !!started.connected, connected: !!started.connected, message: started.message || 'QR not generated' }}));
  process.exit(started.connected ? 0 : 2);
}}
console.log(JSON.stringify({{ event: 'qr', ok: true, message: started.message, qrDataUrl: started.qrDataUrl }}));
const waited = await waitForWebLogin({{
  accountId,
  timeoutMs: {int(args.scan_timeout_ms)},
  currentQrDataUrl: started.qrDataUrl
}});
console.log(JSON.stringify({{ event: 'done', ok: !!waited.connected, connected: !!waited.connected, message: waited.message || null, qrRefreshed: !!waited.qrDataUrl }}));
process.exit(waited.connected ? 0 : 3);
"""

    proc = subprocess.Popen(
        ["node", "--input-type=module", "-e", node_code],
        cwd=str(args.runtime_dir),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ.copy(),
        bufsize=1,
    )

    assert proc.stdout is not None
    for raw_line in proc.stdout:
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps({"event": "log", "message": line}, ensure_ascii=False), flush=True)
            continue
        if event.get("event") == "qr" and event.get("qrDataUrl"):
            data_url = str(event["qrDataUrl"])
            prefix = "data:image/png;base64,"
            if data_url.startswith(prefix):
                output.write_bytes(base64.b64decode(data_url[len(prefix):]))
                os.chmod(output, 0o600)
                print(json.dumps({"event": "qr", "ok": True, "output": str(output), "message": event.get("message")}, ensure_ascii=False), flush=True)
            else:
                print(json.dumps({"event": "error", "message": "QR payload is not PNG data URL"}), flush=True)
        elif event.get("event") == "done":
            print(json.dumps(event, ensure_ascii=False), flush=True)
        else:
            safe = {k: v for k, v in event.items() if k != "qrDataUrl"}
            print(json.dumps(safe, ensure_ascii=False), flush=True)

    err = ""
    if proc.stderr is not None:
        err = proc.stderr.read().strip()
    code = proc.wait()
    if err:
        print(json.dumps({"event": "stderr", "message": err[-2000:]}, ensure_ascii=False), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
