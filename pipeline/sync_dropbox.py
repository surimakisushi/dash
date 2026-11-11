#!/usr/bin/env python3
"""Baixa do Dropbox (API oficial) só o que o robô precisa e espelha em work/ com a mesma estrutura de pastas.

O que baixa:
  - a DLP mais nova da raiz (_DLP_*.xlsx)
  - extratos Itaú (.xlsx) de 5_extratos_Itau_banco e o histórico em _ADM/Extratos e comprovantes pix - Itau
  - extratos PagBank (.xlsx) de 5-extatos_pagbank
  - relatórios 'faturamento*.xls' do PDV (3_Saidas_Chefsolution_PDV/AAAA_MM)
  - conciliacao_aceitos.json (itens que o dono já explicou)
A data de modificação local de cada arquivo é a do Dropbox, porque os leitores escolhem o extrato "mais novo" por essa data.

Variáveis de ambiente (vêm dos Secrets do GitHub): DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN.
Opcional: DROPBOX_NAMESPACE_ID (só se a pasta TEMAKERIA - Docs for um espaço compartilhado e o caminho normal falhar).
Uso: python pipeline/sync_dropbox.py [--check]   (--check só lista, não baixa)
"""
import os, sys, datetime
import dropbox
from dropbox import common, files
from dropbox.exceptions import ApiError
import config

NS_PADRAO = os.environ.get("DROPBOX_NAMESPACE_ID", "14964539427")  # id do espaço compartilhado visto pelo conector; só é usado se o caminho normal falhar


def conectar():
    for v in ("DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN"):
        if not os.environ.get(v):
            sys.exit(f"Falta a variável {v}. Ela deve estar nos Secrets do repositório (Settings > Secrets and variables > Actions).")
    return dropbox.Dropbox(oauth2_refresh_token=os.environ["DROPBOX_REFRESH_TOKEN"], app_key=os.environ["DROPBOX_APP_KEY"],
                           app_secret=os.environ["DROPBOX_APP_SECRET"], timeout=300)


def escolher_modo(dbx):
    """Devolve (cliente, funcao_de_caminho). Tenta o caminho '/TEMAKERIA - Docs/...' e, se não existir, o espaço compartilhado."""
    try:
        dbx.files_list_folder(config.DBX_RAIZ)
        print("Dropbox: usando o caminho", config.DBX_RAIZ)
        return dbx, (lambda p: p)
    except ApiError as e:
        print("Caminho normal falhou (", str(e)[:120], ") - tentando o espaço compartilhado", NS_PADRAO)
    d2 = dbx.with_path_root(common.PathRoot.namespace_id(NS_PADRAO))
    d2.files_list_folder("")  # se falhar aqui, o erro aparece no log
    print("Dropbox: usando o espaço compartilhado", NS_PADRAO)
    return d2, (lambda p: p[len(config.DBX_RAIZ):] if p.startswith(config.DBX_RAIZ) else p)


def listar(dbx, path):
    try:
        r = dbx.files_list_folder(path)
    except ApiError as e:
        print("  aviso: não consegui listar", path, "-", str(e)[:120]); return []
    out = list(r.entries)
    while r.has_more:
        r = dbx.files_list_folder_continue(r.cursor); out += r.entries
    return out


def baixar(dbx, md, destino, so_listar):
    print(("  [lista] " if so_listar else "  baixando ") + md.name + f" ({md.size/1024:.0f} KB, modificado {md.server_modified:%d/%m %H:%M})")
    if so_listar: return
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    dbx.files_download_to_file(destino, md.id)
    ts = md.server_modified.replace(tzinfo=datetime.timezone.utc).timestamp()
    os.utime(destino, (ts, ts))


def so_arquivos(entries): return [e for e in entries if isinstance(e, files.FileMetadata)]
def so_pastas(entries): return [e for e in entries if isinstance(e, files.FolderMetadata)]


def main():
    so_listar = "--check" in sys.argv
    dbx, P = escolher_modo(conectar())
    # 1) DLP (a mais nova da raiz)
    print("DLP:")
    dlps = [f for f in so_arquivos(listar(dbx, P(config.DBX_RAIZ))) if f.name.startswith("_DLP_") and f.name.lower().endswith(".xlsx")]
    if not dlps: sys.exit("DLP não encontrada na raiz de TEMAKERIA - Docs")
    dlp = max(dlps, key=lambda f: f.server_modified)
    baixar(dbx, dlp, os.path.join(config.RAIZ, dlp.name), so_listar)
    # 2) extratos
    for nome, dbx_pasta, local, filtro in (
        ("Extratos Itaú", config.DBX_CA + "/5_extratos_Itau_banco", config.PASTA_ITAU, lambda n: n.lower().endswith(".xlsx") and not n.startswith("~$")),
        ("Extratos PagBank", config.DBX_CA + "/5-extatos_pagbank", config.PASTA_PAGBANK, lambda n: n.lower().endswith(".xlsx") and not n.startswith("~$")),
        ("Histórico Itaú", config.DBX_RAIZ + "/_ADM/Extratos e comprovantes pix - Itau", config.PASTA_HIST, lambda n: n.lower().endswith(".xlsx") and n.startswith("Extrato")),
    ):
        print(nome + ":")
        for f in so_arquivos(listar(dbx, P(dbx_pasta))):
            if filtro(f.name): baixar(dbx, f, os.path.join(local, f.name), so_listar)
    # 3) PDV: só 'faturamento*.xls' das pastas 2026_MM
    print("PDV (faturamento):")
    for pasta in sorted(so_pastas(listar(dbx, P(config.DBX_CA + "/3_Saidas_Chefsolution_PDV"))), key=lambda p: p.name):
        if not pasta.name.startswith("2026_"): continue
        for f in so_arquivos(listar(dbx, P(config.DBX_CA + "/3_Saidas_Chefsolution_PDV/" + pasta.name))):
            if f.name.lower().startswith("faturamento") and f.name.lower().endswith(".xls"):
                baixar(dbx, f, os.path.join(config.PASTA_PDV, pasta.name, f.name), so_listar)
    # 4) itens aceitos
    print("Itens aceitos:")
    for f in so_arquivos(listar(dbx, P(config.DBX_CA + "/7_dashboard"))):
        if f.name == "conciliacao_aceitos.json": baixar(dbx, f, config.ACEITOS, so_listar)
    print("Sincronização concluída" + (" (somente listagem)" if so_listar else ""))


if __name__ == "__main__":
    main()
