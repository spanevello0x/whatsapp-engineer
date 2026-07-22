#!/usr/bin/env node
import process from 'node:process';
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { randomBytes } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import QRCode from 'qrcode';
import {
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  makeWASocket,
  useMultiFileAuthState,
  getContentType,
  downloadMediaMessage
} from '@whiskeysockets/baileys';
import P from 'pino';

const HOME = process.env.HOME || process.cwd();
const STATE_DIR = process.env.WHATSAPP_ENGINEER_STATE_DIR || path.join(HOME, '.openclaw/state/whatsapp-engineer/baileys');
const AUTH_DIR = process.env.WHATSAPP_ENGINEER_AUTH_DIR || path.join(STATE_DIR, 'auth');
const DB_PATH = process.env.WHATSAPP_ENGINEER_DB_PATH || path.join(STATE_DIR, 'messages.db');
const QR_PATH = process.env.WHATSAPP_ENGINEER_QR_PATH || path.join(STATE_DIR, 'qr.png');
const STATUS_PATH = process.env.WHATSAPP_ENGINEER_STATUS_PATH || path.join(STATE_DIR, 'status.json');
const MEDIA_DIR = process.env.WHATSAPP_ENGINEER_MEDIA_DIR || path.join(STATE_DIR, 'media');
const LOG_LEVEL = process.env.WHATSAPP_ENGINEER_BAILEYS_LOG_LEVEL || 'silent';
const ADMIN_HOST = process.env.WHATSAPP_ENGINEER_ADMIN_HOST || '127.0.0.1';
const ADMIN_PORT = Number(process.env.WHATSAPP_ENGINEER_ADMIN_PORT || 18791);
const ADMIN_TOKEN_PATH = process.env.WHATSAPP_ENGINEER_ADMIN_TOKEN_PATH || path.join(STATE_DIR, 'admin-token');
const ADMIN_ALLOW_WRITES = process.env.WHATSAPP_ENGINEER_ADMIN_ALLOW_WRITES === '1';

for (const dir of [STATE_DIR, AUTH_DIR, path.dirname(DB_PATH), path.dirname(QR_PATH), MEDIA_DIR, path.dirname(ADMIN_TOKEN_PATH)]) fs.mkdirSync(dir, { recursive: true });

const db = new DatabaseSync(DB_PATH);
db.exec(`
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS chats (
  jid TEXT PRIMARY KEY,
  name TEXT,
  last_message_time TEXT
);
CREATE TABLE IF NOT EXISTS messages (
  id TEXT,
  chat_jid TEXT,
  sender TEXT,
  content TEXT,
  timestamp TEXT,
  is_from_me INTEGER,
  media_type TEXT,
  filename TEXT,
  url TEXT,
  file_length INTEGER,
  raw_json TEXT,
  local_path TEXT,
  PRIMARY KEY (id, chat_jid)
);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_jid);
`);
try { db.exec('ALTER TABLE messages ADD COLUMN local_path TEXT'); } catch {}
const upsertChat = db.prepare('INSERT OR REPLACE INTO chats (jid, name, last_message_time) VALUES (?, ?, ?)');
const upsertMessage = db.prepare(`INSERT OR REPLACE INTO messages
(id, chat_jid, sender, content, timestamp, is_from_me, media_type, filename, url, file_length, raw_json, local_path)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`);

function ensureAdminToken() {
  if (fs.existsSync(ADMIN_TOKEN_PATH)) return fs.readFileSync(ADMIN_TOKEN_PATH, 'utf8').trim();
  const token = randomBytes(32).toString('hex');
  fs.writeFileSync(ADMIN_TOKEN_PATH, token, { mode: 0o600 });
  try { fs.chmodSync(ADMIN_TOKEN_PATH, 0o600); } catch {}
  return token;
}

const ADMIN_TOKEN = ensureAdminToken();

