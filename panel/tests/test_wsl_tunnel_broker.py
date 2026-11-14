"""Free address and tunnel on WSL (Paulo's WSL report, 2026-11-13).

1. The public list "Yes" right after the address was made ended in "the
   free address service is not online yet" although the service had just
   answered: a name lookup of WSL failing for a moment (curl 6). Calls that
   never reached the service are tried again, the error no longer blames
   the service once it answered, and a "Yes" it could not take is kept and
   sent again by the daily heartbeat.
2. On WSL cloudflared talks HTTP/2 (TCP): QUIC over WSL kept dropping.
3. The screen behind a panel dialog is almost hidden (90%).

The installer functions run on their own (cut out of the installer), with a
stand-in curl, so no broker, root or network is needed.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / "installer"


def _function(name: str) -> str:
    text = INSTALLER.read_text(encoding="utf-8")
    # One line ("f() { ...; }") or a block ending with "}" at the start of a line.
    m = re.search(rf"^{re.escape(name)}\(\) \{{.*\}}$", text, re.M) \
        or re.search(rf"^{re.escape(name)}\(\) \{{[^\n]*\n.*?^\}}\n", text, re.M | re.S)
    assert m, name
    return m.group(0)


FUNCS = ["kv_get", "kv_write", "tunnel_conf_get", "broker_url", "broker_host", "broker_request",
         "broker_cleanup", "broker_offline_text", "broker_error", "broker_set_listing",
         "tunnel_mode_is", "broker_heartbeat", "cloudflared_protocol_dropin", "is_wsl"]


def _run(tmp: Path, body: str, curl: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Runs BODY with the functions above; CURL is the stand-in curl's
    script (it may read $tmp/count, the number of the call)."""
    bin_dir = tmp / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "curl").write_text("#!/bin/bash\nn=$(( $(cat \"$T/count\" 2>/dev/null || echo 0) + 1 ))\n"
                                  "echo $n > \"$T/count\"\n" + curl, encoding="utf-8")
    (bin_dir / "curl").chmod(0o755)
    (bin_dir / "systemctl").write_text("#!/bin/bash\necho \"systemctl $*\" >> \"$T/calls\"\n", encoding="utf-8")
    (bin_dir / "systemctl").chmod(0o755)
    funcs = "\n".join(_function(f) for f in FUNCS)
    script = f"""
set -u
T={tmp}
TUNNEL_CONF=$T/tunnel.conf
KEI_BROKER_URL=https://broker.example.test
KEI_BROKER_RETRY_DELAY=0
KEI_PLATFORM=${{KEI_PLATFORM:-linux}}
CLOUDFLARED_DROPIN=$T/dropin/protocol.conf
PANEL_VERSION=" 9.9.9"
BROKER_BODY=""
t() {{ printf '%s' "$1"; }}
log() {{ echo "LOG $*" >> "$T/log"; }}
msg_error() {{ printf 'ERROR %s\\n' "$2" >> "$T/dialogs"; }}
msg_info() {{ printf 'INFO %s\\n' "$2" >> "$T/dialogs"; }}
json_field() {{ sed -n 's/.*"'"$2"'":"\\([^"]*\\)".*/\\1/p' "$1"; }}
json_str() {{ printf '"%s"' "$1"; }}
broker_sign_headers() {{ printf 'X-KEI-Library: L\\nX-KEI-Timestamp: 1\\nX-KEI-Nonce: %s\\nX-KEI-Signature: S\\n' "$RANDOM"; }}
dpkg-query() {{ echo 26.05; }}
mktemp() {{ command mktemp "$T/tmp.XXXXXX"; }}
{funcs}
{body}
"""
    full_env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "T": str(tmp), **(env or {})}
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=full_env, timeout=60)


# The stand-in curl writes its answer to the -o file and the code on stdout.
ANSWER = 'o=""; prev=""; for a in "$@"; do [ "$prev" = "-o" ] && o="$a"; prev="$a"; done\n'


def test_name_lookup_failure_is_tried_again(tmp_path):
    curl = ANSWER + '[ "$n" -lt 3 ] && exit 6\necho \'{"ok":true}\' > "$o"; printf 200\n'
    r = _run(tmp_path, 'broker_request PUT /v1/listing yes \'{"public":true}\' && echo OK $BROKER_STATUS', curl)
    assert "OK 200" in r.stdout, r.stderr
    assert (tmp_path / "count").read_text().strip() == "3"


