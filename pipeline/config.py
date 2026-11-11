"""Caminhos compartilhados. Tudo que o robô baixa do Dropbox fica em work/, espelhando a estrutura da pasta do Dropbox,
para os leitores (extrato, PDV, DLP) funcionarem com a mesma lógica que já rodava no Mac."""
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
WORK = os.environ.get("DASH_WORK", os.path.join(REPO, "work"))
OUT = os.environ.get("DASH_OUT", os.path.join(REPO, "out"))
SITE = os.environ.get("DASH_SITE", os.path.join(REPO, "site"))

# raiz no Dropbox
DBX_RAIZ = "/TEMAKERIA - Docs"
DBX_CA = DBX_RAIZ + "/_ADM/CONTROLE_AUTOMACAO"

# espelho local (mesma estrutura do Dropbox)
RAIZ = os.path.join(WORK, "TEMAKERIA - Docs")
CA = os.path.join(RAIZ, "_ADM", "CONTROLE_AUTOMACAO")
PASTA_ITAU = os.path.join(CA, "5_extratos_Itau_banco")
PASTA_PAGBANK = os.path.join(CA, "5-extatos_pagbank")
PASTA_PDV = os.path.join(CA, "3_Saidas_Chefsolution_PDV")
PASTA_HIST = os.path.join(RAIZ, "_ADM", "Extratos e comprovantes pix - Itau")
ACEITOS = os.path.join(CA, "7_dashboard", "conciliacao_aceitos.json")
REGRAS = os.path.join(CA, "7_dashboard", "conciliacao_regras.json")   # regras por nome (ex.: retirada de pró-labore), valem para qualquer data

os.makedirs(OUT, exist_ok=True)
