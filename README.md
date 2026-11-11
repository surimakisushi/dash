# Surimaki Dash

Painel financeiro da Temakeria Moema (Nokyoski). Roda sozinho na nuvem, sem depender de computador ligado, e abre por um link no celular ou no computador.

## Como funciona

```
Dropbox (DLP, extratos Itaú/PagBank, PDV)
        │  a cada 3 horas, GitHub Actions
        ▼
pipeline/sync_dropbox.py   baixa só o necessário pela API oficial do Dropbox
pipeline/atualizar.py      lê a DLP, compara PDV x DLP e extrato x DLP, gera os alertas
pipeline/publicar.py       criptografa tudo com a senha do painel (AES-256-GCM)
        ▼
site/  (GitHub Pages)      página que pede a senha e abre os dados no próprio navegador
```

- Os dados financeiros **nunca** ficam no repositório. Eles só existem no servidor durante a execução e são apagados no final.
- O que é publicado é `site/data.enc.json`, que só abre com a senha (`DASH_PASSWORD`).
- Os scripts são os mesmos que já rodavam no Mac (`7_dashboard/scripts`), com os caminhos trocados para a nuvem.

## Configuração (uma vez)

1. **Secrets** em *Settings → Secrets and variables → Actions*:
   - `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_REFRESH_TOKEN` (gerados com `tools/obter_token_dropbox.py`)
   - `DASH_PASSWORD` (senha de abrir o painel, mínimo 8 caracteres; use uma senha forte)
2. **Pages** em *Settings → Pages*: em *Source* escolha **GitHub Actions**.
   Atenção: GitHub Pages em repositório **privado** exige plano pago (GitHub Pro). A página publicada é pública pelo endereço, e é por isso que os dados vão criptografados.
3. Rode o fluxo na aba *Actions → Atualizar Surimaki Dash → Run workflow*. O endereço do painel aparece no final da execução.
4. No iPhone: abra o endereço no Safari, toque em *Compartilhar* e depois em *Adicionar à Tela de Início*.

## Itens que o dono já explicou

O robô lê `conciliacao_aceitos.json` da pasta `7_dashboard` no Dropbox. Itens listados lá aparecem como "aceitos" no painel, e não como alertas abertos.

## Teste sem dados reais

```
python tests/teste_sintetico.py /tmp/teste
```

Monta uma DLP, extratos e PDV inventados e roda o robô inteiro.

## Mudanças na DLP

Se a DLP ganhar ou perder linhas, ajuste `LINHAS` em `pipeline/dlp_extract.py`.
