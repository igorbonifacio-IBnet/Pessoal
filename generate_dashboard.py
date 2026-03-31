#!/usr/bin/env python3
"""Gera dashboard.html — Finanças Igor & Nath (lê de data/wpp_transactions.json)"""

import json
from datetime import datetime, timezone
from pathlib import Path

DATA_FILE = Path('data/wpp_transactions.json')

MONTH_SHEETS = ['MARÇO','ABRIL','MAIO','JUNHO','JULHO','AGOSTO','SETEMBRO','OUTUBRO','NOVEMBRO','DEZEMBRO26']
MONTH_LABELS = {
    'MARÇO':'Mar/26','ABRIL':'Abr/26','MAIO':'Mai/26','JUNHO':'Jun/26','JULHO':'Jul/26',
    'AGOSTO':'Ago/26','SETEMBRO':'Set/26','OUTUBRO':'Out/26','NOVEMBRO':'Nov/26','DEZEMBRO26':'Dez/26'
}

CAT_KW = {
    'Alimentação': ['atacadão','bretas','assaí','banana','carne','mc donalds','mc donald',
                    'pizzaria','almoço','espetinho','padoca','panif','armazem','pamonharia',
                    'bem fast','mourão','açaí','ice coco','biscoito','abast carrefour',
                    'dia a dia','supermercado','compras nath','banana semáforo','mercado',
                    'alimentação mensal','comer fora','hortifruti'],
    'Transporte':  ['uber','99 pop','baratão abast','óleo hb20','troca de óleo','lavagem',
                    'porto pneus','abastecimento','combustível','combustivel','hb20'],
    'Saúde':       ['drogasil','drogaria','mounjaro','vacina','plano de saúde','serasa',
                    'barra prot','farmácia','remédio','médico'],
    'Pet':         ['petshop','petz','biscoito bento','bento','ração'],
    'Vestuário':   ['marisa','roupa','vestido','sutiã','vivara','calçado','tênis','blusa'],
    'Casa':        ['montagem','guarda roupa','papel de parede','madeira guarda','colchão',
                    'limpeza sofá','carrinho melinda','ventilador','fita isolante',
                    'ferragi','módulo','luciano vieira','móveis','compra ont'],
    'Lazer':       ['academia','presente','milhas','açaí villa mix','cinema','smiles','livelo',
                    'anivers'],
    'Eletrônicos': ['amazon ps5','shopee','paygo','celular','notebook','tv','icloud','apple'],
    'Serviços':    ['ibnet','planilha','a/c ibnet','ana luiza','seguro','netflix','spotify',
                    'wepink'],
}
CAT_COLORS = {
    'Alimentação':'#22c55e','Transporte':'#3b82f6','Saúde':'#ec4899',
    'Pet':'#f97316','Vestuário':'#a855f7','Casa':'#14b8a6',
    'Lazer':'#f59e0b','Eletrônicos':'#6366f1','Serviços':'#94a3b8','Outros':'#475569',
}

def cat(desc):
    dl = desc.lower()
    for c, kws in CAT_KW.items():
        if any(kw in dl for kw in kws): return c
    return 'Outros'

def pc(v):
    if not v: return 0.0
    s = str(v).strip().replace('R$','').replace('\xa0','').strip()
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    else:
        parts = s.split('.')
        if len(parts) > 2:
            s = ''.join(parts[:-1]) + '.' + parts[-1]
    try: return round(float(s), 2)
    except: return 0.0

