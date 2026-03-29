#!/usr/bin/env python3
"""Gera dashboard.html a partir do Google Sheets CSV"""

import csv, io, json, urllib.request
from datetime import datetime, timezone

SHEET_ID = '1xOB9bCLSkGPsZbXPHOuZFnA8_KKXMS6sbrrIsHCRak0'

def fetch_csv():
    url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8-sig')

def parse_currency(val):
    if not val:
        return 0.0
    s = str(val).strip().replace('R$', '').replace(' ', '').replace('\xa0', '')
    parts = s.split('.')
    if len(parts) > 2:
        s = ''.join(parts[:-1]) + '.' + parts[-1]
    try:
        return float(s)
    except ValueError:
        return 0.0

def fmt(val):
    return f"R$ {val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def extract_data(rows):
    data = {
        'gastos': [], 'receitas': [],
        'inter_inst': [], 'inter_trans': [],
        'nubank': [], 'caixa': [],
        'total_gastos': 0, 'total_receitas': 0,
        'para_pagar': 0, 'para_receber': 0, 'saldo': 0,
        'total_inter': 0, 'total_nubank': 0, 'total_caixa': 0,
    }

    def g(row, i):
        return row[i].strip() if len(row) > i else ''

    section = None
    for row in rows:
        c0, c1 = g(row, 0), g(row, 1)

        if c0 == 'GASTOS MENSAIS':   section = 'gastos';   continue
        if c0 == 'RECEITA MENSAL':   section = 'receitas'; continue
        if c0 == 'RESTAM PARA O MÊS': section = 'summary'; continue
        if c0 in ('', 'DESCRIÇÃO'):  pass

        # --- Cartão Inter ---
        if section == 'gastos':
            d, desc, val, parc = g(row,6), g(row,7), g(row,8), g(row,9)
            if desc and val and desc not in ('Fatura dezembro','Valor','Total','TOTAL'):
                v = parse_currency(val)
                if v > 0:
                    if d:
                        data['inter_trans'].append({'date':d,'desc':desc,'val':v,'parc':parc})
                    else:
                        data['inter_inst'].append({'desc':desc,'val':v,'parc':parc})
            # Inter total
            if g(row,7) == 'Total' and g(row,8):
                data['total_inter'] = parse_currency(g(row,8))

            # --- Cartão Nubank ---
            nd, nv, np = g(row,12), g(row,13), g(row,14)
            if nd == 'TOTAL' and nv:
                data['total_nubank'] = parse_currency(nv)
            elif nd and nv and nd not in ('Fatura dezembro','TOTAL','Total'):
                v = parse_currency(nv)
                if v > 0:
                    data['nubank'].append({'desc':nd,'val':v,'parc':np})

            # --- Cartão Caixa ---
            cd, cv, cp = g(row,16), g(row,17), g(row,18)
            if cd == 'TOTAL' and cv:
                data['total_caixa'] = parse_currency(cv)
            elif cd and cv and cd not in ('Fatura dezembro','TOTAL','Total'):
                v = parse_currency(cv)
                if v > 0:
                    data['caixa'].append({'desc':cd,'val':v,'parc':cp})

        # --- Gastos ---
        if section == 'gastos':
            if c0 == 'TOTAL' and c1:
                data['total_gastos'] = parse_currency(c1)
            elif c0 and c0 not in ('DESCRIÇÃO','GASTOS MENSAIS'):
                data['gastos'].append({
                    'desc':c0,'val':c1,
                    'data':g(row,2),'obs':g(row,3),'status':g(row,4)
                })

        elif section == 'receitas':
            if c0 == 'TOTAL' and c1:
                data['total_receitas'] = parse_currency(c1)
            elif c0 and c0 != 'DESCRIÇÃO':
                data['receitas'].append({
                    'desc':c0,'val':c1,'data':g(row,2),'status':g(row,4)
                })

        elif section == 'summary':
            if c0 == 'PARA PAGAR':    data['para_pagar']    = parse_currency(c1)
            elif c0 == 'PARA RECEBER': data['para_receber']  = parse_currency(c1)
            elif c0 == 'TOTAL':        data['saldo']          = parse_currency(c1)

    # fallback inter total
    if data['total_inter'] == 0:
        data['total_inter'] = sum(x['val'] for x in data['inter_inst']) + sum(x['val'] for x in data['inter_trans'])
    if data['total_nubank'] == 0:
        data['total_nubank'] = sum(x['val'] for x in data['nubank'])
    if data['total_caixa'] == 0:
        data['total_caixa'] = sum(x['val'] for x in data['caixa'])

    return data

