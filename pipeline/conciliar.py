#!/usr/bin/env python3
"""Concilia saídas do extrato Itaú com os lançamentos de despesa/MP da DLP e gera alertas para o dashboard.
Uso: python pipeline/conciliar.py   (lê out/dlp_itens.json e os extratos de work/; grava out/alertas.json, concil_resumo.json, keeta_semanal.json, status.json)
Regras (mesmas da conciliação de setembro): valor igual (±R$ 0,02) em até 6 dias; soma das parcelas de uma mesma célula;
boleto Itaú Unibanco = fatura do cartão; comissões de cartão/apps são descontos na receita (não saem do banco);
vale/pagamento extra sem saída = provável dinheiro; lançamento futuro = programado."""
import json, os, sys, itertools, datetime, collections
from zoneinfo import ZoneInfo
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import extrato, config
OUT = config.OUT
PASTA_ITAU, PASTA_PAGBANK, PASTAS_HIST, ACEITOS = config.PASTA_ITAU, config.PASTA_PAGBANK, [config.PASTA_HIST], config.ACEITOS
COMISSOES = ("Comissão Cartões", "Comissão Ifood", "Comissão Keeta", "Comissão Rappi")
DINHEIRO = ("Vale Funcionário", "Pagamento Extra", "Vale Transporte")
SOCIO = ("Investimento",)
JANELA = 6; TOL = 0.02
DESDE = os.environ.get('CONCIL_DESDE', '2026-09-01')   # alertas só a partir deste mês (meses anteriores aparecem só no resumo)
INTERNOS = ('APL APLIC', 'RES APLIC', 'RESGATE', 'APLICACAO')            # aplicação automática: movimento entre contas, não é despesa
dt = lambda s: datetime.date.fromisoformat(s)
dias = lambda a,b: abs((dt(a)-dt(b)).days)

