import argparse
import asyncio
import httpx
from bs4 import BeautifulSoup
import re
import json
import zstandard as zstd
import os
import sys
import logging
from typing import Dict, Any, List

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [UFRGS-Sabi] %(message)s'
)
logger = logging.getLogger("ufrgs_aleph")

BASE_URL = "https://sabi.ufrgs.br"
# --out-dir ou KOHA_NEXUS_HARVEST_DIR/data_ufrgs; sem nenhum dos dois, ./data_ufrgs.
OUTPUT_DIR = os.path.join(os.environ.get("KOHA_NEXUS_HARVEST_DIR", "."), "data_ufrgs")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "ufrgs_records.jsonl.zst")
CHECKPOINT_FILE = os.path.join(OUTPUT_DIR, "checkpoint_ufrgs.json")

CONCURRENCY = 8
BATCH_SIZE = 50

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
        r = await self.client.get(f"{BASE_URL}/F", timeout=20.0)
        m = re.search(r'/F/([A-Z0-9\-]+)', r.text)
        if m:
            self.sess_hash = m.group(1)
            logger.info(f"Sessao da UFRGS estabelecida: {self.sess_hash[:20]}...")
        else:
            raise RuntimeError("Nao foi possivel capturar o hash de sessao do Sabi (UFRGS).")

def parse_ufrgs_html(html: str, doc_num: int) -> Dict[str, Any] | None:
    if "Nenhum registro" in html or "Record not found" in html or len(html) < 2000:
        return None
    
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")
    
    fields = []
    leader = "     nam  22     4a 4500"
    
    for tr in rows:
        tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if not tds:
            continue
        
        texto_linha = " ".join(tds)
        
        if "LDR" in texto_linha:
            m_ldr = re.search(r'LDR\s+([^\s]+)', texto_linha)
            if m_ldr:
                leader = m_ldr.group(1)
            continue
            
        m_tag = re.match(r'^([0-9]{3})\b(.*)', tds[0].strip())
        if m_tag:
            tag = m_tag.group(1)
            resto = m_tag.group(2).strip()
            conteudo = " ".join(tds[1:]).strip() if len(tds) > 1 else resto
            fields.append({"tag": tag, "value": conteudo})
        elif len(tds) >= 2 and re.match(r'^[0-9]{3}$', tds[0].strip()):
            tag = tds[0].strip()
            conteudo = " ".join(tds[1:]).strip()
            fields.append({"tag": tag, "value": conteudo})

    if not fields:
        return None
        
    return {
        "institution": "UFRGS",
        "system_id": str(doc_num).zfill(9),
        "leader": leader,
        "fields": fields
    }

async def fetch_record(client: httpx.AsyncClient, session_mgr: AlephSessionManager, doc_num: int, sem: asyncio.Semaphore) -> Dict[str, Any] | None:
    doc_id_str = str(doc_num).zfill(9)
    async with sem:
        for tentativa in range(3):
            try:
                sess_hash = await session_mgr.get_session()
                url = f"{BASE_URL}/F/{sess_hash}?func=direct&doc_number={doc_id_str}&format=001"
                resp = await client.get(url, timeout=15.0)
                
                if resp.status_code == 200:
                    if "window.location" in resp.text and len(resp.text) < 1500:
                        await session_mgr._renew()
                        continue
                    return parse_ufrgs_html(resp.text, doc_num)
                elif resp.status_code in (403, 500):
                    await session_mgr._renew()
            except Exception:
                await asyncio.sleep(0.5 * (tentativa + 1))
        return None

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

async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    start_id = get_checkpoint(1)
    logger.info(f"Iniciando colheita UFRGS a partir do ID: {start_id}")
    
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    cctx = zstd.ZstdCompressor(level=3)
    
    sem = asyncio.Semaphore(CONCURRENCY)
    curr_id = start_id
    
    with open(OUTPUT_FILE, "ab") as f_out:
        with cctx.stream_writer(f_out) as writer:
            async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
                session_mgr = AlephSessionManager(client)
                await session_mgr.get_session()
                
                while True:
                    batch_ids = list(range(curr_id, curr_id + BATCH_SIZE))
                    tasks = [fetch_record(client, session_mgr, doc_id, sem) for doc_id in batch_ids]
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
                    save_checkpoint(curr_id)
                    logger.info(f"Processados ate ID {curr_id} | Validos no lote: {validos}/{BATCH_SIZE}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Colhe registros do Sabi (UFRGS, Aleph).")
    parser.add_argument("--out-dir", default=OUTPUT_DIR,
                        help="pasta de saida e checkpoint (padrao: $KOHA_NEXUS_HARVEST_DIR/data_ufrgs ou ./data_ufrgs)")
    OUTPUT_DIR = parser.parse_args().out_dir
    OUTPUT_FILE = os.path.join(OUTPUT_DIR, "ufrgs_records.jsonl.zst")
    CHECKPOINT_FILE = os.path.join(OUTPUT_DIR, "checkpoint_ufrgs.json")
    asyncio.run(main())