function writeStatus(extra) {
  const payload = {
    updated_at: new Date().toISOString(),
    db_path: DB_PATH,
    auth_dir: AUTH_DIR,
    qr_path: QR_PATH,
    admin_api: {
      enabled: true,
      host: ADMIN_HOST,
      port: ADMIN_PORT,
      token_path: ADMIN_TOKEN_PATH,
      writes_enabled: ADMIN_ALLOW_WRITES
    },
    ...extra
  };
  fs.writeFileSync(STATUS_PATH, JSON.stringify(payload, null, 2));
}

function tsToIso(value) {
  if (!value) return new Date().toISOString();
  const n = Number(value);
  if (Number.isFinite(n)) return new Date(n * 1000).toISOString();
  return new Date().toISOString();
}

function textFromMessage(message) {
  if (!message) return '';
  const m = message.ephemeralMessage?.message || message.viewOnceMessage?.message || message.viewOnceMessageV2?.message || message;
  return m.conversation
    || m.extendedTextMessage?.text
    || m.imageMessage?.caption
    || m.videoMessage?.caption
    || m.documentMessage?.caption
    || m.buttonsResponseMessage?.selectedDisplayText
    || m.listResponseMessage?.title
    || m.templateButtonReplyMessage?.selectedDisplayText
    || '';
}

function mediaInfo(message) {
  if (!message) return { mediaType: '', filename: '', url: '', fileLength: 0 };
  const m = message.ephemeralMessage?.message || message.viewOnceMessage?.message || message.viewOnceMessageV2?.message || message;
  const type = getContentType(m) || '';
  const mm = m[type] || {};
  let mediaType = '';
  if (type.includes('image')) mediaType = 'image';
  else if (type.includes('video')) mediaType = 'video';
  else if (type.includes('audio')) mediaType = 'audio';
  else if (type.includes('document')) mediaType = 'document';
  else if (type.includes('sticker')) mediaType = 'sticker';
  return {
    mediaType,
    filename: mm.fileName || mm.title || '',
    url: mm.url || '',
    fileLength: Number(mm.fileLength || 0) || 0
  };
}

function safeName(value) {
  return String(value || '').replace(/[^a-zA-Z0-9_.@-]+/g, '_').slice(0, 180);
}

function mediaExt(mediaType, filename) {
  if (filename && filename.includes('.')) return filename.split('.').pop().toLowerCase();
  if (mediaType === 'audio') return 'ogg';
  if (mediaType === 'image') return 'jpg';
  if (mediaType === 'video') return 'mp4';
  if (mediaType === 'document') return 'bin';
  if (mediaType === 'sticker') return 'webp';
  return 'bin';
}

async function maybeDownloadMedia(msg, media, chatJid, id) {
  if (!media.mediaType) return '';
  try {
    const ext = mediaExt(media.mediaType, media.filename);
    const day = tsToIso(msg.messageTimestamp).slice(0, 10);
    const dir = path.join(MEDIA_DIR, day, safeName(chatJid));
    fs.mkdirSync(dir, { recursive: true });
    const out = path.join(dir, `${safeName(id)}.${ext}`);
    if (!fs.existsSync(out)) {
      const buf = await downloadMediaMessage(msg, 'buffer', {}, { logger: P({ level: LOG_LEVEL }), reuploadRequest: sock?.updateMediaMessage });
      fs.writeFileSync(out, buf);
    }
    return out;
  } catch (err) {
    console.error('[downloadMedia]', err?.stack || err);
    return '';
  }
}

