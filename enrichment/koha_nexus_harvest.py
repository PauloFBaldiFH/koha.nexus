#!/usr/bin/env python3
"""
Koha.Nexus Authority Harvester (On-Demand CLI)
Atualiza a base local static.db sem manter processos contínuos em segundo plano.
"""

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, '/home/ubuntu/Koha.Nexus/enrichment')
from nexus_enrich import normalize

DB_PATH = '/home/ubuntu/Koha.Nexus/static.db'
PROD_DB_PATH = '/var/lib/koha-nexus-enrich/static.db'
USER_AGENT = 'KohaNexusAuthorityHarvester/2.0 (biblioteca@kohanexus.org)'

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def clean_text(t: str) -> str:
    if not t: return ""
    t = str(t).strip().rstrip(".,;:/ ")
    return "" if len(t) < 3 or t.isdigit() else t

def harvest_loc_canonical(limit_per_country=3000):
    print("\n=== [1/2] COLETANDO AUTORES MUNDIAIS DA LIBRARY OF CONGRESS (NACO/LCCN) ===")
    paises = [
        ('Portugal', 'wd:Q45'), ('França', 'wd:Q142'), ('Reino Unido', 'wd:Q145'),
        ('Estados Unidos', 'wd:Q30'), ('Alemanha', 'wd:Q183'), ('Espanha', 'wd:Q29'),
        ('Itália', 'wd:Q38'), ('Argentina', 'wd:Q414'), ('Rússia', 'wd:Q159')
    ]

    conn = get_connection()
    cur = conn.cursor()
    total_novos = 0

    for pais, qid in paises:
        print(f"[*] Consultando canônicos de {pais}...", end="", flush=True)
        query = f"""
        SELECT ?item ?itemLabel ?lccn ?dataNasc ?dataMorte WHERE {{
          ?item wdt:P31 wd:Q5;
                wdt:P27 {qid};
                wdt:P244 ?lccn;
                wdt:P106 ?ocupacao.
          VALUES ?ocupacao {{ wd:Q36180 wd:Q49757 wd:Q5891 wd:Q201788 wd:Q901 }}
          OPTIONAL {{ ?item wdt:P569 ?dataNasc. }}
          OPTIONAL {{ ?item wdt:P570 ?dataMorte. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "pt,en". }}
        }}
        LIMIT {limit_per_country}
        """
        url = 'https://query.wikidata.org/sparql?' + urllib.parse.urlencode({'query': query, 'format': 'json'})
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})

        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                dados = json.loads(resp.read().decode('utf-8'))
                itens = dados.get('results', {}).get('bindings', [])
                novos = 0
                for row in itens:
                    nome = clean_text(row.get('itemLabel', {}).get('value', ''))
                    if not nome or (nome.startswith('Q') and nome[1:].isdigit()):
                        continue
                    lccn = row.get('lccn', {}).get('value', '')
                    nasc = row.get('dataNasc', {}).get('value', '')[:4]
                    morte = row.get('dataMorte', {}).get('value', '')[:4]
                    dates = f"{nasc}-{morte}" if nasc or morte else ""
                    fkey = normalize.fold(nome)

                    try:
                        cur.execute("""
                            INSERT OR IGNORE INTO auth_headings
                            (kind, heading, key, dates, thesaurus, variants, source, source_id, preliminary, occurrences)
                            VALUES ('personal', ?, ?, ?, 'por', '', 'Library of Congress', ?, 0, 1)
                        """, (nome, fkey, dates, lccn))
                        rid = cur.lastrowid
                        if rid:
                            cur.execute("INSERT INTO auth_fts (rowid, heading, variants) VALUES (?, ?, '')", (rid, nome))
                            novos += 1
                    except Exception:
                        pass
                conn.commit()
                total_novos += novos
                print(f" OK (+{novos:,})", flush=True)
        except Exception as e:
            print(f" Falhou: {e}", flush=True)
        time.sleep(2)

    cur.execute("""
    INSERT OR REPLACE INTO sources (id, name, mode, brazilian, weight, records, headings)
    VALUES ('Library of Congress', 'Library of Congress NACO / LCCN Linked Data', 'linked-data', 0, 1.0,
            (SELECT count(*) FROM auth_headings WHERE source='Library of Congress'),
            (SELECT count(*) FROM auth_headings WHERE source='Library of Congress'))
    """)
    conn.commit()
    conn.close()
    print(f"[+] Total novas autoridades LoC inseridas: {total_novos:,}")
    return total_novos

