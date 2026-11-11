#!/usr/bin/env python3
"""Lê os extratos Itaú (xlsx "Lançamentos") e PagBank (aba 'report') e devolve a lista de movimentos.
Versão da nuvem do extrato.py da pasta 7_dashboard/scripts (mesma lógica; a única mudança é achar a coluna "Data" onde ela estiver,
pois alguns exports começam uma coluna mais à direita)."""
import openpyxl, glob, os, re, datetime
from collections import Counter


def _d(s):
    try: return datetime.datetime.strptime(str(s).strip()[:10], "%d/%m/%Y").strftime("%Y-%m-%d")
    except Exception: return None


def _acha_cabecalho(rows, confere):
    """Devolve (indice_da_linha, deslocamento_da_coluna) do cabeçalho que começa em 'Data', ou (None, 0)."""
    for n, r in enumerate(rows):
        if not r: continue
        for off, x in enumerate(r):
            if x == "Data" and confere(r[off:]): return n, off
    return None, 0


def le_arquivo(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Lançamentos"] if "Lançamentos" in wb.sheetnames else wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True)); mov, saldos = [], []
    hi, off = _acha_cabecalho(rows, lambda r: len(r) > 1 and r[1] and "Lan" in str(r[1]))
    if hi is None: return [], []
    hdr = [str(x or "") for x in rows[hi][off:]]
    ci = {h: i for i, h in enumerate(hdr)}
    iv = ci.get("Valor (R$)"); isl = ci.get("Saldo (R$)"); ira = ci.get("Razão Social"); ic = ci.get("CPF/CNPJ")
    for r in rows[hi+1:]:
        r = tuple(r[off:]) if r else ()
        if len(r) < 2: continue
        d = _d(r[0]); desc = str(r[1] or "").strip()
        if not d or not desc: continue
        if desc.upper().startswith("SALDO"):
            if isl is not None and isl < len(r) and isinstance(r[isl], (int, float)): saldos.append((d, desc, float(r[isl])))
            continue
        v = r[iv] if iv is not None and iv < len(r) else None
        if not isinstance(v, (int, float)): continue
        mov.append({"d": d, "desc": desc, "razao": str(r[ira] or "").strip() if ira is not None and ira < len(r) else "",
                    "doc": str(r[ic] or "").strip() if ic is not None and ic < len(r) else "", "valor": round(float(v), 2)})
    return mov, saldos


def le_pastas(pastas):
    files = []
    for p in pastas: files += glob.glob(os.path.join(p, "Extrato*.xlsx"))
    best = {}; saldos = []
    for f in sorted(files):
        try: mov, sd = le_arquivo(f)
        except Exception as e: print("  aviso: não consegui ler", os.path.basename(f), e); continue
        saldos += [(d, s, v, os.path.basename(f)) for d, s, v in sd]
        c = Counter((m["d"], m["razao"].upper().rstrip(". "), m["valor"]) for m in mov)
        sample = {(m["d"], m["razao"].upper().rstrip(". "), m["valor"]): m for m in mov}
        for k, n in c.items():
            if n > best.get(k, (0, None))[0]: best[k] = (n, sample[k])
    out = []
    for k, (n, m) in best.items(): out += [dict(m) for _ in range(n)]
    out.sort(key=lambda m: (m["d"], m["desc"], m["valor"]))
    return out, saldos, files


def _num_br(s):
    s = str(s).replace("R$", "").replace("\xa0", "").replace(" ", "").strip()
    try: return float(s.replace(".", "").replace(",", "."))
    except Exception: return None


def le_pagbank(path):
    """Extrato PagBank/PagSeguro (aba 'report'): Data, Tipo, Descrição, Entradas, Saidas, Saldo. Devolve (movimentos, saldos)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]; rows = list(ws.iter_rows(values_only=True))
    hi, off = _acha_cabecalho(rows, lambda r: any(str(x or "").startswith("Entrada") for x in r))
    if hi is None: return [], []
    hdr = [str(x or "") for x in rows[hi][off:]]
    ci = {h: i for i, h in enumerate(hdr)}
    it, ide, ie, isd, isl = ci.get("Tipo"), ci.get("Descrição"), ci.get("Entradas"), ci.get("Saidas"), ci.get("Saldo")
    g = lambda r, i: r[i] if i is not None and i < len(r) else None
    mov, saldos = [], []
    for r in rows[hi+1:]:
        r = tuple(r[off:]) if r else ()
        if not r: continue
        d = _d(r[0])
        if not d: continue
        tipo = str(g(r, it) or "").strip()
        if tipo.lower().startswith("saldo"):
            v = _num_br(g(r, isl)) if g(r, isl) is not None else None
            if v is not None: saldos.append((d, "SALDO DO DIA", v))
            continue
        ent = g(r, ie) if isinstance(g(r, ie), (int, float)) else 0
        sai = g(r, isd) if isinstance(g(r, isd), (int, float)) else 0
        v = round(float(ent) + float(sai), 2)   # saídas já vêm negativas
        if v == 0: continue
        desc = str(g(r, ide) or "").strip()
        mov.append({"d": d, "desc": (tipo + " " + desc).strip(), "razao": desc, "doc": "", "valor": v})
    return mov, saldos


def ultimo_arquivo(pasta, leitor):
    """Arquivo .xlsx mais novo (data de modificação) da pasta que o leitor consegue interpretar. Devolve (caminho, mov, saldos) ou (None,[],[])."""
    cands = [f for f in glob.glob(os.path.join(pasta, "*.xlsx")) if not os.path.basename(f).startswith("~$")]
    cands.sort(key=os.path.getmtime, reverse=True)
    for i, f in enumerate(cands):
        try: mov, sd = leitor(f)
        except Exception as e:
            print("  AVISO: não consegui abrir", os.path.basename(f), "-", e); continue
        if not mov: continue   # ex.: fatura de cartão ou arquivo de outro formato
        if i > 0: print("  AVISO: usando", os.path.basename(f), "porque os arquivos mais novos da pasta não são extrato legível")
        return f, mov, sd
    return None, [], []


def carrega_contas(pasta_itau, pasta_pagbank, pastas_historico=()):
    """Movimentos das duas contas. Itaú: sempre o arquivo mais novo de pasta_itau; extratos antigos só completam meses ANTERIORES ao início dele.
    PagBank: sempre o arquivo mais novo de pasta_pagbank. Cada movimento recebe 'conta' = 'Itaú' ou 'PagBank'."""
    fi, mi, si = ultimo_arquivo(pasta_itau, le_arquivo)
    usados = [fi] if fi else []
    movs = []
    if fi:
        ini = min(m["d"] for m in mi)
        hist, _, hf = le_pastas([pasta_itau] + list(pastas_historico))
        movs += [m for m in hist if m["d"] < ini]
        usados += [f for f in hf if f != fi]
        movs += mi
    movs = [dict(m, conta="Itaú") for m in movs]
    fp, mp, sp = ultimo_arquivo(pasta_pagbank, le_pagbank)
    movs += [dict(m, conta="PagBank") for m in mp]
    movs.sort(key=lambda m: (m["d"], m["desc"], m["valor"]))
    return movs, fi, fp, usados, sp