async function storeMessage(msg, source = 'upsert') {
  try {
    const chatJid = msg.key?.remoteJid || '';
    const id = msg.key?.id || '';
    if (!chatJid || !id || chatJid === 'status@broadcast') return;
    const sender = msg.key?.fromMe ? (sock?.user?.id?.split(':')[0] || 'me') : (msg.key?.participant || chatJid || '').split('@')[0];
    const timestamp = tsToIso(msg.messageTimestamp);
    const content = textFromMessage(msg.message);
    const media = mediaInfo(msg.message);
    if (!content && !media.mediaType) return;
    const localPath = await maybeDownloadMedia(msg, media, chatJid, id);
    const chatName = msg.pushName || chatJid.split('@')[0];
    upsertChat.run(chatJid, chatName, timestamp);
    upsertMessage.run(id, chatJid, sender, content, timestamp, msg.key?.fromMe ? 1 : 0, media.mediaType, media.filename, media.url, media.fileLength, JSON.stringify({ source, key: msg.key, messageTimestamp: msg.messageTimestamp, pushName: msg.pushName }), localPath);
  } catch (err) {
    console.error('[storeMessage]', err?.stack || err);
  }
}

function jsonResponse(res, status, payload) {
  const body = JSON.stringify(payload, null, 2);
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(body)
  });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.setEncoding('utf8');
    req.on('data', (chunk) => {
      data += chunk;
      if (data.length > 128 * 1024) reject(new Error('request body too large'));
    });
    req.on('end', () => {
      if (!data.trim()) return resolve({});
      try { resolve(JSON.parse(data)); }
      catch (err) { reject(new Error(`invalid json: ${err.message}`)); }
    });
    req.on('error', reject);
  });
}

function bearerToken(req) {
  const auth = req.headers.authorization || '';
  if (auth.startsWith('Bearer ')) return auth.slice('Bearer '.length).trim();
  return String(req.headers['x-admin-token'] || '').trim();
}

function requireAdminAuth(req, res) {
  if (bearerToken(req) === ADMIN_TOKEN) return true;
  jsonResponse(res, 401, { ok: false, error: 'unauthorized' });
  return false;
}

function normalizeGroupJid(value) {
  const raw = String(value || '').trim();
  if (!raw) throw new Error('groupJid is required');
  if (raw.endsWith('@g.us')) return raw;
  const digits = raw.replace(/\D/g, '');
  if (!digits) throw new Error(`invalid groupJid: ${raw}`);
  return `${digits}@g.us`;
}

function normalizeParticipantJid(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  if (raw.includes('@')) return raw;
  const digits = raw.replace(/\D/g, '');
  if (!digits) return '';
  return `${digits}@s.whatsapp.net`;
}

function normalizeParticipants(value) {
  const arr = Array.isArray(value) ? value : [value];
  return [...new Set(arr.map(normalizeParticipantJid).filter(Boolean))];
}

function summarizeParticipant(participant) {
  const phoneNumber = participant?.phoneNumber || participant?.phone_number || '';
  return {
    id: participant?.id || participant?.jid || '',
    jid: participant?.jid || participant?.id || '',
    phone_number: phoneNumber,
    lid: participant?.lid || participant?.lidJid || '',
    admin: participant?.admin || null,
    name: participant?.name || participant?.notify || participant?.verifiedName || '',
    raw: participant
  };
}

function summarizeJoinRequest(req) {
  const phoneNumber = req?.phone_number || req?.phoneNumber || '';
  return {
    jid: req?.jid || req?.participant || req?.id || '',
    phone_number: phoneNumber,
    lid: req?.lid || req?.lidJid || '',
    request_method: req?.request_method || req?.requestMethod || req?.method || '',
    request_time: req?.request_time || req?.requestTime || req?.t || null,
    raw: req
  };
}

function requireOpenSocket() {
  if (!sock?.user) throw new Error('WhatsApp socket is not open');
  return sock;
}

