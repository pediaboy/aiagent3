/**
 * wa_bridge.js — WhatsApp Web Bridge
 * 
 * Menggunakan whatsapp-web.js untuk koneksi WhatsApp.
 * Berkomunikasi dengan Python via stdin/stdout JSON protocol.
 * 
 * Protocol:
 * - STDOUT: JSON events {"type":"...", "data":{...}}
 * - STDIN:  JSON commands {"id":"...", "type":"...", "data":{...}}
 */

const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

// ─── Config ──────────────────────────────────────────────────────────────────

const SESSION_PATH = path.join(__dirname, 'data', 'wa_session');
const TYPING_WPM   = parseInt(process.env.TYPING_WPM || '300');  // kata per menit

// ─── Output helpers ──────────────────────────────────────────────────────────

function emit(type, data) {
  const line = JSON.stringify({ type, data, ts: Date.now() });
  process.stdout.write(line + '\n');
}

function log(msg) {
  process.stderr.write('[WA] ' + msg + '\n');
}

// ─── Typing simulation ────────────────────────────────────────────────────────

function typingDelay(text) {
  // Hitung delay berdasarkan panjang teks
  // WPM rata-rata manusia: 200-400 wpm, rata-rata 5 char/kata
  const words    = text.length / 5;
  const minutes  = words / TYPING_WPM;
  const ms       = Math.round(minutes * 60 * 1000);
  // Clamp antara 800ms - 6000ms
  return Math.max(800, Math.min(6000, ms));
}

// ─── WhatsApp Client ─────────────────────────────────────────────────────────

const client = new Client({
  authStrategy: new LocalAuth({
    dataPath: SESSION_PATH,
    clientId: 'pedia-agent'
  }),
  puppeteer: {
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-accelerated-2d-canvas',
      '--no-first-run',
      '--no-zygote',
      '--single-process',
      '--disable-gpu',
      '--disable-web-security',
      '--disable-features=IsolateOrigins,site-per-process',
    ],
    executablePath: process.env.CHROME_PATH || undefined,
  },
  webVersion: '2.3000.1014901952',
  webVersionCache: {
    type: 'remote',
    remotePath: 'https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/2.3000.1014901952.html',
  },
});

// ─── Events ──────────────────────────────────────────────────────────────────

client.on('qr', (qr) => {
  log('QR Code received, display in terminal...');
  
  // Tampilkan QR di terminal (stderr agar tidak mix dengan stdout protocol)
  process.stderr.write('\n');
  process.stderr.write('════════════════════════════════════════\n');
  process.stderr.write('  PEDIA AI AGENT — WhatsApp Login\n');
  process.stderr.write('  Scan QR Code ini dengan WhatsApp kamu\n');
  process.stderr.write('════════════════════════════════════════\n\n');
  qrcode.generate(qr, { small: true }, (qrStr) => {
    process.stderr.write(qrStr + '\n');
  });
  process.stderr.write('\n');
  
  // Emit ke Python juga
  emit('qr', { qr });
});

client.on('loading_screen', (percent, message) => {
  log('Loading: ' + percent + '% - ' + message);
  emit('loading', { percent, message });
});

client.on('authenticated', () => {
  log('Authenticated! Session disimpan.');
  emit('authenticated', {});
});

client.on('auth_failure', (msg) => {
  log('Auth failure: ' + msg);
  emit('auth_failure', { message: msg });
});

client.on('ready', async () => {
  log('WhatsApp siap!');
  const info = client.info;
  emit('ready', {
    phone: info.wid.user,
    name:  info.pushname,
    platform: info.platform,
  });
});

client.on('disconnected', (reason) => {
  log('Disconnected: ' + reason);
  emit('disconnected', { reason });
});

// ─── Message Handler ──────────────────────────────────────────────────────────

client.on('message_create', async (msg) => {
  // Skip pesan dari diri sendiri
  if (msg.fromMe) return;
  // Skip status broadcast
  if (msg.isStatus) return;
  // Skip system messages
  if (msg.type === 'revoked') return;

  const chat    = await msg.getChat();
  const contact = await msg.getContact();
  const isGroup = chat.isGroup;
  
  const payload = {
    id:          msg.id._serialized,
    from:        msg.from,
    to:          msg.to,
    body:        msg.body || '',
    type:        msg.type,
    isGroup:     isGroup,
    groupId:     isGroup ? chat.id._serialized : null,
    groupName:   isGroup ? chat.name : null,
    senderId:    contact.id.user,
    senderName:  contact.pushname || contact.name || contact.number,
    senderPhone: contact.number,
    timestamp:   msg.timestamp,
    hasMedia:    msg.hasMedia,
    quotedMsg:   msg.hasQuotedMsg ? (await msg.getQuotedMessage()).body : null,
  };
  
  emit('message', payload);
});

// ─── Command Handler (from Python via stdin) ──────────────────────────────────

const pendingReplies = {};  // id -> {resolve, reject}

readline.createInterface({ input: process.stdin }).on('line', async (line) => {
  let cmd;
  try {
    cmd = JSON.parse(line.trim());
  } catch (e) {
    log('Invalid command JSON: ' + line);
    return;
  }
  
  const { id, type, data } = cmd;
  
  try {
    let result = null;
    
    if (type === 'send_message') {
      const chat = await client.getChatById(data.to);
      
      // Typing indicator
      await chat.sendStateTyping();
      
      // Delay sesuai panjang pesan (simulasi mengetik)
      const delay = typingDelay(data.message);
      await new Promise(r => setTimeout(r, delay));
      
      await chat.clearState();
      await chat.sendMessage(data.message);
      result = { ok: true };
      
    } else if (type === 'send_image') {
      const chat = await client.getChatById(data.to);
      const media = MessageMedia.fromFilePath(data.path);
      
      await chat.sendStateTyping();
      await new Promise(r => setTimeout(r, 1000));
      await chat.clearState();
      await chat.sendMessage(media, { caption: data.caption || '' });
      result = { ok: true };
      
    } else if (type === 'get_groups') {
      const chats = await client.getChats();
      const groups = chats
        .filter(c => c.isGroup)
        .map(g => ({ id: g.id._serialized, name: g.name, participants: g.participants?.length }));
      result = { groups };
      
    } else if (type === 'get_info') {
      result = {
        phone: client.info?.wid?.user,
        name:  client.info?.pushname,
      };
      
    } else if (type === 'ping') {
      result = { pong: true };
    }
    
    emit('cmd_result', { id, ok: true, result });
    
  } catch (e) {
    log('Command error: ' + e.message);
    emit('cmd_result', { id, ok: false, error: e.message });
  }
});

// ─── Start ────────────────────────────────────────────────────────────────────

log('Initializing WhatsApp client...');
client.initialize();

// Graceful shutdown
process.on('SIGINT', async () => {
  log('Shutting down...');
  await client.destroy();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  await client.destroy();
  process.exit(0);
});
