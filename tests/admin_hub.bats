#!/usr/bin/env bats
# Administration hub (section 41): the schedules written by the panel's
# Scheduled tasks screen, the state read by the messaging hub, the SIP2
# form's SIPconfig.xml and the OneDrive / MEGA / S3 cloud connections (a
# stand-in rclone records what it is asked). The files themselves are
# Python: panel/tests/test_cron.py, test_sip.py and test_cloud.py.

setup_file() {
    load lib/common
    kei_start_mariadb
    mysql -e "CREATE DATABASE IF NOT EXISTS $DB CHARACTER SET utf8mb4;"
}

setup() {
    load lib/common
    W="$BATS_TEST_TMPDIR"
    rm -f "$KEI_S/dialogs.log"
    mkdir -p "$W/bin"
    cat > "$W/extra.sh" <<SH
SYS_LANG=en
kei_result() { printf 'RESULT %s=%s\n' "\$1" "\$2" >> "$W/results"; }
require_database() { return 0; }
is_koha_installed() { return 0; }
systemctl() { echo "systemctl \$*" >> "$W/calls"; }
sleep() { :; }
TOOLS_LOG_DIR="$W/logs"
RUN_LOG="$W/run.log"
CRON_TASKS="$W/koha_tasks"
CRON_REINDEX_BIN="$W/koha-kei-reindex"
SIP_CONF="$W/SIPconfig.xml"
KOHA_EMAIL_FLAG="$W/email.enabled"
KEI_PERL_DIR="$W/perl"
PATH="$W/bin:\$PATH"
SH
}

task() { run env KEI_EXTRA="$W/extra.sh" bash "$PANEL" "$@"; echo "$output"; cat "$KEI_S/dialogs.log" 2>/dev/null || true; }

# --- Scheduled tasks --------------------------------------------------

good_cron() {
    cat > "$1" <<'CRON'
# header
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""

# Database backup (compressed SQL) - Daily at 22:15
15 22 * * * root /bin/bash /root/backup_sql.sh >/dev/null 2>&1

# Full search index rebuild - Weekly, Saturday at 02:00
0 2 * * 6 root /usr/local/bin/koha-kei-reindex library >/dev/null 2>&1

#off# 0 4 * * 0 root /usr/sbin/koha-shell library -c "/usr/share/koha/bin/link_bibs_to_authorities.pl" >/dev/null 2>&1
*/10 * * * * root /usr/local/bin/mine.sh
@reboot root /usr/local/bin/at-boot.sh
CRON
}

@test "cron-apply: the panel's file replaces koha_tasks, the old one is kept" {
    echo "old" > "$W/koha_tasks"
    good_cron "$W/new.txt"
    task cron_apply "$W/new.txt"
    [ "$status" -eq 0 ]
    [ ! -e "$W/new.txt" ]
    grep -q '^15 22 \* \* \* root /bin/bash /root/backup_sql.sh' "$W/koha_tasks"
    [ "$(cat "$W/koha_tasks.bak")" = "old" ]
    [ "$(stat -c %a "$W/koha_tasks")" = "644" ]
    grep -q "systemctl restart cron" "$W/calls"
    grep -q "OK Schedules updated successfully" "$KEI_S/dialogs.log"
    # The index job brought its helper.
    [ -x "$W/koha-kei-reindex" ]
    sh -n "$W/koha-kei-reindex"
    grep -q 'koha-elasticsearch --rebuild' "$W/koha-kei-reindex"
}

@test "cron-apply: a line cron would refuse changes nothing" {
    echo "old" > "$W/koha_tasks"
    for bad in 'rm -rf / everything' '0 23 * * root' '0 23 * * * root'; do
        good_cron "$W/new.txt"
        printf '%s\n' "$bad" >> "$W/new.txt"
        task cron_apply "$W/new.txt"
        [ "$status" -eq 1 ]
        [ "$(cat "$W/koha_tasks")" = "old" ]
        [ ! -e "$W/new.txt" ]
    done
    good_cron "$W/new.txt"
    sed -i '/^PATH=/d' "$W/new.txt"
    task cron_apply "$W/new.txt"
    [ "$status" -eq 1 ]
    grep -q "ERROR .*line cron would refuse" "$KEI_S/dialogs.log"
}

