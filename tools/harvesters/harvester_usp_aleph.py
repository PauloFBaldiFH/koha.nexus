import argparse
import asyncio
import httpx
import json
import zstandard as zstd
import os
import sys
import logging
import re
from bs4 import BeautifulSoup
from typing import Dict, Any, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [USP-Dedalus] %(message)s'
)
logger = logging.getLogger("usp_aleph")

# --out-dir ou KOHA_NEXUS_HARVEST_DIR/data_aleph; sem nenhum dos dois, ./data_aleph.
DATA_DIR = os.path.join(os.environ.get("KOHA_NEXUS_HARVEST_DIR", "."), "data_aleph")
CHECKPOINT_FILE = os.path.join(DATA_DIR, "checkpoint_usp.json")
OUTPUT_FILE = os.path.join(DATA_DIR, "usp_records.jsonl.zst")

BASE_URL = "https://dedalus.usp.br"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

def consertar_mojibake(texto: str) -> str:
    try:
        return texto.encode('latin1').decode('utf-8')
    except Exception:
        return texto

def aleph_html_to_iso2709(html_text: str, doc_id: str) -> str | None:
    soup = BeautifulSoup(html_text, 'html.parser')
    fields = []
    leader = '00000nam a2200000 i 4500'

    for tr in soup.find_all('tr'):
        tds = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
        if len(tds) < 2 or not tds[0]:
            continue

        raw_tag = tds[0]
        # Converte &nbsp; para espaço ASCII convencional
        val = consertar_mojibake(' '.join(tds[1:])).replace('\xa0', ' ')

        if raw_tag == 'LDR' and len(val) >= 24:
            leader = val[:24]
            continue

        m = re.match(r'^([0-9]{3})([0-9\s]{0,2})$', raw_tag)
        if m:
            tag = m.group(1)
            inds = m.group(2).ljust(2, ' ')

            if int(tag) < 10:
                field_content = val.encode('utf-8')
            else:
                formatted_val = re.sub(r'\|([a-z0-9])', lambda match: chr(31) + match.group(1), val)
                if not formatted_val.startswith(chr(31)):
                    formatted_val = chr(31) + formatted_val
                field_content = (inds + formatted_val).encode('utf-8')

            fields.append((tag, field_content))

    if not any(t == '245' for t, _ in fields):
        return None

    if not any(t == '001' for t, _ in fields):
        fields.insert(0, ('001', str(doc_id).zfill(9).encode('utf-8')))

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

class AlephSessionManager:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.sess_hash = None
        self.lock = asyncio.Lock()

    async def get_session(self) -> str:
        async with self.lock:
            if not self.sess_hash:
                await self._renew()
            return self.sess_hash

    async def _renew(self):
        r = await self.client.get(f"{BASE_URL}/F")
        m = re.search(r'https://dedalus\.usp\.br/F/([A-Z0-9\-]+)', r.text)
        if m:
            self.sess_hash = m.group(1)
            logger.info(f"Sessão do Aleph inicializada: {self.sess_hash[:20]}...")
        else:
            raise RuntimeError("Não foi possível capturar o hash de sessão do Dedalus.")

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

async def fetch_record(client: httpx.AsyncClient, session_mgr: AlephSessionManager, doc_num: int, sem: asyncio.Semaphore) -> Dict[str, Any] | None:
    doc_id_str = str(doc_num).zfill(9)
    async with sem:
        for _ in range(2):
            sess_hash = await session_mgr.get_session()
            url = f"{BASE_URL}/F/{sess_hash}?func=direct&doc_number={doc_id_str}&format=001&local_base=USP01"
            try:
                resp = await client.get(url)
                if resp.status_code != 200 or len(resp.text) < 1000:
                    # Se vier HTML minúsculo de redirecionamento, a sessão pode ter expirado
                    if "window.location" in resp.text:
                        await session_mgr._renew()
                        continue
                    return None

                html = resp.content.decode('iso-8859-1', errors='replace')
                iso_str = aleph_html_to_iso2709(html, doc_id_str)
                if iso_str:
                    return {"id": doc_num, "marc_iso2709": iso_str}
                return None
            except Exception:
                return None
    return None

async def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    start_id = get_checkpoint(1)
    end_id = 3000000  # Estimativa de teto do Dedalus
    concurrency = 6   # Taxa conservadora para evitar bloqueio no gateway da USP
    batch_size = 50

    logger.info(f"Iniciando colheita Dedalus (USP): ID {start_id} até {end_id} (concorrência={concurrency})")
    sem = asyncio.Semaphore(concurrency)
    cctx = zstd.ZstdCompressor(level=6)

    limits = httpx.Limits(max_connections=concurrency + 4, max_keepalive_connections=concurrency)
    timeout = httpx.Timeout(20.0, connect=10.0)

    async with httpx.AsyncClient(headers=HEADERS, limits=limits, timeout=timeout, follow_redirects=True) as client:
        session_mgr = AlephSessionManager(client)
        await session_mgr.get_session()

        current_id = start_id
        with open(OUTPUT_FILE, "ab") as f_out:
            with cctx.stream_writer(f_out) as writer:
                while current_id <= end_id:
                    batch_end = min(current_id + batch_size, end_id + 1)
                    tasks = [
                        fetch_record(client, session_mgr, cid, sem)
                        for cid in range(current_id, batch_end)
                    ]
                    results = await asyncio.gather(*tasks)

                    salvos = 0
                    for rec in results:
                        if rec:
                            line = (json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8")
                            writer.write(line)
                            salvos += 1

                    current_id = batch_end
                    save_checkpoint(current_id)
                    logger.info(f"Progresso: ID {current_id - 1}/{end_id} | Registros salvos no lote: {salvos}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Colhe registros MARC do Dedalus (USP, Aleph).")
    parser.add_argument("--out-dir", default=DATA_DIR,
                        help="pasta de saida e checkpoint (padrao: $KOHA_NEXUS_HARVEST_DIR/data_aleph ou ./data_aleph)")
    DATA_DIR = parser.parse_args().out_dir
    CHECKPOINT_FILE = os.path.join(DATA_DIR, "checkpoint_usp.json")
    OUTPUT_FILE = os.path.join(DATA_DIR, "usp_records.jsonl.zst")
    asyncio.run(main())
