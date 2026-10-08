"""WireGuard VPN for the staff interface and SSH, seen from the panel.

`config.sh --task vpn-setup | vpn-peer-add | vpn-peer-revoke | vpn-stop`
(installer section 42) does the work; this module checks the answers,
reads a device's profile (/etc/wireguard/kei-peers/NAME.conf, private to
root) and draws its QR code with `qrencode -t ansiutf8`.

A profile is split tunnel only: AllowedIPs 10.66.0.0/24, never 0.0.0.0/0,
and no DNS line, so the device's internet (and the covers Koha's pages load
from Amazon or Syndetics) stays on its own network. profile_problem() checks
that before a profile is shown or copied.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

NET = "10.66.0"
SERVER = NET + ".1"
ALLOWED = NET + ".0/24"
MTU = 1360
KEEPALIVE = 25
DEFAULT_PORT = 51820

DEMO_PROFILE = f"""# koha.nexus VPN: demo. Only {ALLOWED} goes through the VPN; the device's
# internet and DNS stay with its own network.
[Interface]
PrivateKey = cHJpdmF0ZS1rZXktb2YtdGhlLWRlbW8tZGV2aWNlLTAwMDA=
Address = {NET}.2/32
MTU = {MTU}

[Peer]
PublicKey = c2VydmVyLXB1YmxpYy1rZXktb2YtdGhlLWRlbW8tMDAwMDA=
PresharedKey = cHJlc2hhcmVkLWtleS1vZi10aGUtZGVtby1kZXZpY2UwMDA=
Endpoint = vpn.example.org:{DEFAULT_PORT}
AllowedIPs = {ALLOWED}
PersistentKeepalive = {KEEPALIVE}
"""


def peers_dir() -> Path:
    return Path(os.environ.get("KEI_WG_PEERS") or "/etc/wireguard/kei-peers")


def name_problem(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", name or ""):
        return "A device name has letters, digits, _ and - only (up to 32)."
    return ""


def endpoint_problem(endpoint: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", endpoint or ""):
        return "Type the address devices reach this server at: a public IP or a name."
    return ""


def port_problem(port: str) -> str:
    if not str(port).isdigit() or not 1024 <= int(port) <= 65535:
        return "The UDP port must be between 1024 and 65535."
    return ""


def profile_problem(text: str) -> str:
    """"" for a split-tunnel profile as the installer writes it."""
    fields: dict[str, list[str]] = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#"):
            fields.setdefault(key.strip().lower(), []).append(value.strip())
    if fields.get("allowedips") != [ALLOWED]:
        return "The profile must route 10.66.0.0/24 only."
    if "dns" in fields:
        return "The profile must not change the device's DNS."
    if fields.get("mtu") != [str(MTU)] or fields.get("persistentkeepalive") != [str(KEEPALIVE)]:
        return "The profile must have MTU 1360 and PersistentKeepalive 25."
    if not fields.get("privatekey") or not fields.get("endpoint"):
        return "The profile is incomplete."
    return ""


def read_profile(name: str) -> str:
    return (peers_dir() / f"{name}.conf").read_text(encoding="utf-8")


def qr(text: str, qrencode: str = "qrencode") -> str:
    """The QR code of the profile, in terminal blocks ("" without qrencode).
    Comment lines are left out: a smaller code fits more terminals."""
    if not shutil.which(qrencode):
        return ""
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#")).strip() + "\n"
    run = subprocess.run([qrencode, "-t", "ansiutf8", "-m", "2"], input=body.encode("utf-8"),
                         capture_output=True, timeout=10, check=False)
    return run.stdout.decode("utf-8", "replace") if run.returncode == 0 else ""


def parse_peer(row: str) -> dict[str, object]:
    """One `peer=` row of vpn-status: name, address, handshake, rx, tx."""
    parts = (row.split("\t") + ["", "", "0", "0", "0"])[:5]
    nums = [int(p) if p.isdigit() else 0 for p in parts[2:]]
    return {"name": parts[0], "address": parts[1], "handshake": nums[0], "rx": nums[1], "tx": nums[2]}


def size(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{n} B"


def ago(epoch: int, now: float | None = None) -> tuple[str, int]:
    """("never", 0) or (unit key, amount) for the last handshake."""
    if not epoch:
        return "never", 0
    secs = max(0, int((now or time.time()) - epoch))
    if secs < 120:
        return "seconds", secs
    if secs < 7200:
        return "minutes", secs // 60
    if secs < 172800:
        return "hours", secs // 3600
    return "days", secs // 86400
