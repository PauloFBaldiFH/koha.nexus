#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "${EUID}" -ne 0 ]]; then echo 'Execute: sudo ./install.sh'; exit 1; fi
if [[ ! -f ./z39_explorer.py || ! -f ./seeds.tsv || ! -f ./z39-explorer.service ]]; then
  echo 'Execute este script a partir da pasta extraida do pacote.'; exit 1
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y yaz python3-requests python3-bs4
if ! id z39explorer >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/z39-explorer --shell /usr/sbin/nologin z39explorer
fi
install -d -m 0755 -o root -g root /opt/z39-explorer
install -d -m 0750 -o z39explorer -g z39explorer /var/lib/z39-explorer
install -m 0755 ./z39_explorer.py /opt/z39-explorer/z39_explorer.py
install -m 0640 -o root -g z39explorer ./seeds.tsv /opt/z39-explorer/seeds.tsv
install -m 0644 ./z39-explorer.service /etc/systemd/system/z39-explorer.service
systemctl daemon-reload
printf '\nInstalado. Para iniciar: sudo systemctl start --no-block z39-explorer.service\n'
printf 'Acompanhar: sudo journalctl -u z39-explorer -f\n'
printf 'Resultados: /var/lib/z39-explorer/reports/\n'
