#!/usr/bin/env python3
"""Roda UMA vez no seu computador para gerar a chave de renovação (refresh token) do Dropbox.
A chave aparece só no seu terminal. Copie-a e cadastre nos Secrets do GitHub; não envie para ninguém, nem para o Claude.
Uso: python3 obter_token_dropbox.py"""
import urllib.request, urllib.parse, urllib.error, json, getpass, base64

print("== Chave de acesso do Dropbox para o Surimaki Dash ==\n")
print("Antes de continuar, na página do seu app no Dropbox (aba Permissions) deixe marcadas SÓ estas duas e clique em Submit:")
print("   files.metadata.read   e   files.content.read\n")
key = input("App key: ").strip()
secret = getpass.getpass("App secret (não aparece ao digitar): ").strip()
url = "https://www.dropbox.com/oauth2/authorize?" + urllib.parse.urlencode({"client_id": key, "response_type": "code", "token_access_type": "offline"})
print("\n1) Abra este endereço no navegador, entre na conta do Dropbox da Temakeria e clique em Permitir:\n")
print(url + "\n")
codigo = input("2) Cole aqui o código que o Dropbox mostrar: ").strip()
corpo = urllib.parse.urlencode({"code": codigo, "grant_type": "authorization_code"}).encode()
req = urllib.request.Request("https://api.dropboxapi.com/oauth2/token", data=corpo)
req.add_header("Authorization", "Basic " + base64.b64encode(f"{key}:{secret}".encode()).decode())
try:
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())
except urllib.error.HTTPError as e:
    raise SystemExit("O Dropbox recusou: " + e.read().decode()[:300])
print("\nPermissões concedidas:", r.get("scope"))
print("\nREFRESH TOKEN (copie tudo, é o valor de DROPBOX_REFRESH_TOKEN):\n")
print(r["refresh_token"])
print("\nPronto. Agora cadastre os 3 valores nos Secrets do GitHub e feche este terminal.")