@test "koha-kei-reindex: Zebra or Elasticsearch, whichever Koha uses" {
    task cron_reindex_script
    printf '%s\n' "$output" > "$W/reindex"
    sed -i "s#/usr/sbin/#$W/bin/#g" "$W/reindex"
    for c in koha-elasticsearch koha-rebuild-zebra; do
        printf '#!/bin/sh\necho %s "$@"\n' "$c" > "$W/bin/$c"; chmod +x "$W/bin/$c"
    done
    printf '#!/bin/sh\necho "$ENGINE"\n' > "$W/bin/koha-mysql"; chmod +x "$W/bin/koha-mysql"
    [ "$(ENGINE=Elasticsearch sh "$W/reindex" library)" = "koha-elasticsearch --rebuild -d library" ]
    [ "$(ENGINE=Zebra sh "$W/reindex" library)" = "koha-rebuild-zebra -f -v -b -a library" ]
    run sh "$W/reindex" 'lib;rm'
    [ "$status" -eq 2 ]
}

# --- Messaging hub ----------------------------------------------------

@test "hub-status: e-mail, SMTP servers without passwords, SMS driver, libraries" {
    mysql "$DB" -e "DROP TABLE IF EXISTS systempreferences, smtp_servers, branches;
CREATE TABLE systempreferences (variable varchar(50) PRIMARY KEY, value mediumtext);
CREATE TABLE smtp_servers (id int AUTO_INCREMENT PRIMARY KEY, name varchar(80), host varchar(80), port int,
  timeout int, ssl_mode enum('disabled','ssl','starttls'), user_name varchar(80), password varchar(80),
  debug tinyint, is_default tinyint);
CREATE TABLE branches (branchcode varchar(10) PRIMARY KEY, branchname longtext);
INSERT INTO systempreferences VALUES ('KohaAdminEmailAddress', 'lib@example.org'), ('SMSSendDriver', 'Twilio'),
  ('staffClientBaseURL', 'https://staff.example.org/');
INSERT INTO smtp_servers VALUES (1, 'Gmail', 'smtp.gmail.com', 587, 60, 'starttls', 'lib@gmail.com', 'app-pass-S3CRET', 0, 1);
INSERT INTO branches VALUES ('CPL', 'Centerville'), ('MPL', 'Midway');"
    touch "$W/email.enabled"
    task hub_status
    [ "$status" -eq 0 ]
    grep -qx "RESULT staff_url=https://staff.example.org" "$W/results"
    grep -qx "RESULT email=on" "$W/results"
    grep -qx "RESULT admin_email=lib@example.org" "$W/results"
    grep -qx "RESULT sms_driver=Twilio" "$W/results"
    grep -qx "RESULT messaging=no" "$W/results"
    grep -qx "$(printf 'RESULT smtp=Gmail\tsmtp.gmail.com\t587\tstarttls\tlib@gmail.com\t1')" "$W/results"
    grep -qx "$(printf 'RESULT branch=CPL\tCenterville')" "$W/results"
    grep -q "RESULT sip=" "$W/results" && grep -q "RESULT z3950=" "$W/results"
    ! grep -q "S3CRET" "$W/results"
}

# --- SIP2 -------------------------------------------------------------

sip_xml() {
    cat > "$1" <<'XML'
<acsconfig xmlns="http://openncip.org/acs-config/1.0/">
  <listeners>
    <service port="0.0.0.0:6002/tcp" transport="RAW" protocol="SIP/2.00" />
  </listeners>
  <accounts>
    <login id="selfcheck" password="S3cret-pass" institution="CPL" />
  </accounts>
  <institutions>
    <institution id="CPL" implementation="ILS" parms=""><policy checkout="true" /></institution>
  </institutions>
</acsconfig>
XML
}

@test "sip-apply: SIPconfig.xml replaced, the old one kept, SIP restarted" {
    echo '<acsconfig xmlns="http://openncip.org/acs-config/1.0/"></acsconfig>' > "$W/SIPconfig.xml"
    chmod 640 "$W/SIPconfig.xml"
    sip_xml "$W/new.xml"
    printf 'pgrep() { return 0; }\n' >> "$W/extra.sh"
    task sip_apply "$W/new.xml" 6002 no
    [ "$status" -eq 0 ]
    [ ! -e "$W/new.xml" ]
    grep -q 'id="selfcheck"' "$W/SIPconfig.xml"
    [ "$(stat -c %a "$W/SIPconfig.xml")" = "640" ]
    backup=$(ls "$W"/SIPconfig.xml.kei-*)
    [ "$(stat -c %a "$backup")" = "600" ]
    grep -q "RESULT sip=yes" "$W/results"
    grep -q "OK .*SIP2 is set up.*port 6002" "$KEI_S/dialogs.log"
    ! grep -rq "S3cret-pass" "$W/run.log" "$KEI_S/dialogs.log" 2>/dev/null
}

