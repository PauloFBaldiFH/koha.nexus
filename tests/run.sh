#!/usr/bin/env bash
# The test database and command doubles exist only in a fresh Docker container.
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: bash tests/run.sh [--filter REGEX] [tests/FILE.bats ...]

With no files, run Magic Import reliability, migration and library-tool tests.
Docker must be running. The repository is mounted read-only; the new container
and its temporary scratch directory are removed when this command finishes.
HELP
}

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
bats_args=()
files=()
while (($#)); do
    case "$1" in
        --help|-h) usage; exit 0 ;;
        --filter|-f)
            (($# >= 2)) || { usage >&2; exit 2; }
            bats_args+=(--filter "$2"); shift 2 ;;
        --) shift; files+=("$@"); break ;;
        -*) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
        *) files+=("$1"); shift ;;
    esac
done
if ((${#files[@]} == 0)); then
    files=(tests/magic_import_reliability.bats tests/magic_import.bats tests/library_tools.bats)
fi
for requested in "${files[@]}"; do
    case "$requested" in
        "$repo"/*) path="$requested" ;;
        *) path="$repo/$requested" ;;
    esac
    [[ -f $path ]] || { printf 'Test file not found: %s\n' "$requested" >&2; exit 2; }
    path=$(realpath -- "$path")
    case "$path" in
        "$repo"/tests/*.bats) bats_args+=("/repo/${path#"$repo/"}") ;;
        *) printf 'Expected a Bats file inside this repository tests/: %s\n' "$requested" >&2; exit 2 ;;
    esac
done
command -v docker >/dev/null || { echo 'Docker is required for the isolated test database.' >&2; exit 2; }
docker info >/dev/null 2>&1 || { echo 'Docker is not available. Start it and run this command again.' >&2; exit 2; }

scratch=$(mktemp -d "${TMPDIR:-/tmp}/kei-import-tests.XXXXXXXX")
chmod 700 "$scratch"
container="kei-import-tests-${UID}-$(date +%s)-${RANDOM}"
created=0
cleanup() {
    local status=$?
    trap - EXIT
    if [[ $created == 1 ]]; then
        # Container root created private files in the bind mount; remove them
        # there so an unprivileged host can remove its scratch directory too.
        docker exec "$container" find /scratch -mindepth 1 -delete >/dev/null 2>&1 || true
        docker rm -f "$container" >/dev/null 2>&1 || true
    fi
    rm -rf -- "$scratch" || true
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf 'Starting disposable Debian 12 test container: %s\n' "$container"
docker run --detach --name "$container" \
    --mount "type=bind,source=$repo,target=/repo,readonly" \
    --mount "type=bind,source=$scratch,target=/scratch" \
    --env KEI_TEST_SANDBOX=1 \
    debian:bookworm sleep infinity >/dev/null
created=1
if ! docker exec "$container" bash /repo/tests/lib/bootstrap-import-harness.sh > "$scratch/bootstrap.log" 2>&1; then
    tail -n 100 "$scratch/bootstrap.log" >&2
    exit 1
fi
printf 'Dependencies ready. Running synthetic Bats tests.\n'
docker exec "$container" bash -c 'source /scratch/bats.env; exec bats "$@"' bash "${bats_args[@]}"
