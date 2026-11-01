#!/bin/sh
# koha.nexus for Windows: Koha's clean stop inside Debian (WSL2).
# Installed by the Windows side as /usr/local/bin/koha-graceful-shutdown.sh
# (KohaEasy.Core.psm1 Update-KohaStopScript) and run as root before WSL
# stops the distro: by the shutdown watcher when Windows shuts down,
# restarts or signs out, and through stdin by Stop, Restart and "Shut down
# the PC safely". Koha's services stop in the order a clean shutdown uses:
# the web, Koha's own daemons and the search engine first, so nothing writes
# to the database any more; then MariaDB, the one whose files must not be
# cut off mid-write; then the queue, the cache and Elasticsearch, which can
# take long and hold nothing that cannot be rebuilt (at the end of a Windows
# session the time is short, so MariaDB goes before them); then everything
# still cached is written to Debian's virtual disk (ext4.vhdx), and
# koha-stop-guard records the clean stop the next start looks for. A few
# seconds on a library PC; the caller bounds it (timeout) all the same.
# Exit 0 only when everything stopped and the guard recorded it.
# "@step N": how far the stop got, for the progress the Windows side shows.
# Tests: tests/graceful_shutdown.bats (KOHA_STOP_GUARD points at a stand-in).
guard=${KOHA_STOP_GUARD:-/usr/local/sbin/koha-stop-guard}
rc=0
if [ "$(ps -p 1 -o comm= 2>/dev/null)" != "systemd" ]; then
  # No systemd (an old wsl.conf): nothing is a unit, but a MariaDB started
  # by hand still gets its own clean shutdown before the disk is synced.
  echo "@step 2"
  if command -v mariadb-admin >/dev/null 2>&1 && mariadb-admin ping >/dev/null 2>&1; then
    mariadb-admin shutdown || { echo "did not stop: mariadb"; rc=1; }
  fi
  echo "@step 4"
  sync
  exit $rc
fi
stop_units() {
  units=""
  for s in "$@"; do systemctl cat "$s.service" >/dev/null 2>&1 && units="$units $s.service"; done
  [ -n "$units" ] || return 0
  systemctl stop $units || { echo "did not stop:$units"; rc=1; }
}
echo "@step 1"
stop_units apache2 koha-common
# Plack, Zebra, the indexers and both queues of the background workers of
# each instance, also when the panel started them outside koha-common.
for i in $(koha-list 2>/dev/null); do
  for t in koha-plack koha-worker koha-indexer koha-es-indexer koha-zebra; do
    command -v "$t" >/dev/null 2>&1 && "$t" --stop "$i" >/dev/null 2>&1
  done
  command -v koha-worker >/dev/null 2>&1 && koha-worker --stop --queue long_tasks "$i" >/dev/null 2>&1
done
echo "@step 2"
stop_units mariadb
echo "@step 3"
stop_units rabbitmq-server memcached elasticsearch
echo "@step 4"
sync
if [ -x "$guard" ]; then
  "$guard" stop || { echo "not marked clean (see /var/log/koha-easy-install/stop-guard.log)"; rc=1; }
else
  echo "no clean-stop guard in this Debian yet"
fi
exit $rc