def harvest_bn_canonical():
    print("\n=== [2/2] COLETANDO AUTORIDADES NACIONAIS (BIBLIOTECA NACIONAL / BRASIL) ===")
    conn = get_connection()
    cur = conn.cursor()

    query = """
    SELECT ?item ?itemLabel ?bnId ?dataNasc ?dataMorte (GROUP_CONCAT(DISTINCT ?alias; separator="|") AS ?aliases) WHERE {
      ?item wdt:P31 wd:Q5;
            wdt:P27 wd:Q155;
            wdt:P4619 ?bnId;
            wdt:P106 ?ocupacao.
      VALUES ?ocupacao { wd:Q36180 wd:Q49757 wd:Q201788 wd:Q901 wd:Q5891 wd:Q40348 wd:Q82955 }
      OPTIONAL { ?item wdt:P569 ?dataNasc. }
      OPTIONAL { ?item wdt:P570 ?dataMorte. }
      OPTIONAL { ?item skos:altLabel ?alias. FILTER(LANG(?alias) = "pt") }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "pt". }
    }
    GROUP BY ?item ?itemLabel ?bnId ?dataNasc ?dataMorte
    LIMIT 10000
    """
    url = 'https://query.wikidata.org/sparql?' + urllib.parse.urlencode({'query': query, 'format': 'json'})
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})

    novos = 0
    try:
        print("[*] Consultando personalidades brasileiras registradas na BN...", end="", flush=True)
        with urllib.request.urlopen(req, timeout=60) as resp:
            dados = json.loads(resp.read().decode('utf-8'))
            itens = dados.get('results', {}).get('bindings', [])
            for row in itens:
                nome = clean_text(row.get('itemLabel', {}).get('value', ''))
                if not nome or (nome.startswith('Q') and nome[1:].isdigit()):
                    continue
                bn_id = row.get('bnId', {}).get('value', '')
                nasc = row.get('dataNasc', {}).get('value', '')[:4]
                morte = row.get('dataMorte', {}).get('value', '')[:4]
                dates = f"{nasc}-{morte}" if nasc or morte else ""
                aliases = row.get('aliases', {}).get('value', '')
                fkey = normalize.fold(nome)

                try:
                    cur.execute("""
                        INSERT OR IGNORE INTO auth_headings
                        (kind, heading, key, dates, thesaurus, variants, source, source_id, preliminary, occurrences)
                        VALUES ('personal', ?, ?, ?, 'por', ?, 'Wikidata/BN', ?, 0, 1)
                    """, (nome, fkey, dates, aliases, bn_id))
                    rid = cur.lastrowid
                    if rid:
                        cur.execute("INSERT INTO auth_fts (rowid, heading, variants) VALUES (?, ?, ?)", (rid, nome, aliases))
                        novos += 1
                except Exception:
                    pass
            conn.commit()
            print(f" OK (+{novos:,})", flush=True)
    except Exception as e:
        print(f" Falhou: {e}", flush=True)

    conn.close()
    print(f"[+] Total novas autoridades BN inseridas: {novos:,}")
    return novos

def sync_and_restart():
    print("\n[*] Sincronizando static.db com a pasta de produção (/var/lib/koha-nexus-enrich/)...")
    res = os.system(f"sudo cp -v {DB_PATH} {PROD_DB_PATH}")
    if res == 0:
        print("[*] Reiniciando serviço SRU do repositório...")
        # Usa o nome canônico do serviço no repositório (com fallback seguro para gateway local)
        os.system("sudo systemctl restart koha-nexus-sru.service 2>/dev/null || sudo systemctl restart koha-nexus-gateway.service 2>/dev/null")
        print("[+] Serviço pronto e atualizado!")
    else:
        print("[!] Erro na sincronização com produção.")

def main():
    parser = argparse.ArgumentParser(description="Koha.Nexus On-Demand Authority Harvester")
    parser.add_argument("--source", choices=["loc", "bn", "all"], default="all",
                        help="Fonte para coleta: 'loc' (Library of Congress), 'bn' (Biblioteca Nacional), 'all' (ambas)")
    parser.add_argument("--no-sync", action="store_true", help="Não sincroniza nem reinicia o gateway ao final")

    args = parser.parse_args()

    total = 0
    if args.source in ("loc", "all"):
        total += harvest_loc_canonical()
    if args.source in ("bn", "all"):
        total += harvest_bn_canonical()

    print(f"\n==========================================")
    print(f"Total global de novas autoridades: {total:,}")
    print(f"==========================================")

    if not args.no_sync and total > 0:
        sync_and_restart()

if __name__ == "__main__":
    main()
