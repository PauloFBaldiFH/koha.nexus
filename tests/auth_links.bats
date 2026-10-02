#!/usr/bin/env bats
# Authorization links (rclone / Google Drive, Cloudflare Tunnel): the link is
# caught from the tool's output and opened as a QR code, in the browser of
# this computer or copied, with every method kept available.

setup() {
    load lib/common
    kei_reset_env
    BIN="$BATS_TEST_TMPDIR/bin"
    mkdir -p "$BIN"
    printf 'PATH="%s:$PATH"\n' "$BIN" > "$BATS_TEST_TMPDIR/path.sh"
    export KEI_EXTRA="$BATS_TEST_TMPDIR/path.sh"
    export KEI_WIN_OPENER="$BATS_TEST_TMPDIR/rundll32.exe"
    export CF_URL RC_URL TOKEN BIN
    unset DISPLAY WAYLAND_DISPLAY
    rm -f /root/.kei-rclone-auth.* /root/.kei-cloudflared-login.*
}

teardown() {
    pkill -f "$BIN/" 2>/dev/null || true
    rm -f /root/.kei-rclone-auth.* /root/.kei-cloudflared-login.*
    kei_kill_daemons
    kei_start_mariadb
    kei_start_memcached
}

CF_URL='https://dash.cloudflare.com/argotunnel?aud=&callback=https%3A%2F%2Flogin.cloudflareaccess.org%2FabcDEF123'
RC_URL='http://127.0.0.1:53682/auth?state=Xy_z-123'
TOKEN='{"access_token":"ya29.SECRET","token_type":"Bearer","refresh_token":"1//REFRESH","expiry":"2026-09-28T15:00:00Z"}'

fake() {   # fake NAME BODY: a test double first in the panel's PATH
    printf '#!/bin/bash\n%s\n' "$2" > "$BIN/$1"
    chmod 755 "$BIN/$1"
}
fake_cloudflared() {   # prints the link, "authorizes" after $1 seconds
    fake cloudflared "echo \"cloudflared \$*\" >> $KEI_S/calls.log
echo 'Please open the following URL and log in with your Cloudflare account:'
echo
echo '$CF_URL'
echo
echo 'Leave cloudflared running to download the cert automatically.'
trap 'kill \$! 2>/dev/null' TERM
sleep ${1:-1} & wait
echo 'You have successfully logged in.'"
}
fake_rclone() {
    fake rclone "echo \"rclone \$*\" >> $KEI_S/calls.log
echo 'NOTICE: Please go to the following link: $RC_URL' >&2
echo 'NOTICE: Log in and authorize rclone for access' >&2
sleep 1
echo 'Paste the following into your remote machine --->'
echo '$TOKEN'
echo '<---End paste'"
}

@test "A01 the link is read from the tool's output, and only a plain http(s) link" {
    printf 'NOTICE: Please go to the following link: %s\nNOTICE: Waiting for code...\n' "$RC_URL" > "$BATS_TEST_TMPDIR/rc.out"
    panel eval 'extract_auth_url "$BATS_TEST_TMPDIR/rc.out" "$RCLONE_AUTH_URL_RE"'
    assert '[ "$output" = "$RC_URL" ]' "$output"
    printf 'Please open the following URL:\n\n%s\n\nLeave cloudflared running\n' "$CF_URL" > "$BATS_TEST_TMPDIR/cf.out"
    panel eval 'extract_auth_url "$BATS_TEST_TMPDIR/cf.out" "$CLOUDFLARE_AUTH_URL_RE"'
    assert '[ "$output" = "$CF_URL" ]' "$output"

    local bad
    for bad in 'javascript:alert(1)' 'https://x.test/"onmouseover' "https://x.test/'" 'https://x.test/a b' 'https://x.test/`id`' 'file:///etc/shadow' 'https://'; do
        panel is_auth_url "$bad"
        assert '[ "$status" -ne 0 ]' "must be refused: $bad"
    done
    panel is_auth_url "$CF_URL"
    assert '[ "$status" -eq 0 ]'
}

@test "A02 methods offered: QR code when the flow allows it, browser only where one exists, link always" {
    panel auth_methods "$CF_URL" yes
    assert '[ "$output" = "$(printf "qr\nlink")" ]' "Linux server over SSH: $output"
    panel auth_methods "$RC_URL" no
    assert '[ "$output" = "link" ]' "no QR when the answer must come back to this computer: $output"

    fake xdg-open 'echo "xdg-open $*" >> '"$KEI_S"'/calls.log'
    DISPLAY=:0 panel auth_methods "$CF_URL" yes
    assert '[ "$output" = "$(printf "qr\nbrowser\nlink")" ]' "Linux desktop: $output"

    fake rundll32.exe 'echo "rundll32 $*" >> '"$KEI_S"'/calls.log'
    mv "$BIN/rundll32.exe" "$KEI_WIN_OPENER"
    KEI_PLATFORM_OVERRIDE=wsl2 panel auth_methods "$RC_URL" no
    assert '[ "$output" = "$(printf "browser\nlink")" ]' "WSL opens the Windows browser: $output"
}

