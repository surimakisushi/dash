#!/usr/bin/env python3
"""Configura as chaves do Surimaki Dash. Rode UMA vez no seu Mac:  python3 configurar_dash.py
As chaves ficam só no seu computador e nos Secrets do GitHub (nunca passam pelo Claude).
O que faz: gera a chave de renovação do Dropbox, cria uma senha forte para abrir o painel e grava as 4 chaves no repositório.
Se o GitHub CLI (gh) estiver instalado e logado, grava sozinho; senão, copia cada valor para a área de transferência e você só cola."""
import urllib.request, urllib.parse, urllib.error, json, getpass, base64, secrets, shutil, subprocess, webbrowser, re

REPO = "surimakisushi/dash"
ALFABETO = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # sem letras parecidas (l, I, 1, O, 0)


def copiar(texto):
    try:
        subprocess.run(["pbcopy"], input=texto.encode(), check=True); return True
    except Exception:
        return False


def gh_pronto():
    return bool(shutil.which("gh")) and subprocess.run(["gh", "auth", "status"], capture_output=True).returncode == 0


print("== Surimaki Dash: configuração das chaves ==\n")
print("PASSO 1. No site do Dropbox, no app que você criou, aba Permissions: deixe marcadas SÓ")
print("   files.metadata.read   e   files.content.read   (e clique em Submit).\n")
def pede(rotulo, oculto=False):
    """Pede um valor e recusa o que não parece uma chave do Dropbox (letras e números, sem espaços, 10 a 40 caracteres)."""
    while True:
        v = (getpass.getpass if oculto else input)(rotulo).strip()
        if re.fullmatch(r"[A-Za-z0-9]{10,40}", v): return v
        print("   Isso não parece uma chave do Dropbox (deve ter só letras e números, sem espaços).")
        print("   Volte ao site do Dropbox, copie o valor de novo e cole aqui.\n")


key = pede("App key (copie no site do Dropbox, aba Settings): ")
secret = pede("App secret (clique em 'Reveal app secret', copie e cole; não aparece ao colar): ", oculto=True)

url = "https://www.dropbox.com/oauth2/authorize?" + urllib.parse.urlencode({"client_id": key, "response_type": "code", "token_access_type": "offline"})
print("\nPASSO 2. Vou abrir o Dropbox no navegador. Clique em Permitir (entre na conta da Temakeria, se pedir).")
print("   Se a página não abrir sozinha, use este endereço:\n\n" + url + "\n")
try: webbrowser.open(url)
except Exception: pass
codigo = input("Cole aqui o código que o Dropbox mostrar: ").strip()
req = urllib.request.Request("https://api.dropboxapi.com/oauth2/token", data=urllib.parse.urlencode({"code": codigo, "grant_type": "authorization_code"}).encode())
req.add_header("Authorization", "Basic " + base64.b64encode(f"{key}:{secret}".encode()).decode())
try:
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())
except urllib.error.HTTPError as e:
    raise SystemExit("O Dropbox recusou: " + e.read().decode()[:300] + "\nConfira a App key, o App secret e se o código é recente.")
print("\nPermissões concedidas:", r.get("scope"))

print("\nPASSO 3. Senha para abrir o painel (você vai digitá-la no celular).")
print("   Aperte Enter para usar uma senha forte gerada agora, ou digite a sua (mínimo 12 caracteres).")
digitada = getpass.getpass("Senha (opcional): ").strip()
senha = digitada if len(digitada) >= 12 else "".join(secrets.choice(ALFABETO) for _ in range(14))
if digitada and len(digitada) < 12: print("   Muito curta; usei uma senha gerada.")

valores = [("DROPBOX_APP_KEY", key), ("DROPBOX_APP_SECRET", secret), ("DROPBOX_REFRESH_TOKEN", r["refresh_token"]), ("DASH_PASSWORD", senha)]
print("\nPASSO 4. Gravando as chaves no repositório " + REPO + " ...")
if gh_pronto():
    for nome, valor in valores:
        p = subprocess.run(["gh", "secret", "set", nome, "--repo", REPO], input=valor.encode(), capture_output=True)
        print(("  OK   " if p.returncode == 0 else "  FALHOU ") + nome + ("" if p.returncode == 0 else " - " + p.stderr.decode()[:200]))
else:
    print("  (gh não está instalado ou logado; vamos pelo navegador, e eu copio cada valor para você colar)")
    print("  Abra, no navegador logado como surimakisushi:  https://github.com/" + REPO + "/settings/secrets/actions/new\n")
    for nome, valor in valores:
        ok = copiar(valor)
        print(f"  Nome: {nome}")
        print("  " + ("O valor JÁ ESTÁ COPIADO: cole (Cmd+V) no campo Secret e clique em Add secret." if ok else "Valor: " + valor))
        input("  Quando salvar, aperte Enter para o próximo... ")
        print()

print("=" * 60)
print("SENHA DO PAINEL (anote em lugar seguro): " + senha)
print("=" * 60)
print("\nPronto. Próximo passo: no GitHub, Settings > Pages > Source: 'GitHub Actions'.")
print("Depois rode: https://github.com/" + REPO + "/actions  ->  Atualizar Surimaki Dash  ->  Run workflow")
copiar("")  # limpa a área de transferência
