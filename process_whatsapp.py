#!/usr/bin/env python3
"""
Processa mensagens do WhatsApp via Evolution API.
Usa Groq AI para interpretar linguagem natural e registra gastos/receitas
no wpp_transactions.json. Opcionalmente faz upload de comprovantes no Google Drive.

Variáveis de ambiente esperadas (GitHub Secrets):
  GROQ_API_KEY            - Chave da API Groq
  EVOLUTION_API_URL       - URL base do Evolution API (ex: https://seu-evolution.com)
  EVOLUTION_API_TOKEN     - Token de autenticação do Evolution API
  EVOLUTION_INSTANCE      - Nome da instância WhatsApp no Evolution
  GOOGLE_CREDENTIALS      - JSON da service account Google (opcional, para Drive)
  GOOGLE_DRIVE_FOLDER_ID  - ID da pasta no Drive para salvar comprovantes (opcional)
  WPP_MESSAGE             - Mensagem recebida (passada pelo workflow)
  WPP_FROM                - Número do remetente
  WPP_MEDIA_URL           - URL da mídia/comprovante (opcional)
  WPP_MEDIA_MIME          - MIME type da mídia (opcional)
  WPP_TIMESTAMP           - Timestamp da mensagem
"""

import json
import os
import re
import sys
import urllib.request
import urllib.parse
import urllib.error
import base64
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DATA_FILE = Path('data/wpp_transactions.json')

MONTH_MAP = {
    '1': 'MARÇO',   '01': 'MARÇO',   'janeiro': 'MARÇO',
    '2': 'ABRIL',   '02': 'ABRIL',   'fevereiro': 'ABRIL',
    '3': 'MARÇO',   '03': 'MARÇO',   'março': 'MARÇO',   'marco': 'MARÇO',
    '4': 'ABRIL',   '04': 'ABRIL',   'abril': 'ABRIL',
    '5': 'MAIO',    '05': 'MAIO',    'maio': 'MAIO',
    '6': 'JUNHO',   '06': 'JUNHO',   'junho': 'JUNHO',
    '7': 'JULHO',   '07': 'JULHO',   'julho': 'JULHO',
    '8': 'AGOSTO',  '08': 'AGOSTO',  'agosto': 'AGOSTO',
    '9': 'SETEMBRO','09': 'SETEMBRO','setembro': 'SETEMBRO',
    '10': 'OUTUBRO',                 'outubro': 'OUTUBRO',
    '11': 'NOVEMBRO',               'novembro': 'NOVEMBRO',
    '12': 'DEZEMBRO26',             'dezembro': 'DEZEMBRO26',
}

MONTH_CURRENT_DEFAULT = {
    3: 'MARÇO', 4: 'ABRIL', 5: 'MAIO', 6: 'JUNHO',
    7: 'JULHO', 8: 'AGOSTO', 9: 'SETEMBRO', 10: 'OUTUBRO',
    11: 'NOVEMBRO', 12: 'DEZEMBRO26',
}

CARD_MAP = {
    'inter': 'inter', 'nubank igor': 'nubank_igor', 'nubank nath': 'nubank_nath',
    'nubank': 'nubank_igor', 'itau': 'itau', 'itaú': 'itau',
    'caixa': 'caixa', 'bb': 'caixa',
}

CARD_DISPLAY = {
    'inter': 'Inter', 'nubank_igor': 'Nubank Igor', 'nubank_nath': 'Nubank Nath',
    'itau': 'Itaú', 'caixa': 'Caixa',
}

GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL   = 'llama-3.3-70b-versatile'

SYSTEM_PROMPT = """Você é um assistente financeiro pessoal. Analise a mensagem e extraia informações de gasto ou receita.

Retorne SOMENTE um JSON válido com este formato:

Para GASTO:
{
  "tipo": "gasto",
  "desc": "descrição do gasto",
  "val": 99.90,
  "cartao": "inter|nubank_igor|nubank_nath|itau|caixa|null",
  "mes": "MARÇO|ABRIL|MAIO|JUNHO|JULHO|AGOSTO|SETEMBRO|OUTUBRO|NOVEMBRO|DEZEMBRO26|null",
  "status": "Pago|Não pago",
  "parcela": "1/3 (ou vazio)",
  "data": "DD/MM"
}

Para RECEITA:
{
  "tipo": "receita",
  "desc": "descrição da receita",
  "val": 5000.00,
  "mes": "MARÇO|...|null",
  "status": "Recebido|A receber",
  "data": "DD/MM"
}

Para RESUMO (quando pedir saldo, resumo, extrato):
{"tipo": "resumo"}

Para AJUDA (quando não entender):
{"tipo": "ajuda"}

Regras:
- Valores em reais (R$ 45,00 = 45.0, 1.200 = 1200.0)
- Se não mencionar cartão, cartao = null (será gasto fixo)
- Se não mencionar mês, mes = null (usar mês atual)
- Se não mencionar status, gasto = "Não pago", receita = "A receber"
- Exemplos de mensagem e cartão: "nubank", "nu", "inter", "itaú", "caixa"
"""

