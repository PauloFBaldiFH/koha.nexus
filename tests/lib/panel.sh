#!/bin/bash
# Test driver: loads the installer as a library (no menu), applies the test
# doubles and runs one function in its own process, so the signal tests can
# interrupt it like a real terminal session would.
#   panel.sh <function> [args...]
# KEI_INSTALLER  installer to load (default: the one in this repository)
# KEI_EXTRA      optional file sourced last (per-test tweaks)
KEI_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=/dev/null
source "${KEI_INSTALLER:-$KEI_REPO/installer}" || exit 97
# shellcheck source=tests/lib/overrides.sh
source "$KEI_REPO/tests/lib/overrides.sh"
# shellcheck source=/dev/null
[ -n "${KEI_EXTRA:-}" ] && source "$KEI_EXTRA"
"$@"
