#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { DatabaseSync } from 'node:sqlite';
import {
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  makeWASocket,
  useMultiFileAuthState,
  downloadMediaMessage,
  getContentType
} from '@whiskeysockets/baileys';
import P from 'pino';

function arg(name, def=null) { const i=process.argv.indexOf(`--${name}`); return i>=0 && i+1<process.argv.length ? process.argv[i+1] : def; }
const messageId = arg('message-id');
if (!messageId) { console.error('usage: download_baileys_media.mjs --message-id <id>'); process.exit(2); }
const HOME=process.env.HOME||process.cwd();
const STATE_DIR=process.env.WHATSAPP_ENGINEER_STATE_DIR||path.join(HOME,'.openclaw/state/whatsapp-engineer/baileys');
const AUTH_DIR=path.join(STATE_DIR,'auth');
const DB_PATH=path.join(STATE_DIR,'messages.db');
const MEDIA_DIR=path.join(STATE_DIR,'media');
fs.mkdirSync(MEDIA_DIR,{recursive:true});
const db=new DatabaseSync(DB_PATH);
try { db.exec('ALTER TABLE messages ADD COLUMN local_path TEXT'); } catch {}
const row=db.prepare('select id, chat_jid, sender, timestamp, media_type, filename, raw_json from messages where id=?').get(messageId);
if (!row) { console.log(JSON.stringify({ok:false,error:'message_not_found',message_id:messageId},null,2)); process.exit(2); }
function safeName(v){return String(v||'').replace(/[^a-zA-Z0-9_.@-]+/g,'_').slice(0,180)}
function ext(mediaType, filename){ if(filename&&filename.includes('.')) return filename.split('.').pop(); if(mediaType==='audio') return 'ogg'; if(mediaType==='image') return 'jpg'; if(mediaType==='video') return 'mp4'; return 'bin'; }
function getMsgObj(){ try { const raw=JSON.parse(row.raw_json||'{}'); return raw; } catch { return {}; } }
const raw=getMsgObj();
const key=raw.key || { remoteJid: row.chat_jid, id: row.id, fromMe: false };
const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
const { version } = await fetchLatestBaileysVersion();
const logger=P({level:'silent'});
const sock=makeWASocket({ version, logger, printQRInTerminal:false, markOnlineOnConnect:false, auth:{creds:state.creds, keys:makeCacheableSignalKeyStore(state.keys, logger)} });
sock.ev.on('creds.update', saveCreds);
let done=false;
const timeout=setTimeout(()=>{ if(!done){ console.log(JSON.stringify({ok:false,error:'timeout_waiting_open'},null,2)); try{sock.end()}catch{}; process.exit(3);} }, 30000);
sock.ev.on('connection.update', async ({connection,lastDisconnect})=>{
  if(connection==='open'){
    try{
      let msg=null;
      if (typeof sock.loadMessage === 'function') {
        msg = await sock.loadMessage(row.chat_jid, row.id);
      }
      if(!msg && typeof sock.fetchMessage === 'function') {
        msg = await sock.fetchMessage(row.chat_jid, row.id);
      }
      if(!msg){ throw new Error('Baileys socket has no cached message object for this id; cannot reconstruct encrypted media from DB metadata only'); }
      const day=String(row.timestamp||new Date().toISOString()).slice(0,10);
      const outDir=path.join(MEDIA_DIR,day,safeName(row.chat_jid)); fs.mkdirSync(outDir,{recursive:true});
      const out=path.join(outDir,`${safeName(row.id)}.${ext(row.media_type,row.filename)}`);
      const buf=await downloadMediaMessage(msg,'buffer',{}, {logger, reuploadRequest: sock.updateMediaMessage});
      fs.writeFileSync(out,buf);
      db.prepare('update messages set local_path=? where id=?').run(out,row.id);
      done=true; clearTimeout(timeout); console.log(JSON.stringify({ok:true,local_path:out,bytes:buf.length,message_id:row.id},null,2)); try{sock.end()}catch{}; process.exit(0);
    }catch(e){ done=true; clearTimeout(timeout); console.log(JSON.stringify({ok:false,error:String(e?.message||e),message_id:row.id},null,2)); try{sock.end()}catch{}; process.exit(4); }
  }
  if(connection==='close'){
    const status=lastDisconnect?.error?.output?.statusCode;
    if(status===DisconnectReason.loggedOut){ done=true; clearTimeout(timeout); console.log(JSON.stringify({ok:false,error:'logged_out'},null,2)); process.exit(5); }
  }
});
