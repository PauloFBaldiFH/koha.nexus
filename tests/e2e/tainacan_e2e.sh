#!/bin/bash
# The whole Tainacan experience on a throwaway machine with systemd, real
# WordPress and the real Tainacan plugin (it needs wordpress.org and Docker
# Hub: CI, .github/workflows/tainacan-e2e.yml), driven the way the panel
# does it and checked through a real browser:
#
#   1. install through the panel's tasks (Docker's plan and Yes first when
#      Docker is missing, then Tainacan's plan and Yes)
#   2. the administrator's credentials, the login, the admin page
#   3-5. a public collection and an item with metadata and an image, both
#      published; a private collection and item
#   6. without a login: found from the home page, opened, searched
#   7. the private ones stay private (pages and API)
#   8. Docker restarted and the machine rebooted: everything still there
#   9. a backup and an isolated restore test with the same data
#
#   tests/e2e/tainacan_e2e.sh IMAGE OUTDIR
#
# Read-only facts of each level (tests/e2e/tainacan_probe.sh) are printed
# before and after. Every check prints "ok" or "FAIL"; the script goes on
# after a failure (the next steps say more) and exits 1 at the end.
set -uo pipefail
image="$1"; out="$2"; name="${KEI_E2E_MACHINE:-kn-e2e}"
here="$(cd "$(dirname "$0")" && pwd)"; repo="$(cd "$here/../.." && pwd)"
C="$repo/tests/system/container.sh"
mkdir -p "$out"
fails=0
ok()   { echo "ok   $*"; }
fail() { echo "FAIL $*"; fails=$((fails + 1)); }
in_vm() { "$C" run "$name" bash -c "$1"; }
task() { in_vm "config.sh --task $*" 2>&1 | tee -a "$out/tasks.log" | grep -E '^@@(msg|result|step)' ; return "${PIPESTATUS[0]}"; }
section() { printf '\n===== %s =====\n' "$*"; }

section "machine"
"$C" start "$image" "$name"
in_vm 'install -m 755 /src/installer /usr/local/bin/config.sh && install -m 755 /src/tests/e2e/tainacan_probe.sh /usr/local/bin/kn-probe'

section "1. install through the panel's tasks"
plan=$(task tainacan-plan)
echo "$plan"
if ! in_vm 'command -v docker' >/dev/null; then
    task docker-plan
    if task docker-install confirm; then ok "Docker installed after its plan and Yes"; else fail "Docker install"; fi
fi
url=$(task tainacan-plan | sed -n 's/^@@result address=//p' | head -n 1)
echo "address offered by the plan: ${url:-?}"
if task tainacan-install confirm "$url"; then ok "Tainacan installed"; else fail "Tainacan install"; fi
url=$(in_vm 'bash -c "source /usr/local/bin/config.sh >/dev/null 2>&1; _kei_tn_get url"' 2>/dev/null)
echo "installed address: $url"

section "probe after install"
in_vm kn-probe | tee "$out/probe-install.txt"

section "2. credentials"
# The task's text holds the password: checked here, never printed or kept.
creds=$(in_vm 'config.sh --task tainacan-credentials' 2>&1)
printf '%s\n' "$creds" | grep -q 'wp-admin' && ok "the credentials task gives the admin address, user and password" \
    || fail "credentials task"
unset creds
user=$(in_vm 'bash -c "source /usr/local/bin/config.sh >/dev/null 2>&1; _kei_tn_env KN_ADMIN_USER"' 2>/dev/null)
pass=$(in_vm 'bash -c "source /usr/local/bin/config.sh >/dev/null 2>&1; _kei_tn_env KN_ADMIN_PASSWORD"' 2>/dev/null)
[ -n "${GITHUB_ACTIONS:-}" ] && echo "::add-mask::$pass"
export KN_USER="$user" KN_PASS="$pass"
B() { python3 "$here/tainacan_browser.py" "$1" "$url" "$out"; }

section "2. browser: look and log in"
B look || fail "browser look"
section "3-5. browser: collections and items"
B seed || fail "browser seed"
section "6-7. browser: public and private"
B public || fail "browser public"
B direct || fail "browser direct addresses"

section "8. persistence: Docker restart"
counts_before=$(in_vm 'bash -c "source /usr/local/bin/config.sh >/dev/null 2>&1; _kei_tn_counts"' 2>/dev/null)
in_vm 'systemctl restart docker' && sleep 20
counts=$(in_vm 'bash -c "source /usr/local/bin/config.sh >/dev/null 2>&1; _kei_tn_counts"' 2>/dev/null)
[ -n "$counts_before" ] && [ "$counts" = "$counts_before" ] && ok "same data after Docker restarted ($counts)" || fail "data after Docker restart: '$counts_before' -> '$counts'"
section "8. persistence: machine reboot"
"$C" reboot "$name"
for _ in $(seq 1 60); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$url/")" = 200 ] && break
    sleep 5
done
counts=$(in_vm 'bash -c "source /usr/local/bin/config.sh >/dev/null 2>&1; _kei_tn_counts"' 2>/dev/null)
[ "$counts" = "$counts_before" ] && ok "same data after the reboot ($counts)" || fail "data after reboot: '$counts_before' -> '$counts'"
B public || fail "browser public after the reboot"

section "9. backup and isolated restore test"
if task tainacan-backup; then ok "backup"; else fail "backup"; fi
# The message is in the installer's language: the exit status and the
# counts it compared ("(ok COLLECTIONS ITEMS ATTACHMENTS)") are what count.
if rt=$(task tainacan-restore-test latest); then rt_ok=1; else rt_ok=0; fi
echo "$rt"
[ "$rt_ok" = 1 ] && printf '%s' "$rt" | grep -q '(ok [0-9]* [0-9]* [0-9]*)' && ok "isolated restore test" \
    || fail "isolated restore test"

section "probe at the end"
in_vm kn-probe | tee "$out/probe-end.txt"
in_vm 'config.sh --status-json' 2>/dev/null | grep '^{' | tail -n 1 | python3 -c 'import json,sys
d = json.load(sys.stdin); print(json.dumps([p for p in d["platforms"] if p["id"] == "tainacan"][0], ensure_ascii=False))' || true

section "result"
echo "failed checks in this script: $fails"
[ "$fails" = 0 ]
