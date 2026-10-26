import argparse
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import unquote
import httpx
import zstandard as zstd

# --out-dir ou KOHA_NEXUS_HARVEST_DIR/data_harvested/pergamum_pucpr;
# sem nenhum dos dois, ./data_harvested/pergamum_pucpr.
DATA_DIR = Path(os.environ.get("KOHA_NEXUS_HARVEST_DIR", ".")) / "data_harvested" / "pergamum_pucpr"
ARQUIVO_ZST = DATA_DIR / "pergamum_dados.jsonl.zst"

BASE_URL = (
    "https://www.pergamum.pucpr.br/redepergamum/consultas/site_CRP/pesquisa.php"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:157.0) Gecko/20100101"
        " Firefox/157.0"
    ),
    "Accept": "*/*",
    "Referer": (
        "https://www.pergamum.pucpr.br/redepergamum/consultas/site_CRP/pesquisa.php"
    ),
}

# Lista inicial de termos e letras para varrer o acervo
TERMOS = [
    "brasil",
    "direito",
    "historia",
    "medicina",
    "educacao",
    "filosofia",
    "teologia",
    "jesus",
    "quimica",
    "fisica",
    "administracao",
    "engenharia",
]


def extrair_fichas_do_html(html_str: str) -> list[dict]:
  """Extrai os códigos de acervo e referências brutas do retorno AJAX"""
  itens = []
  padrao = r'carrega_dados_acervo\(["\'](\d+)["\']\);[^>]*><strong>(.*?)</strong>'
  matches = re.findall(padrao, html_str)

  for cod_acervo, texto_bruto in matches:
    itens.append({
        "cod_acervo": cod_acervo,
        "referencia": unquote(texto_bruto).replace("&nbsp;", " ").strip(),
    })
  return itens


def main():
  DATA_DIR.mkdir(parents=True, exist_ok=True)
  print("[*] Iniciando colheita no Pergamum via AJAX...")
  cctx = zstd.ZstdCompressor(level=15)

  with open(ARQUIVO_ZST, "ab") as f_out:
    with cctx.stream_writer(f_out) as compressor:
      with httpx.Client(
          timeout=30.0, follow_redirects=True, headers=HEADERS
      ) as client:
        for termo in TERMOS:
          print(f"[>] Pesquisando termo: '{termo}'...")
          params = {
              "rs": "ajax_resultados",
              "rst": "",
              "rsrnd": str(int(time.time() * 1000)),
              "rsargs[]": [
                  "0",
                  termo,
                  "TITULO",
                  "obra",
                  "50",
                  "",
                  "",
                  "",
                  "",
                  "-1",
              ],
          }

          try:
            resp = client.get(BASE_URL, params=params)
            if resp.status_code != 200:
              print(f"[!] Erro HTTP {resp.status_code} para '{termo}'")
              continue

            fichas = extrair_fichas_do_html(resp.text)
            print(f"[✓] Encontradas {len(fichas)} obras para '{termo}'.")

            for ficha in fichas:
              registro = {
                  "cod_acervo": ficha["cod_acervo"],
                  "termo_origem": termo,
                  "referencia_bruta": ficha["referencia"],
              }
              linha = json.dumps(registro, ensure_ascii=False) + "\n"
              compressor.write(linha.encode("utf-8"))

            time.sleep(1.0)

          except Exception as e:
            print(f"[!] Falha na requisição para '{termo}': {e}")

  print(
      f"\n[✔] Varredura concluída. Dados armazenados em: {ARQUIVO_ZST}"
  )


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Colhe referencias do catalogo Pergamum da PUCPR (busca AJAX).")
  parser.add_argument("--out-dir", type=Path, default=DATA_DIR,
                      help="pasta de saida (padrao: $KOHA_NEXUS_HARVEST_DIR/data_harvested/pergamum_pucpr ou ./data_harvested/pergamum_pucpr)")
  DATA_DIR = parser.parse_args().out_dir
  ARQUIVO_ZST = DATA_DIR / "pergamum_dados.jsonl.zst"
  main()
