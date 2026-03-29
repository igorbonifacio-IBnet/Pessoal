#!/usr/bin/env python3
"""Gera dashboard.html — Finanças Igor & Nath"""

import csv, io, json, urllib.request, urllib.parse
from datetime import datetime, timezone

SHEET_ID = '1xOB9bCLSkGPsZbXPHOuZFnA8_KKXMS6sbrrIsHCRak0'

MONTH_SHEETS = [
    'MARÇO','ABRIL','MAIO','JUNHO','JULHO',
    'AGOSTO','SETEMBRO','OUTUBRO','NOVEMBRO','DEZEMBRO26'
]
MONTH_LABELS = {
    'MARÇO':'Mar/26','ABRIL':'Abr/26','MAIO':'Mai/26','JUNHO':'Jun/26','JULHO':'Jul/26',
    'AGOSTO':'Ago/26','SETEMBRO':'Set/26','OUTUBRO':'Out/26','NOVEMBRO':'Nov/26','DEZEMBRO26':'Dez/26'
}

# ── Categorias ──────────────────────────────────────────────────────────────
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

def fetch_csv(sheet_name):
    url = (f'https://docs.google.com/spreadsheets/d/{SHEET_ID}'
           f'/export?format=csv&sheet={urllib.parse.quote(sheet_name)}')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode('utf-8-sig')
    except Exception as e:
        print(f'  Aviso: não carregou {sheet_name}: {e}')
        return None

def pc(v):
    """Converte valor monetário BR (R$ 1.234,56) para float."""
    if not v: return 0.0
    s = str(v).strip().replace('R$','').replace('\xa0','').strip()
    if ',' in s:
        # formato BR: 1.234,56 → remove pontos → 1234,56 → troca vírgula → 1234.56
        s = s.replace('.', '').replace(',', '.')
    else:
        # sem vírgula: pode ser inteiro ou formato com ponto decimal
        parts = s.split('.')
        if len(parts) > 2:
            s = ''.join(parts[:-1]) + '.' + parts[-1]
    try: return round(float(s), 2)
    except: return 0.0

def is_card_header(s):
    """Ignora linhas de cabeçalho das colunas de cartão."""
    sl = s.lower()
    return (not s or sl in {'valor','total','descrição','data','parcela'} or
            sl.startswith('fatura ') or sl.startswith('cartão '))

