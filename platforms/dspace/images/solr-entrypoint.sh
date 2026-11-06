#!/bin/bash
set -euo pipefail
umask 027
# Initial creation only. Never overwrite configsets in an existing data volume.
for core in authority oai search statistics qaevent suggestion audit; do
    precreate-core "$core" "/opt/nexus-solr/$core"
done
exec solr-foreground "$@"