def groq_parse(message: str) -> dict:
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        raise RuntimeError('GROQ_API_KEY não configurado')

    payload = json.dumps({
        'model': GROQ_MODEL,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': message},
        ],
        'temperature': 0.1,
        'max_tokens': 300,
    }).encode('utf-8')

    req = urllib.request.Request(
        GROQ_API_URL,
        data=payload,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())

    content = resp['choices'][0]['message']['content'].strip()
    # Extrai JSON mesmo que venha com markdown
    m = re.search(r'\{.*\}', content, re.DOTALL)
    if m:
        return json.loads(m.group())
    raise ValueError(f'Resposta inesperada do Groq: {content}')

def send_wpp(to: str, text: str):
    """Envia mensagem de volta pelo Evolution API."""
    api_url   = os.environ.get('EVOLUTION_API_URL', '').rstrip('/')
    api_token = os.environ.get('EVOLUTION_API_TOKEN', '')
    instance  = os.environ.get('EVOLUTION_INSTANCE', '')
    if not all([api_url, api_token, instance]):
        print(f'[WPP reply skipped] {text}')
        return

    url = f'{api_url}/message/sendText/{instance}'
    payload = json.dumps({'number': to, 'text': text}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={
        'apikey': api_token,
        'Content-Type': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f'[WPP reply sent] status={r.status}')
    except Exception as e:
        print(f'[WPP reply error] {e}')

def upload_to_drive(media_url: str, filename: str, mime: str) -> tuple[str, str]:
    """
    Baixa a mídia e faz upload para o Google Drive.
    Retorna (drive_url, thumb_url) ou ('', '') em caso de falha.
    """
    creds_json  = os.environ.get('GOOGLE_CREDENTIALS', '')
    folder_id   = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '')
    if not creds_json or not folder_id:
        print('[Drive] Credenciais não configuradas, pulando upload.')
        return '', ''

    try:
        # Baixa o arquivo de mídia
        req = urllib.request.Request(media_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as r:
            file_bytes = r.read()

        # Gera token de acesso usando service account
        creds = json.loads(creds_json)
        access_token = get_service_account_token(creds, 'https://www.googleapis.com/auth/drive.file')

        # Upload multipart para o Drive
        boundary = 'boundary_wpp_comprovante'
        metadata = json.dumps({'name': filename, 'parents': [folder_id]}).encode('utf-8')
        body = (
            f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'.encode() +
            metadata +
            f'\r\n--{boundary}\r\nContent-Type: {mime}\r\n\r\n'.encode() +
            file_bytes +
            f'\r\n--{boundary}--'.encode()
        )
        upload_req = urllib.request.Request(
            'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,webViewLink',
            data=body,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': f'multipart/related; boundary={boundary}',
            }
        )
        with urllib.request.urlopen(upload_req, timeout=60) as r:
            result = json.loads(r.read())

        file_id   = result['id']
        drive_url = result.get('webViewLink', f'https://drive.google.com/file/d/{file_id}/view')

        # Torna o arquivo público (leitura)
        perm_req = urllib.request.Request(
            f'https://www.googleapis.com/drive/v3/files/{file_id}/permissions',
            data=json.dumps({'role': 'reader', 'type': 'anyone'}).encode(),
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            }
        )
        with urllib.request.urlopen(perm_req, timeout=15):
            pass

        thumb_url = f'https://drive.google.com/thumbnail?id={file_id}&sz=w400'
        print(f'[Drive] Upload OK: {drive_url}')
        return drive_url, thumb_url

    except Exception as e:
        print(f'[Drive] Erro no upload: {e}')
        return '', ''

