#!/usr/bin/env bash

TERMO="brasil"
TIMEOUT=10

echo "================================================================================"
echo " DIAGNÓSTICO SRU KOHA (SERVIDOR-BIBLIOTECA)"
echo " Termo: \"$TERMO\" | Timeout: ${TIMEOUT}s"
echo "================================================================================"
printf "%-46s | %-6s | %-12s | %-8s\n" "SERVIDOR" "HTTP" "REGISTROS" "TEMPO"
echo "--------------------------------------------------------------------------------"

sudo koha-mysql library -N -B -e "SELECT servername, host, port, db FROM z3950servers WHERE servertype = 'sru';" | while IFS=$'\t' read -r name host port db; do
    db_clean=$(echo "$db" | sed 's|^/||')
    url="http://${host}:${port}/${db_clean}?operation=searchRetrieve&version=1.1&query=bath.title=%22${TERMO// /%20}%22&maximumRecords=1"

    start=$(date +%s%N)
    response=$(curl -s --max-time "$TIMEOUT" -w "\n%{http_code}" "$url" 2>/dev/null)
    end=$(date +%s%N)

    duracao=$(( (end - start) / 1000000 ))
    tempo_fmt="${duracao}ms"

    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" = "200" ]; then
        num_records=$(echo "$body" | grep -oPm1 "(?<=<zs:numberOfRecords>)[^<]+" || echo "?")
        if [ "$num_records" != "?" ] && [ "$num_records" -gt 0 ] 2>/dev/null; then
            status_txt="\e[32mOK ($num_records rec)\e[0m"
        else
            status_txt="\e[33m0 registros\e[0m"
        fi
    elif [ -z "$http_code" ] || [ "$http_code" = "000" ]; then
        http_code="TIMEOUT"
        status_txt="\e[31mTIMEOUT/OFF\e[0m"
        tempo_fmt=">${TIMEOUT}s"
    else
        status_txt="\e[31mHTTP $http_code\e[0m"
    fi

    nome_fmt=$(echo "$name" | cut -c 1-44)
    printf "%-46s | %-6s | %-20b | %-8s\n" "$nome_fmt" "$http_code" "$status_txt" "$tempo_fmt"
done
echo "================================================================================"
