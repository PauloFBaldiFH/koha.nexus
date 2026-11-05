#!/usr/bin/env bash
# ======================================================================
# KOHA.NEXUS - DEEP CLEANUP & UNINSTALL
# Remove o Koha e tudo o que o painel criou, deixando a máquina pronta
# para uma nova instalação limpa (ideal para repetir testes).
#
# Uso:
#   sudo bash uninstall.sh            remove Koha, bancos koha_*, backups,
#                                     configurações, túnel, cron e painel
#   sudo bash uninstall.sh --full     também remove MariaDB, Apache,
#                                     Memcached, Elasticsearch, RabbitMQ,
#                                     cloudflared, rclone e o SWAP criado
#                                     (volta ao estado de antes da instalação)
#   --yes                             não pede confirmação (automação)
#
# Com outras plataformas no registro (/var/lib/koha-nexus/owned.tsv), o
# Apache, o cloudflared, o túnel e o painel são mantidos; só o Koha sai.
# O Docker nunca é removido por aqui, nem quando foi o Koha.Nexus que o
# instalou (o registro dessa instalação, docker.state, também fica).
# ======================================================================

# Copyright (C) 2026 Paulo F. Baldi FH
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. It is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the LICENSE file
# or <https://www.gnu.org/licenses/>.
# ======================================================================

set -o pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"
export DEBIAN_FRONTEND=noninteractive
[ "${EUID:-$(id -u)}" -ne 0 ] && { echo "Execute como root: sudo bash $0"; exit 1; }

ASSUME_YES="no"
FULL="no"
for arg in "$@"; do
    case "$arg" in
        -y|--yes)  ASSUME_YES="yes" ;;
        -f|--full) FULL="yes" ;;
        -h|--help)
            sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "Opção desconhecida: $arg (use --full, --yes ou --help)"; exit 1 ;;
    esac
done

# Registro de propriedade (installer: kei_owned_*). Recursos de outra
# plataforma além do Koha (um site zz-koha-nexus-*, um endereço do túnel)
# continuam: o Apache, o cloudflared, o túnel e o painel ficam, e só o que é
# do Koha sai. Sem outras plataformas, nada muda.
OWNED_FILE="${KEI_OWNED_DIR:-/var/lib/koha-nexus}/owned.tsv"
OTHER_PLATFORMS=""
if [ -f "$OWNED_FILE" ]; then
    OTHER_PLATFORMS=$(awk -F'\t' 'NF >= 4 && $3 != "koha" { print $3 }' "$OWNED_FILE" | sort -u | tr '\n' ' ')
    OTHER_PLATFORMS="${OTHER_PLATFORMS% }"
fi
keep_shared() { [ -n "$OTHER_PLATFORMS" ]; }
# other_site NAME: um site do Apache registrado para outra plataforma.
other_site() {
    [ -f "$OWNED_FILE" ] || return 1
    awk -F'\t' -v n="$1" '$1 == "apache-site" && $2 == n && $3 != "koha" { f = 1 } END { exit !f }' "$OWNED_FILE"
}

if [ "$ASSUME_YES" != "yes" ]; then
    echo "======================================================================"
    echo " ATENÇÃO: esta operação APAGA DEFINITIVAMENTE deste servidor:"
    echo "  - o Koha, todas as instâncias e os bancos de dados koha_*"
    echo "  - os backups locais em /var/backups/koha_sql e /var/backups/koha_marc"
    echo "  - configurações, credenciais, túnel Cloudflare, cron e o painel"
    if [ "$FULL" = "yes" ]; then
        echo "  - MODO --full: também MariaDB (TODOS os bancos), Apache, Memcached,"
        echo "    Elasticsearch, RabbitMQ, cloudflared, rclone e o /swapfile"
    fi
    if keep_shared; then
        echo ""
        echo " Outras plataformas registradas neste servidor: $OTHER_PLATFORMS"
        echo " O Apache, o cloudflared, o túnel e o painel são mantidos para elas;"
        echo " só o que é do Koha é removido."
    fi
    echo ""
    echo " Se quiser guardar os dados, copie os backups para outro lugar ANTES."
    echo "======================================================================"
    printf 'Digite APAGAR para continuar (qualquer outra coisa cancela): '
    read -r answer < /dev/tty || answer=""
    if [ "$answer" != "APAGAR" ]; then
        echo "Cancelado. Nada foi alterado."
        exit 0
    fi
