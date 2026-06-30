/**
 * wa_bridge.js — WhatsApp Web Bridge v3.0
 * Protocol: stdout=JSON events, stdin=JSON commands
 * Features: QR login, session permanen, quoted reply, read receipt, typing indicator
 */

const { Client, LocalAuth, MessageMedia, MessageTypes } = require('whatsapp-web.js');
const qrcode  = require('qrcode-terminal');
const fs      = require('fs');
const path    = require('path');
const readline= require('readline');

const SESSION_PATH = path.join(__dirname, 'data', 'wa_session');
const TYPING_WPM   = parseInt(process.env.TYPING_WPM || '250');

function emit(type, data) {
  process.stdout.write(JSON.stringify({ type, data, ts: Date.now() }) + '\n');
}
function log(msg) { process.stderr.write('[WA] ' + msg + '\n'); }

function typingDelay(text) {
  const words   = (text || '').length / 5;
  const minutes = words / TYPING_WPM;
  const ms      = Math.round(minutes * 60 * 1000);
  return Math.max(1000, Math.min(15000, ms));
}

// ─── Client ───────────────────────────────────────────────────────────────────

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: SESSION_PATH, clientId: 'pedia-agent' }),
  puppeteer: {
    headless: true,
    args: [
      '--no-sandbox','--disable-setuid-sandbox',
      '--disable-dev-shm-usage','--disable-accelerated-2d-canvas',
      '--no-first-run','--no-zygote','--single-process','--disable-gpu',
    ],
    executablePath: process.env.CHROME_PATH || undefined,
  },
  webVersion: '2.3000.1014901952',
  webVersionCache: {
    type: 'remote',
    remotePath: 'https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/2.3000.1014901952.html',
  },
});

// ─── Events ───────────────────────────────────────────────────────────────────

client.on('qr', (qr) => {
  process.stderr.write('\n');
  process.stderr.write('╔════════════════════════════════════════╗\n');
  process.stderr.write('║   PEDIA AI AGENT — WhatsApp Login      ║\n');
  process.stderr.write('║   Scan QR Code ini dengan WhatsApp     ║\n');
  process.stderr.write('╚════════════════════════════════════════╝\n\n');
  qrcode.generate(qr, { small: true }, (qrStr) => { process.stderr.write(qrStr + '\n'); });
  emit('qr', { qr });
});

client.on('loading_screen', (percent, message) => {
  log('Loading ' + percent + '% - ' + message);
  emit('loading', { percent, message });
});

client.on('authenticated', () => {
  log('Authenticated!');
  emit('authenticated', {});
});

client.on('auth_failure', (msg) => {
  log('Auth failure: ' + msg);
  emit('auth_failure', { message: msg });
});

client.on('ready', async () => {
  const info = client.info;
  log('Ready! ' + info.wid.user + ' (' + info.pushname + ')');
  emit('ready', { phone: info.wid.user, name: info.pushname, platform: info.platform });
});

client.on('disconnected', (reason) => {
  log('Disconnected: ' + reason);
  emit('disconnected', { reason });
});

// ─── Message events ───────────────────────────────────────────────────────────

client.on('message', async (msg) => {
  if (msg.fromMe) return;
  if (msg.isStatus) return;
  if (msg.type === 'revoked') return;

  try {
    const chat    = await msg.getChat();
    const contact = await msg.getContact();
    const isGroup = chat.isGroup;

    // Read receipt
    await chat.sendSeen();

    let quotedBody = null;
    if (msg.hasQuotedMsg) {
      try {
        const quoted = await msg.getQuotedMessage();
        quotedBody = quoted.body || null;
      } catch(e) {}
    }

    // Media info
    let mediaPath = null;
    let mediaMime = null;
    if (msg.hasMedia) {
      try {
        const media = await msg.downloadMedia();
        if (media) {
          const ext = media.mimetype.split('/')[1].split(';')[0];
          const fname = 'data/media_' + Date.now() + '.' + ext;
          fs.writeFileSync(fname, media.data, 'base64');
          mediaPath = fname;
          mediaMime = media.mimetype;
        }
      } catch(e) { log('Media download error: ' + e.message); }
    }

    const payload = {
      id:          msg.id._serialized,
      from:        msg.from,
      to:          msg.to,
      body:        msg.body || '',
      type:        msg.type,
      isGroup,
      groupId:     isGroup ? chat.id._serialized : null,
      groupName:   isGroup ? chat.name : null,
      senderId:    contact.id.user,
      senderName:  contact.pushname || contact.name || contact.number,
      senderPhone: contact.number,
      timestamp:   msg.timestamp,
      hasMedia:    msg.hasMedia,
      mediaPath,
      mediaMime,
      quotedBody,
    };

    emit('message', payload);
  } catch(e) {
    log('message handler error: ' + e.message);
  }
});

// ─── Command handler ──────────────────────────────────────────────────────────

const cmdFutures = {};

readline.createInterface({ input: process.stdin }).on('line', async (line) => {
  let cmd;
  try { cmd = JSON.parse(line.trim()); } catch(e) { return; }
  const { id, type, data } = cmd;
  try {
    let result = null;

    if (type === 'send_message') {
      const chat = await client.getChatById(data.to);

      // Typing indicator
      await chat.sendStateTyping();
      const delay = typingDelay(data.message || '');
      await new Promise(r => setTimeout(r, delay));
      await chat.clearState();

      // Quoted reply
      if (data.quote_id) {
        try {
          const messages = await chat.fetchMessages({ limit: 50 });
          const target   = messages.find(m => m.id._serialized === data.quote_id);
          if (target) {
            await target.reply(data.message);
            result = { ok: true };
          }
        } catch(e) {}
      }
      if (!result) {
        await chat.sendMessage(data.message);
        result = { ok: true };
      }

    } else if (type === 'send_image') {
      const chat  = await client.getChatById(data.to);
      const media = MessageMedia.fromFilePath(data.path);
      await chat.sendStateTyping();
      await new Promise(r => setTimeout(r, 1500));
      await chat.clearState();
      await chat.sendMessage(media, { caption: data.caption || '' });
      result = { ok: true };

    } else if (type === 'get_groups') {
      const chats  = await client.getChats();
      const groups = chats.filter(c => c.isGroup).map(g => ({
        id: g.id._serialized, name: g.name,
        participants: g.participants ? g.participants.length : 0
      }));
      result = { groups };

    } else if (type === 'get_info') {
      result = { phone: client.info?.wid?.user, name: client.info?.pushname };

    } else if (type === 'ping') {
      result = { pong: true };
    }

    emit('cmd_result', { id, ok: true, result });
  } catch(e) {
    log('cmd error: ' + e.message);
    emit('cmd_result', { id, ok: false, error: e.message });
  }
});

// ─── Init ─────────────────────────────────────────────────────────────────────

log('Initializing...');
client.initialize();

process.on('SIGINT',  async () => { await client.destroy(); process.exit(0); });
process.on('SIGTERM', async () => { await client.destroy(); process.exit(0); });