def extract(text):
    if not text: return None
    rows = list(csv.reader(io.StringIO(text)))

    d = {
        'gastos':[], 'receitas':[],
        'inter':[], 'itau':[], 'nubank':[], 'caixa':[], 'nubank_nath':[],
        'total_gastos':0,'total_receitas':0,
        'para_pagar':0,'para_receber':0,'saldo':0,
        'total_inter':0,'total_itau':0,'total_nubank':0,'total_caixa':0,'total_nubank_nath':0,
    }

    def g(r, i): return r[i].strip() if len(r) > i else ''

    sec = None

    for row in rows:
        # ── Dados principais estão na coluna 1 (há 1 coluna vazia no início) ──
        c1 = g(row, 1)   # descrição / header de seção
        c2 = g(row, 2)   # valor
        c3 = g(row, 3)   # data
        c4 = g(row, 4)   # observação
        c5 = g(row, 5)   # status

        # ── Detecção de seção ──
        if c1 == 'GASTOS MENSAIS':  sec = 'g'; continue
        if c1 == 'RECEITA MENSAL':  sec = 'r'; continue
        if c1 in ('DESCRIÇÃO', ''): continue

        # ── PARA PAGAR / RECEBER (sem header de seção) ──
        if c1 == 'PARA PAGAR':   d['para_pagar']   = pc(c2); sec = 's'; continue
        if c1 == 'PARA RECEBER': d['para_receber']  = pc(c2); continue

        # ── Cartões: parseados apenas dentro da seção de gastos ──
        if sec == 'g':
            # Inter — cols 7(date), 8(desc), 9(val), 10(parc)
            di, dsc, vi, pi = g(row,7), g(row,8), g(row,9), g(row,10)
            if dsc and not is_card_header(dsc):
                v = pc(vi)
                if v > 0:
                    item = {'desc':dsc,'val':v,'parc':pi,'cat':cat(dsc)}
                    if di: item['date'] = di
                    d['inter'].append(item)
            if g(row,8).lower() == 'total' and g(row,9):
                d['total_inter'] = pc(g(row,9))

            # Itaú — cols 12(date), 13(desc), 14(val), 15(parc)
            di2, dsc2, vi2, pi2 = g(row,12), g(row,13), g(row,14), g(row,15)
            if dsc2 and not is_card_header(dsc2):
                v = pc(vi2)
                if v > 0:
                    item = {'desc':dsc2,'val':v,'parc':pi2,'cat':cat(dsc2)}
                    if di2: item['date'] = di2
                    d['itau'].append(item)
            if g(row,13).lower() == 'total' and g(row,14):
                d['total_itau'] = pc(g(row,14))

            # Nubank Igor — cols 17(desc), 18(val), 19(parc)
            nd, nv, np = g(row,17), g(row,18), g(row,19)
            if nd.lower() == 'total' and nv:
                d['total_nubank'] = pc(nv)
            elif nd and not is_card_header(nd):
                v = pc(nv)
                if v > 0: d['nubank'].append({'desc':nd,'val':v,'parc':np,'cat':cat(nd)})

            # Caixa — cols 21(desc), 22(val), 23(parc)
            cd, cv, cp = g(row,21), g(row,22), g(row,23)
            if cd.lower() == 'total' and cv:
                d['total_caixa'] = pc(cv)
            elif cd and not is_card_header(cd):
                v = pc(cv)
                if v > 0: d['caixa'].append({'desc':cd,'val':v,'parc':cp,'cat':cat(cd)})

            # Nubank Nath — cols 25(desc), 26(val), 27(parc)
            nn, nnn, pnn = g(row,25), g(row,26), g(row,27)
            if nn.lower() == 'total' and nnn:
                d['total_nubank_nath'] = pc(nnn)
            elif nn and not is_card_header(nn):
                v = pc(nnn)
                if v > 0: d['nubank_nath'].append({'desc':nn,'val':v,'parc':pnn,'cat':cat(nn)})

        # ── Gastos fixos ──
        if sec == 'g':
            if c1 == 'TOTAL' and c2:
                d['total_gastos'] = pc(c2)
            elif c1:
                d['gastos'].append({'desc':c1,'val_str':c2,'val':pc(c2),
                                    'data':c3,'obs':c4,'status':c5})
        elif sec == 'r':
            if c1 == 'TOTAL' and c2:
                d['total_receitas'] = pc(c2)
            elif c1:
                d['receitas'].append({'desc':c1,'val_str':c2,'val':pc(c2),
                                      'data':c3,'status':c5})
        elif sec == 's':
            if c1 == 'TOTAL' and c2:
                d['saldo'] = pc(c2)

    # Fallback: totais dos cartões pela soma dos itens
    if d['total_inter']      == 0: d['total_inter']      = round(sum(x['val'] for x in d['inter']),2)
    if d['total_itau']       == 0: d['total_itau']       = round(sum(x['val'] for x in d['itau']),2)
    if d['total_nubank']     == 0: d['total_nubank']     = round(sum(x['val'] for x in d['nubank']),2)
    if d['total_caixa']      == 0: d['total_caixa']      = round(sum(x['val'] for x in d['caixa']),2)
    if d['total_nubank_nath'] == 0: d['total_nubank_nath'] = round(sum(x['val'] for x in d['nubank_nath']),2)

    return d

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
.month-bar{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-bottom:26px}
.month-btn{padding:7px 16px;border-radius:20px;border:1.5px solid #334155;background:transparent;
  color:#94a3b8;cursor:pointer;font-size:.82rem;font-weight:500;transition:all .15s}
.month-btn:hover{border-color:#3b82f6;color:#93c5fd}
.month-btn.active{background:#3b82f6;border-color:#3b82f6;color:#fff;font-weight:700}
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
footer{text-align:center;color:#334155;font-size:.7rem;margin-top:20px;
       padding-top:10px;border-top:1px solid #1e293b}
</style>
</head>
<body>
<h1>💰 Finanças Igor &amp; Nath</h1>
<p class="subtitle">Atualizado: __UPDATED__</p>
<div class="month-bar">__MONTH_BUTTONS__</div>

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

<footer>Dashboard Financeiro · Igor &amp; Nath · Dados sincronizados do Google Sheets</footer>

<script>
const DATA   = __DATA__;
const LABELS = __LABELS__;
const CC     = __CAT_COLORS__;
const ORDER  = __MONTH_ORDER__;
let CH = {};
const CANVAS_IDS = ['cBar','cCat','cPizza','cCartoes'];

const fmt = v => 'R$\u00a0' + Math.abs(+v||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
const fmtS = v => (v<0?'\u2212':'')+fmt(v);
const brl  = v => 'R$\u00a0'+Math.round(Math.abs(+v||0)).toLocaleString('pt-BR');

function badge(s){
  const n=/n[ãa]o/i.test(s);
  return `<span class="badge ${n?'nao':'pago'}">${s||'—'}</span>`;
}
function catBadge(c){
  return `<span class="cat" style="background:${CC[c]||'#475569'}">${c}</span>`;
}
function getCatTotals(d){
  const t={};
  const all=[...(d.inter||[]),...(d.itau||[]),...(d.nubank||[]),...(d.caixa||[]),...(d.nubank_nath||[])];
  all.forEach(x=>{ t[x.cat]=(t[x.cat]||0)+x.val; });
  return t;
}

// Destrói charts e recria os canvas do zero (evita bug de reuso do Chart.js)
function dc(){
  Object.values(CH).forEach(c=>{try{c.destroy();}catch{}});
  CH={};
  CANVAS_IDS.forEach(id=>{
    const old=document.getElementById(id);
    if(old){
      const n=document.createElement('canvas');
      n.id=id;
      old.parentNode.replaceChild(n,old);
    }
  });
}

function mkCharts(d){
  dc();
  const tc='#94a3b8', gc='#1e293b';
  const yScale = {ticks:{color:tc,callback:brl},grid:{color:'#334155'}};
  const xScale = {ticks:{color:tc},grid:{color:gc}};

  CH.bar=new Chart(document.getElementById('cBar'),{type:'bar',data:{
    labels:['Receita','Gastos','Saldo'],
    datasets:[{data:[d.total_receitas,d.total_gastos,d.saldo],borderRadius:6,
      backgroundColor:['#22c55e88','#ef444488',d.saldo>=0?'#3b82f688':'#f43f5e88'],
      borderColor:['#22c55e','#ef4444',d.saldo>=0?'#3b82f6':'#f43f5e'],borderWidth:2}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false}},scales:{x:xScale,y:yScale}}});

  const ct=getCatTotals(d);
  const ck=Object.keys(ct).filter(k=>ct[k]>0).sort((a,b)=>ct[b]-ct[a]);
  if(ck.length){
    CH.cat=new Chart(document.getElementById('cCat'),{type:'doughnut',data:{
      labels:ck,datasets:[{data:ck.map(k=>ct[k]),backgroundColor:ck.map(k=>CC[k]||'#475569'),borderWidth:0}]},
      options:{responsive:true,maintainAspectRatio:false,
        plugins:{legend:{position:'right',labels:{color:tc,font:{size:10},boxWidth:10,padding:6}}}}});
  }

  const gl=(d.gastos||[]).filter(g=>g.val>0);
  const COLS=['#6366f1','#ef4444','#8b5cf6','#ec4899','#f59e0b','#14b8a6','#22c55e','#3b82f6','#f97316','#94a3b8'];
  if(gl.length){
    CH.piz=new Chart(document.getElementById('cPizza'),{type:'doughnut',data:{
      labels:gl.map(g=>g.desc),
      datasets:[{data:gl.map(g=>g.val),backgroundColor:COLS,borderWidth:0}]},
      options:{responsive:true,maintainAspectRatio:false,
        plugins:{legend:{position:'right',labels:{color:tc,font:{size:10},boxWidth:10,padding:6}}}}});
  }

  const cartLabels=['Inter','Itaú','Nubank','Caixa','Nubank Nath'];
  const cartVals=[d.total_inter,d.total_itau,d.total_nubank,d.total_caixa,d.total_nubank_nath];
  const cartColors=['#f59e0b88','#6366f188','#a855f788','#22c55e88','#ec489988'];
  const cartBorder=['#f59e0b','#6366f1','#a855f7','#22c55e','#ec4899'];
  CH.car=new Chart(document.getElementById('cCartoes'),{type:'bar',data:{
    labels:cartLabels,
    datasets:[{data:cartVals,backgroundColor:cartColors,borderColor:cartBorder,borderWidth:2,borderRadius:6}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false}},scales:{x:xScale,y:yScale}}});
}

function mkItems(items){
  if(!items||!items.length) return '<p class="no-data">Sem itens.</p>';
  return items.map(x=>`
    <div class="ci">
      <span class="desc">${x.desc}${x.date?' <small>('+x.date+')</small>':''}</span>
      <div class="right">${catBadge(x.cat)}<span class="v">${fmt(x.val)}</span><small>${x.parc||''}</small></div>
    </div>`).join('');
}

function setNoData(msg){
  dc(); // limpa e recria canvases
  ['tbody-gastos','tbody-receitas','tbody-trans'].forEach(id=>{
    document.getElementById(id).innerHTML=
      `<tr><td colspan="5" class="no-data">${msg}</td></tr>`;
  });
  document.getElementById('cartao-grid').innerHTML=
    `<div style="grid-column:1/-1;text-align:center;color:#475569;padding:30px">${msg}</div>`;
  ['v-rec','v-gas','v-sal','v-pag','v-prec'].forEach(id=>{
    document.getElementById(id).textContent='—';
  });
  document.getElementById('card-saldo').className='card c-pos';
}

function render(d){
  if(!d){
    setNoData('Sem dados para este mês ainda.');
    return;
  }
  // Mês com dados mas todos zerados
  if(d.total_gastos===0 && d.total_receitas===0){
    setNoData('Este mês ainda não tem dados preenchidos na planilha.');
    return;
  }

  // Cards de resumo
  document.getElementById('v-rec').textContent  = fmt(d.total_receitas);
  document.getElementById('v-gas').textContent  = fmt(d.total_gastos);
  document.getElementById('v-sal').textContent  = fmtS(d.saldo);
  document.getElementById('v-pag').textContent  = fmt(d.para_pagar);
  document.getElementById('v-prec').textContent = fmt(d.para_receber);
  const cs = document.getElementById('card-saldo');
  cs.className = 'card '+(d.saldo>=0?'c-pos':'c-neg');

  // Gráficos
  mkCharts(d);

  // Boxes dos cartões
  document.getElementById('cartao-grid').innerHTML = [
    {title:'💳 Cartão Inter', items:d.inter,      total:d.total_inter},
    {title:'💳 Cartão Itaú',  items:d.itau,       total:d.total_itau},
    {title:'💳 Nubank Igor',  items:d.nubank,      total:d.total_nubank},
    {title:'💳 Cartão Caixa', items:d.caixa,       total:d.total_caixa},
    {title:'💳 Nubank Nath',  items:d.nubank_nath, total:d.total_nubank_nath},
  ].filter(c=>c.items&&(c.items.length>0||c.total>0)).map(c=>`
    <div class="cartao-box">
      <h2>${c.title}</h2>
      ${mkItems(c.items)}
      <div class="ctotal">Total fatura: ${fmt(c.total)}</div>
    </div>`).join('');

  // Tabela gastos
  document.getElementById('tbody-gastos').innerHTML=(d.gastos||[]).map(r=>
    `<tr><td>${r.desc}</td><td>${r.val_str}</td><td>${r.data||'—'}</td><td>${r.obs||'—'}</td><td>${badge(r.status)}</td></tr>`
  ).join('') || '<tr><td colspan="5" class="no-data">Sem gastos.</td></tr>';

  // Tabela receitas
  document.getElementById('tbody-receitas').innerHTML=(d.receitas||[]).map(r=>
    `<tr><td>${r.desc}</td><td>${r.val_str}</td><td>${r.data||'—'}</td><td>${badge(r.status)}</td></tr>`
  ).join('') || '<tr><td colspan="4" class="no-data">Sem receitas.</td></tr>';

  // Tabela transações Inter com data
  const trans=(d.inter||[]).filter(x=>x.date);
  document.getElementById('tbody-trans').innerHTML=trans.map(r=>
    `<tr><td>${r.date}</td><td>${r.desc}</td><td>${fmt(r.val)}</td><td>${r.parc||'—'}</td><td>${catBadge(r.cat)}</td></tr>`
  ).join('') || '<tr><td colspan="5" class="no-data">Sem transações detalhadas.</td></tr>';
}

function switchMonth(m){
  document.querySelectorAll('.month-btn').forEach(b=>b.classList.toggle('active',b.dataset.month===m));
  render(DATA[m]);
}

// Abre no mês mais recente com dados
const firstWithData = ORDER.find(m=>DATA[m]&&(DATA[m].total_gastos>0||DATA[m].total_receitas>0))
  || ORDER.find(m=>DATA[m]) || ORDER[0];
switchMonth(firstWithData);
</script>
</body>
</html>"""

def generate_html(all_data, updated):
    first = (next((m for m in MONTH_SHEETS if all_data.get(m) and
                   (all_data[m]['total_gastos']>0 or all_data[m]['total_receitas']>0)), None)
             or next((m for m in MONTH_SHEETS if all_data.get(m)), MONTH_SHEETS[0]))
    btns = ''.join(
        f'<button class="month-btn" data-month="{m}" onclick="switchMonth(\'{m}\')">'
        f'{MONTH_LABELS[m]}</button>'
        for m in MONTH_SHEETS if all_data.get(m) is not None
    )
    html = HTML
    html = html.replace('__DATA__',         json.dumps(all_data, ensure_ascii=False))
    html = html.replace('__LABELS__',       json.dumps(MONTH_LABELS, ensure_ascii=False))
    html = html.replace('__CAT_COLORS__',   json.dumps(CAT_COLORS, ensure_ascii=False))
    html = html.replace('__MONTH_ORDER__',  json.dumps(MONTH_SHEETS, ensure_ascii=False))
    html = html.replace('__UPDATED__',      updated)
    html = html.replace('__MONTH_BUTTONS__', btns)
    return html

def main():
    now = datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')
    all_data = {}
    for sheet in MONTH_SHEETS:
        print(f'Buscando {sheet}...')
        text = fetch_csv(sheet)
        data = extract(text)
        all_data[sheet] = data
        if data and (data['total_gastos'] > 0 or data['total_receitas'] > 0):
            print(f'  OK  gastos={data["total_gastos"]:.2f}  receitas={data["total_receitas"]:.2f}')
        else:
            print(f'  Sem dados ou valores zerados')
    print('Gerando dashboard.html...')
    with open('dashboard.html', 'w', encoding='utf-8') as f:
        f.write(generate_html(all_data, now))
    print('Pronto!')

if __name__ == '__main__':
    main()
