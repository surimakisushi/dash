#!/usr/bin/env python3
"""Grava no Controle_Estoque_Temakeria_v2.xlsx (Dropbox) as contagens salvas no app Estoque Surimaki.

Como funciona
  1. O app grava um .json por contagem salva em  <raiz>/2 - Planilhas/estoque_app/pendentes/
  2. Este robô lê esses arquivos, compara cada item contado com o saldo que a planilha calcula
     (estoque inicial da aba Itens + entradas - saídas da aba Movimentação) e, quando há diferença,
     acrescenta uma linha de 'Ajuste' na aba Movimentação (só 'De' para diminuir, só 'Para' para aumentar),
     exatamente como a aba 'Como usar' manda fazer. Itens iguais ao sistema não geram linha.
  3. Antes de gravar, guarda uma cópia da planilha em estoque_app/backup/. Só grava se a planilha não mudou
     desde a leitura (se você a estiver editando, o robô espera a próxima rodada).
  4. Depois de gravar, move os .json para estoque_app/processadas/.

Variáveis de ambiente (Secrets do GitHub): DROPBOX_ESTOQUE_APP_KEY, DROPBOX_ESTOQUE_REFRESH_TOKEN.
Uso: python pipeline/estoque_gravar.py [--seco]   (--seco mostra o que faria e não grava nada)
"""
import os, sys, io, json, datetime
import openpyxl
import config

PASTA = config.DBX_RAIZ + "/2 - Planilhas"
PLANILHA = PASTA + "/Controle_Estoque_Temakeria_v2.xlsx"
PENDENTES = PASTA + "/estoque_app/pendentes"
PROCESSADAS = PASTA + "/estoque_app/processadas"
BACKUP = PASTA + "/estoque_app/backup"
LOCAIS = {"G": "Geladeira", "D": "Depósito"}
LIN_ITENS = range(6, 206)        # aba Itens: linhas 6 a 205
LIN_MOV = range(9, 1006)         # aba Movimentação: linhas 9 a 1005 (6 a 8 são exemplos e não contam)


def _n(v):
    return float(v) if isinstance(v, (int, float)) else 0.0


def ler_itens(wb):
    """cod -> {nome, ini:{Geladeira,Depósito}}"""
    ws = wb["Itens"]; out = {}
    for r in LIN_ITENS:
        cod, nome = ws.cell(r, 1).value, ws.cell(r, 2).value
        if cod and nome:
            out[str(cod).strip()] = {"nome": str(nome), "ini": {"Geladeira": _n(ws.cell(r, 6).value), "Depósito": _n(ws.cell(r, 7).value)}}
    return out


def saldo_sistema(wb, itens):
    """Replica a aba Estoque: inicial + entradas (Para) - saídas (De), por item e local, nas linhas 9 a 1005."""
    ws = wb["Movimentação"]
    s = {(i["nome"], l): i["ini"][l] for i in itens.values() for l in LOCAIS.values()}
    for r in LIN_MOV:
        nome, de, para, q = ws.cell(r, 2).value, ws.cell(r, 4).value, ws.cell(r, 5).value, ws.cell(r, 6).value
        if not nome or not isinstance(q, (int, float)): continue
        if para in LOCAIS.values(): s[(nome, para)] = s.get((nome, para), 0.0) + q
        if de in LOCAIS.values(): s[(nome, de)] = s.get((nome, de), 0.0) - q
    return s


def primeira_linha_livre(wb):
    ws = wb["Movimentação"]
    for r in LIN_MOV:
        if not any(ws.cell(r, c).value not in (None, "") for c in (1, 2, 3, 4, 5, 6, 8)):
            return r
    raise SystemExit("A aba Movimentação está cheia (997 linhas). Siga a orientação da aba 'Como usar' e refaça o arquivo.")


def ja_lancada(wb, doc_id):
    ws = wb["Movimentação"]; marca = "[" + doc_id + "]"
    return any(isinstance(ws.cell(r, 8).value, str) and marca in ws.cell(r, 8).value for r in LIN_MOV)


def aplicar(wb, doc, doc_id):
    """Acrescenta os ajustes de uma contagem. Devolve (linhas_escritas, avisos)."""
    itens = ler_itens(wb); avisos = []
    if ja_lancada(wb, doc_id):
        return [], ["já estava lançada: " + doc_id]
    sis = saldo_sistema(wb, itens)
    ws = wb["Movimentação"]
    data = datetime.datetime.strptime(doc["date"], "%Y-%m-%d")
    dd = data.strftime("%d/%m")
    escritas = []
    for chave, c in sorted((doc.get("counts") or {}).items()):
        if not c or c.get("v") is None: continue
        cod, lk = chave.rsplit("_", 1)
        loc = LOCAIS.get(lk); it = itens.get(cod)
        if not loc or not it:
            avisos.append(f"{chave}: item ou local desconhecido, ignorado"); continue
        q = c["v"]
        if not isinstance(q, (int, float)) or q < 0 or q != int(q):
            avisos.append(f"{chave}: quantidade inválida ({q}), ignorada"); continue
        atual = sis.get((it["nome"], loc), 0.0)
        dif = int(q) - atual
        if dif == 0: continue
        if dif != int(dif):
            avisos.append(f"{it['nome']} ({loc}): saldo do sistema não é inteiro ({atual}), ignorado"); continue
        r = primeira_linha_livre(wb)
        ws.cell(r, 1).value = data
        ws.cell(r, 2).value = it["nome"]
        ws.cell(r, 3).value = "Ajuste"
        ws.cell(r, 4).value = loc if dif < 0 else None
        ws.cell(r, 5).value = loc if dif > 0 else None
        ws.cell(r, 6).value = abs(int(dif))
        obs = f"Contagem do app {dd}: contado {int(q)}, sistema {int(atual)}"
        if c.get("low"): obs += " (conferir: leitura por foto)"
        ws.cell(r, 8).value = obs + f" [{doc_id}]"
        sis[(it["nome"], loc)] = float(q)
        escritas.append((r, it["nome"], loc, int(dif)))
    if not escritas:
        avisos.append("contagem igual ao sistema: nenhum ajuste necessário")
    return escritas, avisos


