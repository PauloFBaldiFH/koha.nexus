#!/usr/bin/env bash
# Reference signer for Koha broker requests: the same steps the installer
# will run. Needs bash, openssl (1.1.1+ / 3.x), coreutils and curl.
#
#   kei-sign.sh keygen KEYFILE
#       create an Ed25519 private key (mode 0600)
#   kei-sign.sh pubkey KEYFILE
#       print the raw 32-byte public key in base64 (sent once, at enrollment)
#   kei-sign.sh headers KEYFILE LIBRARY_ID METHOD PATH [BODYFILE]
#       print the four X-KEI-* headers for a request, one per line
#   kei-sign.sh curl KEYFILE LIBRARY_ID METHOD URL [BODYFILE]
#       send a signed request with curl (JSON body from BODYFILE)
#
# Signed string (no trailing newline):
#   KEI-SIG-v1\n<METHOD>\n<path?query>\n<unix time>\n<nonce>\n<sha256 hex of body>
set -euo pipefail

die() { echo "kei-sign: $*" >&2; exit 1; }

cmd_keygen() {
    local key="$1"
    [ -e "$key" ] && die "$key already exists"
    (umask 077 && openssl genpkey -algorithm ed25519 -out "$key")
    chmod 600 "$key"
}

cmd_pubkey() {
    openssl pkey -in "$1" -pubout -outform DER | tail -c 32 | base64 | tr -d '\n'
    echo
}

cmd_headers() {
    local key="$1" lib="$2" method="$3" path="$4" body="${5:-}" ts nonce body_hash tmp sig
    ts=$(date +%s)
    nonce=$(openssl rand -hex 16)
    if [ -n "$body" ]; then
        body_hash=$(sha256sum < "$body" | cut -d' ' -f1)
    else
        body_hash=$(printf '' | sha256sum | cut -d' ' -f1)
    fi
    tmp=$(mktemp)
    trap 'rm -f "$tmp"' RETURN
    printf 'KEI-SIG-v1\n%s\n%s\n%s\n%s\n%s' "${method^^}" "$path" "$ts" "$nonce" "$body_hash" > "$tmp"
    sig=$(openssl pkeyutl -sign -inkey "$key" -rawin -in "$tmp" | base64 | tr -d '\n')
    printf 'X-KEI-Library: %s\nX-KEI-Timestamp: %s\nX-KEI-Nonce: %s\nX-KEI-Signature: %s\n' "$lib" "$ts" "$nonce" "$sig"
}

cmd_curl() {
    local key="$1" lib="$2" method="$3" url="$4" body="${5:-}" rest path args=()
    rest="${url#*://}"
    path="/${rest#*/}"
    [ "$rest" = "${rest#*/}" ] && path="/"
    while IFS= read -r h; do args+=(-H "$h"); done < <(cmd_headers "$key" "$lib" "$method" "$path" "$body")
    if [ -n "$body" ]; then
        args+=(-H "Content-Type: application/json" --data-binary "@$body")
    fi
    curl -sS -X "${method^^}" "${args[@]}" "$url"
    echo
}

[ $# -ge 1 ] || die "usage: kei-sign.sh keygen|pubkey|headers|curl ..."
sub="$1"; shift
case "$sub" in
    keygen)  [ $# -eq 1 ] || die "usage: keygen KEYFILE"; cmd_keygen "$@" ;;
    pubkey)  [ $# -eq 1 ] || die "usage: pubkey KEYFILE"; cmd_pubkey "$@" ;;
    headers) [ $# -ge 4 ] || die "usage: headers KEYFILE LIBRARY_ID METHOD PATH [BODYFILE]"; cmd_headers "$@" ;;
    curl)    [ $# -ge 4 ] || die "usage: curl KEYFILE LIBRARY_ID METHOD URL [BODYFILE]"; cmd_curl "$@" ;;
    *) die "unknown command: $sub" ;;
esac
