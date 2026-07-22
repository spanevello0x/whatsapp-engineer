# Embedded WhatsApp Profiles MCP

Servidor MCP `whatsapp-profiles` embutido na skill.

Ele consulta `profiles.json` e os bancos `messages.db` gerados pelo `whatsapp-mcp-local-kit` em modo perfis.

Dados e sessoes NAO ficam nesta pasta:

- `profiles.json`
- `whatsapp.db`
- `messages.db`
- logs
- QR Codes
- midias

Use `scripts/setup_embedded_mcp.py` para criar a venv local em `~/.openclaw/state/whatsapp-engineer/mcp-venv` e registrar o MCP no OpenClaw.