def get_service_account_token(creds: dict, scope: str) -> str:
    """Obtém access token via JWT para service account do Google."""
    import time
    import hmac
    import hashlib

    now = int(time.time())
    header = base64.urlsafe_b64encode(json.dumps({'alg': 'RS256', 'typ': 'JWT'}).encode()).rstrip(b'=')
    claim  = base64.urlsafe_b64encode(json.dumps({
        'iss': creds['client_email'],
        'scope': scope,
        'aud': 'https://oauth2.googleapis.com/token',
        'exp': now + 3600,
        'iat': now,
    }).encode()).rstrip(b'=')

    signing_input = header + b'.' + claim

    # Usa cryptography se disponível, senão tenta openssl via subprocess
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        private_key = serialization.load_pem_private_key(
            creds['private_key'].encode(), password=None
        )
        signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b'=')
    except ImportError:
        import subprocess, tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
            f.write(creds['private_key'])
            key_path = f.name
        result = subprocess.run(
            ['openssl', 'dgst', '-sha256', '-sign', key_path],
            input=signing_input, capture_output=True
        )
        os.unlink(key_path)
        sig_b64 = base64.urlsafe_b64encode(result.stdout).rstrip(b'=')

    jwt_token = signing_input + b'.' + sig_b64

    token_req = urllib.request.Request(
        'https://oauth2.googleapis.com/token',
        data=urllib.parse.urlencode({
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'assertion': jwt_token.decode(),
        }).encode(),
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    with urllib.request.urlopen(token_req, timeout=15) as r:
        return json.loads(r.read())['access_token']

def load_data() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data: dict):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def ensure_month(data: dict, month: str):
    if month not in data:
        data[month] = {
            'gastos': [], 'receitas': [],
            'inter': [], 'itau': [], 'nubank_igor': [], 'caixa': [], 'nubank_nath': [],
            'comprovantes': [],
            'total_gastos': 0, 'total_receitas': 0,
            'para_pagar': 0, 'para_receber': 0, 'saldo': 0,
        }
    if 'comprovantes' not in data[month]:
        data[month]['comprovantes'] = []

def resolve_month(mes_str) -> str:
    if not mes_str:
        # Usar mês atual
        m = datetime.now(timezone.utc).month
        return MONTH_CURRENT_DEFAULT.get(m, 'MARÇO')
    key = str(mes_str).lower().strip()
    return MONTH_MAP.get(key, 'MARÇO')

