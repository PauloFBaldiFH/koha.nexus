#!/usr/bin/env python3
import subprocess
import sys

def run_mysql(query: str):
    cmd = ["sudo", "koha-mysql", "library", "-e", query]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"[!] Erro ao executar MySQL: {res.stderr.strip()}", file=sys.stderr)
        return False
    if res.stdout.strip():
        print(res.stdout)
    return True

sql = """
-- 1. Desativar registros legados ou duplicados
UPDATE z3950servers SET checked = 0 WHERE recordtype = 'authority';

-- 2. Rank 1: Nexus Autoridades (Cloud Pública via Cloudflare)
INSERT INTO z3950servers (
    id, servername, host, port, db, userid, password, checked, rank,
    syntax, encoding, timeout, recordtype, servertype, sru_options, sru_fields, attributes
) VALUES (
    116, 'Nexus Autoridades (Cloud)', 'https://sru.koha.nexus', 443, 'sru/_union-aut', '', '', 1, 1,
    'MARC21', 'utf8', 10, 'authority', 'sru', 'sru=get,sru_version=1.1',
    'nameany=bath.personalName,authorany=bath.personalName,authorpersonal=bath.personalName,authorcorp=bath.corporateName,authormeetingcon=bath.conferenceName,subject=bath.topicalSubject,subjectany=bath.topicalSubject,srchany=cql.serverChoice',
    NULL
) ON DUPLICATE KEY UPDATE
    servername = 'Nexus Autoridades (Cloud)',
    host = 'https://sru.koha.nexus', port = 443, db = 'sru/_union-aut', checked = 1, rank = 1,
    syntax = 'MARC21', encoding = 'utf8', timeout = 10, servertype = 'sru',
    sru_options = VALUES(sru_options), sru_fields = VALUES(sru_fields);

-- 3. Rank 2: LoC Nomes (NAF)
UPDATE z3950servers SET
    servername = 'BIBLIOTECA DOS NOMES DO CONGRESSO',
    host = 'lx2.loc.gov',
    port = 210,
    db = 'NAF',
    servertype = 'zed',
    syntax = 'USMARC',
    encoding = 'utf-8',
    attributes = '1=1016',
    timeout = 10,
    checked = 1,
    rank = 2
WHERE id = 2 OR (host = 'lx2.loc.gov' AND db = 'NAF');

-- 4. Rank 2: LoC Assuntos (SAF)
UPDATE z3950servers SET
    servername = 'BIBLIOTECA DOS ASSUNTOS DO CONGRESSO',
    host = 'lx2.loc.gov',
    port = 210,
    db = 'SAF',
    servertype = 'zed',
    syntax = 'USMARC',
    encoding = 'utf-8',
    attributes = '1=1016',
    timeout = 10,
    checked = 1,
    rank = 2
WHERE id = 3 OR (host = 'lx2.loc.gov' AND db = 'SAF');

-- 5. Rank 3: Biblioteca Nacional (Mantida para desambiguação legada)
UPDATE z3950servers SET
    servername = 'BIBLIOTECA NACIONAL (AUTORIDADES)',
    host = 'https://sru.koha.nexus',
    port = 443,
    db = 'sru/bn-aut',
    servertype = 'sru',
    syntax = 'MARC21',
    encoding = 'utf-8',
    timeout = 15,
    checked = 1,
    rank = 3
WHERE id = 115 OR (host = 'https://sru.koha.nexus' AND db = 'sru/bn-aut');

-- Exibir status final consolidado
SELECT id, rank, servername, host, port, db, servertype, syntax, attributes, checked
FROM z3950servers
WHERE recordtype = 'authority' AND checked = 1
ORDER BY rank ASC, id ASC;
"""

print("[*] Sincronizando servidores de autoridade no Koha...")
run_mysql(sql)
print("[+] Topologia configurada com sucesso!")