def concilia(itens, mov, corte):
    deb = [dict(m, i=n, usado=False, valor=-m["valor"]) for n,m in enumerate(mov) if m["valor"] < 0 and not any(t in m["desc"].upper() for t in INTERNOS)]
    parts = []
    for it in itens:
        if it["item"].strip() in COMISSOES: continue
        for k,p in enumerate(it["partes"]): parts.append({"d": it["d"], "item": it["item"].strip(), "linha": it["linha"], "grupo": it["grupo"], "valor": p, "cel": (it["d"],it["linha"]), "k": k, "par": None, "tipo": None})
    parts.sort(key=lambda p: (p["d"], p["linha"], p["k"]))
    def livres(): return [x for x in deb if not x["usado"]]
    # 1) valor igual, data mais próxima
    for p in parts:
        c = [x for x in livres() if abs(x["valor"]-p["valor"]) <= TOL and dias(x["d"],p["d"]) <= JANELA]
        if c:
            x = min(c, key=lambda x: dias(x["d"],p["d"])); x["usado"] = True; p["par"] = [x]; p["tipo"] = "conciliado"
    # 2) soma das parcelas da mesma célula = um débito
    cels = collections.defaultdict(list)
    for p in parts:
        if not p["par"]: cels[p["cel"]].append(p)
    for cel,ps in cels.items():
        if len(ps) < 2: continue
        tot = sum(p["valor"] for p in ps)
        c = [x for x in livres() if abs(x["valor"]-tot) <= TOL and dias(x["d"],ps[0]["d"]) <= JANELA]
        if c:
            x = min(c, key=lambda x: dias(x["d"],ps[0]["d"])); x["usado"] = True
            for p in ps: p["par"] = [x]; p["tipo"] = "conciliado"
    # 3) um débito = soma de parcelas soltas do mesmo item (até 3; qualquer quantidade para SISPAG de R$ 1.000 ou mais)
    soltas = [p for p in parts if not p["par"]]
    for x in livres():
        cand = [p for p in soltas if not p["par"] and dias(p["d"],x["d"]) <= JANELA]
        byitem = collections.defaultdict(list)
        for p in cand: byitem[p["linha"]].append(p)
        grande = "SISPAG" in x["desc"].upper() and x["valor"] >= 1000
        done = False
        for linha,ps in byitem.items():
            for n in (range(2, min(len(ps),12)+1) if grande else (2,3)):
                if len(ps) < n or len(ps) > 14: continue
                for comb in itertools.combinations(ps, n):
                    if abs(sum(p["valor"] for p in comb)-x["valor"]) <= TOL:
                        x["usado"] = True
                        for p in comb: p["par"] = [x]; p["tipo"] = "conciliado"
                        done = True; break
                if done: break
            if done: break
    # 3b) boleto Itaú Unibanco = fatura do cartão; a DLP lança a fatura em lote num só dia (pode haver 1-2 itens do dia que não são cartão)
    for x in livres():
        if "UNIBANCO" in (x["razao"]+x["desc"]).upper() and "BOLETO" in x["desc"].upper():
            melhor = None
            bydia = collections.defaultdict(list)
            for p in parts:
                if not p["par"] and -7 <= (dt(p["d"])-dt(x["d"])).days <= 1 and p["d"] <= corte and p["item"] not in DINHEIRO and p["item"] not in COMISSOES: bydia[p["d"]].append(p)
            for d,ps in bydia.items():
                nomes = sorted({p["item"] for p in ps})
                for k in range(0,3):
                    for fora in itertools.combinations(nomes, k):
                        sel = [p for p in ps if p["item"] not in fora]
                        dif = abs(sum(p["valor"] for p in sel) - x["valor"])
                        if sel and (melhor is None or dif < melhor[0]) : melhor = (dif, sel, d)
            if melhor and melhor[0] <= max(15, 0.03*x["valor"]):
                x["usado"] = True; x["fatura"] = True; x["lote_dif"] = round(sum(p["valor"] for p in melhor[1]) - x["valor"], 2); x["lote_dia"] = melhor[2]
                for p in melhor[1]: p["par"] = [x]; p["tipo"] = "fatura"
    # 4) quase iguais (até 5%): possível valor diferente
    for p in [p for p in parts if not p["par"] and p["d"] <= corte]:
        c = [x for x in livres() if dias(x["d"],p["d"]) <= 3 and abs(x["valor"]-p["valor"]) <= max(1.0, 0.05*p["valor"])]
        if c:
            x = min(c, key=lambda x: abs(x["valor"]-p["valor"])); x["usado"] = True; p["par"] = [x]
            p["tipo"] = "conciliado" if abs(x["valor"]-p["valor"]) <= 0.5 else "valor_diferente"
    return deb, parts