fi

step() { printf '\n\e[1;36m>>> %s\e[0m\n' "$*"; }

# Espera o APT/dpkg terminar em vez de matá-lo (matar o dpkg no meio de uma
# instalação corrompe o banco de pacotes).
wait_for_apt() {
    local waited=0
    while fuser /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/lib/apt/lists/lock >/dev/null 2>&1 \
          || pgrep -x 'apt|apt-get|dpkg' >/dev/null 2>&1; do
        [ "$waited" -eq 0 ] && echo "    Aguardando outro processo do APT/dpkg terminar..."
        sleep 3
        waited=$((waited + 3))
        if [ "$waited" -ge 300 ]; then
            echo "    [AVISO] O APT continua ocupado após 5 minutos; seguindo mesmo assim."
            return 1
        fi
    done
    return 0
}

# Remove pacotes com purge (apaga também os arquivos de configuração do
# dpkg). Com "force" (só para os pacotes do Koha), se o apt falhar a remoção
# é forçada pelo dpkg: um pacote "meio removido" deixa o dpkg achando que os
# arquivos de /etc/koha existem e a próxima instalação falha
# (apache-site.conf.in). Pacotes gerais (Apache, MariaDB...) nunca são
# forçados: em máquinas com desktop outros programas dependem deles.
purge_packages() {
    local force="no" installed=() leftover=() p
    [ "$1" = "force" ] && { force="yes"; shift; }
    for p in "$@"; do
        dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -qE 'install|config-files|half' && installed+=("$p")
    done
    [ ${#installed[@]} -eq 0 ] && return 0
    echo "    Removendo: ${installed[*]}"
    apt-get purge -y "${installed[@]}" >/dev/null 2>&1 || true
    for p in "${installed[@]}"; do
        dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -qE 'install|config-files|half' || continue
        if [ "$force" = "yes" ]; then
            echo "    [!] $p não saiu com apt; forçando com dpkg"
            dpkg --purge --force-remove-reinstreq --force-depends "$p" >/dev/null 2>&1 || true
        else
            leftover+=("$p")
        fi
    done
    if [ ${#leftover[@]} -gt 0 ]; then
        echo "    [i] Mantidos porque outros programas desta máquina dependem deles:"
        echo "        ${leftover[*]}"
        echo "        (não atrapalha uma nova instalação do Koha)"
    fi
    return 0
}

KOHA_PACKAGES=(koha-common koha-elasticsearch koha-perldeps koha-l10n)
FULL_PACKAGES=(elasticsearch rabbitmq-server cloudflared rclone
               mariadb-server mariadb-client mariadb-common mariadb-server-core mariadb-client-core
               apache2 apache2-bin apache2-data apache2-utils libapache2-mpm-itk
               memcached libcache-memcached-fast-perl)

# ----------------------------------------------------------------------
step "[1/9] Parando serviços do Koha, indexadores e túnel..."
if keep_shared; then
    systemctl stop 'koha-*' 'koha-es-indexer@*' 'koha-zebra-daemon@*' 2>/dev/null || true
    systemctl disable 'koha-es-indexer@*' 'koha-zebra-daemon@*' 2>/dev/null || true
else
    systemctl stop 'koha-*' 'koha-es-indexer@*' 'koha-zebra-daemon@*' cloudflared 2>/dev/null || true
    systemctl disable 'koha-es-indexer@*' 'koha-zebra-daemon@*' cloudflared 2>/dev/null || true
    command -v cloudflared >/dev/null 2>&1 && cloudflared service uninstall >/dev/null 2>&1
fi
pkill -f 'zebrasrv|rebuild_zebra|es_indexer_daemon|koha-worker|background_jobs_worker|starman.*koha|z3950_responder|SIPServer' 2>/dev/null
sleep 2
pkill -9 -f 'zebrasrv|rebuild_zebra|es_indexer_daemon|koha-worker|background_jobs_worker|starman.*koha|z3950_responder|SIPServer' 2>/dev/null
keep_shared || pkill -f 'cloudflared tunnel' 2>/dev/null

# ----------------------------------------------------------------------
step "[2/9] Removendo as instâncias do Koha..."
# koha-remove precisa do MariaDB no ar para apagar banco e usuário
systemctl start mariadb >/dev/null 2>&1 || true
if command -v koha-list >/dev/null 2>&1; then
    for inst in $(koha-list 2>/dev/null); do
        echo "    Instância: $inst"
        koha-remove "$inst" >/dev/null 2>&1 || true
    done
fi

# ----------------------------------------------------------------------
step "[3/9] Limpando bancos de dados e usuários koha_* no MariaDB..."
if mysql -e "SELECT 1;" >/dev/null 2>&1; then
    for db in $(mysql -Nse "SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'koha%';" 2>/dev/null); do
        echo "    Banco: $db"
        mysql -e "DROP DATABASE IF EXISTS \`$db\`;" 2>/dev/null || true
    done
    mysql -Nse "SELECT CONCAT(QUOTE(User), '@', QUOTE(Host)) FROM mysql.user WHERE User LIKE 'koha%';" 2>/dev/null \
        | while read -r account; do
            [ -n "$account" ] && mysql -e "DROP USER IF EXISTS ${account};" 2>/dev/null
        done
    mysql -e "FLUSH PRIVILEGES;" 2>/dev/null || true
else
    echo "    MariaDB não está acessível; pulando (nada a limpar ou já removido)."
fi

# ----------------------------------------------------------------------
step "[4/9] Removendo pacotes..."
wait_for_apt
dpkg --configure -a >/dev/null 2>&1 || true
apt-get install -f -y >/dev/null 2>&1 || true
purge_packages force "${KOHA_PACKAGES[@]}"
if [ "$FULL" = "yes" ]; then
    if keep_shared; then
        echo "    [i] Apache e cloudflared mantidos: outras plataformas os usam ($OTHER_PLATFORMS)."
        full=()
        for p in "${FULL_PACKAGES[@]}"; do
            case "$p" in apache2*|libapache2-*|cloudflared) ;; *) full+=("$p") ;; esac
        done
        systemctl stop mariadb memcached elasticsearch rabbitmq-server 2>/dev/null || true
        purge_packages "${full[@]}"
    else
        systemctl stop mariadb apache2 memcached elasticsearch rabbitmq-server 2>/dev/null || true
        purge_packages "${FULL_PACKAGES[@]}"
    fi
fi
apt-get autoremove -y --purge >/dev/null 2>&1 || true

# ----------------------------------------------------------------------
step "[5/9] Restaurando o Apache e as portas padrão..."
if [ -d /etc/apache2 ]; then
    for site in /etc/apache2/sites-enabled/*; do
        [ -e "$site" ] || continue
        other_site "$(basename "$site")" && continue
        grep -qsi 'koha' "$site" && { a2dissite "$(basename "$site")" >/dev/null 2>&1 || rm -f "$site"; }
    done
    rm -f /etc/apache2/sites-available/library.conf /etc/apache2/sites-enabled/library.conf
    sed -i '/^[[:space:]]*Listen[[:space:]]\+8080[[:space:]]*$/d' /etc/apache2/ports.conf 2>/dev/null
    a2ensite 000-default >/dev/null 2>&1 || true
    systemctl restart apache2 >/dev/null 2>&1 || true
fi

# ----------------------------------------------------------------------
step "[6/9] Removendo tarefas agendadas, scripts, unidades e repositórios..."
rm -f /etc/cron.d/koha_* /etc/cron.d/koha-common
rm -f /root/backup_sql.sh /root/backup_marc.sh /usr/local/bin/koha-es-watchdog.sh
rm -f /usr/local/bin/koha-zebra-watchdog.sh /usr/local/bin/koha-wait-services.sh
if keep_shared; then
    echo "    [i] Painel (config.sh) mantido para as outras plataformas."
else
    rm -f /usr/local/bin/config.sh /usr/local/bin/config.sh.bak-* /usr/local/bin/.config.sh.*
    rm -f /usr/local/bin/koha-nexus /etc/koha-nexus /usr/local/lib/koha-nexus
fi
rm -f /usr/local/bin/koha-foreach /tmp/koha-foreach
systemctl disable --now koha-stop-guard-recover.service koha-stop-guard.service >/dev/null 2>&1 || true
rm -f /usr/local/sbin/koha-stop-guard /etc/systemd/system/koha-stop-guard.service /etc/systemd/system/koha-stop-guard-recover.service
rm -f /etc/systemd/system/koha-es-indexer@.service
rm -rf /etc/systemd/system/multi-user.target.wants/koha-* /etc/systemd/system/koha-*.service.d
rm -f /etc/systemd/system/apache2.service.d/koha-easy-install.conf
rmdir /etc/systemd/system/apache2.service.d 2>/dev/null
rm -f /etc/apt/sources.list.d/koha.list /etc/apt/sources.list.d/elastic*.list
rm -f /usr/share/keyrings/koha-keyring.gpg /usr/share/keyrings/elasticsearch-keyring.gpg
keep_shared || rm -f /etc/apt/sources.list.d/cloudflared.list /etc/apt/keyrings/cloudflare-main.gpg
rm -f /etc/fail2ban/jail.d/koha-easy-install.local
rm -f /etc/mysql/mariadb.conf.d/99-koha-tuning.cnf /etc/mysql/mariadb.conf.d/98-koha-durability.cnf
rm -f /etc/systemd/journald.conf.d/00-koha-limits.conf /etc/logrotate.d/koha-easy-install
rm -f /etc/elasticsearch/jvm.options.d/koha_heap.options
systemctl daemon-reload 2>/dev/null || true
systemctl reset-failed 2>/dev/null || true
systemctl restart cron 2>/dev/null || true
systemctl restart fail2ban 2>/dev/null || true
if command -v ufw >/dev/null 2>&1; then
    # Só as portas abertas pelo painel; a do SSH fica (evita perder o acesso).
    for p in 8080 53682 2100 6001; do
        ufw delete allow "${p}/tcp" >/dev/null 2>&1
        ufw delete deny "${p}/tcp" >/dev/null 2>&1
    done
    for net in 127.0.0.1 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16; do
        ufw delete allow from "$net" to any port 8080 proto tcp >/dev/null 2>&1
    done
fi

# ----------------------------------------------------------------------
step "[7/9] Apagando diretórios, credenciais, backups e caches..."
# /etc/koha só é apagado DEPOIS do purge: apagar antes (com o pacote ainda
# instalado) era o que fazia o koha-create falhar na reinstalação.
rm -rf /etc/koha /var/lib/koha /var/log/koha /var/run/koha /run/koha /var/lock/koha \
       /var/cache/koha /var/spool/koha /usr/share/koha
if keep_shared; then
    rm -rf /run/koha-easy-install /var/lib/koha-easy-install
else
    rm -rf /etc/koha-easy-install /var/log/koha-easy-install /run/koha-easy-install /var/lib/koha-easy-install
fi
rm -rf /var/backups/koha_sql /var/backups/koha_marc
if keep_shared; then
    # Só as entradas do Koha saem do ingress: as que o registro dá ao Koha
    # ou, num arquivo anterior ao registro, a primeira em localhost:80 e a
    # primeira em localhost:8080. Entradas feitas à mão ficam.
    koha_hosts=" $(awk -F'\t' '$1 == "ingress" && $3 == "koha" { printf "%s ", $2 }' "$OWNED_FILE")"
    for conf in /etc/cloudflared/config.yml; do
        [ -f "$conf" ] || continue
        awk -v koha="$koha_hosts" '
            /^[[:space:]]*- hostname:/ { held = $0; h = $0; sub(/.*hostname:[[:space:]]*/, "", h); gsub(/["\047[:space:]]/, "", h); next }
            held != "" {
                drop = 0
                if (koha != " ") drop = index(koha, " " h " ") > 0
                else if ($0 ~ /service:[[:space:]]*http:\/\/localhost:80[[:space:]]*$/ && !k80) drop = k80 = 1
                else if ($0 ~ /service:[[:space:]]*http:\/\/localhost:8080[[:space:]]*$/ && !k8080) drop = k8080 = 1
                held_line = held; held = ""
                if (drop) next
                print held_line
            }
            { print }' "$conf" > "$conf.tmp" && cat "$conf.tmp" > "$conf"
        rm -f "$conf.tmp"
    done
    systemctl try-restart cloudflared >/dev/null 2>&1 || true
    awk -F'\t' '$3 != "koha"' "$OWNED_FILE" > "$OWNED_FILE.tmp" && mv -f "$OWNED_FILE.tmp" "$OWNED_FILE"
    echo "    [i] Túnel e registro mantidos para: $OTHER_PLATFORMS"
else
    rm -rf /etc/cloudflared /root/.cloudflared /home/*/.cloudflared
    # docker.state (Docker instalado pelo Koha.Nexus) fica: o Docker não é
    # removido aqui, e o registro diz que ele pode ser removido depois.
    if [ -f "$(dirname "$OWNED_FILE")/docker.state" ]; then
        find "$(dirname "$OWNED_FILE")" -mindepth 1 ! -name docker.state -delete
        echo "    [i] Docker mantido (instalado pelo Koha.Nexus): para removê-lo, use o painel ou apt-get purge docker-ce."
    else
        rm -rf "$(dirname "$OWNED_FILE")"
    fi
fi
rm -f /root/koha_credentials.txt /root/credenciais_koha.txt /root/koha_patrons_template.csv
rm -f /var/run/koha_panel.lock /var/run/koha_backup.pid /var/run/koha_es_watchdog.pid \
      /var/lock/koha_backup.lock /var/lock/koha_es_rebuild.lock /run/lock/koha_zebra_watchdog.lock
rm -rf /tmp/koha_* /tmp/koha-* /tmp/drop_koha_dbs.sql /tmp/99-koha-tuning.bak
if [ "$FULL" = "yes" ]; then
    rm -rf /etc/elasticsearch /var/lib/elasticsearch /var/log/elasticsearch /usr/share/elasticsearch
    rm -rf /etc/rabbitmq /var/lib/rabbitmq /var/log/rabbitmq
    rm -rf /etc/mysql /var/lib/mysql /var/log/mysql
    rm -rf /root/.config/rclone /home/*/.config/rclone
fi

# ----------------------------------------------------------------------
step "[8/9] Restaurando tela de login e memória virtual..."
if [ -r /etc/os-release ]; then
    pretty_name=$(. /etc/os-release; echo "${PRETTY_NAME:-Linux}")
    printf '%s \\n \\l\n\n' "$pretty_name" > /etc/issue
    printf '%s\n' "$pretty_name" > /etc/issue.net
    : > /etc/motd
fi
if [ "$FULL" = "yes" ] && [ -f /swapfile ] && grep -q '^/swapfile' /etc/fstab 2>/dev/null; then
    swapoff /swapfile 2>/dev/null
    sed -i '\|^/swapfile[[:space:]]|d' /etc/fstab
    rm -f /swapfile
    echo "    /swapfile removido."
fi

# ----------------------------------------------------------------------
step "[9/9] Atualizando a lista de pacotes e conferindo o resultado..."
apt-get update >/dev/null 2>&1 || true

problems=0
check() {
    if eval "$2" >/dev/null 2>&1; then
        printf '    [\e[1;31mRESTOU\e[0m] %s\n' "$1"; problems=$((problems + 1))
    else
        printf '    [ \e[1;32mOK\e[0m  ] %s\n' "$1"
    fi
}
check "pacote koha-common removido"          "dpkg-query -W -f='\${Status}' koha-common | grep -qE 'install|config-files|half'"
check "diretório /etc/koha apagado"          "[ -e /etc/koha ]"
if ! keep_shared; then
    check "painel (config.sh) removido"      "[ -e /usr/local/bin/config.sh ]"
    check "configuração do painel apagada"   "[ -e /etc/koha-easy-install ]"
fi
check "tarefas cron do Koha removidas"       "ls /etc/cron.d/koha_* "
check "bancos koha_* removidos"              "mysql -Nse \"SELECT 1 FROM information_schema.schemata WHERE schema_name LIKE 'koha%'\" | grep -q 1"
check "porta 8080 livre"                     "ss -lnt | awk '{print \$4}' | grep -Eq '[.:]8080\$'"
if [ "$FULL" = "yes" ]; then
    check "MariaDB removido"                 "dpkg-query -W -f='\${Status}' mariadb-server | grep -q 'ok installed'"
    keep_shared || check "porta 80 livre"    "ss -lnt | awk '{print \$4}' | grep -Eq '[.:]80\$'"
fi

check "sistema de pacotes consistente"      "! apt-get check"

echo "----------------------------------------------------------------------"
if [ "$problems" -eq 0 ]; then
    echo "Limpeza concluída. A máquina está pronta para uma nova instalação."
else
    echo "Limpeza concluída com $problems pendência(s) acima. Rode o script de novo;"
    echo "se persistir, reinicie o servidor e execute outra vez."
fi
echo "----------------------------------------------------------------------"
