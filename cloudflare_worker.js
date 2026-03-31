/**
 * Cloudflare Worker — Webhook Bridge: Evolution API → GitHub Actions
 *
 * Variáveis de ambiente (Cloudflare Worker Secrets):
 *   GITHUB_TOKEN   - Personal Access Token com permissão repo/workflow
 *   GITHUB_OWNER   - Dono do repositório (ex: igorbonifacio-IBnet)
 *   GITHUB_REPO    - Nome do repositório (ex: Pessoal)
 *   WPP_SECRET     - Segredo opcional para validar webhook (deixe vazio para desativar)
 *
 * Como fazer deploy:
 *   1. Acesse https://workers.cloudflare.com e crie um novo Worker
 *   2. Cole este código no editor
 *   3. Vá em Settings > Variables e adicione as variáveis acima como Secrets
 *   4. Salve e publique — copie a URL gerada (ex: https://financas-wpp.SEU_USUARIO.workers.dev)
 *   5. Configure essa URL no Evolution API como webhook endpoint
 */

export default {
  async fetch(request, env) {
    // Aceita apenas POST
    if (request.method !== 'POST') {
      return new Response('Method Not Allowed', { status: 405 });
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return new Response('Invalid JSON', { status: 400 });
    }

    // Validação opcional de segredo (header x-webhook-secret)
    if (env.WPP_SECRET) {
      const secret = request.headers.get('x-webhook-secret') || '';
      if (secret !== env.WPP_SECRET) {
        return new Response('Unauthorized', { status: 401 });
      }
    }

    // Extrai dados da mensagem do Evolution API
    // Suporta formato v1 e v2 do Evolution API
    const event = body.event || body.type || '';

    // Ignora eventos que não são mensagens recebidas
    const validEvents = ['messages.upsert', 'message', 'MESSAGES_UPSERT'];
    if (validEvents.length > 0 && !validEvents.some(e => event.includes(e) || event === e)) {
      // Aceita mesmo sem evento reconhecido para compatibilidade
    }

    const msgData = body.data || body;
    const key     = msgData.key || {};
    const msg     = msgData.message || {};

    // Ignora mensagens enviadas pelo próprio bot
    if (key.fromMe === true) {
      return new Response('OK', { status: 200 });
    }

    // Extrai texto da mensagem (vários formatos do Evolution API)
    const text = (
      msg.conversation ||
      msg.extendedTextMessage?.text ||
      msg.imageMessage?.caption ||
      msg.documentMessage?.caption ||
      msg.videoMessage?.caption ||
      ''
    ).trim();

    // Extrai URL de mídia (imagem/comprovante)
    let mediaUrl  = '';
    let mediaMime = '';
    const imgMsg = msg.imageMessage || msg.documentMessage || msg.videoMessage;
    if (imgMsg) {
      // O Evolution API pode fornecer a URL da mídia diretamente
      mediaUrl  = imgMsg.url || imgMsg.directPath || '';
      mediaMime = imgMsg.mimetype || 'image/jpeg';
    }

    // Se não tem texto nem mídia, ignora
    if (!text && !mediaUrl) {
      return new Response('OK', { status: 200 });
    }

    const from      = key.remoteJid || '';
    const timestamp = msgData.messageTimestamp || Math.floor(Date.now() / 1000);
    const msgShort  = text.substring(0, 50).replace(/[^\w\s\-.,]/g, '') || 'comprovante';

    // Dispara o GitHub Actions via repository_dispatch
    const owner = env.GITHUB_OWNER || 'igorbonifacio-IBnet';
    const repo  = env.GITHUB_REPO  || 'Pessoal';

    const ghResponse = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/dispatches`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
          'Accept':        'application/vnd.github.v3+json',
          'Content-Type':  'application/json',
          'User-Agent':    'CloudflareWorker-WPP-Bridge/1.0',
        },
        body: JSON.stringify({
          event_type: 'whatsapp_message',
          client_payload: {
            message:       text,
            message_short: msgShort,
            from:          from,
            media_url:     mediaUrl,
            media_mime:    mediaMime,
            timestamp:     String(timestamp),
          },
        }),
      }
    );

    if (!ghResponse.ok) {
      const errBody = await ghResponse.text();
      console.error(`GitHub dispatch failed: ${ghResponse.status} - ${errBody}`);
      return new Response('GitHub Error', { status: 502 });
    }

    console.log(`Dispatched: from=${from} text="${msgShort}" media=${mediaUrl ? 'yes' : 'no'}`);
    return new Response('OK', { status: 200 });
  },
};