def main():
    itens = json.load(open(os.path.join(OUT, "dlp_itens.json")))
    mov_all, f_itau, f_pag, files, saldos_pag = extrato.carrega_contas(PASTA_ITAU, PASTA_PAGBANK, PASTAS_HIST)
    print("Itaú  (mais novo):", os.path.basename(f_itau) if f_itau else "NENHUM")
    print("PagBank (mais novo):", os.path.basename(f_pag) if f_pag else "NENHUM")
    mov = [m for m in mov_all if m["conta"] == "Itaú"]
    if not mov: sys.exit("Nenhum extrato do Itaú legível em " + PASTA_ITAU)
    corte = max(m["d"] for m in mov)
    # PagBank: entra na conciliação só o que SAI da conta para terceiros; transferência para a própria empresa (Itaú) é movimento interno
    pag_deb = [dict(m, desc="[PagBank] " + m["desc"]) for m in mov_all if m["conta"] == "PagBank" and m["valor"] < 0 and "LANCHONETE BAR E TEMAKERIA" not in (m["razao"] + m["desc"]).upper()]
    deb, parts = concilia(itens, mov + pag_deb, corte)
    pag_ate = max((m["d"] for m in mov_all if m["conta"] == "PagBank"), default="")
    alertas, resumo = [], collections.defaultdict(lambda: collections.Counter())
    n = 0
    def add(**k):
        nonlocal n; n += 1; alertas.append(dict(id=f"A{n:04d}", **k))
    for p in parts:
        m = p["d"][:7]; r = resumo[m]
        if p["tipo"] == "conciliado": r["conciliado_dlp"] += p["valor"]; r["n_conc"] += 1; continue
        if p["tipo"] == "fatura": r["lote_fatura"] += p["valor"]; continue
        if p["tipo"] == "valor_diferente":
            x = p["par"][0]; r["valor_dif"] += p["valor"]
            add(mes=m, data=p["d"], tipo="Valor diferente", gravidade="media", item=p["item"], valor_dlp=p["valor"], valor_extrato=x["valor"], diferenca=round(x["valor"]-p["valor"],2),
                descricao=f"DLP lançou R$ {p['valor']:.2f}; extrato pagou R$ {x['valor']:.2f} ({x['razao'] or x['desc']}, {x['d']})", acao="Conferir a nota ou o boleto e corrigir a DLP"); continue
        if p["d"] > corte:
            r["programado"] += p["valor"]; r["n_prog"] += 1; continue
        if p["item"] in DINHEIRO:
            r["dinheiro"] += p["valor"]; r["n_din"] += 1; continue
        if p["item"] in SOCIO:
            r["socio"] += p["valor"]; continue
        r["so_dlp"] += p["valor"]; r["n_so_dlp"] += 1
        grav = "alta" if p["valor"] >= 500 else ("media" if p["valor"] >= 100 else "baixa")
        add(mes=m, data=p["d"], tipo="Na DLP, sem saída no extrato", gravidade=grav, item=p["item"], valor_dlp=p["valor"], valor_extrato=0, diferenca=round(-p["valor"],2),
            descricao=f"{p['item']} lançado na DLP em {p['d']} e nenhuma saída igual no extrato (±{JANELA} dias)", acao="Ver se foi pago em dinheiro, no cartão, em outra conta ou se a data está errada")
    for x in deb:
        m = x["d"][:7]; r = resumo[m]; r["saidas_extrato"] += x["valor"]
        if x.get("fatura"):
            r["fatura_cartao"] += x["valor"]
            if abs(x["lote_dif"]) > 15: add(mes=m, data=x["d"], tipo="Fatura do cartão x lote da DLP", gravidade="media", item="Fatura Itaú Unibanco", valor_dlp=round(x["valor"]+x["lote_dif"],2), valor_extrato=x["valor"], diferenca=round(-x["lote_dif"],2), descricao=f"Boleto da fatura R$ {x['valor']:.2f}; lote lançado na DLP em {x['lote_dia']} soma R$ {x['valor']+x['lote_dif']:.2f}", acao="Conferir itens da fatura lançados na DLP")
            continue
        if x["usado"]: r["conciliado_ext"] += x["valor"]; continue
        if "TAR " in x["desc"].upper()[:4] or x["desc"].upper().startswith("TAR"): r["tarifas"] += x["valor"]; continue
        if "UNIBANCO" in (x["razao"]+x["desc"]).upper() and "BOLETO" in x["desc"].upper():
            r["fatura_cartao"] += x["valor"]; continue
        r["so_extrato"] += x["valor"]; r["n_so_ext"] += 1
        add(mes=m, data=x["d"], tipo="No extrato, sem lançamento na DLP", gravidade="alta" if x["valor"] >= 500 else ("media" if x["valor"] >= 100 else "baixa"), item=x["razao"] or x["desc"], valor_dlp=0, valor_extrato=x["valor"], diferenca=round(x["valor"],2),
            descricao=f"{x['desc']} de R$ {x['valor']:.2f} para {x['razao'] or 'favorecido não informado'} sem lançamento correspondente", acao="Lançar na DLP ou identificar o pagamento")
    # saldo do extrato: saldo anterior + movimentos = último saldo informado, por arquivo
    for f in files:
        mv, sd = extrato.le_arquivo(f)
        ant = [v for d,s_,v in sd if "ANTERIOR" in s_.upper()]
        tot = [(d,v) for d,s_,v in sd if "TOTAL DISPON" in s_.upper()] or [(d,v) for d,s_,v in sd if "ANTERIOR" not in s_.upper()]
        if ant and tot and mv:
            dfim, vfim = tot[-1]
            calc = round(ant[0]+sum(m["valor"] for m in mv if m["d"] <= dfim and not any(t in m["desc"].upper() for t in INTERNOS)),2)
            if abs(calc-vfim) > 0.05:
                add(mes=dfim[:7], data=dfim, tipo="Extrato não fecha", gravidade="alta", item=os.path.basename(f), valor_dlp=0, valor_extrato=vfim, diferenca=round(vfim-calc,2),
                    descricao=f"Saldo anterior + lançamentos até {dfim} = R$ {calc:.2f}, mas o extrato informa R$ {vfim:.2f}", acao="Baixar o extrato de novo; pode faltar período ou lançamento")
    # repasse Keeta: um Pix por semana (quarta) referente à semana anterior (seg-dom)
    dlp = json.load(open(os.path.join(OUT, "dlp_diario.json")))
    sem = collections.defaultdict(float)
    for d in dlp:
        x = dt(d["d"]); sem[(x - datetime.timedelta(days=x.weekday())).isoformat()] += d["keeta"]
    rep = collections.defaultdict(float)
    for m in mov:
        if m["valor"] > 0 and "KEETA" in m["razao"].upper():
            x = dt(m["d"]); rep[(x - datetime.timedelta(days=x.weekday()+7)).isoformat()] += m["valor"]
    keeta = []
    for w in sorted(sem):
        v = sem[w]; quarta = (dt(w)+datetime.timedelta(days=9)).isoformat()
        if v <= 0 or quarta > corte or w < "2026-08-24": continue
        rp = rep.get(w, 0); ret = 1-rp/v
        keeta.append({"semana": w, "venda_dlp": round(v,2), "repasse": round(rp,2), "retencao": round(ret,4)})
        if rp == 0: add(mes=w[:7], data=quarta, tipo="Repasse Keeta ausente", gravidade="alta", item="Keeta", valor_dlp=round(v,2), valor_extrato=0, diferenca=round(-v,2), descricao=f"Semana de {w}: venda Keeta na DLP e nenhum repasse no extrato", acao="Verificar o portal Keeta")
        elif ret < 0.33 or ret > 0.50: add(mes=w[:7], data=quarta, tipo="Retenção Keeta fora do padrão", gravidade="media", item="Keeta", valor_dlp=round(v,2), valor_extrato=round(rp,2), diferenca=round(rp-v*0.58,2), descricao=f"Semana de {w}: repasse de {100*(1-ret):.1f}% da venda (faixa usual 53% a 64%)", acao="Conferir vendas Keeta lançadas ou cupons no portal")
    aceitos = {}
    if os.path.exists(ACEITOS):
        for a in json.load(open(ACEITOS)): aceitos[a["chave"]] = a.get("motivo","")
    final = []
    for a in alertas:
        if a["mes"] < DESDE[:7]: continue
        a["chave"] = f'{a["data"]}|{str(a["item"]).strip()}|{abs(a["diferenca"]):.2f}'
        a["status"] = "aceito" if a["chave"] in aceitos else "aberto"
        a["motivo"] = aceitos.get(a["chave"], "")
        final.append(a)
    alertas = final
    rs = []
    for m,r in sorted(resumo.items()):
        rs.append({"mes": m, **{k: round(v,2) for k,v in r.items()}})
    json.dump(alertas, open(os.path.join(OUT,"alertas.json"),"w"), ensure_ascii=False)
    json.dump(rs, open(os.path.join(OUT,"concil_resumo.json"),"w"), ensure_ascii=False)
    json.dump(keeta, open(os.path.join(OUT,"keeta_semanal.json"),"w"), ensure_ascii=False)
    ult = max((d["d"] for d in dlp if d["tem_venda"]), default="")
    json.dump([{"extrato_ate": corte, "dlp_ate": ult, "arquivos_extrato": len(files), "itau_arquivo": os.path.basename(f_itau) if f_itau else "", "pagbank_arquivo": os.path.basename(f_pag) if f_pag else "", "pagbank_ate": pag_ate, "gerado_em": datetime.datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M")}], open(os.path.join(OUT,"status.json"),"w"), ensure_ascii=False)
    print("extrato até", corte, "| arquivos", len(files), "| alertas", len(alertas))
    for r in rs[-3:]: print(r)
if __name__ == "__main__": main()
