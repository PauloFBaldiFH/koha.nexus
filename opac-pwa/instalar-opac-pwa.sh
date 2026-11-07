#!/usr/bin/env bash
# Koha.Nexus - instala os arquivos do PWA e da carteirinha digital no OPAC do Koha.
#
# Uso (como root, a partir da pasta opac-pwa/ do repositório):
#   sudo ./instalar-opac-pwa.sh
#
# Caminho do OPAC (DocumentRoot) padrão: /usr/share/koha/opac/htdocs
# Para outro caminho: sudo KOHA_OPAC_HTDOCS=/caminho/htdocs ./instalar-opac-pwa.sh
#
# O script só copia arquivos. Não altera o núcleo do Koha nem as preferências:
# os blocos de OpacUserJS e OpacUserCSS são colados à mão (ver README.md).
set -euo pipefail

HTDOCS="${KOHA_OPAC_HTDOCS:-/usr/share/koha/opac/htdocs}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="$HTDOCS/koha-nexus-pwa"

if [ "$(id -u)" -ne 0 ]; then
  echo "Execute com sudo." >&2
  exit 1
fi

if [ ! -d "$HTDOCS" ]; then
  echo "Não encontrei $HTDOCS. Confira o DocumentRoot do OPAC em /etc/apache2/sites-enabled/ e rode com KOHA_OPAC_HTDOCS=..." >&2
  exit 1
fi

# manifest.json e service-worker.js ficam na raiz do OPAC (escopo "/").
# Não sobrescreve arquivos diferentes que já existam ali.
for f in manifest.json service-worker.js; do
  if [ -e "$HTDOCS/$f" ] && ! cmp -s "$SRC/$f" "$HTDOCS/$f"; then
    echo "Já existe $HTDOCS/$f com conteúdo diferente. Renomeie ou remova esse arquivo e rode de novo." >&2
    exit 1
  fi
done

# Pastas: 755 (root:root). Arquivos: 644 (root:root), legíveis pelo Apache (www-data).
install -d -m 0755 -o root -g root "$DEST_DIR" "$DEST_DIR/icons"

install -m 0644 -o root -g root "$SRC/manifest.json"        "$HTDOCS/manifest.json"
install -m 0644 -o root -g root "$SRC/service-worker.js"    "$HTDOCS/service-worker.js"
install -m 0644 -o root -g root "$SRC/carteirinha.js"       "$DEST_DIR/carteirinha.js"
install -m 0644 -o root -g root "$SRC/carteirinha.css"      "$DEST_DIR/carteirinha.css"
install -m 0644 -o root -g root "$SRC/offline.html"         "$DEST_DIR/offline.html"
for icon in "$SRC"/icons/*.png; do
  install -m 0644 -o root -g root "$icon" "$DEST_DIR/icons/$(basename "$icon")"
done

echo "Arquivos instalados em:"
echo "  $HTDOCS/manifest.json"
echo "  $HTDOCS/service-worker.js"
echo "  $DEST_DIR/ (carteirinha.js, carteirinha.css, offline.html, icons/)"
echo
echo "Próximo passo: colar carteirinha.css em OpacUserCSS e carteirinha.js em OpacUserJS (ver README.md)."
