"""--status-json outputs for the tests, shaped like kei_status_json prints them."""

import copy
import json

HEALTHY = {
    "schema": 1, "generated_at": 1792057390, "panel_version": "1.5.56", "platform": "wsl",
    "wsl_net": "mirrored", "autostart": "logon", "state": "ok", "koha_installed": True,
    "services": {"apache2": "active", "mariadb": "active", "memcached": "active",
                 "rabbitmq-server": "active", "koha-common": "active", "cron": "active",
                 "elasticsearch": "inactive", "cloudflared": "inactive"},
    "plack": True,
    "http": {"staff": 200, "opac": 200},
    "backup": {"last_file": "koha_library_2026-10-14_23h00.sql.gz", "last_epoch": 1792018800,
               "last_size": 52428800, "last_kind": "nightly", "last_result": "ok", "log_epoch": 1792018860},
    "recovery": {"epoch": 0, "state": "none", "finished": 0, "db": "-", "backup": "-", "index": "-"},
    "access": {"opac_port": 80, "staff_port": 8080, "lan_ip": "192.168.0.10", "lan_reachable": True,
               "tunnel_mode": "", "public_opac": "", "public_staff": "", "public_ip": ""},
    "disk": {"total": 270553174016, "free": 32131735552},
    "memory": {"total": 16874930176, "available": 16367075328},
}


def status_json(**overrides):
    """HEALTHY with top-level keys replaced (a nested dict replaces the whole block)."""
    data = copy.deepcopy(HEALTHY)
    data.update(overrides)
    return json.dumps(data)
