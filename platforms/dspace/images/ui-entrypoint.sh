#!/bin/sh
set -eu
umask 027
# Avoid upstream's self-signed fallback, which disables outbound TLS validation.
# TLS terminates at the managed reverse proxy; this listener stays HTTP.
case "${DSPACE_UI_SSL:-false}:${DSPACE_SSL:-false}" in
    false:false) ;;
    *) echo 'Terminate TLS at the reverse proxy; set DSPACE_UI_SSL=false.' >&2; exit 78 ;;
esac
# Do not fall back to the upstream demonstration backend.
: "${DSPACE_UI_BASEURL:?Set the canonical public UI URL}"
: "${DSPACE_REST_HOST:?Set the public API host}"
: "${DSPACE_REST_PORT:?Set the public API port}"
: "${DSPACE_REST_SSL:?Set whether the public API uses TLS}"
: "${DSPACE_REST_NAMESPACE:?Set the public API namespace}"
: "${DSPACE_REST_SSRBASEURL:?Set the internal SSR API URL}"
exec node dist/server/main.js "$@"
