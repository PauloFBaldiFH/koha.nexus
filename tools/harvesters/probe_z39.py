#!/usr/bin/env python3
import subprocess
import sys
import json
import re

COMMON_DATABASES = ["biblioteca", "acervo", "default", "koha", "opac", "voyager", "main"]

def probe_target(host, port=210, timeout=4):
    """
    Testa handshake Z39.50 via yaz-client e retorna metadados se for válido.
    """
    result = {
        "host": host,
        "port": port,
        "alive": False,
        "valid_z3950": False,
        "databases": [],
        "working_db": None,
        "syntax": "MARC21"
    }

    # Gera comandos yaz para inicialização e tentativa de busca em bases comuns
    yaz_commands = "open " + host + ":" + str(port) + "\n"
    for db in COMMON_DATABASES:
        yaz_commands += f"base {db}\n"
        yaz_commands += "format usmarc\n"
        yaz_commands += "find @attr 1=4 brasil\n"
    yaz_commands += "quit\n"

    try:
        proc = subprocess.run(
            ["yaz-client"],
            input=yaz_commands,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = proc.stdout

        if "Connected" in output:
            result["alive"] = True

        if "OK" in output and ("Init response: OK" in output or "Target Name" in output):
            result["valid_z3950"] = True

            # Extrair nome da base que respondeu positivamente a um search
            for block in output.split("Connecting"):
                for db in COMMON_DATABASES:
                    if f"base {db}" in block and "Number of hits: " in block:
                        hits_match = re.search(r"Number of hits:\s+(\d+)", block)
                        if hits_match and int(hits_match.group(1)) > 0:
                            result["working_db"] = db
                            result["hits_sample"] = int(hits_match.group(1))
                            break
                if result["working_db"]:
                    break

    except subprocess.TimeoutExpired:
        result["alive"] = True
    except Exception as e:
        result["error"] = str(e)

    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: ./probe_z39.py <ip/host> [porta]")
        sys.exit(1)
    
    h = sys.argv[1]
    p = int(sys.argv[2]) if len(sys.argv) > 2 else 210
    res = probe_target(h, p)
    print(json.dumps(res, indent=2))
