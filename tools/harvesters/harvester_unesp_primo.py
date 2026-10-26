import argparse
import asyncio
import httpx
import json
import zstandard as zstd
import os
import sys
import logging
import re
from typing import Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [UNESP-Alma] %(message)s'
)
logger = logging.getLogger("unesp_alma")

# --out-dir ou KOHA_NEXUS_HARVEST_DIR/data_unesp; sem nenhum dos dois, ./data_unesp.
DATA_DIR = os.path.join(os.environ.get("KOHA_NEXUS_HARVEST_DIR", "."), "data_unesp")
CHECKPOINT_FILE = os.path.join(DATA_DIR, "checkpoint_unesp.json")
OUTPUT_FILE = os.path.join(DATA_DIR, "unesp_records.jsonl.zst")

VID = "55UNESP_INST:UNESP"
BASE_URL = "https://unesp.primo.exlibrisgroup.com/primaws/rest/pub/sourceRecord"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/plain, */*"
}

def unesp_text_to_iso2709(raw_text: str) -> str | None:
    lines = raw_text.strip().splitlines()
    fields = []
    leader = '00000nam a2200000 a 4500'

    for line in lines:
        parts = line.split('\t', 1)
        if len(parts) < 2:
            continue
        tag = parts[0].strip()
        val = parts[1].rstrip()

        if tag.lower() == 'leader':
            if len(val) >= 24:
                leader = val[:24]
            continue

        if not re.match(r'^[0-9]{3}$', tag):
            continue

        if int(tag) < 10:
            field_content = val.encode('utf-8')
        else:
            inds = val[:2].replace('#', ' ')
            resto = val[2:]
            formatted = re.sub(r'\$([a-z0-9])', lambda m: chr(31) + m.group(1), resto)
            field_content = (inds + formatted).encode('utf-8')

        fields.append((tag, field_content))

    if not any(t == '245' for t, _ in fields):
        return None

    body = b''
    directory = b''
    offset = 0
    for tag, content in fields:
        raw_entry = content + b'\x1e'
        length = len(raw_entry)
        directory += f'{tag}{length:04d}{offset:05d}'.encode('ascii')
        body += raw_entry
        offset += length

    base_address = 24 + len(directory) + 1
    total_length = base_address + len(body) + 1
    leader_final = f'{total_length:05d}' + leader[5:12] + f'{base_address:05d}' + leader[17:24]
    iso_bytes = leader_final.encode('ascii') + directory + b'\x1e' + body + b'\x1d'
    
    return iso_bytes.decode('iso-8859-1', errors='replace')

def get_checkpoint(default_id: int = 1) -> int:
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r") as f:
                return json.load(f).get("last_id", default_id)
        except Exception:
            pass
    return default_id

def save_checkpoint(last_id: int):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"last_id": last_id}, f)

async def fetch_record(client: httpx.AsyncClient, seq_id: int, sem: asyncio.Semaphore) -> Dict[str, Any] | None:
    mms = f"99{seq_id:09d}0206341"
    doc_id = f"alma{mms}"
    url = f"{BASE_URL}?vid={VID}&docId={doc_id}"
    
    async with sem:
        try:
            resp = await client.get(url)
            if resp.status_code == 200 and len(resp.text) > 100:
                iso_str = unesp_text_to_iso2709(resp.text)
                if iso_str:
                    return {"id": seq_id, "mms_id": mms, "marc_iso2709": iso_str}
            return None
        except Exception:
            return None

async def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    start_id = get_checkpoint(1)
    end_id = 1500000
    concurrency = 10
    batch_size = 50

    logger.info(f"Iniciando colheita UNESP: ID {start_id} até {end_id} (concorrência={concurrency})")
    sem = asyncio.Semaphore(concurrency)
    cctx = zstd.ZstdCompressor(level=6)

    limits = httpx.Limits(max_connections=concurrency + 4, max_keepalive_connections=concurrency)
    timeout = httpx.Timeout(15.0, connect=8.0)

    async with httpx.AsyncClient(headers=HEADERS, limits=limits, timeout=timeout) as client:
        current_id = start_id
        with open(OUTPUT_FILE, "ab") as f_out:
            with cctx.stream_writer(f_out) as writer:
                while current_id <= end_id:
                    batch_end = min(current_id + batch_size, end_id + 1)
                    tasks = [
                        fetch_record(client, cid, sem)
                        for cid in range(current_id, batch_end)
                    ]
                    results = await asyncio.gather(*tasks)

                    salvos = 0
                    for rec in results:
                        if rec:
                            line = (json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8")
                            writer.write(line)
                            salvos += 1

                    # Descarrega os dados do buffer zstd diretamente para o disco
                    writer.flush(zstd.FLUSH_FRAME)
                    f_out.flush()

                    current_id = batch_end
                    save_checkpoint(current_id)
                    logger.info(f"Progresso: ID {current_id - 1}/{end_id} | Registros salvos no lote: {salvos}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Colhe registros MARC da UNESP (Primo/Alma).")
    parser.add_argument("--out-dir", default=DATA_DIR,
                        help="pasta de saida e checkpoint (padrao: $KOHA_NEXUS_HARVEST_DIR/data_unesp ou ./data_unesp)")
    DATA_DIR = parser.parse_args().out_dir
    CHECKPOINT_FILE = os.path.join(DATA_DIR, "checkpoint_unesp.json")
    OUTPUT_FILE = os.path.join(DATA_DIR, "unesp_records.jsonl.zst")
    asyncio.run(main())
