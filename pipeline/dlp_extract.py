#!/usr/bin/env python3
"""Lê a DLP (aba "26") e grava em out/: dlp_diario.json, desp_categorias.json, mp_fornecedores.json, dlp_itens.json.
Uso: python pipeline/dlp_extract.py "/caminho/_DLP_Nokyoski Moema.xlsx"
Linhas da aba 26: 56-72 canais, 74 serviço pago, 76 venda total, 81 compra MP (total), 82-121 fornecedores MP,
126-173 despesas, 177 aporte, 178 retirada. Se a DLP ganhar linhas, ajuste LINHAS abaixo."""
import openpyxl, datetime, json, re, sys, os
from collections import defaultdict
import config
OUT = config.OUT
LINHAS = dict(canais={"cartoes": [56,57,58,59,60,61,62,63], "vr": [64,65,66], "ifood": [67], "keeta": [68], "pix": [69], "food99": [70], "dinheiro": [71], "despesas_pagas": [72]},
              servico_pago=74, venda_total=76, mp_total=81, mp_forn=range(82,122), desp=range(126,174), aporte=177, retirada=178, comandas=53, pessoas=54)
SIMPLE = re.compile(r"^=\s*[\d\.\s\+]+$")
def num(v): return float(v) if isinstance(v,(int,float)) else 0.0
def load(path, data_only):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=data_only)
    return list(wb["26"].iter_rows(min_row=1, max_row=200, values_only=True))
def main(path):
    vals = load(path, True); frm = load(path, False)
    hdr = vals[1]; lab = lambda n: str(vals[n-1][1] or vals[n-1][2] or "").strip()
    R = lambda n,i: num(vals[n-1][i])
    cols = [(i,v) for i,v in enumerate(hdr) if isinstance(v, datetime.datetime) and v.year == 2026]
    days, itens = [], []
    for i,v in cols:
        d = {"d": v.strftime("%Y-%m-%d")}
        for k,rs in LINHAS["canais"].items(): d[k] = round(sum(R(r,i) for r in rs),2)
        d["servico_pago"] = round(R(LINHAS["servico_pago"],i),2); d["venda_total"] = round(R(LINHAS["venda_total"],i),2)
        d["comandas"] = R(LINHAS["comandas"],i); d["pessoas"] = R(LINHAS["pessoas"],i)
        d["mp"] = round(R(LINHAS["mp_total"],i),2)
        d["mp_forn"] = {lab(r): round(R(r,i),2) for r in LINHAS["mp_forn"] if R(r,i)}
        d["desp"] = {lab(r): round(R(r,i),2) for r in LINHAS["desp"] if R(r,i)}
        d["desp_total"] = round(sum(d["desp"].values()),2)
        d["lucro_bruto"] = round(d["venda_total"]-d["mp"],2); d["lucro_liq"] = round(d["lucro_bruto"]-d["desp_total"],2)
        d["aporte"] = round(R(LINHAS["aporte"],i),2); d["retirada"] = round(R(LINHAS["retirada"],i),2)
        d["tem_venda"] = 1 if d["venda_total"] > 0 else 0
        days.append(d)
        for grupo,rs in (("MP",LINHAS["mp_forn"]),("DESP",LINHAS["desp"])):
            for r in rs:
                total = R(r,i)
                if not total: continue
                raw = frm[r-1][i]
                parts = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", raw)] if isinstance(raw,str) and SIMPLE.match(raw) else [total]
                if abs(sum(parts)-total) > 0.05: parts = [total]
                itens.append({"d": d["d"], "linha": r, "item": lab(r), "grupo": grupo, "valor": round(total,2), "partes": [round(p,2) for p in parts]})
    cat, forn = defaultdict(float), defaultdict(float)
    for d in days:
        for k,v in d["desp"].items(): cat[(d["d"][:7],k)] += v
        for k,v in d["mp_forn"].items(): forn[(d["d"][:7],k)] += v
    flat = [{k: d[k] for k in ["d","venda_total","cartoes","vr","ifood","keeta","pix","food99","dinheiro","despesas_pagas","servico_pago","comandas","pessoas","mp","desp_total","lucro_bruto","lucro_liq","tem_venda"]} | {"aporte": abs(d["aporte"]), "retirada": abs(d["retirada"])} for d in days]
    os.makedirs(OUT, exist_ok=True)
    w = lambda n,o: json.dump(o, open(os.path.join(OUT,n),"w"), ensure_ascii=False)
    w("dlp_diario.json", flat)
    w("desp_categorias.json", [{"mes":m,"categoria":k,"valor":round(v,2)} for (m,k),v in sorted(cat.items()) if v])
    w("mp_fornecedores.json", [{"mes":m,"fornecedor":k,"valor":round(v,2)} for (m,k),v in sorted(forn.items()) if v])
    w("dlp_itens.json", itens)
    ult = max((d["d"] for d in days if d["tem_venda"]), default="")
    print(f"DLP lida: {len(days)} dias, {len(itens)} lançamentos de despesa/MP; última venda em {ult}")
if __name__ == "__main__": main(sys.argv[1])