# ---------------------------------------------------------------- Dropbox
def conectar():
    import dropbox
    for v in ("DROPBOX_ESTOQUE_APP_KEY", "DROPBOX_ESTOQUE_REFRESH_TOKEN"):
        if not os.environ.get(v):
            sys.exit(f"Falta a variável {v} (Secrets do repositório). Rode tools/configurar_estoque.py no seu Mac.")
    return dropbox.Dropbox(oauth2_refresh_token=os.environ["DROPBOX_ESTOQUE_REFRESH_TOKEN"], app_key=os.environ["DROPBOX_ESTOQUE_APP_KEY"], timeout=120)


def modo_caminho(dbx):
    """Igual ao sync_dropbox: tenta o caminho normal e, se não existir, o espaço compartilhado."""
    from dropbox import common
    from dropbox.exceptions import ApiError
    try:
        dbx.files_list_folder(config.DBX_RAIZ); return dbx, (lambda p: p)
    except ApiError:
        pass
    ns = os.environ.get("DROPBOX_NAMESPACE_ID", "14964539427")
    d2 = dbx.with_path_root(common.PathRoot.namespace_id(ns)); d2.files_list_folder("")
    return d2, (lambda p: p[len(config.DBX_RAIZ):] if p.startswith(config.DBX_RAIZ) else p)


def principal(seco=False):
    from dropbox import files
    from dropbox.exceptions import ApiError
    dbx, P = modo_caminho(conectar())
    try:
        pend = [e for e in dbx.files_list_folder(P(PENDENTES)).entries if isinstance(e, files.FileMetadata) and e.name.endswith(".json")]
    except ApiError:
        print("Sem pasta de pendentes ainda: nada a fazer."); return 0
    if not pend:
        print("Nenhuma contagem pendente."); return 0
    pend.sort(key=lambda e: e.name)
    print(f"{len(pend)} contagem(ns) pendente(s).")
    md, resp = dbx.files_download(P(PLANILHA))
    bruto = resp.content
    wb = openpyxl.load_workbook(io.BytesIO(bruto))
    feitas = []
    for e in pend:
        _, r = dbx.files_download(e.path_lower)
        try:
            doc = json.loads(r.content.decode("utf-8"))
            assert doc["date"] and isinstance(doc.get("counts"), dict)
        except Exception as ex:
            print("  arquivo inválido, ignorado:", e.name, ex); continue
        escritas, avisos = aplicar(wb, doc, e.name[:-5])
        print(f"  {e.name}: {len(escritas)} ajuste(s)")
        for x in escritas: print(f"     linha {x[0]}: {x[1]} ({x[2]}) {x[3]:+d}")
        for a in avisos: print("     aviso:", a)
        feitas.append(e)
    if seco or not feitas:
        print("(modo seco: nada gravado)" if seco else "Nada a gravar."); return 0
    wb.calculation.fullCalcOnLoad = True    # sem valores guardados, o Excel recalcula as fórmulas ao abrir
    saida = io.BytesIO(); wb.save(saida)
    agora = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    try: dbx.files_create_folder_v2(P(BACKUP))
    except ApiError: pass
    dbx.files_upload(bruto, P(f"{BACKUP}/Controle_Estoque_Temakeria_v2_antes_{agora}.xlsx"))
    # só grava se a planilha continua na mesma versão que foi lida (senão, tenta de novo na próxima rodada)
    res = dbx.files_upload(saida.getvalue(), P(PLANILHA), mode=files.WriteMode.update(md.rev))
    if res.name != md.name:    # a planilha mudou durante a leitura: o Dropbox criou uma "cópia em conflito"
        print("A planilha foi alterada enquanto o robô trabalhava; descartando a cópia em conflito e tentando de novo na próxima rodada.")
        dbx.files_delete_v2(res.path_lower)
        return 1
    print("Planilha atualizada.")
    try: dbx.files_create_folder_v2(P(PROCESSADAS))
    except ApiError: pass
    for e in feitas:
        dbx.files_move_v2(e.path_lower, P(f"{PROCESSADAS}/{e.name}"), autorename=True)
    print("Contagens movidas para processadas.")
    return 0


if __name__ == "__main__":
    sys.exit(principal(seco="--seco" in sys.argv))
