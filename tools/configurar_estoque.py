#!/usr/bin/env python3
"""Configura o app de ESTOQUE (robô que lança no Controle_Estoque_Temakeria_v2.xlsx as contagens salvas no app Estoque Surimaki).
Rode UMA vez no seu Mac:  python3 configurar_estoque.py
Para refazer SÓ a chave de acesso (DROPBOX_ESTOQUE_REFRESH_TOKEN):  python3 configurar_estoque.py token
É um terceiro app do Dropbox, separado do app de leitura do painel (que continua só leitura). Precisa ser do tipo "Full Dropbox",
pois a planilha fica em /TEMAKERIA - Docs/2 - Planilhas e um app "App folder" não enxerga essa pasta.
Este script gera a chave de acesso dele (fluxo PKCE, sem App secret) e grava 2 chaves nos Secrets do GitHub:
  DROPBOX_ESTOQUE_APP_KEY e DROPBOX_ESTOQUE_REFRESH_TOKEN
As chaves ficam só no seu computador e nos Secrets do GitHub (nunca passam pelo Claude)."""
import urllib.request, urllib.parse, urllib.error, json, hashlib, base64, secrets, shutil, subprocess, webbrowser, re, sys

REPO = "surimakisushi/dash"


def copiar(texto):
    try:
        subprocess.run(["pbcopy"], input=texto.encode(), check=True); return True
    except Exception:
        return False


def gh_pronto():
    return bool(shutil.which("gh")) and subprocess.run(["gh", "auth", "status"], capture_output=True).returncode == 0


print("== Surimaki Estoque: robô da planilha ==\n")
print("No site do Dropbox, no app de ESTOQUE (tipo Full Dropbox), aba Permissions, deixe marcadas:")
print("   files.metadata.read   files.content.read   files.content.write   (e clique em Submit).\n")
while True:
    key = input("App key do app de ESTOQUE (aba Settings): ").strip()
    if re.fullmatch(r"[A-Za-z0-9]{10,40}", key): break
    print("   Isso não parece uma chave do Dropbox (só letras e números, sem espaços). Copie de novo no site do Dropbox.\n")

verificador = secrets.token_urlsafe(64)
desafio = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).decode().rstrip("=")
url = "https://www.dropbox.com/oauth2/authorize?" + urllib.parse.urlencode({"client_id": key, "response_type": "code", "token_access_type": "offline",
                                                                            "code_challenge": desafio, "code_challenge_method": "S256"})
print("\nVou abrir o Dropbox no navegador. Clique em Permitir (na conta da Temakeria).")
print("Se a página não abrir sozinha, use este endereço:\n\n" + url + "\n")
try: webbrowser.open(url)
except Exception: pass
codigo = input("Cole aqui o código que o Dropbox mostrar: ").strip()
req = urllib.request.Request("https://api.dropboxapi.com/oauth2/token", data=urllib.parse.urlencode(
    {"code": codigo, "grant_type": "authorization_code", "code_verifier": verificador, "client_id": key}).encode())
try:
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())
except urllib.error.HTTPError as e:
    raise SystemExit("O Dropbox recusou: " + e.read().decode()[:300] + "\nConfira a App key e se o código é recente.")
print("\nPermissões concedidas:", r.get("scope"))
if "files.content.write" not in (r.get("scope") or ""):
    raise SystemExit("Faltou a permissão files.content.write. Marque-a na aba Permissions, clique em Submit e rode este script de novo.")

valores = [("DROPBOX_ESTOQUE_REFRESH_TOKEN", r["refresh_token"])] if (len(sys.argv) > 1 and sys.argv[1] == "token") else [("DROPBOX_ESTOQUE_APP_KEY", key), ("DROPBOX_ESTOQUE_REFRESH_TOKEN", r["refresh_token"])]
print("\nGravando as chaves no repositório " + REPO + " ...")
if gh_pronto():
    for nome, valor in valores:
        p = subprocess.run(["gh", "secret", "set", nome, "--repo", REPO], input=valor.encode(), capture_output=True)
        print(("  OK   " if p.returncode == 0 else "  FALHOU ") + nome + ("" if p.returncode == 0 else " - " + p.stderr.decode()[:200]))
else:
    print("  (vamos pelo navegador; eu copio cada valor para você colar)")
    print("  Abra, no navegador logado como surimakisushi:  https://github.com/" + REPO + "/settings/secrets/actions/new\n")
    for nome, valor in valores:
        ok = copiar(valor)
        print(f"  1) No campo Name, DIGITE (não cole): {nome}")
        print("  2) No campo Secret, cole com Cmd+V (" + ("o valor JÁ ESTÁ COPIADO" if ok else "valor: " + valor) + ") e clique em Add secret.")
        input("  Quando salvar, aperte Enter para o próximo... ")
        print()
print("\nPronto. Me avise no chat que terminou.")
copiar("")  # limpa a área de transferência