def badge(status):
    s = status.lower()
    if 'não' in s or 'nao' in s:
        return f'<span class="badge nao">{status}</span>'
    return f'<span class="badge pago">{status}</span>'

def tr_gastos(g):
    rows = ''
    for item in g['gastos']:
        rows += f"""<tr>
          <td>{item['desc']}</td><td>{item['val']}</td>
          <td>{item['data']}</td><td>{item['obs']}</td>
          <td>{badge(item['status'])}</td>
        </tr>"""
    return rows

def tr_receitas(g):
    rows = ''
    for item in g['receitas']:
        rows += f"""<tr>
          <td>{item['desc']}</td><td>{item['val']}</td>
          <td>{item['data']}</td><td>{badge(item['status'])}</td>
        </tr>"""
    return rows

def card_rows(items):
    return ''.join(
        f'<div class="cartao-item"><span class="desc">{x["desc"]}</span>'
        f'<span class="val">{fmt(x["val"])} <small>{x["parc"]}</small></span></div>'
        for x in items
    )

def generate_html(data):
    now = datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')
    saldo_class = 'positivo' if data['saldo'] >= 0 else 'negativo'
    saldo_label = fmt(data['saldo'])

    # Chart data
    gastos_labels = json.dumps([x['desc'] for x in data['gastos'] if parse_currency(x['val']) > 0][:10])
    gastos_values = json.dumps([parse_currency(x['val']) for x in data['gastos'] if parse_currency(x['val']) > 0][:10])

    receitas_labels = json.dumps([x['desc'] for x in data['receitas']])
    receitas_values = json.dumps([parse_currency(x['val']) for x in data['receitas']])
    receitas_colors = json.dumps([
        '#22c55e' if 'recebido' in x['status'].lower() and 'não' not in x['status'].lower() else '#ef4444'
        for x in data['receitas']
    ])

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Dashboard Financeiro</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:24px}}
    h1{{text-align:center;font-size:1.8rem;margin-bottom:6px;color:#f8fafc}}
    .subtitle{{text-align:center;color:#94a3b8;font-size:.85rem;margin-bottom:28px}}
    .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin-bottom:24px}}
    .card{{background:#1e293b;border-radius:12px;padding:18px;border-left:4px solid}}
    .card.receita{{border-color:#22c55e}}.card.gasto{{border-color:#ef4444}}
    .card.saldo-positivo{{border-color:#3b82f6}}.card.saldo-negativo{{border-color:#f43f5e}}
    .card.pagar{{border-color:#f59e0b}}.card.receber{{border-color:#a855f7}}
    .card h3{{font-size:.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}}
    .card .valor{{font-size:1.5rem;font-weight:700}}
    .card.receita .valor{{color:#22c55e}}.card.gasto .valor{{color:#ef4444}}
    .card.saldo-positivo .valor{{color:#3b82f6}}.card.saldo-negativo .valor{{color:#f43f5e}}
    .card.pagar .valor{{color:#f59e0b}}.card.receber .valor{{color:#a855f7}}
    .grid-2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px;margin-bottom:24px}}
    .box{{background:#1e293b;border-radius:12px;padding:20px}}
    .box h2{{font-size:.95rem;color:#cbd5e1;margin-bottom:14px;border-bottom:1px solid #334155;padding-bottom:8px}}
    .chart-wrap{{position:relative;height:250px}}
    .table-wrap{{overflow-x:auto}}
    table{{width:100%;border-collapse:collapse;font-size:.82rem}}
    th{{background:#0f172a;color:#94a3b8;text-align:left;padding:9px 10px;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em}}
    td{{padding:8px 10px;border-bottom:1px solid #1e293b55}}
    tr:hover td{{background:#1e293b55}}
    .badge{{display:inline-block;padding:2px 9px;border-radius:999px;font-size:.7rem;font-weight:600}}
    .badge.pago{{background:#14532d;color:#4ade80}}.badge.nao{{background:#7f1d1d;color:#fca5a5}}
    .cartao-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:16px;margin-bottom:24px}}
    .cartao-box{{background:#1e293b;border-radius:12px;padding:18px}}
    .cartao-box h2{{font-size:.95rem;color:#cbd5e1;margin-bottom:12px}}
    .cartao-item{{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #334155;font-size:.8rem}}
    .cartao-item:last-of-type{{border-bottom:none}}
    .cartao-item .desc{{color:#94a3b8;flex:1;padding-right:8px}}
    .cartao-item .val{{color:#f8fafc;font-weight:600;white-space:nowrap}}
    .cartao-item small{{color:#64748b;margin-left:4px}}
    .cartao-total{{margin-top:10px;text-align:right;font-size:.88rem;color:#ef4444;font-weight:700}}
    footer{{text-align:center;color:#475569;font-size:.72rem;margin-top:20px}}
  </style>
</head>
<body>
<h1>Dashboard Financeiro</h1>
<p class="subtitle">Atualizado automaticamente · {now}</p>

<div class="cards">
  <div class="card receita"><h3>Receita Total</h3><div class="valor">{fmt(data['total_receitas'])}</div></div>
  <div class="card gasto"><h3>Gastos Totais</h3><div class="valor">{fmt(data['total_gastos'])}</div></div>
  <div class="card saldo-{saldo_class}"><h3>Saldo Líquido</h3><div class="valor">{saldo_label}</div></div>
  <div class="card pagar"><h3>Ainda a Pagar</h3><div class="valor">{fmt(data['para_pagar'])}</div></div>
  <div class="card receber"><h3>Ainda a Receber</h3><div class="valor">{fmt(data['para_receber'])}</div></div>
</div>

<div class="grid-2">
  <div class="box"><h2>Receita vs Gastos</h2><div class="chart-wrap"><canvas id="cBar"></canvas></div></div>
  <div class="box"><h2>Composição dos Gastos</h2><div class="chart-wrap"><canvas id="cPizza"></canvas></div></div>
</div>

<div class="grid-2">
  <div class="box"><h2>Receitas por Status</h2><div class="chart-wrap"><canvas id="cReceitas"></canvas></div></div>
  <div class="box"><h2>Faturas dos Cartões</h2><div class="chart-wrap"><canvas id="cCartoes"></canvas></div></div>
</div>

<div class="cartao-grid">
  <div class="cartao-box">
    <h2>💳 Cartão Inter</h2>
    {card_rows(data['inter_inst'])}
    <div class="cartao-total">Total parcelas: {fmt(data['total_inter'])}</div>
  </div>
  <div class="cartao-box">
    <h2>💳 Cartão Nubank</h2>
    {card_rows(data['nubank'])}
    <div class="cartao-total">Total: {fmt(data['total_nubank'])}</div>
  </div>
  <div class="cartao-box">
    <h2>💳 Cartão Caixa</h2>
    {card_rows(data['caixa'])}
    <div class="cartao-total">Total: {fmt(data['total_caixa'])}</div>
  </div>
</div>

<div class="box" style="margin-bottom:20px">
  <h2>Gastos Mensais</h2>
  <div class="table-wrap"><table>
    <thead><tr><th>Descrição</th><th>Valor</th><th>Vencimento</th><th>Tipo</th><th>Status</th></tr></thead>
    <tbody>{tr_gastos(data)}</tbody>
  </table></div>
</div>

<div class="box" style="margin-bottom:20px">
  <h2>Receitas Mensais</h2>
  <div class="table-wrap"><table>
    <thead><tr><th>Descrição</th><th>Valor</th><th>Data</th><th>Status</th></tr></thead>
    <tbody>{tr_receitas(data)}</tbody>
  </table></div>
</div>

<footer>Dashboard Financeiro · Dados do Google Sheets · Gerado em {now}</footer>

<script>
const COLORS = ['#6366f1','#ef4444','#8b5cf6','#ec4899','#f59e0b','#14b8a6','#22c55e','#3b82f6','#94a3b8','#f97316'];
const opts = (cb) => ({{
  responsive:true, maintainAspectRatio:false,
  plugins:{{legend:{{display:false}}}},
  scales:{{
    x:{{ticks:{{color:'#94a3b8'}},grid:{{color:'#1e293b'}}}},
    y:{{ticks:{{color:'#94a3b8',callback:cb}},grid:{{color:'#334155'}}}}
  }}
}});
const brl = v => 'R$ '+Number(v).toLocaleString('pt-BR',{{minimumFractionDigits:0,maximumFractionDigits:0}});

new Chart(document.getElementById('cBar'),{{
  type:'bar',
  data:{{
    labels:['Receita','Gastos','Saldo Restante'],
    datasets:[{{
      data:[{data['total_receitas']},{data['total_gastos']},{data['saldo']}],
      backgroundColor:['#22c55e88','#ef444488','#3b82f688'],
      borderColor:['#22c55e','#ef4444','#3b82f6'],
      borderWidth:2,borderRadius:6
    }}]
  }},
  options:opts(brl)
}});

new Chart(document.getElementById('cPizza'),{{
  type:'doughnut',
  data:{{
    labels:{gastos_labels},
    datasets:[{{
      data:{gastos_values},
      backgroundColor:COLORS,borderWidth:0
    }}]
  }},
  options:{{
    responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{position:'right',labels:{{color:'#94a3b8',font:{{size:10}},boxWidth:10,padding:8}}}}}}
  }}
}});

new Chart(document.getElementById('cReceitas'),{{
  type:'bar',
  data:{{
    labels:{receitas_labels},
    datasets:[{{
      data:{receitas_values},
      backgroundColor:{receitas_colors},
      borderRadius:4
    }}]
  }},
  options:{{...opts(brl),indexAxis:'y'}}
}});

new Chart(document.getElementById('cCartoes'),{{
  type:'bar',
  data:{{
    labels:['Inter','Nubank','Caixa'],
    datasets:[{{
      data:[{data['total_inter']},{data['total_nubank']},{data['total_caixa']}],
      backgroundColor:['#f59e0b88','#a855f788','#22c55e88'],
      borderColor:['#f59e0b','#a855f7','#22c55e'],
      borderWidth:2,borderRadius:6
    }}]
  }},
  options:opts(brl)
}});
</script>
</body>
</html>"""

def main():
    print("Buscando CSV do Google Sheets...")
    text = fetch_csv()
    rows = list(csv.reader(io.StringIO(text)))
    print(f"  {len(rows)} linhas lidas")

    print("Extraindo dados...")
    data = extract_data(rows)
    print(f"  Gastos: {len(data['gastos'])} | Receitas: {len(data['receitas'])}")
    print(f"  Total gastos: {fmt(data['total_gastos'])} | Receitas: {fmt(data['total_receitas'])}")

    print("Gerando dashboard.html...")
    html = generate_html(data)
    with open('dashboard.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("  dashboard.html gerado com sucesso!")

if __name__ == '__main__':
    main()
