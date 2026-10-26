import argparse
import asyncio
import json
import os
import re
from pathlib import Path
from bs4 import BeautifulSoup
import httpx
import zstandard as zstd

# --out-dir ou KOHA_NEXUS_HARVEST_DIR/data_harvested/zeus_ufsc;
# sem nenhum dos dois, ./data_harvested/zeus_ufsc.
OUTPUT_DIR = Path(os.environ.get("KOHA_NEXUS_HARVEST_DIR", ".")) / "data_harvested" / "zeus_ufsc"
OUTPUT_FILE = OUTPUT_DIR / "acervo_zeus_raw.jsonl.zst"

BASE_URL = "https://catalogo.bu.ufsc.br/zbib/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:157.0) Gecko/20100101"
        " Firefox/157.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Todos os alvos mapeados (target15 - UFPR excluído propositalmente)
TODOS_TARGETS = [i for i in range(71) if i != 15]

# Termos para varredura do acervo
TERMOS_BUSCA = [
    "brasil",
    "historia",
    "direito",
    "medicina",
    "educacao",
    "ciencia",
    "tecnologia",
    "filosofia",
    "literatura",
    "administracao",
    "economia",
    "engenharia",
    "arte",
    "sociedade",
    "cultura",
    "jesus",
    "quimica",
    "fisica",
    "biologia",
]

TAMANHO_LOTE_TARGETS = 12
CONCORRENCIA = 3


def chunk_list(lista: list, n: int):
  for i in range(0, len(lista), n):
    yield lista[i : i + n]


def extrair_raw_records(html_str: str) -> list[str]:
  soup = BeautifulSoup(html_str, "html.parser")
  records = []
  for inp in soup.find_all("input", {"name": "rawRecord"}):
    val = inp.get("value", "").strip()
    if val:
      records.append(val)
  return records


async def buscar_termo_lote(
    client: httpx.AsyncClient,
    termo: str,
    target_ids: list[int],
    sem: asyncio.Semaphore,
    compressor,
    progresso_vistos: set,
):
  params = [
      ("searchString", termo),
      ("searchType", "4"),  # 4 = Busca por Título
  ]
  for tid in target_ids:
    params.append((f"targets[{tid}]", "on"))

  async with sem:
    try:
      resp = await client.get(
          BASE_URL, params=params, headers=HEADERS, timeout=45.0
      )
      if resp.status_code == 200:
        records = extrair_raw_records(resp.text)
        novos = 0
        for r in records:
          # Identificador básico pelos primeiros bytes do ISO-2709
          rec_hash = hash(r[:80])
          if rec_hash not in progresso_vistos:
            progresso_vistos.add(rec_hash)
            dado = {
                "termo": termo,
                "targets": target_ids,
                "raw_record": r,
            }
            linha = json.dumps(dado, ensure_ascii=False) + "\n"
            compressor.write(linha.encode("utf-8"))
            novos += 1
        print(
            f"[✓] Termo '{termo}' | Targets: {target_ids[0]}-{target_ids[-1]} |"
            f" Novos registos: {novos}"
        )
      else:
        print(f"[!] HTTP {resp.status_code} para '{termo}'")
    except Exception as e:
      print(
          f"[!] Erro na pesquisa '{termo}' (Targets"
          f" {target_ids[0]}-{target_ids[-1]}): {e}"
      )


async def main():
  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
  print("[*] Iniciando recolha massiva Z39.50 através do agregador UFSC...")
  cctx = zstd.ZstdCompressor(level=15)
  sem = asyncio.Semaphore(CONCORRENCIA)
  vistos = set()

  lotes_alvos = list(chunk_list(TODOS_TARGETS, TAMANHO_LOTE_TARGETS))

  with open(OUTPUT_FILE, "ab") as f_out:
    with cctx.stream_writer(f_out) as compressor:
      limits = httpx.Limits(
          max_keepalive_connections=10, max_connections=CONCORRENCIA
      )
      async with httpx.AsyncClient(limits=limits, follow_redirects=True) as client:
        for termo in TERMOS_BUSCA:
          print(f"\n--- Processando termo: '{termo}' ---")
          tarefas = [
              buscar_termo_lote(
                  client, termo, lote, sem, compressor, vistos
              )
              for lote in lotes_alvos
          ]
          await asyncio.gather(*tarefas)
          await asyncio.sleep(1.0)

  print(
      f"\n[✔] Recolha concluída com sucesso! Registos guardados em:"
      f" {OUTPUT_FILE}"
  )


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Colhe registros ISO 2709 pelo agregador Z39.50 Zeus (UFSC).")
  parser.add_argument("--out-dir", type=Path, default=OUTPUT_DIR,
                      help="pasta de saida (padrao: $KOHA_NEXUS_HARVEST_DIR/data_harvested/zeus_ufsc ou ./data_harvested/zeus_ufsc)")
  OUTPUT_DIR = parser.parse_args().out_dir
  OUTPUT_FILE = OUTPUT_DIR / "acervo_zeus_raw.jsonl.zst"
  asyncio.run(main())
