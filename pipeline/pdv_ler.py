#!/usr/bin/env python3
"""Lê os relatórios 'faturamento' do PDV Chef Solution (coluna Físico) e compara com a DLP por período.
Saídas em out/: pdv_dlp.json (um registro por período) e pdv_alertas.json (diferenças acima do limite).
Limites: alta >= R$ 1.000, média >= R$ 300 (diferença de qualquer grupo ou do total)."""
import xlrd, glob, os, re, json, datetime, sys, unicodedata
import config
OUT, PDV = config.OUT, config.PASTA_PDV
MESES = {"janeiro":1,"fevereiro":2,"marco":3,"abril":4,"maio":5,"junho":6,"julho":7,"agosto":8,"agoste":8,"setembro":9,"outubro":10,"novembro":11,"dezembro":12}
def norm(s): return unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode().lower()
def periodo(nome, pasta_mes):
    n = norm(nome)
    if "inteiro" in n or re.search(r"faturamento mes", n): return None
    m = re.search(r"(\d{1,2})(?:[./](\d{1,2}))?\s*(?:ate|a)\s*(\d{1,2})(?:[./](\d{1,2}))?", n)
    if not m:
        # relatório de um dia só, ex.: "faturamento 27.10.2026.xls" (pasta AAAA_MM_por_dia)
        d = re.search(r"(\d{1,2})[./](\d{1,2})[./](20\d{2})", n)
        if not d: return None
        try: dia = datetime.date(int(d.group(3)), int(d.group(2)), int(d.group(1)))
        except ValueError: return None
        return dia, dia
    
    d1, m1, d2, m2 = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
    nome_mes = next((v for k,v in MESES.items() if k in n), None)
    fim_m = int(m2) if m2 else (nome_mes or pasta_mes)
    ini_m = int(m1) if m1 else (fim_m if d1 <= d2 else (fim_m-1 or 12))
    y = 2026
    try: ini = datetime.date(y if ini_m <= fim_m else y-1, ini_m, d1); fim = datetime.date(y, fim_m, d2)
    except ValueError: return None
    if fim < ini: return None
    return ini, fim
def le_fisico(path):
    sh = xlrd.open_workbook(path, logfile=open(os.devnull,"w")).sheet_by_index(0)
    g = {}
    for r in range(1, sh.nrows):
        nome = norm(str(sh.cell_value(r,0))).strip()
        try: fis = float(sh.cell_value(r,3))
        except Exception: continue
        g.setdefault(nome, []).append(fis)
    return g
def main():
    dlp = {d["d"]: d for d in json.load(open(os.path.join(OUT,"dlp_diario.json")))}
    regs, alertas = [], []
    # 1) quais dias têm relatório diário: o período que já está inteiro coberto por relatórios diários não entra de novo (evita contar duas vezes)
    arquivos = []
    for f in sorted(glob.glob(os.path.join(PDV, "20*", "*.xls"))):
        nome = os.path.basename(f)
        if not norm(nome).startswith("faturamento") : continue
        pasta_mes = int(os.path.basename(os.path.dirname(f))[5:7])
        p = periodo(nome, pasta_mes)
        if p: arquivos.append((f, nome, p))
    dias_com_relatorio = {p[0] for _, _, p in arquivos if p[0] == p[1]}
    for f, nome, p in arquivos:
        ini, fim = p
        if ini != fim and all((ini+datetime.timedelta(days=i)) in dias_com_relatorio for i in range((fim-ini).days+1)): continue
        try: g = le_fisico(f)
        except Exception as e: print("  aviso: não li", nome, e); continue
        # grupos de topo (linhas-pai): Cartao, Ticket, Outros, Pix, Dinheiro
        def top(*ns): return round(sum(g[n][0] for n in ns if n in g), 2)
        pdv = {"cartao_vale": top("cartao","ticket"), "delivery": top("outros"), "pix": top("pix"), "dinheiro": top("dinheiro")}
        pdv["total"] = round(sum(pdv.values()),2)
        dias = [(ini+datetime.timedelta(days=i)).isoformat() for i in range((fim-ini).days+1)]
        L = [dlp[d] for d in dias if d in dlp]
        dl = {"cartao_vale": sum(x["cartoes"]+x["vr"] for x in L), "delivery": sum(x["ifood"]+x["keeta"]+x["food99"] for x in L), "pix": sum(x["pix"] for x in L), "dinheiro": sum(x["dinheiro"] for x in L)}
        dl["total"] = sum(dl.values()); dl = {k: round(v,2) for k,v in dl.items()}
        dif = {k: round(dl[k]-pdv[k],2) for k in pdv}
        pior = max(abs(v) for v in dif.values())
        reg = {"periodo": (ini.strftime('%d/%m') if ini == fim else f"{ini.strftime('%d/%m')} a {fim.strftime('%d/%m')}"), "ini": ini.isoformat(), "fim": fim.isoformat(), "arquivo": nome, "dias_dlp": len(L),
               **{f"pdv_{k}": v for k,v in pdv.items()}, **{f"dlp_{k}": v for k,v in dl.items()}, **{f"dif_{k}": v for k,v in dif.items()}, "maior_dif": pior}
        reg["situacao"] = "diverge" if pior >= 300 else "confere"
        regs.append(reg)
        if pior >= 300:
            k = max(dif, key=lambda x: abs(dif[x]))
            incompleta = dl["total"] <= 0.6*pdv["total"]
            if incompleta: reg["situacao"] = "DLP incompleta"
            alertas.append({"mes": fim.isoformat()[:7], "data": fim.isoformat(), "tipo": "PDV com a DLP incompleta" if incompleta else "PDV x DLP", "gravidade": "alta" if pior >= 1000 else "media", "item": f"PDV {reg['periodo']} ({k.replace('_',' ')})",
                            "valor_dlp": dl[k], "valor_extrato": pdv[k], "diferenca": dif[k], "descricao": f"{reg['periodo']}: DLP {dl[k]:.2f} x PDV {pdv[k]:.2f} em {k.replace('_',' ')}", "acao": "Lançar o período na DLP" if incompleta else "Conferir o fechamento do dia no PDV e o lançamento na DLP"})
    regs.sort(key=lambda r: r["ini"])
    json.dump(regs, open(os.path.join(OUT,"pdv_dlp.json"),"w"), ensure_ascii=False)
    json.dump(alertas, open(os.path.join(OUT,"pdv_alertas.json"),"w"), ensure_ascii=False)
    print(len(regs), "períodos do PDV |", len(alertas), "divergências")
    for r in regs[-14:]: print(r["periodo"], r["pdv_total"], r["dlp_total"], r["maior_dif"], r["situacao"])
if __name__ == "__main__": main()
