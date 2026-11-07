#!/usr/bin/env bash
# Verificação estática do módulo opac-pwa (sem Koha, sem rede).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

fail=0
ok() { echo "ok   $1"; }
bad() { echo "FAIL $1"; fail=1; }

# JSON válido
if python3 -c 'import json,sys; json.load(open(sys.argv[1]))' manifest.json 2>/dev/null; then ok "manifest.json é JSON válido"; else bad "manifest.json"; fi

# Campos exigidos pelo PWA
python3 - <<'EOF' && ok "manifest tem display standalone, portrait, start_url, ícones 192/512/maskable" || { bad "campos do manifest"; }
import json
m = json.load(open("manifest.json"))
assert m["display"] == "standalone"
assert m["orientation"] == "portrait"
assert m["start_url"] and m["scope"] == "/"
sizes = {i["sizes"] for i in m["icons"]}
assert {"192x192", "512x512"} <= sizes
assert any(i.get("purpose") == "maskable" for i in m["icons"])
for i in m["icons"]:
    assert i["src"].startswith("/koha-nexus-pwa/icons/")
EOF

# Sintaxe JS (Node)
if command -v node >/dev/null 2>&1; then
  for f in service-worker.js carteirinha.js; do
    if node --check "$f" 2>/dev/null; then ok "sintaxe $f"; else bad "sintaxe $f"; fi
  done
else
  bad "node não instalado; sintaxe não verificada"
fi

# Ícones existem
for f in icons/icon-192.png icons/icon-512.png icons/icon-maskable-512.png; do
  [ -s "$f" ] && ok "$f" || bad "$f ausente"
done

# Nenhum caminho do cache de páginas do Koha pode ser guardado
if grep -n "cgi-bin" service-worker.js | grep -q "cache.put\|addAll"; then bad "SW guarda cgi-bin no cache"; else ok "SW não guarda páginas cgi-bin"; fi

exit $fail
