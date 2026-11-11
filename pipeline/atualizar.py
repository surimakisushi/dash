#!/usr/bin/env python3
"""Atualização completa na nuvem: DLP -> PDV x DLP -> extrato x DLP -> alertas. Grava tudo em out/.
Pré-requisito: pipeline/sync_dropbox.py já rodou (os arquivos estão em work/). Uso: python pipeline/atualizar.py"""
import os, sys, glob, subprocess, json, datetime
import config
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = config.OUT

cands = sorted(glob.glob(os.path.join(config.RAIZ, "_DLP_*.xlsx")), key=os.path.getmtime)
if not cands: sys.exit("DLP não encontrada em " + config.RAIZ + " (o sync_dropbox.py rodou?)")
dlp = cands[-1]
print("DLP:", os.path.basename(dlp), "| modificada em", datetime.datetime.fromtimestamp(os.path.getmtime(dlp)).strftime("%d/%m/%Y %H:%M"))
for cmd in (["dlp_extract.py", dlp], ["pdv_ler.py"], ["conciliar.py"]):
    r = subprocess.run([sys.executable, os.path.join(HERE, cmd[0])] + cmd[1:], capture_output=True, text=True)
    print(r.stdout.strip()[:1500])
    if r.returncode: sys.exit(r.stderr[-1500:] or ("falhou: " + cmd[0]))
# junta os alertas do PDV, aplica "aceitos" e o corte DESDE
al = json.load(open(os.path.join(OUT, "alertas.json")))
aceitos = {}
if os.path.exists(config.ACEITOS): aceitos = {a["chave"]: a.get("motivo", "") for a in json.load(open(config.ACEITOS))}
desde = os.environ.get("CONCIL_DESDE", "2026-09-01")[:7]
for i, a in enumerate(json.load(open(os.path.join(OUT, "pdv_alertas.json"))), 1):
    if a["mes"] < desde: continue
    a = dict(a, id=f"P{i:04d}"); a["chave"] = f'{a["data"]}|{a["item"]}|{abs(a["diferenca"]):.2f}'
    a["status"] = "aceito" if a["chave"] in aceitos else "aberto"; a["motivo"] = aceitos.get(a["chave"], ""); al.append(a)
json.dump(al, open(os.path.join(OUT, "alertas.json"), "w"), ensure_ascii=False)
ab = [a for a in al if a["status"] == "aberto"]
print(f"ALERTAS: {len(ab)} abertos ({sum(a['gravidade']=='alta' for a in ab)} altos, {sum(a['gravidade']=='media' for a in ab)} médios, {sum(a['gravidade']=='baixa' for a in ab)} baixos), {len(al)-len(ab)} aceitos")
