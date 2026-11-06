#!/bin/sh
set -eu
umask 027
# Installation must supply private configuration, never the upstream defaults.
[ -r /dspace/config/local.cfg ] || { echo 'Missing DSpace local.cfg.' >&2; exit 78; }
# Migration is intentionally NOT part of container startup.
case "${1:-server}" in
    server)
        [ "$#" -eq 0 ] || shift
        exec java -jar /dspace/webapps/server-boot.jar "$@"
        ;;
    cli)
        shift
        exec /dspace/bin/dspace "$@"
        ;;
    *) echo 'Expected server or cli COMMAND [ARGS].' >&2; exit 64 ;;
esac