async function adminGroupSnapshot(body) {
  const active = requireOpenSocket();
  const groupJid = normalizeGroupJid(body.groupJid || body.jid || body.group);
  const [metadataResult, requestsResult] = await Promise.allSettled([
    body.includeMembers === false ? null : active.groupMetadata(groupJid),
    body.includePending === false ? null : active.groupRequestParticipantsList(groupJid)
  ]);
  const metadata = metadataResult.status === 'fulfilled' ? metadataResult.value : null;
  const requests = requestsResult.status === 'fulfilled' ? requestsResult.value : [];
  return {
    ok: true,
    group_jid: groupJid,
    subject: metadata?.subject || '',
    owner: metadata?.owner || '',
    desc: metadata?.desc || '',
    member_count: metadata?.participants?.length || 0,
    members: (metadata?.participants || []).map(summarizeParticipant),
    pending_requests: (requests || []).map(summarizeJoinRequest),
    errors: {
      members: metadataResult.status === 'rejected' ? String(metadataResult.reason?.stack || metadataResult.reason) : null,
      pending_requests: requestsResult.status === 'rejected' ? String(requestsResult.reason?.stack || requestsResult.reason) : null
    }
  };
}

async function adminRequestUpdate(body) {
  const active = requireOpenSocket();
  const groupJid = normalizeGroupJid(body.groupJid || body.jid || body.group);
  const action = String(body.action || '').trim();
  if (!['approve', 'reject'].includes(action)) throw new Error('action must be approve or reject');
  const participants = normalizeParticipants(body.participants || body.participant);
  if (!participants.length) throw new Error('participants are required');
  const dryRun = body.dryRun !== false || body.execute !== true;
  if (dryRun) return { ok: true, dryRun: true, group_jid: groupJid, action, participants };
  if (!ADMIN_ALLOW_WRITES) throw new Error('admin writes disabled; set WHATSAPP_ENGINEER_ADMIN_ALLOW_WRITES=1 to execute');
  const result = await active.groupRequestParticipantsUpdate(groupJid, participants, action);
  return { ok: true, dryRun: false, group_jid: groupJid, action, participants, result };
}

async function adminParticipantsUpdate(body) {
  const active = requireOpenSocket();
  const groupJid = normalizeGroupJid(body.groupJid || body.jid || body.group);
  const action = String(body.action || '').trim();
  if (!['remove'].includes(action)) throw new Error('only remove is exposed by this admin endpoint');
  const participants = normalizeParticipants(body.participants || body.participant);
  if (!participants.length) throw new Error('participants are required');
  const dryRun = body.dryRun !== false || body.execute !== true;
  if (dryRun) return { ok: true, dryRun: true, group_jid: groupJid, action, participants };
  if (!ADMIN_ALLOW_WRITES) throw new Error('admin writes disabled; set WHATSAPP_ENGINEER_ADMIN_ALLOW_WRITES=1 to execute');
  const result = await active.groupParticipantsUpdate(groupJid, participants, action);
  return { ok: true, dryRun: false, group_jid: groupJid, action, participants, result };
}

function startAdminServer() {
  const server = http.createServer(async (req, res) => {
    try {
      if (!requireAdminAuth(req, res)) return;
      const url = new URL(req.url || '/', `http://${ADMIN_HOST}:${ADMIN_PORT}`);
      if (req.method === 'GET' && url.pathname === '/admin/status') {
        return jsonResponse(res, 200, {
          ok: true,
          state: sock?.user ? 'open' : 'not-open',
          user: sock?.user || null,
          writes_enabled: ADMIN_ALLOW_WRITES
        });
      }
      if (req.method !== 'POST') return jsonResponse(res, 405, { ok: false, error: 'method not allowed' });
      const body = await readBody(req);
      if (url.pathname === '/admin/group-snapshot') return jsonResponse(res, 200, await adminGroupSnapshot(body));
      if (url.pathname === '/admin/group-request-update') return jsonResponse(res, 200, await adminRequestUpdate(body));
      if (url.pathname === '/admin/group-participants-update') return jsonResponse(res, 200, await adminParticipantsUpdate(body));
      return jsonResponse(res, 404, { ok: false, error: 'not found' });
    } catch (err) {
      return jsonResponse(res, 500, { ok: false, error: String(err?.message || err), stack: process.env.WHATSAPP_ENGINEER_ADMIN_DEBUG === '1' ? String(err?.stack || err) : undefined });
    }
  });
  server.listen(ADMIN_PORT, ADMIN_HOST, () => {
    console.log(JSON.stringify({ event: 'admin.open', host: ADMIN_HOST, port: ADMIN_PORT, token_path: ADMIN_TOKEN_PATH, writes_enabled: ADMIN_ALLOW_WRITES }));
  });
  server.on('error', (err) => {
    console.error('[admin.server]', err?.stack || err);
    writeStatus({ admin_api_error: String(err?.message || err) });
    adminServer = null;
    setTimeout(() => {
      if (!adminServer) adminServer = startAdminServer();
    }, 5000);
  });
  return server;
}

