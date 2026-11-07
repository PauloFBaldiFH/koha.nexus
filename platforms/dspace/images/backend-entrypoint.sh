#!/bin/sh
set -eu
umask 027
# Installation must supply private configuration, never the upstream defaults.
[ -r /dspace/config/local.cfg ] || { echo 'Missing DSpace local.cfg.' >&2; exit 78; }
# Migration is intentionally NOT part of container startup.
case "${1:-server}" in
    server)
        [ "$#" -eq 0 ] || shift
        # Upstream Context checks Flyway and can apply pending migrations.
        # Refuse before loading it unless the explicit CLI operation recorded
        # this exact release and database history. This also runs after reboot.
        java -cp '/usr/local/lib/nexus-dspace:/dspace/lib/*' NexusSchemaGuard check
        exec java -Ddspace.dir=/dspace -jar /dspace/webapps/server-boot.jar "$@"
        ;;
    cli)
        shift
        JAVA_OPTS="${JAVA_OPTS:--Xmx512m} -Ddspace.dir=/dspace"
        export JAVA_OPTS
        exec /dspace/bin/dspace "$@"
        ;;
    schema-record)
        [ "$#" -eq 1 ] || exit 64
        exec java -cp '/usr/local/lib/nexus-dspace:/dspace/lib/*' NexusSchemaGuard record
        ;;
    *) echo 'Expected server or cli COMMAND [ARGS].' >&2; exit 64 ;;
esac
