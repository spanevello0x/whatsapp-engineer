# Digest Format

Use PT-BR direto e operacional. Evite texto longo quando houver pouca atividade.

## Telegram HTML Template

```html
<b>Resumo WhatsApp</b>
<b>Periodo:</b> {periodo}
<b>Origem:</b> {perfil} / {chat}

<b>Principais pontos</b>
- {ponto}

<b>Pendencias</b>
- <b>{responsavel}</b>: {acao} {prazo}

<b>Decisoes</b>
- {decisao}

<b>Audios</b>
- {hora}, {remetente}: {resumo_transcricao}

<b>Links e arquivos</b>
- {titulo_ou_nome}: {url_ou_descricao}

<b>Riscos</b>
- {risco}
```

## Rules

- Sempre indicar periodo e origem.
- Consolidar mensagens repetidas em um unico ponto.
- Separar fato de inferencia. Use "Parece que" quando for inferencia.
- Para audio, incluir horario, remetente e resumo; transcricao literal so quando for curta ou solicitada.
- Para grupos ativos, limitar a mensagem principal e adicionar "Detalhes omitidos por volume" quando necessario.
- Para Telegram, dividir mensagens acima de 3500 caracteres.