def load_json_data():
    """Carrega dados do wpp_transactions.json e normaliza para o formato do dashboard."""
    if not DATA_FILE.exists():
        print(f'Aviso: {DATA_FILE} não encontrado. Criando estrutura vazia.')
        return {}

    with open(DATA_FILE, encoding='utf-8') as f:
        raw = json.load(f)

    all_data = {}
    for month in MONTH_SHEETS:
        md = raw.get(month)
        if not md:
            all_data[month] = None
            continue

        d = {
            'gastos': [], 'receitas': [],
            'inter': [], 'itau': [], 'nubank': [], 'caixa': [], 'nubank_nath': [],
            'total_gastos': 0, 'total_receitas': 0,
            'para_pagar': 0, 'para_receber': 0, 'saldo': 0,
            'total_inter': 0, 'total_itau': 0, 'total_nubank': 0,
            'total_caixa': 0, 'total_nubank_nath': 0,
            'comprovantes': [],
        }

        # ── Gastos fixos ──
        for item in md.get('gastos', []):
            val = pc(item.get('val', item.get('val_str', 0)))
            d['gastos'].append({
                'desc': item.get('desc', ''),
                'val_str': item.get('val_str', f"R$ {val:.2f}".replace('.', ',')),
                'val': val,
                'data': item.get('data', ''),
                'obs': item.get('obs', item.get('notes', '')),
                'status': item.get('status', ''),
            })

        # ── Receitas ──
        for item in md.get('receitas', []):
            val = pc(item.get('val', item.get('val_str', 0)))
            d['receitas'].append({
                'desc': item.get('desc', ''),
                'val_str': item.get('val_str', f"R$ {val:.2f}".replace('.', ',')),
                'val': val,
                'data': item.get('data', ''),
                'status': item.get('status', ''),
            })

        # ── Cartões ──
        card_map = {'inter': 'inter', 'itau': 'itau', 'nubank_igor': 'nubank',
                    'nubank': 'nubank', 'caixa': 'caixa', 'nubank_nath': 'nubank_nath'}
        for src_key, dst_key in card_map.items():
            for item in md.get(src_key, []):
                val = pc(item.get('val', item.get('val_str', 0)))
                if val > 0:
                    entry = {
                        'desc': item.get('desc', ''),
                        'val': val,
                        'parc': item.get('parc', item.get('parcela', '')),
                        'cat': item.get('cat', cat(item.get('desc', ''))),
                    }
                    if item.get('date') or item.get('data'):
                        entry['date'] = item.get('date', item.get('data', ''))
                    if item.get('comprovante_url'):
                        entry['comprovante_url'] = item['comprovante_url']
                    d[dst_key].append(entry)

        # ── Totais ──
        d['total_gastos']      = pc(md.get('total_gastos', 0)) or round(sum(g['val'] for g in d['gastos']), 2)
        d['total_receitas']    = pc(md.get('total_receitas', 0)) or round(sum(r['val'] for r in d['receitas']), 2)
        d['para_pagar']        = pc(md.get('para_pagar', 0))
        d['para_receber']      = pc(md.get('para_receber', 0))
        d['saldo']             = pc(md.get('saldo', 0)) or round(d['total_receitas'] - d['total_gastos'], 2)
        d['total_inter']       = pc(md.get('total_inter', 0)) or round(sum(x['val'] for x in d['inter']), 2)
        d['total_itau']        = pc(md.get('total_itau', 0)) or round(sum(x['val'] for x in d['itau']), 2)
        d['total_nubank']      = pc(md.get('total_nubank', 0)) or round(sum(x['val'] for x in d['nubank']), 2)
        d['total_caixa']       = pc(md.get('total_caixa', 0)) or round(sum(x['val'] for x in d['caixa']), 2)
        d['total_nubank_nath'] = pc(md.get('total_nubank_nath', 0)) or round(sum(x['val'] for x in d['nubank_nath']), 2)

        # ── Comprovantes ──
        d['comprovantes'] = md.get('comprovantes', [])

        all_data[month] = d

    return all_data