@test "sip-apply: broken XML or a bad port changes nothing" {
    echo '<acsconfig/>' > "$W/SIPconfig.xml"
    printf '<acsconfig><accounts>\n' > "$W/bad.xml"
    task sip_apply "$W/bad.xml" 6001 no
    [ "$status" -eq 1 ]
    sip_xml "$W/new.xml"
    task sip_apply "$W/new.xml" 80 no
    [ "$status" -eq 1 ]
    [ "$(cat "$W/SIPconfig.xml")" = "<acsconfig/>" ]
    [ ! -e "$W/bad.xml" ] && [ ! -e "$W/new.xml" ]
    grep -q "ERROR .*SIP2 settings from the panel" "$KEI_S/dialogs.log"
}

@test "sip-apply: SIP2 not starting is said" {
    echo '<acsconfig/>' > "$W/SIPconfig.xml"
    sip_xml "$W/new.xml"
    printf 'pgrep() { return 1; }\n' >> "$W/extra.sh"
    task sip_apply "$W/new.xml" 6001 no
    [ "$status" -eq 1 ]
    grep -q "ERROR .*did not start" "$KEI_S/dialogs.log"
}

# --- Cloud: OneDrive, MEGA, S3 ----------------------------------------

fake_rclone() {
    cat > "$W/bin/rclone" <<SH
#!/bin/bash
printf '%s\n' "\$*" >> "$W/rclone.log"
[ "\${RCLONE_FAIL:-}" = "\$3" ] && { echo "Failed to create: bad secret_access_key=XYZ"; exit 1; }
exit 0
SH
    chmod +x "$W/bin/rclone"
    cat >> "$W/extra.sh" <<SH
rclone_prepare() { return 0; }
validate_and_register_rclone() { echo "VALIDATE \$1" >> "$W/results"; }
SH
}

@test "cloud-provider: MEGA, the password scrambled by rclone, the file deleted" {
    fake_rclone
    printf 'name\tmega\ntype\tmega\nuser\tlib@example.org\npass\tMy pass\n' > "$W/c.tsv"
    task cloud_provider_add "$W/c.tsv"
    [ "$status" -eq 0 ]
    [ ! -e "$W/c.tsv" ]
    grep -qx "config create mega mega user lib@example.org pass My pass --obscure --non-interactive" "$W/rclone.log"
    grep -qx "VALIDATE mega" "$W/results"
}

@test "cloud-provider: S3 goes through an alias to the bucket" {
    fake_rclone
    printf 'name\tbackups\ntype\ts3\nprovider\tWasabi\naccess_key_id\tAK\nsecret_access_key\tSK\nendpoint\thttps://s3.wasabisys.com\nbucket\tmy-library\n' > "$W/c.tsv"
    task cloud_provider_add "$W/c.tsv"
    [ "$status" -eq 0 ]
    grep -qx "config create backups-s3 s3 provider Wasabi access_key_id AK secret_access_key SK endpoint https://s3.wasabisys.com --obscure --non-interactive" "$W/rclone.log"
    grep -qx "config create backups alias remote backups-s3:my-library --non-interactive" "$W/rclone.log"
    grep -qx "VALIDATE backups" "$W/results"
}

@test "cloud-provider: the Google Drive name, a bad type or bucket are refused" {
    fake_rclone
    for body in 'name\tgdrive\ntype\tmega\n' 'name\tx\ntype\tdrive\n' 'name\tx\ntype\ts3\nbucket\tBad_Bucket\n' 'name\t-x\ntype\tmega\n'; do
        printf "$body" > "$W/c.tsv"
        task cloud_provider_add "$W/c.tsv"
        [ "$status" -eq 1 ]
        [ ! -e "$W/c.tsv" ]
    done
    [ ! -e "$W/rclone.log" ]
}

@test "cloud-provider: an rclone error is said, its secrets stay out of the log" {
    fake_rclone
    printf 'name\tod\ntype\tonedrive\ntoken\t{"access_token":"TOKEN-S3CRET"}\n' > "$W/c.tsv"
    printf 'RCLONE_FAIL=od\nexport RCLONE_FAIL\n' >> "$W/extra.sh"
    task cloud_provider_add "$W/c.tsv"
    [ "$status" -eq 1 ]
    grep -q "ERROR .*rclone could not create the connection" "$KEI_S/dialogs.log"
    ! grep -rq "S3CRET\|XYZ" "$W/run.log" "$KEI_S/dialogs.log" 2>/dev/null
}

@test "admin hub: the panel knows the tasks" {
    for task in cron-apply hub-status sip-apply cloud-provider; do
        grep -q "^        ${task}) " "$KEI_REPO/installer"
    done
}
