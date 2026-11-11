#!/usr/bin/env python3
"""Junta os JSONs de out/ em um único pacote e CRIPTOGRAFA com a senha do dashboard (AES-256-GCM, chave via PBKDF2-SHA256).
Grava site/data.enc.json. O site só consegue abrir esse arquivo depois que a pessoa digita a senha no navegador.
A senha vem da variável DASH_PASSWORD (Secret do GitHub). Uso: python pipeline/publicar.py"""
import os, sys, json, base64, secrets, datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import config

DATASETS = ["status", "dlp_diario", "desp_categorias", "mp_fornecedores", "alertas", "concil_resumo", "keeta_semanal", "pdv_dlp"]
ITER = 600_000


def deriva(senha, sal):
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sal, iterations=ITER).derive(senha.encode("utf-8"))


def main():
    senha = os.environ.get("DASH_PASSWORD", "")
    if len(senha) < 8: sys.exit("DASH_PASSWORD ausente ou curta demais (mínimo 8 caracteres). Cadastre em Settings > Secrets and variables > Actions.")
    pacote = {}
    for d in DATASETS:
        p = os.path.join(config.OUT, d + ".json")
        if not os.path.exists(p): sys.exit("Falta " + p + " (o atualizar.py rodou?)")
        pacote[d] = json.load(open(p))
    pacote["gerado_em_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    claro = json.dumps(pacote, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sal, iv = secrets.token_bytes(16), secrets.token_bytes(12)
    cifrado = AESGCM(deriva(senha, sal)).encrypt(iv, claro, None)
    saida = {"v": 1, "iter": ITER, "salt": base64.b64encode(sal).decode(), "iv": base64.b64encode(iv).decode(), "ct": base64.b64encode(cifrado).decode(),
             "gerado_em_utc": pacote["gerado_em_utc"]}
    os.makedirs(config.SITE, exist_ok=True)
    destino = os.path.join(config.SITE, "data.enc.json")
    json.dump(saida, open(destino, "w"))
    print(f"Pacote criptografado: {len(claro)/1024:.0f} KB -> {len(cifrado)/1024:.0f} KB em site/data.enc.json")


if __name__ == "__main__":
    main()
