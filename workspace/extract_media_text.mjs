#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

function arg(name, def = '') {
  const i = process.argv.indexOf(`--${name}`);
  if (i >= 0 && process.argv[i + 1]) return process.argv[i + 1];
  return def;
}

const file = process.argv[2];
const kind = (arg('kind', '') || '').toLowerCase();
const lang = arg('lang', 'por+eng');
const maxChars = Number(arg('max-chars', '12000')) || 12000;
const timeoutNote = 'Use limites baixos no pipeline; OCR de imagem é CPU-bound.';

if (!file) {
  console.error('usage: node extract_media_text.mjs <file> --kind image|document [--lang por+eng] [--max-chars 12000]');
  process.exit(2);
}

const p = path.resolve(file);
if (!fs.existsSync(p)) {
  console.log(JSON.stringify({ ok: false, error: 'file_missing', path: p }, null, 2));
  process.exit(2);
}

function trim(text) {
  return String(text || '').replace(/\s+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim().slice(0, maxChars);
}

async function extractPdf() {
  const { PDFParse } = await import('pdf-parse');
  const buffer = fs.readFileSync(p);
  const parser = new PDFParse({ data: buffer });
  try {
    const result = await parser.getText();
    return { ok: true, kind: 'pdf_text', text: trim(result?.text || ''), pages: result?.total || null };
  } finally {
    await parser.destroy?.();
  }
}

async function extractImage() {
  const { createWorker } = await import('tesseract.js');
  const worker = await createWorker(lang, 1, {
    logger: () => {},
    cachePath: path.join(process.env.HOME || process.cwd(), '.cache', 'openclaw-tesseract'),
  });
  try {
    const result = await worker.recognize(p);
    return {
      ok: true,
      kind: 'image_ocr',
      text: trim(result?.data?.text || ''),
      confidence: result?.data?.confidence ?? null,
      note: timeoutNote,
    };
  } finally {
    await worker.terminate();
  }
}

try {
  const ext = path.extname(p).toLowerCase();
  let out;
  if (kind === 'document' || ext === '.pdf') {
    if (ext !== '.pdf') out = { ok: false, error: 'unsupported_document_type', ext };
    else out = await extractPdf();
  } else if (kind === 'image' || ['.jpg', '.jpeg', '.png', '.webp'].includes(ext)) {
    out = await extractImage();
  } else {
    out = { ok: false, error: 'unsupported_media_type', kind, ext };
  }
  console.log(JSON.stringify(out, null, 2));
  process.exit(out.ok ? 0 : 2);
} catch (err) {
  console.log(JSON.stringify({ ok: false, error: 'extraction_failed', detail: String(err?.stack || err).slice(0, 2000) }, null, 2));
  process.exit(1);
}
