#!/usr/bin/env python3
"""Teste de ponta a ponta com dados INVENTADOS (nenhum dado real): monta uma DLP, extratos Itaú/PagBank e um PDV falsos no mesmo formato,
roda dlp_extract -> pdv_ler -> conciliar -> atualizar -> publicar e confere os resultados.
Uso: python tests/teste_sintetico.py <pasta_temporaria_vazia>"""
import os, sys, json, subprocess, datetime, shutil
import openpyxl

tmp = os.path.abspath(sys.argv[1]); shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
work, out, site = (os.path.join(tmp, x) for x in ("work", "out", "site"))
raiz = os.path.join(work, "TEMAKERIA - Docs"); ca = os.path.join(raiz, "_ADM", "CONTROLE_AUTOMACAO")
for p in (os.path.join(ca, "5_extratos_Itau_banco"), os.path.join(ca, "5-extatos_pagbank"), os.path.join(ca, "3_Saidas_Chefsolution_PDV", "2026_11"), os.path.join(ca, "7_dashboard")): os.makedirs(p)

# --- DLP falsa: aba "26", cabeçalho de datas na linha 2, rótulos na coluna B ---
wb = openpyxl.Workbook(); ws = wb.active; ws.title = "26"
dias = [datetime.datetime(2026, 11, d) for d in range(1, 6)]
for i, d in enumerate(dias): ws.cell(row=2, column=4 + i, value=d)
def lin(n, rotulo, valores):
    ws.cell(row=n, column=2, value=rotulo)
    for i, v in enumerate(valores): ws.cell(row=n, column=4 + i, value=v)
lin(53, "Comandas", [30, 32, 28, 35, 40]); lin(54, "Pessoas", [60, 64, 55, 70, 80])
lin(56, "Cartão", [1000, 1100, 900, 1200, 1300]); lin(68, "Keeta", [500, 600, 0, 0, 0]); lin(71, "Dinheiro", [100, 100, 100, 100, 100])
lin(76, "Venda total", [1600, 1800, 1000, 1300, 1400]); lin(81, "Compra MP", [500, 500, 300, 400, 400])
lin(82, "Nordsee", [500, 0, 0, 0, 0]); lin(126, "Folha de Pagamento", [0, 0, 0, 800, 0]); lin(127, "Energia", [0, 0, 300, 0, 0])
lin(177, "Aporte Financeiro", [0, 0, 0, 0, 0]); lin(178, "Retirada (socios)", [0, 0, 0, 0, 200])
wb.save(os.path.join(raiz, "_DLP_Nokyoski Moema.xlsx"))

# --- Itaú falso: com UMA COLUNA EM BRANCO à esquerda (como o export novo), saldo anterior/total, fatura e Keeta ---
wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lançamentos"
ws.append(["Lançamentos"]); ws.append([None, "Periodo:", "01/11/2026 até 05/11/2026"]); ws.append([])
ws.append([None, "Data", "Lançamento", "Razão Social", "CPF/CNPJ", "Valor (R$)", "Saldo (R$)"])
ws.append([None, "31/10/2026", "SALDO ANTERIOR", None, None, None, 1000])
ws.append([None, "01/11/2026", "BOLETO PAGO", "NORDSEE C I EXPORTADORA LTDA", "00.246.279/0001-98", -500, None])
ws.append([None, "03/11/2026", "PAGAMENTOS", "ENEL DISTRIBUICAO", "61.695.227/0001-93", -300, None])
ws.append([None, "04/11/2026", "SISPAG SALARIOS", None, None, -800, None])
ws.append([None, "04/11/2026", "PIX RECEBIDO KEETA D04/11", "KEETA DELIVERY BRAZIL LTD", "61.086.275/0001-84", 2000, None])
ws.append([None, "05/11/2026", "PIX ENVIADO", "FULANO SEM LANCAMENTO", "000", -777.77, None])
ws.append([None, "05/11/2026", "SALDO TOTAL DISPONÍVEL DIA", None, None, None, 1000 - 500 - 300 - 800 + 2000 - 777.77])
wb.save(os.path.join(ca, "5_extratos_Itau_banco", "26_11_05_Extrato_Lançamentos_ITAU.xlsx"))

# --- PagBank falso (com saldo em texto BR) ---
wb = openpyxl.Workbook(); ws = wb.active; ws.title = "report"
ws.append(["report"]); ws.append([]); ws.append(["Data", "Tipo", "Descrição", "Entradas", "Saidas", "Saldo"])
ws.append(["03/11/2026", "Vendas", "Disponivel CREDITO VISA", 100.0, None, None])
ws.append(["03/11/2026", "Pix enviado", "Lanchonete Bar E Temakeria Moema Ltda", None, -6000.0, None])
ws.append(["03/11/2026", "Saldo do dia", "R$ 1.950,06", None, None, "R$ 1.950,06"])
wb.save(os.path.join(ca, "5-extatos_pagbank", "26_11_05_PagSeguro.xlsx"))

json.dump([], open(os.path.join(ca, "7_dashboard", "conciliacao_aceitos.json"), "w"))
os.makedirs(os.path.join(work, "notas"))
json.dump({"chave": "2026-11-05|FULANO SEM LANCAMENTO|777.77", "motivo": "teste de nota", "criado_em": "2026-11-11T12:00:00Z"}, open(os.path.join(work, "notas", "nota_x.json"), "w"))
json.dump([{"contem": "ninguem", "motivo": "regra que não bate"}], open(os.path.join(ca, "7_dashboard", "conciliacao_regras.json"), "w"))

env = dict(os.environ, DASH_WORK=work, DASH_OUT=out, DASH_SITE=site, DASH_PASSWORD="senha-de-teste-123", CONCIL_DESDE="2026-11-01", DASH_VERBOSE="1")
def roda(*args):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, env=env, cwd=REPO)
    print(r.stdout.strip());
    if r.returncode: print(r.stderr[-2000:]); sys.exit("FALHOU: " + " ".join(args))
roda(os.path.join(REPO, "pipeline", "atualizar.py"))
roda(os.path.join(REPO, "pipeline", "publicar.py"))

dlp = json.load(open(os.path.join(out, "dlp_diario.json"))); assert len(dlp) == 5 and dlp[0]["venda_total"] == 1600, dlp[:1]
st = json.load(open(os.path.join(out, "status.json")))[0]; assert st["extrato_ate"] == "2026-11-05" and st["dlp_ate"] == "2026-11-05", st
assert st["pagbank_ate"] == "2026-11-03", st
al = json.load(open(os.path.join(out, "alertas.json")))
aberto = [a for a in al if a["status"] == "aberto"]; aceito = [a for a in al if a["status"] == "aceito"]
print("abertos:", [(a["tipo"], a["item"], a["diferenca"]) for a in aberto]); print("aceitos:", [(a["tipo"], a["item"]) for a in aceito])
assert any("FULANO" in a["item"] and "explicado no app" in a["motivo"] for a in aceito), "a nota do app deveria aceitar o item"
assert not any("NORDSEE" in a["item"].upper() for a in aberto), "Nordsee 500 deveria conciliar"
assert os.path.exists(os.path.join(site, "data.enc.json"))
print("OK: pipeline sintético passou. Pacote em", os.path.join(site, "data.enc.json"))
