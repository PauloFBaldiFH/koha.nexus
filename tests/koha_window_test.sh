#!/bin/bash
# koha-window (KohaEasy.Core.psm1, written into Debian by Windows): what is
# left running when the panel ends by itself, and when its window is closed
# under it. A pty from script(1) stands in for the Windows terminal; killing
# script is the closed window (the pty hangs up and WSL's relay is gone).
set -u
repo=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'for p in $(cat "$work/pids" 2>/dev/null); do kill -KILL "$p" 2>/dev/null; done' EXIT
awk '/^\$script:WindowScript = /{f=1;next} /^.@$/{f=0} f' "$repo/windows/KohaEasy.Core.psm1" > "$work/koha-window"
sh -n "$work/koha-window" || { echo "FAIL koha-window does not parse"; exit 1; }
failed=0
check() { if [ "$2" = 0 ]; then echo "ok   $1"; else echo "FAIL $1"; failed=1; fi; }
# PIDs of "sleep N" (exact words, so no shell that merely mentions it).
sleeps() { ps -eo pid=,args= | awk -v n="$1" '$2 == "sleep" && index($3, n) == 1 && NF == 3 {print $1}'; }
alive() { [ -n "$(sleeps "$1")" ]; }
remember() { sleeps 91 >> "$work/pids"; }
stop_sleeps() { for p in $(sleeps 91); do kill "$p" 2>/dev/null; done; }
watchers() { ps -eo args= | awk -v w="$work" '$1 == "sh" && $2 == w "/koha-window" || $1 == "tail" && index($2, "--pid=") == 1'; }

# A panel that starts what a routine may leave behind: a detached helper in
# the window's session (nohup), one that ignores the hang-up, one that keeps
# the terminal, and a job started on purpose in its own session (setsid).
cat > "$work/panel" <<'SH'
#!/bin/sh
nohup sleep 9101 >/dev/null 2>&1 </dev/null &
( trap '' HUP; exec sleep 9102 ) >/dev/null 2>&1 </dev/null &
sleep 9103 &
setsid sleep 9104 >/dev/null 2>&1 </dev/null &
[ "${1:-}" = wait ] && exec sleep 9100
exit 0
SH
chmod +x "$work/panel"

# 1. The window is closed while the panel runs.
script -qec "sh $work/koha-window $work/panel wait" /dev/null </dev/null >/dev/null 2>&1 &
window=$!
sleep 2
remember
kill -KILL "$window"
wait "$window" 2>/dev/null
sleep 4
alive 9100; check "closed window: the panel is stopped" $((1 - $?))
alive 9101; check "closed window: a helper of its session is stopped" $((1 - $?))
alive 9102; check "closed window: a helper that ignores the hang-up is stopped" $((1 - $?))
alive 9103; check "closed window: a process on the terminal is stopped" $((1 - $?))
alive 9104; check "closed window: a job in its own session keeps running" $?
[ -z "$(watchers)" ]; check "closed window: koha-window and its watcher ended" $?
stop_sleeps

# 2. The panel ends by itself: only what keeps the terminal is stopped.
script -qec "sh $work/koha-window $work/panel" /dev/null </dev/null >/dev/null 2>&1
sleep 3
remember
alive 9101; check "panel ended: a detached helper keeps running" $?
alive 9103; check "panel ended: a process on the terminal is stopped" $((1 - $?))
alive 9104; check "panel ended: a job in its own session keeps running" $?
[ -z "$(watchers)" ]; check "panel ended: no watcher is left" $?
stop_sleeps

exit "$failed"