def test_a_post_cut_halfway_is_not_sent_twice(tmp_path):
    # curl 28: the request may have reached the service; a POST is not repeated.
    r = _run(tmp_path, 'broker_request POST /v1/device/start no "{}" || echo FAIL $BROKER_CURL_RC', "exit 28\n")
    assert "FAIL 28" in r.stdout
    assert (tmp_path / "count").read_text().strip() == "1"


def test_lookup_failure_after_an_answer_does_not_say_service_offline(tmp_path):
    curl = ANSWER + 'if [ "$n" = 1 ]; then echo \'{}\' > "$o"; printf 200; exit 0; fi\nexit 6\n'
    r = _run(tmp_path, 'broker_request GET /v1/capabilities no; broker_request GET /v1/x no; broker_error', curl)
    assert "for a moment" in r.stdout
    assert "not online yet" not in r.stdout
    # Never seen: the service is not online (its name does not exist).
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    r = _run(fresh, 'broker_request GET /v1/x no; broker_error', "exit 6\n")
    assert "not online yet" in r.stdout


def test_public_list_yes_is_kept_and_sent_by_the_heartbeat(tmp_path):
    (tmp_path / "tunnel.conf").write_text("TUNNEL_MODE=broker\nBROKER_URL=https://broker.example.test\n")
    r = _run(tmp_path, "broker_set_listing true keep; echo rc=$?", "exit 6\n")
    assert "rc=1" in r.stdout
    conf = (tmp_path / "tunnel.conf").read_text()
    assert "PUBLIC_LISTING=pending" in conf
    dialogs = (tmp_path / "dialogs").read_text()
    assert dialogs.startswith("INFO ") and "answer is saved" in dialogs
    # The daily heartbeat sends it once the service answers.
    (tmp_path / "count").unlink()
    curl = ANSWER + 'echo \'{"ok":true}\' > "$o"; printf 200\n'
    r = _run(tmp_path, "broker_heartbeat; echo rc=$?", curl)
    assert "rc=0" in r.stdout, r.stderr
    assert "PUBLIC_LISTING=yes" in (tmp_path / "tunnel.conf").read_text()


def test_menu_no_is_not_kept(tmp_path):
    # Only the "Yes" after the address was made is kept; the menu shows the error.
    (tmp_path / "tunnel.conf").write_text("TUNNEL_MODE=broker\nPUBLIC_LISTING=yes\n")
    _run(tmp_path, "broker_set_listing false", "exit 6\n")
    assert "PUBLIC_LISTING=yes" in (tmp_path / "tunnel.conf").read_text()
    assert (tmp_path / "dialogs").read_text().startswith("ERROR ")


def test_tunnel_uses_http2_on_wsl_only(tmp_path):
    dropin = tmp_path / "dropin" / "protocol.conf"
    _run(tmp_path, "cloudflared_protocol_dropin", "", env={"KEI_PLATFORM": "wsl2"})
    assert "Environment=TUNNEL_TRANSPORT_PROTOCOL=http2" in dropin.read_text()
    _run(tmp_path, "cloudflared_protocol_dropin", "", env={"KEI_PLATFORM": "linux"})
    assert not dropin.exists()
    _run(tmp_path, "cloudflared_protocol_dropin", "", env={"KEI_PLATFORM": "linux", "KEI_TUNNEL_PROTOCOL": "http2"})
    assert dropin.exists()


def test_tunnel_restarts_apply_the_protocol():
    text = INSTALLER.read_text(encoding="utf-8")
    for anchor in ('display_explanation "Restarting Cloudflare Tunnel..."',
                   'display_explanation "Resuming the tunnel..."'):
        for m in re.finditer(re.escape(anchor), text):
            assert "cloudflared_protocol_dropin" in text[m.end():m.end() + 80], anchor
    for fn in ("broker_connect", "cloudflare_service_install"):
        assert "cloudflared_protocol_dropin" in _function(fn), fn


def test_dialog_backdrop_hides_the_screen_behind():
    css = (REPO / "panel" / "kei_panel" / "panel.tcss").read_text(encoding="utf-8")
    assert re.search(r"^ModalScreen \{\s*background: \$background 90%;", css, re.M)
    assert "$background 70%" not in css
