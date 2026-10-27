#!/usr/bin/env bash
# Install files only; DO NOT enable/start any network probing or change existing Koha.
set -Eeuo pipefail
if [[ ${EUID} -ne 0 ]]; then echo 'Execute com sudo: sudo ./install.sh'; exit 1; fi
if ! command -v python3 >/dev/null; then echo 'Python3 não encontrado.'; exit 1; fi
if ! id z39explorer >/dev/null 2>&1; then
  useradd --system --home /var/lib/z39-atlas --shell /usr/sbin/nologin z39explorer
fi
install -d -m 0755 /opt/z39-atlas
install -d -m 0750 -o z39explorer -g z39explorer /var/lib/z39-atlas
install -m 0755 z39atlas.py /opt/z39-atlas/z39atlas.py
install -m 0644 README.md /opt/z39-atlas/README.md
install -d -m 0755 /opt/z39-atlas/data /opt/z39-atlas/systemd
install -m 0644 data/legacy-confirmed-2026-10-27.csv /opt/z39-atlas/data/legacy-confirmed-2026-10-27.csv
install -m 0644 systemd/z39-atlas.service.example /opt/z39-atlas/systemd/z39-atlas.service.example
if [[ ! -e /opt/z39-atlas/allowed-hosts.txt ]]; then
  install -m 0640 -o z39explorer -g z39explorer allowed-hosts.example.txt /opt/z39-atlas/allowed-hosts.txt
fi
cat <<'EOF'
Instalação de arquivos concluída: /opt/z39-atlas
NENHUMA busca ativa foi iniciada. Nenhum serviço Koha foi modificado.
Para descoberta passiva:
  sudo -u z39explorer python3 /opt/z39-atlas/z39atlas.py --db /var/lib/z39-atlas/atlas.sqlite3 import-csv /opt/z39-atlas/data/legacy-confirmed-2026-10-27.csv
  sudo -u z39explorer python3 /opt/z39-atlas/z39atlas.py --db /var/lib/z39-atlas/atlas.sqlite3 harvest --max-pages 60 --delay 3
Para sondagem ativa: revise README, allowed-hosts.txt e confirme autorização.
EOF