def fmt_brl(val: float) -> str:
    return f"R$ {val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def process_message():
    message   = os.environ.get('WPP_MESSAGE', '').strip()
    from_num  = os.environ.get('WPP_FROM', '')
    media_url = os.environ.get('WPP_MEDIA_URL', '')
    media_mime= os.environ.get('WPP_MEDIA_MIME', 'image/jpeg')

    if not message and not media_url:
        print('Mensagem vazia, ignorando.')
        return

    print(f'Mensagem recebida de {from_num}: {message[:80]}')

    # Parse com Groq
    try:
        parsed = groq_parse(message or 'comprovante')
    except Exception as e:
        print(f'Erro ao chamar Groq: {e}')
        send_wpp(from_num, '❌ Não consegui interpretar a mensagem. Tente novamente.')
        return

    tipo = parsed.get('tipo', 'ajuda')
    print(f'Groq interpretou: tipo={tipo} parsed={parsed}')

    data = load_data()

    if tipo == 'resumo':
        month = resolve_month(None)
        md = data.get(month, {})
        total_g = md.get('total_gastos', 0)
        total_r = md.get('total_receitas', 0)
        saldo   = total_r - total_g
        reply = (
            f'📊 *Resumo {month.title()}*\n'
            f'💚 Receitas: {fmt_brl(total_r)}\n'
            f'❤️ Gastos: {fmt_brl(total_g)}\n'
            f'{"🔵" if saldo >= 0 else "🔴"} Saldo: {fmt_brl(saldo)}'
        )
        send_wpp(from_num, reply)
        return

    if tipo == 'ajuda':
        send_wpp(from_num,
            '🤖 *Como registrar:*\n\n'
            '💸 *Gasto:* `gastei 45 no mc donalds nubank igor`\n'
            '💳 *Cartão:* `compra 200 reais itaú`\n'
            '💰 *Receita:* `recebi 5000 salário`\n'
            '📊 *Resumo:* `resumo` ou `saldo`\n\n'
            '_Cartões disponíveis: inter, nubank igor, nubank nath, itaú, caixa_'
        )
        return

    month = resolve_month(parsed.get('mes'))
    ensure_month(data, month)

    # Upload de comprovante se veio mídia
    drive_url, thumb_url = '', ''
    if media_url:
        ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        ext = 'jpg' if 'jpeg' in media_mime else media_mime.split('/')[-1]
        fname = f'comprovante_{ts}.{ext}'
        drive_url, thumb_url = upload_to_drive(media_url, fname, media_mime)

    val = float(parsed.get('val', 0))
    desc = parsed.get('desc', 'Sem descrição')
    status = parsed.get('status', '')
    data_str = parsed.get('data', datetime.now(timezone.utc).strftime('%d/%m'))

    if tipo == 'gasto':
        cartao = parsed.get('cartao') or ''
        # Normaliza nome do cartão
        for alias, key in CARD_MAP.items():
            if alias in (cartao or '').lower():
                cartao = key
                break
        else:
            if cartao not in ('inter', 'itau', 'nubank_igor', 'nubank_nath', 'caixa'):
                cartao = None

        item = {
            'desc': desc,
            'val_str': fmt_brl(val),
            'val': val,
            'data': data_str,
            'status': status or 'Não pago',
            'parc': parsed.get('parcela', ''),
        }
        if drive_url:
            item['comprovante_url'] = drive_url

        if cartao:
            item['cat'] = 'Outros'
            data[month][cartao].append(item)
            card_display = CARD_DISPLAY.get(cartao, cartao)
            reply = f'✅ *Gasto registrado!*\n📝 {desc}\n💳 {card_display}\n💰 {fmt_brl(val)}\n📅 {month.title()}'
        else:
            data[month]['gastos'].append(item)
            reply = f'✅ *Gasto registrado!*\n📝 {desc}\n💰 {fmt_brl(val)}\n📅 {month.title()}'

        if drive_url:
            reply += '\n📎 Comprovante salvo no Drive'

        # Recalcula totais
        recalc_totals(data[month])

    elif tipo == 'receita':
        item = {
            'desc': desc,
            'val_str': fmt_brl(val),
            'val': val,
            'data': data_str,
            'status': status or 'A receber',
        }
        data[month]['receitas'].append(item)
        reply = f'✅ *Receita registrada!*\n📝 {desc}\n💰 {fmt_brl(val)}\n📅 {month.title()}'

        recalc_totals(data[month])
    else:
        reply = '❓ Não entendi. Envie `ajuda` para ver os comandos.'

    # Adiciona comprovante na lista de comprovantes do mês
    if drive_url:
        data[month]['comprovantes'].append({
            'desc': desc,
            'val': val,
            'val_str': fmt_brl(val),
            'date': data_str,
            'card': CARD_DISPLAY.get(cartao, '') if tipo == 'gasto' and cartao else '',
            'drive_url': drive_url,
            'thumb_url': thumb_url,
        })

    save_data(data)
    send_wpp(from_num, reply)
    print(f'Processado com sucesso: {tipo} - {desc} - {fmt_brl(val)}')

def recalc_totals(md: dict):
    """Recalcula totais do mês a partir dos itens."""
    md['total_gastos']      = round(sum(g.get('val', 0) for g in md.get('gastos', [])), 2)
    md['total_receitas']    = round(sum(r.get('val', 0) for r in md.get('receitas', [])), 2)
    md['total_inter']       = round(sum(x.get('val', 0) for x in md.get('inter', [])), 2)
    md['total_itau']        = round(sum(x.get('val', 0) for x in md.get('itau', [])), 2)
    md['total_nubank']      = round(sum(x.get('val', 0) for x in md.get('nubank_igor', [])), 2)
    md['total_caixa']       = round(sum(x.get('val', 0) for x in md.get('caixa', [])), 2)
    md['total_nubank_nath'] = round(sum(x.get('val', 0) for x in md.get('nubank_nath', [])), 2)

    all_gastos = (
        md['total_gastos'] +
        md['total_inter'] + md['total_itau'] +
        md['total_nubank'] + md['total_caixa'] + md['total_nubank_nath']
    )
    nao_pago = sum(
        g.get('val', 0) for g in md.get('gastos', [])
        if 'não' in (g.get('status', '') or '').lower()
    )
    md['para_pagar']   = round(nao_pago, 2)
    a_receber = sum(
        r.get('val', 0) for r in md.get('receitas', [])
        if 'receber' in (r.get('status', '') or '').lower()
    )
    md['para_receber'] = round(a_receber, 2)
    md['saldo']        = round(md['total_receitas'] - all_gastos, 2)

if __name__ == '__main__':
    process_message()