@test "A03 browser: the Windows browser under WSL gets the link as one argument" {
    printf '#!/bin/bash\nprintf "%%s\\n" "$@" > %s/opener.args\n' "$KEI_S" > "$KEI_WIN_OPENER"
    chmod 755 "$KEI_WIN_OPENER"
    KEI_PLATFORM_OVERRIDE=wsl2 panel eval 'open_in_browser "$CF_URL"; sleep 1'
    assert '[ "$status" -eq 0 ]' "$output"
    assert '[ "$(sed -n 1p $KEI_S/opener.args)" = "url.dll,FileProtocolHandler" ]' "$(cat $KEI_S/opener.args)"
    assert '[ "$(sed -n 2p $KEI_S/opener.args)" = "$CF_URL" ]' "the & of the link must survive: $(cat $KEI_S/opener.args)"

    panel open_in_browser "$CF_URL"
    assert '[ "$status" -ne 0 ]' "no browser on a Linux server"
    KEI_PLATFORM_OVERRIDE=wsl2 panel open_in_browser 'https://x.test/"bad'
    assert '[ "$status" -ne 0 ]' "odd links are never opened"
}

@test "A04 QR code: qrencode gets the link as one argument, sized for a terminal" {
    fake qrencode 'printf "%s\n" "$@" > '"$KEI_S"'/qrencode.args; echo "██ QR ██"'
    panel show_auth_qr "$CF_URL"
    assert '[ "$status" -eq 0 ]' "$output"
    assert 'echo "$output" | grep -q "██ QR ██"'
    assert 'grep -qx -- "-l" $KEI_S/qrencode.args && grep -qx "L" $KEI_S/qrencode.args' "low error correction: $(cat $KEI_S/qrencode.args)"
    assert '[ "$(tail -n1 $KEI_S/qrencode.args)" = "$CF_URL" ]' "$(cat $KEI_S/qrencode.args)"
}

@test "A05 Cloudflare: link offered as QR code, browser or text; returns when cloudflared finishes" {
    fake_cloudflared 2
    fake qrencode 'echo "██ QR ██"'
    inputs link
    panel eval 'cloudflare_login; echo "rc=$?"'
    assert 'echo "$output" | grep -qx "rc=0"' "$output"
    assert 'echo "$output" | grep -qF "$CF_URL"' "the link to copy: $output"
    assert 'echo "$output" | grep -q "\[Q\].*\[L\].*\[C\]"' "keys to switch method while waiting: $output"
    assert 'dialogs | grep -q "MENU \[Authorization\] => link"' "$(dialogs)"
    assert 'calls | grep -q "cloudflared tunnel login"'
    assert '[ -z "$(ls /root/.kei-cloudflared-login.* 2>/dev/null)" ]' "temporary output removed"

    : > "$KEI_S/dialogs.log"
    panel eval 'cloudflare_login; echo "rc=$?"'
    assert 'echo "$output" | grep -q "██ QR ██"' "QR code is the first choice on a server: $output"
}

@test "A06 Google Drive: token captured without being shown, no QR code, SSH tunnel explained" {
    fake_rclone
    panel eval 'rclone_authorize_here; echo "rc=$?"; [ "$RCLONE_TOKEN" = "$TOKEN" ] && echo "token captured"'
    assert 'echo "$output" | grep -qx "rc=0"' "$output"
    assert 'echo "$output" | grep -qx "token captured"' "$output"
    assert '! echo "$output" | grep -q "ya29.SECRET\|1//REFRESH"' "the token must never be printed: $output"
    assert 'echo "$output" | grep -qF "$RC_URL"'
    assert 'echo "$output" | grep -q "ssh -L 53682:127.0.0.1:53682"' "$output"
    assert 'echo "$output" | grep -q "QR code is not offered"'
    assert 'dialogs | grep -q "MENU \[Authorization\] => link"' "$(dialogs)"
    assert 'calls | grep -q "rclone authorize drive --auth-no-open-browser"'
    assert '[ -z "$(ls /root/.kei-rclone-auth.* 2>/dev/null)" ]' "the file with the token is removed"
}

@test "A07 CTRL+C while waiting stops the tool and returns to the panel" {
    fake_cloudflared 60
    panel eval '( sleep 3; kill -INT $$ ) & cloudflare_login; echo "rc=$?"; sleep 1; pgrep -f "$BIN/cloudflared" >/dev/null && echo "still running" || echo "stopped"'
    assert 'echo "$output" | grep -qx "rc=130"' "$output"
    assert 'echo "$output" | grep -qx "stopped"' "$output"
    assert '[ -z "$(ls /root/.kei-cloudflared-login.* 2>/dev/null)" ]'
}

@test "A08 no link from the tool: clear error, nothing left behind" {
    fake rclone 'echo "Failed to start auth webserver: listen tcp 127.0.0.1:53682: bind: address already in use" >&2; exit 1'
    panel eval 'rclone_authorize_here; echo "rc=$?"'
    assert 'echo "$output" | grep -qx "rc=1"' "$output"
    assert 'echo "$output" | grep -q "port 53682"' "$output"
    assert '[ -z "$(ls /root/.kei-rclone-auth.* 2>/dev/null)" ]'
    assert 'grep -q "if rclone_authorize_here; then" "$KEI_REPO/installer" && grep -q "^        cloudflare_login$" "$KEI_REPO/installer"' \
        "both menus use the new flow"
    assert '! grep -q "rclone authorize \"drive\" --auth-no-open-browser 2>&1 | tee" "$KEI_REPO/installer"' "the token is no longer echoed to the terminal"
}
