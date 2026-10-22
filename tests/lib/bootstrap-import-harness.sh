#!/usr/bin/env bash
# Internal container setup for tests/run.sh. Never run against an installed library.
set -euo pipefail

if [[ ${KEI_TEST_SANDBOX:-} != 1 || ! -f /.dockerenv || $EUID != 0 ]]; then
    echo 'Requires root inside the explicitly enabled disposable Docker sandbox.' >&2
    exit 2
fi
if [[ ! -f /repo/installer || ! -f /repo/tests/lib/common.bash || ! -d /scratch ]]; then
    echo 'Expected /repo read-only and a private /scratch bind mount.' >&2
    exit 2
fi
if ! findmnt -n -o OPTIONS -T /repo | tr ',' '\n' | grep -qx ro; then
    echo 'Refusing: /repo must be mounted read-only.' >&2
    exit 2
fi
if [[ -f /usr/share/koha/lib/C4/Context.pm ]] ||
    dpkg-query -W -f='${Status}' koha-common 2>/dev/null | grep -q 'install ok installed'; then
    echo 'Refusing to replace tools alongside a real Koha installation.' >&2
    exit 2
fi

export DEBIAN_FRONTEND=noninteractive
packages=(bats mariadb-server mariadb-client memcached whiptail dialog curl wget gnupg
          libxml2-utils xsltproc zip unzip xz-utils zstd psmisc iproute2 util-linux
          python3 python3-pytest python3-xlrd python3-xlwt
          libmarc-record-perl libmarc-charset-perl libmarc-xml-perl
          libdbi-perl libdbd-mysql-perl libtext-csv-perl yaz procps ca-certificates)
missing=()
for package in "${packages[@]}"; do
    dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed' || missing+=("$package")
done
if ((${#missing[@]})); then
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends "${missing[@]}"
fi

mkdir -p /usr/local/lib/kei-mock /usr/share/koha/bin/{cronjobs,maintenance,migration_tools,admin} \
    /etc/koha/sites/library /etc/koha-easy-install /etc/default /etc/cron.d \
    /etc/systemd/system /var/lib/koha/library /run/kei-mock /var/lock
touch /run/kei-mock/.disposable-harness
id library-koha >/dev/null 2>&1 || useradd --system --no-create-home --home-dir /var/lib/koha/library library-koha
install -m 755 /repo/tests/mocks/koha-mock /usr/local/lib/kei-mock/koha-mock
install -m 755 /repo/tests/mocks/koha-script /usr/local/lib/kei-mock/koha-script
install -m 755 /repo/tests/mocks/http-mock /usr/local/lib/kei-mock/http-mock
install -m 755 /repo/tests/mocks/curl /usr/local/bin/curl
cp -R /repo/tests/mocks/perl5 /usr/local/lib/kei-mock/
chmod -R a+rX /usr/local/lib/kei-mock/perl5
install -m 644 /repo/tests/mocks/koha-functions.sh /usr/share/koha/bin/koha-functions.sh
install -m 600 /repo/tests/mocks/koha-conf.xml /etc/koha/sites/library/koha-conf.xml
for tool in koha-list koha-shell koha-mysql koha-plack koha-zebra koha-indexer \
    koha-es-indexer koha-worker koha-sip koha-z3950-responder koha-email-enable; do
    ln -sfn /usr/local/lib/kei-mock/koha-mock "/usr/sbin/$tool"
done
for script in stage_file.pl commit_file.pl import_patrons.pl update_patrons_category.pl \
    delete_patrons.pl batch_anonymise.pl search_for_data_inconsistencies.pl \
    link_bibs_to_authorities.pl koha-preferences; do
    ln -sfn /usr/local/lib/kei-mock/koha-script "/usr/share/koha/bin/$script"
done

# Service operations record state. MariaDB and Memcached themselves remain
# real processes started below by the repository's service test helpers.
cat > /usr/local/bin/systemctl <<'MOCK'
#!/usr/bin/env bash
set -u
s=/run/kei-mock
mkdir -p "$s/svc" "$s/svc-fail"
printf 'systemctl %s\n' "$*" >> "$s/calls.log"
operation=''
units=()
for argument in "$@"; do
    case "$argument" in
        -*) ;;
        start|stop|restart|try-restart|reload|is-active|is-enabled|status|show|enable|disable|mask|unmask|daemon-reload|reset-failed|is-system-running)
            [[ -n $operation ]] || { operation=$argument; continue; }
            units+=("$argument") ;;
        *) units+=("$argument") ;;
    esac
done
case "$operation" in
    daemon-reload|reset-failed) exit 0 ;;
    is-system-running) printf 'running\n'; exit 0 ;;
esac
rc=0
for unit in "${units[@]}"; do
    unit=${unit%.service}
    if [[ -e $s/svc-fail/$unit ]]; then rc=1; continue; fi
    case "$operation" in
        start|restart|try-restart|reload) touch "$s/svc/$unit" ;;
        stop) rm -f "$s/svc/$unit" ;;
        is-active|status) [[ -e $s/svc/$unit ]] || rc=3 ;;
        is-enabled) [[ -e $s/enabled/$unit ]] || rc=1 ;;
        enable) mkdir -p "$s/enabled"; touch "$s/enabled/$unit" ;;
        disable) rm -f "$s/enabled/$unit" ;;
        show) printf 'ActiveState=%s\n' "$( [[ -e $s/svc/$unit ]] && echo active || echo inactive )" ;;
        mask|unmask) ;;
        *) printf 'Unsupported test systemctl operation: %s\n' "$operation" >&2; exit 2 ;;
    esac
done
exit "$rc"
MOCK
chmod 755 /usr/local/bin/systemctl

cat > /scratch/bats.env <<'ENV'
export KEI_TEST_SANDBOX=1
export KEI_INSTALLER=/scratch/installer-library.sh
export KOHA_PANEL_LANG=en
export KOHA_PANEL_LANG_FULL=en-GB
export KEI_PLATFORM_OVERRIDE=linux
export TERM=xterm
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ENV

# This starts dependencies only; no installer function or functional test runs.
source /repo/tests/lib/common.bash
kei_start_mariadb
kei_start_memcached
mysql <<'SQL'
CREATE USER IF NOT EXISTS 'koha_library'@'localhost' IDENTIFIED BY 'KeiTest-Pass_42';
CREATE USER IF NOT EXISTS 'koha_library'@'127.0.0.1' IDENTIFIED BY 'KeiTest-Pass_42';
GRANT ALL PRIVILEGES ON koha_library.* TO 'koha_library'@'localhost';
GRANT ALL PRIVILEGES ON koha_library.* TO 'koha_library'@'127.0.0.1';
SQL
python3 /repo/tests/lib/prepare-import-library.py /repo/installer /scratch/installer-library.sh
bash -n /scratch/installer-library.sh
mysql --batch --skip-column-names -e 'SELECT 1'
printf 'Disposable Bats dependencies, services, and tool doubles are ready. No functional tests have run.\n'