# ─────────────────────────── HTML TEMPLATE ────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Dashboard — Igor &amp; Nath</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:20px}
h1{text-align:center;font-size:1.7rem;color:#f8fafc;margin-bottom:6px}
.subtitle{text-align:center;color:#64748b;font-size:.8rem;margin-bottom:20px}
.month-bar{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-bottom:14px}
.month-btn{padding:7px 16px;border-radius:20px;border:1.5px solid #334155;background:transparent;
  color:#94a3b8;cursor:pointer;font-size:.82rem;font-weight:500;transition:all .15s}
.month-btn:hover{border-color:#3b82f6;color:#93c5fd}
.month-btn.active{background:#3b82f6;border-color:#3b82f6;color:#fff;font-weight:700}
/* ── Tab bar ── */
.tab-bar{display:flex;gap:4px;margin-bottom:20px;border-bottom:2px solid #1e293b}
.tab-btn{padding:10px 20px;border:none;background:transparent;color:#64748b;
  cursor:pointer;font-size:.85rem;font-weight:500;border-bottom:2px solid transparent;
  margin-bottom:-2px;transition:all .15s}
.tab-btn:hover{color:#cbd5e1}
.tab-btn.active{color:#3b82f6;border-bottom-color:#3b82f6;font-weight:700}
.tab-panel{display:none}.tab-panel.active{display:block}
/* ── Filter bar ── */
.filter-bar{background:#1e293b;border-radius:12px;padding:14px 16px;margin-bottom:20px;
  display:flex;flex-direction:column;gap:10px}
.fg-row{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.fg-label{font-size:.68rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;
  white-space:nowrap;margin-right:4px;padding:3px 0}
.chip{padding:4px 13px;border-radius:999px;border:1.5px solid #334155;background:transparent;
  color:#94a3b8;cursor:pointer;font-size:.75rem;font-weight:500;transition:all .15s}
.chip:hover{border-color:#60a5fa;color:#93c5fd}
.chip.active{background:#3b82f6;border-color:#3b82f6;color:#fff;font-weight:700}
.chip-clear{border-color:#475569;color:#64748b;margin-left:6px}
.chip-clear:hover{border-color:#ef4444;color:#fca5a5}
.chip-pago.active{background:#22c55e;border-color:#22c55e}
.chip-nao.active{background:#ef4444;border-color:#ef4444}
/* ── Refresh button ── */
.refresh-btn{position:fixed;bottom:24px;right:24px;width:48px;height:48px;border-radius:50%;
  background:#3b82f6;border:none;color:#fff;font-size:1.4rem;cursor:pointer;
  box-shadow:0 4px 14px #0008;transition:background .2s,transform .3s;z-index:999;line-height:1}
.refresh-btn:hover{background:#2563eb;transform:rotate(180deg)}
/* ── Cards ── */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin-bottom:22px}
.card{background:#1e293b;border-radius:12px;padding:16px;border-left:4px solid}
.card.c-rec{border-color:#22c55e}.card.c-gas{border-color:#ef4444}
.card.c-pos{border-color:#3b82f6}.card.c-neg{border-color:#f43f5e}
.card.c-pag{border-color:#f59e0b}.card.c-prec{border-color:#a855f7}
.card h3{font-size:.7rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}
.card .val{font-size:1.35rem;font-weight:700}
.card.c-rec .val{color:#22c55e}.card.c-gas .val{color:#ef4444}
.card.c-pos .val{color:#3b82f6}.card.c-neg .val{color:#f43f5e}
.card.c-pag .val{color:#f59e0b}.card.c-prec .val{color:#a855f7}
.grid-2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;margin-bottom:20px}
.box{background:#1e293b;border-radius:12px;padding:18px}
.box h2{font-size:.88rem;color:#cbd5e1;margin-bottom:12px;border-bottom:1px solid #334155;padding-bottom:7px}
.chart-wrap{position:relative;height:240px}
.table-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.8rem}
th{background:#0f172a;color:#64748b;text-align:left;padding:8px 10px;
   font-size:.68rem;text-transform:uppercase;letter-spacing:.06em}
td{padding:7px 10px;border-bottom:1px solid #1e293b55;vertical-align:middle}
tr:hover td{background:#ffffff07}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:.68rem;font-weight:600}
.badge.pago{background:#14532d;color:#4ade80}.badge.nao{background:#7f1d1d;color:#fca5a5}
.cat{display:inline-block;padding:2px 9px;border-radius:999px;font-size:.66rem;font-weight:700;color:#0f172a}
.cartao-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px;margin-bottom:20px}
.cartao-box{background:#1e293b;border-radius:12px;padding:16px}
.cartao-box h2{font-size:.88rem;color:#cbd5e1;margin-bottom:10px}
.ci{display:flex;justify-content:space-between;align-items:center;
    padding:6px 0;border-bottom:1px solid #33415577;gap:8px}
.ci:last-of-type{border-bottom:none}
.ci .desc{color:#94a3b8;font-size:.78rem;flex:1;min-width:0;
          white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ci .right{display:flex;align-items:center;gap:5px;white-space:nowrap}
.ci .v{color:#f8fafc;font-size:.8rem;font-weight:600}
.ci small{color:#64748b;font-size:.7rem}
.ctotal{margin-top:10px;text-align:right;font-size:.85rem;color:#ef4444;font-weight:700}
.no-data{color:#475569;text-align:center;padding:30px;font-size:.9rem}
/* ── Comprovantes ── */
.comp-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px;padding:4px 0}
.comp-card{background:#1e293b;border-radius:12px;overflow:hidden;transition:transform .15s}
.comp-card:hover{transform:translateY(-2px)}
.comp-thumb{width:100%;height:150px;object-fit:cover;background:#0f172a;display:block}
.comp-thumb-placeholder{width:100%;height:150px;background:#0f172a;display:flex;
  align-items:center;justify-content:center;font-size:2rem;color:#334155}
.comp-info{padding:10px 12px}
.comp-desc{font-size:.82rem;color:#e2e8f0;font-weight:600;margin-bottom:4px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.comp-meta{font-size:.72rem;color:#64748b;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.comp-val{color:#ef4444;font-weight:700}
.comp-card a{color:#3b82f6;font-size:.72rem;text-decoration:none}
.comp-card a:hover{text-decoration:underline}
.comp-empty{text-align:center;padding:60px 20px;color:#475569}
.comp-empty .icon{font-size:3rem;margin-bottom:12px}
footer{text-align:center;color:#334155;font-size:.7rem;margin-top:20px;
       padding-top:10px;border-top:1px solid #1e293b}
</style>
</head>
<body>
<h1>💰 Finanças Igor &amp; Nath</h1>
<p class="subtitle">Atualizado: __UPDATED__</p>
<div class="month-bar">__MONTH_BUTTONS__</div>

<div class="tab-bar">
  <button class="tab-btn active" onclick="switchTab('visao-geral',this)">Visão Geral</button>
  <button class="tab-btn" onclick="switchTab('comprovantes',this)">Comprovantes</button>
</div>

<!-- ══════════ TAB: VISÃO GERAL ══════════ -->
<div id="tab-visao-geral" class="tab-panel active">

<div class="filter-bar">
  <div class="fg-row">
    <span class="fg-label">Categorias</span>
    <button class="chip" data-grp="cats" data-val="Alimentação"  onclick="toggleFilt(this)">Alimentação</button>
    <button class="chip" data-grp="cats" data-val="Transporte"   onclick="toggleFilt(this)">Transporte</button>
    <button class="chip" data-grp="cats" data-val="Saúde"        onclick="toggleFilt(this)">Saúde</button>
    <button class="chip" data-grp="cats" data-val="Pet"          onclick="toggleFilt(this)">Pet</button>
    <button class="chip" data-grp="cats" data-val="Vestuário"    onclick="toggleFilt(this)">Vestuário</button>
    <button class="chip" data-grp="cats" data-val="Casa"         onclick="toggleFilt(this)">Casa</button>
    <button class="chip" data-grp="cats" data-val="Lazer"        onclick="toggleFilt(this)">Lazer</button>
    <button class="chip" data-grp="cats" data-val="Eletrônicos"  onclick="toggleFilt(this)">Eletrônicos</button>
    <button class="chip" data-grp="cats" data-val="Serviços"     onclick="toggleFilt(this)">Serviços</button>
    <button class="chip" data-grp="cats" data-val="Outros"       onclick="toggleFilt(this)">Outros</button>
  </div>
  <div class="fg-row">
    <span class="fg-label">Cartões</span>
    <button class="chip" data-grp="cards" data-val="inter"       onclick="toggleFilt(this)">Inter</button>
    <button class="chip" data-grp="cards" data-val="itau"        onclick="toggleFilt(this)">Itaú</button>
    <button class="chip" data-grp="cards" data-val="nubank"      onclick="toggleFilt(this)">Nubank Igor</button>
    <button class="chip" data-grp="cards" data-val="caixa"       onclick="toggleFilt(this)">Caixa</button>
    <button class="chip" data-grp="cards" data-val="nubank_nath" onclick="toggleFilt(this)">Nubank Nath</button>
    <span class="fg-label" style="margin-left:10px">Status</span>
    <button class="chip chip-pago" data-grp="status" data-val="pago"     onclick="toggleFilt(this)">Pago</button>
    <button class="chip chip-nao"  data-grp="status" data-val="nao_pago" onclick="toggleFilt(this)">Não Pago</button>
    <button class="chip chip-clear" onclick="clearFilts()">✕ Limpar filtros</button>
  </div>
</div>

<button class="refresh-btn" onclick="location.reload()" title="Atualizar dados">↻</button>

<div class="cards">
  <div class="card c-rec"><h3>Receita Total</h3><div class="val" id="v-rec">—</div></div>
  <div class="card c-gas"><h3>Gastos Totais</h3><div class="val" id="v-gas">—</div></div>
  <div class="card c-pos" id="card-saldo"><h3>Saldo Líquido</h3><div class="val" id="v-sal">—</div></div>
  <div class="card c-pag"><h3>Ainda a Pagar</h3><div class="val" id="v-pag">—</div></div>
  <div class="card c-prec"><h3>Ainda a Receber</h3><div class="val" id="v-prec">—</div></div>
</div>

<div class="grid-2">
  <div class="box"><h2>Receita vs Gastos</h2><div class="chart-wrap"><canvas id="cBar"></canvas></div></div>
  <div class="box"><h2>Gastos por Categoria (Cartão)</h2><div class="chart-wrap"><canvas id="cCat"></canvas></div></div>
</div>
<div class="grid-2">
  <div class="box"><h2>Composição dos Gastos Fixos</h2><div class="chart-wrap"><canvas id="cPizza"></canvas></div></div>
  <div class="box"><h2>Faturas dos Cartões</h2><div class="chart-wrap"><canvas id="cCartoes"></canvas></div></div>
</div>

<div class="cartao-grid" id="cartao-grid"></div>

<div class="box" style="margin-bottom:18px">
  <h2>Gastos Mensais Fixos</h2>
  <div class="table-wrap"><table>
    <thead><tr><th>Descrição</th><th>Valor</th><th>Vencimento</th><th>Tipo</th><th>Status</th></tr></thead>
    <tbody id="tbody-gastos"></tbody>
  </table></div>
</div>
<div class="box" style="margin-bottom:18px">
  <h2>Receitas Mensais</h2>
  <div class="table-wrap"><table>
    <thead><tr><th>Descrição</th><th>Valor</th><th>Data</th><th>Status</th></tr></thead>
    <tbody id="tbody-receitas"></tbody>
  </table></div>
</div>
<div class="box" style="margin-bottom:18px">
  <h2>Transações Detalhadas (Inter)</h2>
  <div class="table-wrap"><table>
    <thead><tr><th>Data</th><th>Descrição</th><th>Valor</th><th>Parcela</th><th>Categoria</th></tr></thead>
    <tbody id="tbody-trans"></tbody>
  </table></div>
</div>

</div><!-- end tab visao-geral -->

<!-- ══════════ TAB: COMPROVANTES ══════════ -->
<div id="tab-comprovantes" class="tab-panel">
  <div class="box" style="margin-bottom:18px">
    <h2>Comprovantes e Anexos</h2>
    <div id="comp-container"></div>
  </div>
</div>

<footer>Dashboard Financeiro · Igor &amp; Nath · Alimentado via WhatsApp</footer>

<script>
const DATA   = __DATA__;
const LABELS = __LABELS__;
const CC     = __CAT_COLORS__;
const ORDER  = __MONTH_ORDER__;
let CH = {};
const CANVAS_IDS = ['cBar','cCat','cPizza','cCartoes'];
const CARD_KEYS  = ['inter','itau','nubank','caixa','nubank_nath'];
const CARD_TITLES= {
  inter:'💳 Cartão Inter', itau:'💳 Cartão Itaú',
  nubank:'💳 Nubank Igor', caixa:'💳 Cartão Caixa', nubank_nath:'💳 Nubank Nath'
};

let FILT = {cats:new Set(), cards:new Set(), status:new Set()};
let CURR_DATA = null;
let CURR_MONTH = null;

const fmt  = v => 'R$\u00a0'+Math.abs(+v||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
const fmtS = v => (v<0?'\u2212':'')+fmt(v);
const brl  = v => 'R$\u00a0'+Math.round(Math.abs(+v||0)).toLocaleString('pt-BR');

function badge(s){
  const n=/n[ãa]o/i.test(s);
  return `<span class="badge ${n?'nao':'pago'}">${s||'—'}</span>`;
}
function catBadge(c){
  return `<span class="cat" style="background:${CC[c]||'#475569'}">${c}</span>`;
}

function switchTab(id, el){
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');
  el.classList.add('active');
  if(id==='comprovantes') renderComprovantes(CURR_DATA);
}

function toggleFilt(el){
  const grp=el.dataset.grp, val=el.dataset.val;
  if(FILT[grp].has(val)){ FILT[grp].delete(val); el.classList.remove('active'); }
  else { FILT[grp].add(val); el.classList.add('active'); }
  applyFilters();
}

function clearFilts(){
  FILT={cats:new Set(), cards:new Set(), status:new Set()};
  document.querySelectorAll('.chip').forEach(c=>c.classList.remove('active'));
  applyFilters();
}

function filteredCards(d){
  const activeCards=FILT.cards.size>0?FILT.cards:new Set(CARD_KEYS);
  const activeCats =FILT.cats.size>0 ?FILT.cats :null;
  const fc={};
  CARD_KEYS.forEach(k=>{
    if(!activeCards.has(k)){ fc[k]=[]; return; }
    fc[k]=(d[k]||[]).filter(x=>!activeCats||activeCats.has(x.cat));
  });
  return fc;
}

function filteredStatus(items){
  if(FILT.status.size===0) return items||[];
  return (items||[]).filter(x=>{
    const isPago=!(/n[ãa]o/i.test(x.status||''));
    return (FILT.status.has('pago')&&isPago)||(FILT.status.has('nao_pago')&&!isPago);
  });
}

function dc(){
  Object.values(CH).forEach(c=>{try{c.destroy();}catch{}});
  CH={};
  CANVAS_IDS.forEach(id=>{
    const old=document.getElementById(id);
    if(old){ const n=document.createElement('canvas'); n.id=id; old.parentNode.replaceChild(n,old); }
  });
}

function mkCharts(d, fc){
  dc();
  const tc='#94a3b8', gc='#1e293b';
  const yScale={ticks:{color:tc,callback:brl},grid:{color:'#334155'}};
  const xScale={ticks:{color:tc},grid:{color:gc}};

  CH.bar=new Chart(document.getElementById('cBar'),{type:'bar',data:{
    labels:['Receita','Gastos','Saldo'],
    datasets:[{data:[d.total_receitas,d.total_gastos,d.saldo],borderRadius:6,
      backgroundColor:['#22c55e88','#ef444488',d.saldo>=0?'#3b82f688':'#f43f5e88'],
      borderColor:['#22c55e','#ef4444',d.saldo>=0?'#3b82f6':'#f43f5e'],borderWidth:2}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false}},scales:{x:xScale,y:yScale}}});

  const ct={};
  CARD_KEYS.forEach(k=>{ (fc[k]||[]).forEach(x=>{ ct[x.cat]=(ct[x.cat]||0)+x.val; }); });
  const ck=Object.keys(ct).filter(k=>ct[k]>0).sort((a,b)=>ct[b]-ct[a]);
  if(ck.length){
    CH.cat=new Chart(document.getElementById('cCat'),{type:'doughnut',data:{
      labels:ck,datasets:[{data:ck.map(k=>ct[k]),backgroundColor:ck.map(k=>CC[k]||'#475569'),borderWidth:0}]},
      options:{responsive:true,maintainAspectRatio:false,
        plugins:{legend:{position:'right',labels:{color:tc,font:{size:10},boxWidth:10,padding:6}}}}});
  }

  const gl=filteredStatus(d.gastos||[]).filter(g=>g.val>0);
  const COLS=['#6366f1','#ef4444','#8b5cf6','#ec4899','#f59e0b','#14b8a6','#22c55e','#3b82f6','#f97316','#94a3b8'];
  if(gl.length){
    CH.piz=new Chart(document.getElementById('cPizza'),{type:'doughnut',data:{
      labels:gl.map(g=>g.desc),datasets:[{data:gl.map(g=>g.val),backgroundColor:COLS,borderWidth:0}]},
      options:{responsive:true,maintainAspectRatio:false,
        plugins:{legend:{position:'right',labels:{color:tc,font:{size:10},boxWidth:10,padding:6}}}}});
  }

  const cartVals=CARD_KEYS.map(k=>(fc[k]||[]).reduce((s,x)=>s+x.val,0));
  const cartColors=['#f59e0b88','#6366f188','#a855f788','#22c55e88','#ec489988'];
  const cartBorder=['#f59e0b','#6366f1','#a855f7','#22c55e','#ec4899'];
  CH.car=new Chart(document.getElementById('cCartoes'),{type:'bar',data:{
    labels:['Inter','Itaú','Nubank Igor','Caixa','Nubank Nath'],
    datasets:[{data:cartVals,backgroundColor:cartColors,borderColor:cartBorder,borderWidth:2,borderRadius:6}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false}},scales:{x:xScale,y:yScale}}});
}

function mkItems(items){
  if(!items||!items.length) return '<p class="no-data">Sem itens.</p>';
  return items.map(x=>{
    const compLink=x.comprovante_url
      ?` <a href="${x.comprovante_url}" target="_blank" title="Ver comprovante">📎</a>`:'';
    return `<div class="ci">
      <span class="desc">${x.desc}${x.date?' <small>('+x.date+')</small>':''}${compLink}</span>
      <div class="right">${catBadge(x.cat)}<span class="v">${fmt(x.val)}</span><small>${x.parc||''}</small></div>
    </div>`;
  }).join('');
}

function renderComprovantes(d){
  const el=document.getElementById('comp-container');
  if(!d||!d.comprovantes||!d.comprovantes.length){
    el.innerHTML=`<div class="comp-empty"><div class="icon">📂</div>
      <p>Nenhum comprovante para este mês.</p>
      <p style="font-size:.78rem;margin-top:6px;color:#334155">
        Envie uma foto pelo WhatsApp ao registrar um gasto.</p></div>`;
    return;
  }
  el.innerHTML=`<div class="comp-grid">${d.comprovantes.map(c=>{
    const thumb=c.thumb_url||c.drive_url
      ?`<img class="comp-thumb" src="${c.thumb_url||c.drive_url}" alt="comprovante" loading="lazy"
             onerror="this.style.display='none';this.nextSibling.style.display='flex'">`
      :'';
    const placeholder=`<div class="comp-thumb-placeholder" style="display:${thumb?'none':'flex'}">🧾</div>`;
    const verLink=c.drive_url?`<a href="${c.drive_url}" target="_blank">Ver comprovante ↗</a>`:'';
    const card=c.card?`<span>${c.card}</span>`:'';
    return `<div class="comp-card">
      ${thumb}${placeholder}
      <div class="comp-info">
        <div class="comp-desc">${c.desc||'Sem descrição'}</div>
        <div class="comp-meta">
          <span class="comp-val">${c.val_str||''}</span>
          ${card}<span>${c.date||''}</span>
        </div>
        <div style="margin-top:6px">${verLink}</div>
      </div>
    </div>`;
  }).join('')}</div>`;
}

function setNoData(msg){
  dc();
  CURR_DATA=null;
  ['tbody-gastos','tbody-receitas','tbody-trans'].forEach(id=>{
    document.getElementById(id).innerHTML=`<tr><td colspan="5" class="no-data">${msg}</td></tr>`;
  });
  document.getElementById('cartao-grid').innerHTML=
    `<div style="grid-column:1/-1;text-align:center;color:#475569;padding:30px">${msg}</div>`;
  ['v-rec','v-gas','v-sal','v-pag','v-prec'].forEach(id=>{ document.getElementById(id).textContent='—'; });
  document.getElementById('card-saldo').className='card c-pos';
  document.getElementById('comp-container').innerHTML=
    `<div class="comp-empty"><div class="icon">📂</div><p>${msg}</p></div>`;
}

function applyFilters(){
  if(!CURR_DATA) return;
  const d=CURR_DATA;
  const fc=filteredCards(d);
  mkCharts(d, fc);

  const activeCards=FILT.cards.size>0?FILT.cards:new Set(CARD_KEYS);
  document.getElementById('cartao-grid').innerHTML=CARD_KEYS
    .map(k=>({key:k,title:CARD_TITLES[k],items:fc[k],total:fc[k].reduce((s,x)=>s+x.val,0)}))
    .filter(c=>activeCards.has(c.key)&&(c.items.length>0||c.total>0))
    .map(c=>`<div class="cartao-box"><h2>${c.title}</h2>${mkItems(c.items)}
      <div class="ctotal">Total fatura: ${fmt(c.total)}</div></div>`).join('');

  const fg=filteredStatus(d.gastos||[]);
  document.getElementById('tbody-gastos').innerHTML=fg.map(r=>
    `<tr><td>${r.desc}</td><td>${r.val_str}</td><td>${r.data||'—'}</td><td>${r.obs||'—'}</td><td>${badge(r.status)}</td></tr>`
  ).join('')||'<tr><td colspan="5" class="no-data">Sem gastos.</td></tr>';

  const fr=filteredStatus(d.receitas||[]);
  document.getElementById('tbody-receitas').innerHTML=fr.map(r=>
    `<tr><td>${r.desc}</td><td>${r.val_str}</td><td>${r.data||'—'}</td><td>${badge(r.status)}</td></tr>`
  ).join('')||'<tr><td colspan="4" class="no-data">Sem receitas.</td></tr>';

  const trans=fc.inter.filter(x=>x.date);
  document.getElementById('tbody-trans').innerHTML=trans.map(r=>
    `<tr><td>${r.date}</td><td>${r.desc}</td><td>${fmt(r.val)}</td><td>${r.parc||'—'}</td><td>${catBadge(r.cat)}</td></tr>`
  ).join('')||'<tr><td colspan="5" class="no-data">Sem transações detalhadas.</td></tr>';
}

function render(d){
  if(!d){ setNoData('Sem dados para este mês ainda.'); return; }
  if(d.total_gastos===0&&d.total_receitas===0){
    setNoData('Este mês ainda não tem dados preenchidos.'); return;
  }
  CURR_DATA=d;
  document.getElementById('v-rec').textContent  = fmt(d.total_receitas);
  document.getElementById('v-gas').textContent  = fmt(d.total_gastos);
  document.getElementById('v-sal').textContent  = fmtS(d.saldo);
  document.getElementById('v-pag').textContent  = fmt(d.para_pagar);
  document.getElementById('v-prec').textContent = fmt(d.para_receber);
  document.getElementById('card-saldo').className='card '+(d.saldo>=0?'c-pos':'c-neg');
  applyFilters();
  // Atualiza comprovantes se a aba estiver ativa
  if(document.getElementById('tab-comprovantes').classList.contains('active'))
    renderComprovantes(d);
}

function switchMonth(m){
  CURR_MONTH=m;
  document.querySelectorAll('.month-btn').forEach(b=>b.classList.toggle('active',b.dataset.month===m));
  render(DATA[m]);
}

const firstWithData=ORDER.find(m=>DATA[m]&&(DATA[m].total_gastos>0||DATA[m].total_receitas>0))
  ||ORDER.find(m=>DATA[m])||ORDER[0];
switchMonth(firstWithData);
</script>
</body>
</html>"""

def generate_html(all_data, updated):
    btns = ''.join(
        f'<button class="month-btn" data-month="{m}" onclick="switchMonth(\'{m}\')">'
        f'{MONTH_LABELS[m]}</button>'
        for m in MONTH_SHEETS if all_data.get(m) is not None
    )
    html = HTML
    html = html.replace('__DATA__',          json.dumps(all_data, ensure_ascii=False))
    html = html.replace('__LABELS__',        json.dumps(MONTH_LABELS, ensure_ascii=False))
    html = html.replace('__CAT_COLORS__',    json.dumps(CAT_COLORS, ensure_ascii=False))
    html = html.replace('__MONTH_ORDER__',   json.dumps(MONTH_SHEETS, ensure_ascii=False))
    html = html.replace('__UPDATED__',       updated)
    html = html.replace('__MONTH_BUTTONS__', btns)
    return html

def main():
    now = datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')
    print('Carregando data/wpp_transactions.json...')
    all_data = load_json_data()
    for month, data in all_data.items():
        if data and (data['total_gastos'] > 0 or data['total_receitas'] > 0):
            print(f'  {month}: gastos={data["total_gastos"]:.2f}  receitas={data["total_receitas"]:.2f}')
        else:
            print(f'  {month}: sem dados')
    print('Gerando dashboard.html...')
    with open('dashboard.html', 'w', encoding='utf-8') as f:
        f.write(generate_html(all_data, now))
    print('Pronto!')

if __name__ == '__main__':
    main()
