#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import os from 'node:os';
import { spawnSync } from 'node:child_process';
import ffmpeg from '@ffmpeg-installer/ffmpeg';
import wavefile from 'wavefile';
const { WaveFile } = wavefile;

function arg(name, def=null) {
  const idx = process.argv.indexOf(`--${name}`);
  if (idx >= 0 && idx + 1 < process.argv.length) return process.argv[idx + 1];
  return def;
}

const positional = [];
for (let i = 2; i < process.argv.length; i++) {
  const v = process.argv[i];
  if (v.startsWith('--')) { i++; continue; }
  positional.push(v);
}
const audio = positional[0];
const model = arg('model', process.env.WHATSAPP_ENGINEER_TRANSCRIBE_MODEL || 'Xenova/whisper-tiny');
const language = arg('language', process.env.WHATSAPP_ENGINEER_TRANSCRIBE_LANGUAGE || 'portuguese');
const task = arg('task', 'transcribe');
const format = arg('format', 'json');
const cacheDir = process.env.TRANSFORMERS_CACHE || path.join(process.env.HOME || '.', '.openclaw/state/whatsapp-engineer/transformers-cache');

if (!audio) {
  console.error('usage: node transcribe_audio_node.mjs <audio> [--model Xenova/whisper-tiny] [--language portuguese] [--format json|text]');
  process.exit(2);
}
if (!fs.existsSync(audio)) {
  console.error(`audio file not found: ${audio}`);
  process.exit(2);
}
fs.mkdirSync(cacheDir, { recursive: true });
process.env.TRANSFORMERS_CACHE = cacheDir;

function decodeToFloat32(input) {
  const tmp = path.join(os.tmpdir(), `whatsapp-engineer-${process.pid}-${Date.now()}.wav`);
  const r = spawnSync(ffmpeg.path, ['-y', '-i', input, '-ac', '1', '-ar', '16000', '-f', 'wav', tmp], { encoding: 'utf8' });
  if (r.status !== 0) {
    throw new Error(`ffmpeg failed: ${r.stderr || r.stdout}`);
  }
  const wav = new WaveFile(fs.readFileSync(tmp));
  wav.toBitDepth('32f');
  wav.toSampleRate(16000);
  const samples = wav.getSamples(true, Float32Array);
  try { fs.unlinkSync(tmp); } catch {}
  return samples;
}

const started = Date.now();
const audioData = decodeToFloat32(audio);
const { pipeline, env } = await import('@xenova/transformers');
env.cacheDir = cacheDir;
env.allowLocalModels = true;
env.allowRemoteModels = true;

const transcriber = await pipeline('automatic-speech-recognition', model, { cache_dir: cacheDir });
const result = await transcriber(audioData, {
  sampling_rate: 16000,
  language,
  task,
  chunk_length_s: 30,
  stride_length_s: 5,
});
const text = typeof result === 'string' ? result : (result?.text || '');
if (format === 'text') {
  console.log(text.trim());
} else {
  console.log(JSON.stringify({ ok: true, text: text.trim(), model, language, task, audio, duration_ms: Date.now() - started }, null, 2));
}
