import argparse
import os
import xml.etree.ElementTree as ET
import requests
import time

# Endereco do gateway: --gateway ou KOHA_NEXUS_GATEWAY_URL.
# Exemplos: https://sru.koha.nexus  ou  http://<ip-da-vps>:5000
parser = argparse.ArgumentParser(description="Testa cada alvo SRU do gateway com uma busca simples.")
parser.add_argument("--gateway", default=os.environ.get("KOHA_NEXUS_GATEWAY_URL", "https://sru.koha.nexus"),
                    help="URL base do gateway (padrao: $KOHA_NEXUS_GATEWAY_URL ou https://sru.koha.nexus)")
parser.add_argument("--termo", default="jesus", help="termo pesquisado em cada alvo (padrao: jesus)")
parser.add_argument("--timeout", type=float, default=20, help="segundos por alvo (padrao: 20)")
args = parser.parse_args()

GATEWAY_URL = args.gateway.rstrip("/")
TERMO_BUSCA = args.termo
TIMEOUT_SEGUNDOS = args.timeout

# Lista ordenada com as 71 siglas mapeadas no gateway
ALVOS = [
    # Nacionais e Governamentais
    "bn", "fundacentro", "senado", "senado-folio",
    # Estaduais
    "usp", "unicamp", "unesp", "uerj",
    # Universidades Federais
    "ufg", "ufmg", "ufpe", "ufsc", "ufscar", "unifesp",
    "ufu", "ufpr", "ufrgs", "uff", "utfpr",
    # Países de Língua Portuguesa
    "coimbra", "porto", "bn-portugal", "porbase", "macau",
    # Estados Unidos
    "loc", "nlm", "harvard", "yale", "wisconsin", "mit",
    "suno", "pennstate", "upenn", "nysl", "tufts",
    "art-chicago", "fsu", "nga",
    # Canadá
    "ubc", "trent", "memorial", "sfu", "toronto",
    # Reino Unido e Nova Zelândia
    "bl", "oxford", "christchurch",
    # Espanha e América Latina
    "bne", "castilla-leon", "bizkaia", "barcelona",
    "argentina", "colombia", "buap-mexico", "pucp-peru", "upc-peru",
    # Europa Continental
    "italia", "abes-franca", "gent-belgica", "kobv-alemanha",
    "tuhh-alemanha", "swb-alemanha", "polonia", "suica",
    "suecia", "tchequia", "grecia", "russia-state", "bashkir-russia",
    # Ásia e África
    "africa-do-sul", "hong-kong", "taiwan"
]

print(f"{'='*60}")
print(f" Testando {len(ALVOS)} Alvos SRU no Gateway: {GATEWAY_URL}")
print(f" Termo pesquisado: '{TERMO_BUSCA}' | Timeout por alvo: {TIMEOUT_SEGUNDOS}s")
print(f"{'='*60}\n")

total_ok = 0
total_zero = 0
total_falhas = 0

for indice, sigla in enumerate(ALVOS, 1):
    url = f"{GATEWAY_URL}/sru/{sigla}"
    inicio = time.time()
    
    try:
        resp = requests.get(url, params={"query": TERMO_BUSCA}, timeout=TIMEOUT_SEGUNDOS)
        tempo = round(time.time() - inicio, 2)
        
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            total_elem = root.find(".//{http://www.loc.gov/zing/srw/}numberOfRecords")
            qtd = total_elem.text if total_elem is not None else "0"
            
            if qtd != "0":
                print(f"[{indice:02d}/{len(ALVOS)}] [OK]     {sigla:<16} -> {qtd:>2} registros ({tempo}s)")
                total_ok += 1
            else:
                print(f"[{indice:02d}/{len(ALVOS)}] [--]     {sigla:<16} ->  0 registros ({tempo}s)")
                total_zero += 1
        else:
            print(f"[{indice:02d}/{len(ALVOS)}] [HTTP {resp.status_code}] {sigla:<16} ({tempo}s)")
            total_falhas += 1

    except requests.exceptions.Timeout:
        tempo = round(time.time() - inicio, 2)
        print(f"[{indice:02d}/{len(ALVOS)}] [TIMEOUT] {sigla:<16} -> Demorou mais de {TIMEOUT_SEGUNDOS}s")
        total_falhas += 1
    except requests.exceptions.ConnectionError:
        print(f"\n[ERRO FATAL] Não foi possível conectar ao gateway {GATEWAY_URL}.")
        print("Verifique o endereço (--gateway) e se a porta está acessível pelo firewall da rede/VPS.")
        break
    except Exception as e:
        print(f"[{indice:02d}/{len(ALVOS)}] [ERRO]   {sigla:<16} -> {e}")
        total_falhas += 1

print(f"\n{'='*60}")
print(f" RESUMO DO TESTE:")
print(f"  - Com registros encontrados: {total_ok}")
print(f"  - Sem registros para o termo: {total_zero}")
print(f"  - Falhas / Timeout:          {total_falhas}")
print(f"{'='*60}")
