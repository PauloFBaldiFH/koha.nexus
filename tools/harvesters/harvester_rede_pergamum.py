import argparse
import asyncio
import httpx
import json
import zstandard as zstd
import os
import sys
import logging
from typing import Dict, Any, List

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [Rede-Pergamum] %(message)s'
)
logger = logging.getLogger("rede_pergamum")

TARGETS = [
    {"code": "UFMG",   "base": "https://catalogobiblioteca.ufmg.br/api/acervo"},
    {"code": "UFSCar", "base": "https://pergamum.ufscar.br/api/acervo"},
    {"code": "UFMS",   "base": "https://pergamum.ufms.br/api/acervo"},
    {"code": "UFPE",   "base": "https://biblioteca.ufpe.br/api/acervo"},
    {"code": "UFV",    "base": "https://pergamum.ufv.br/api/acervo"},
    {"code": "UFPel",  "base": "https://pergamum.ufpel.edu.br/api/acervo"},
]

CONCURRENCY_PER_TARGET = 8
BATCH_SIZE = 50

# Pasta base: cada alvo grava em <pasta>/data_<codigo>/.
# --out-dir ou KOHA_NEXUS_HARVEST_DIR; sem nenhum dos dois, a pasta atual.
OUT_BASE = os.environ.get("KOHA_NEXUS_HARVEST_DIR", ".")

def parse_pergamum_record(data: Dict[str, Any], doc_id: int, inst_code: str) -> Dict[str, Any] | None:
    if not isinstance(data, dict) or "campos" not in data or not data["campos"]:
        return None

    marc_fields = []
    for c in data.get("campos", []):
        detalhes = c.get("detalhes", [])
        for d in detalhes:
            tag_num = str(d.get("paragrafo", "")).zfill(3)
            if not tag_num.isdigit():
                continue

            secoes = d.get("_secao", [])
            textos = d.get("descricao", [])
            extras = d.get("extra", [])

            ind1 = " "
            ind2 = " "
            if extras and isinstance(extras, list) and len(extras) > 0:
                e0 = extras[0]
                if isinstance(e0, dict):
                    ind1 = e0.get("indi1") or " "
                    ind2 = e0.get("indi2") or " "

            subcampos = []
            for s, t in zip(secoes, textos):
                if t:
                    subcampos.append({"code": str(s), "value": str(t).strip()})

            if subcampos:
                marc_fields.append({
                    "tag": tag_num,
                    "ind1": ind1,
                    "ind2": ind2,
                    "subfields": subcampos
                })

    if not marc_fields:
        return None

    return {
        "institution": inst_code,
        "system_id": str(doc_id),
        "tipo_obra": data.get("tipo_obra", ""),
        "fields": marc_fields
    }

async def fetch_item(client: httpx.AsyncClient, base_url: str, doc_id: int, inst_code: str, sem: asyncio.Semaphore) -> Dict[str, Any] | None:
    async with sem:
        url = f"{base_url}/{doc_id}"
        for retry in range(3):
            try:
                resp = await client.get(url, timeout=12.0)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        return parse_pergamum_record(data, doc_id, inst_code)
                    except Exception:
                        return None
                elif resp.status_code in (404, 500):
                    return None
            except Exception:
                await asyncio.sleep(0.4 * (retry + 1))
        return None

def get_checkpoint(ckpt_path: str, default_id: int = 1) -> int:
    if os.path.exists(ckpt_path):
        try:
            with open(ckpt_path, "r") as f:
                return json.load(f).get("last_id", default_id)
        except Exception:
            pass
    return default_id

def save_checkpoint(ckpt_path: str, last_id: int):
    with open(ckpt_path, "w") as f:
        json.dump({"last_id": last_id}, f)

async def worker_target(target: Dict[str, str]):
    code = target["code"]
    base_url = target["base"]
    out_dir = os.path.join(OUT_BASE, f"data_{code.lower()}")
    os.makedirs(out_dir, exist_ok=True)

    out_file = os.path.join(out_dir, f"{code.lower()}_records.jsonl.zst")
    ckpt_file = os.path.join(out_dir, f"checkpoint_{code.lower()}.json")

    start_id = get_checkpoint(ckpt_file, 1)
    logger.info(f"[{code}] Iniciando colheita a partir do ID {start_id}")

    sem = asyncio.Semaphore(CONCURRENCY_PER_TARGET)
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    cctx = zstd.ZstdCompressor(level=3)

    curr_id = start_id
    with open(out_file, "ab") as f_out:
        with cctx.stream_writer(f_out) as writer:
            async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
                while True:
                    batch_ids = list(range(curr_id, curr_id + BATCH_SIZE))
                    tasks = [fetch_item(client, base_url, bid, code, sem) for bid in batch_ids]
                    results = await asyncio.gather(*tasks)

                    validos = 0
                    for r in results:
                        if r:
                            linha = json.dumps(r, ensure_ascii=False) + "\n"
                            writer.write(linha.encode("utf-8"))
                            validos += 1

                    writer.flush(zstd.FLUSH_FRAME)
                    f_out.flush()

                    curr_id += BATCH_SIZE
                    save_checkpoint(ckpt_file, curr_id)
                    logger.info(f"[{code}] Ate ID {curr_id} | Validos: {validos}/{BATCH_SIZE}")

async def main():
    logger.info(f"Iniciando enxame Pergamum para {len(TARGETS)} alvos simultâneos.")
    await asyncio.gather(*(worker_target(t) for t in TARGETS))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Colhe registros das APIs Pergamum (UFMG, UFSCar, UFMS, UFPE, UFV, UFPel).")
    parser.add_argument("--out-dir", default=OUT_BASE,
                        help="pasta base; cada alvo grava em <pasta>/data_<codigo> (padrao: $KOHA_NEXUS_HARVEST_DIR ou a pasta atual)")
    OUT_BASE = parser.parse_args().out_dir
    asyncio.run(main())