let sock;
let adminServer;
let signalsRegistered = false;

function registerSignalHandlers() {
  if (signalsRegistered) return;
  signalsRegistered = true;
  process.on('SIGTERM', () => { writeStatus({ state: 'stopping' }); try { adminServer?.close?.(); } catch {} try { sock?.end?.(); } catch {} process.exit(0); });
  process.on('SIGINT', () => { writeStatus({ state: 'stopping' }); try { adminServer?.close?.(); } catch {} try { sock?.end?.(); } catch {} process.exit(0); });
}

async function main() {
  writeStatus({ state: 'starting' });
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();
  const logger = P({ level: LOG_LEVEL });
  sock = makeWASocket({
    version,
    logger,
    printQRInTerminal: false,
    browser: ['whatsapp-engineer', 'Chrome', '1.8.0'],
    syncFullHistory: process.env.WHATSAPP_ENGINEER_SYNC_FULL_HISTORY === '1',
    markOnlineOnConnect: false,
    auth: { creds: state.creds, keys: makeCacheableSignalKeyStore(state.keys, logger) }
  });
  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      await QRCode.toFile(QR_PATH, qr, { type: 'png', width: 768, margin: 2 });
      writeStatus({ state: 'qr', connection, qr_path: QR_PATH });
      console.log(JSON.stringify({ event: 'qr', qr_path: QR_PATH }));
    }
    if (connection === 'open') {
      writeStatus({ state: 'open', connection, user: sock.user });
      console.log(JSON.stringify({ event: 'open', user: sock.user }));
    }
    if (connection === 'close') {
      const status = lastDisconnect?.error?.output?.statusCode;
      writeStatus({ state: 'close', connection, status, logged_out: status === DisconnectReason.loggedOut });
      console.log(JSON.stringify({ event: 'close', status }));
      if (status === 440) {
        console.error('[connection] conflict 440; exiting to avoid reconnect storm');
        setTimeout(() => process.exit(0), 1000);
        return;
      }
      if (status !== DisconnectReason.loggedOut) setTimeout(() => main().catch(console.error), 5000);
    }
  });
  sock.ev.on('messaging-history.set', async ({ chats, messages, isLatest }) => {
    let stored = 0;
    for (const chat of chats || []) {
      const jid = chat.id || chat.jid;
      if (jid) upsertChat.run(jid, chat.name || chat.subject || jid.split('@')[0], chat.conversationTimestamp ? tsToIso(chat.conversationTimestamp) : null);
    }
    for (const msg of messages || []) { await storeMessage(msg, 'history'); stored++; }
    writeStatus({ state: 'history', history_latest: Boolean(isLatest), history_batch_messages: messages?.length || 0 });
    console.log(JSON.stringify({ event: 'history', messages: messages?.length || 0, stored, isLatest }));
  });
  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    let stored = 0;
    for (const msg of messages || []) { await storeMessage(msg, type || 'upsert'); stored++; }
    if (stored) console.log(JSON.stringify({ event: 'messages.upsert', type, stored }));
  });
  if (!adminServer) adminServer = startAdminServer();
  registerSignalHandlers();
}

main().catch((err) => { writeStatus({ state: 'error', error: String(err?.stack || err) }); console.error(err); process.exit(1); });
