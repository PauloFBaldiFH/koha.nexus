"""Which hosts and addresses on-demand enrichment may never contact.

Only direct, public Z39.50 servers are allowed. Refused, before any
lookup: names under koha.nexus (the gateway's Cloudflare tunnel,
sru.koha.nexus, and catalog.koha.nexus), localhost, an IP literal that is
not public, the koha.nexus VPS, a database named sru/..., and the ports
of the koha.nexus services and of HTTPS. Refused after the lookup: any
address that is not public, the VPS, and Cloudflare's published ranges
(where the tunnel answers). A name with any refused address is refused
as a whole, and the connection goes to the checked address, so the name
cannot point elsewhere between the check and the connect.

ALLOWED networks bypass the address check (tests use 127.0.0.1); the
name rules always apply.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass, field

from nexus_gateway.z3950 import Z3950Error

DENIED_SUFFIXES = ("koha.nexus",)
DENIED_NAMES = ("localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback")
VPS_ADDRESSES = ("137.131.205.31",)
# 443: HTTPS (the tunnel); 5000: the local gateway; 5006: the Pergamum
# bridge; 8088: the shared catalogue.
DENIED_PORTS = frozenset({443, 5000, 5006, 8088})
# Cloudflare's published ranges (https://www.cloudflare.com/ips/), checked
# 2026-10: sru.koha.nexus and catalog.koha.nexus answer from these.
CLOUDFLARE = (
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22", "141.101.64.0/18",
    "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20", "197.234.240.0/22", "198.41.128.0/17",
    "162.158.0.0/15", "104.16.0.0/13", "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
    "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32", "2405:8100::/32",
    "2a06:98c0::/29", "2c0f:f248::/32",
)
_CLOUDFLARE = tuple(ipaddress.ip_network(n) for n in CLOUDFLARE)
_VPS = tuple(ipaddress.ip_address(a) for a in VPS_ADDRESSES)


class PolicyError(Z3950Error):
    """The host or its address may not be contacted (kind "policy")."""

    def __init__(self, message: str, phase: str = "connect"):
        super().__init__(message, phase=phase, kind="policy")


def _literal(host: str):
    try:
        return ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return None


def address_refusal(ip, allowed=()) -> str:
    """Why this address may not be contacted, or "" when it may."""
    ip = ipaddress.ip_address(ip) if isinstance(ip, str) else ip
    if any(ip in net for net in allowed):
        return ""
    if ip in _VPS:
        return f"{ip} is the koha.nexus server"
    if any(ip in net for net in _CLOUDFLARE):
        return f"{ip} is a Cloudflare address (the koha.nexus tunnel answers there)"
    if not ip.is_global:
        return f"{ip} is not a public address"
    return ""


def name_refusal(host: str, port: int, db: str = "", allowed=()) -> str:
    """Why this server may not be contacted, from its name, port and
    database alone (no lookup), or "" when it may."""
    name = host.strip().rstrip(".").lower()
    if not name:
        return "no host"
    if name.startswith(("http://", "https://")):
        return f"{host} is a web address, not a Z39.50 host"
    if any(name == s or name.endswith("." + s) for s in DENIED_SUFFIXES):
        return f"{name} is a koha.nexus endpoint (only the opt-in koha.nexus network may use it)"
    if name in DENIED_NAMES:
        return f"{name} is this machine"
    if port in DENIED_PORTS:
        return f"port {port} belongs to HTTPS or a koha.nexus service"
    if db.strip().lower().startswith(("sru/", "/sru")):
        return f"database {db} is a koha.nexus gateway row"
    ip = _literal(name)
    if ip is not None:
        return address_refusal(ip, allowed)
    return ""


@dataclass
class Policy:
    """The checks above, with ALLOWED networks (tests only) and a resolver
    (loop.getaddrinfo by default)."""
    allowed: tuple = ()
    resolver: object = None
    dns_timeout: float = 3.0
    _allowed: tuple = field(init=False, repr=False)

    def __post_init__(self):
        self._allowed = tuple(ipaddress.ip_network(n) for n in self.allowed)

    def refusal(self, host: str, port: int, db: str = "") -> str:
        return name_refusal(host, port, db, self._allowed)

    async def _lookup(self, host: str, port: int) -> list[str]:
        if self.resolver is not None:
            return list(await self.resolver(host, port))
        infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
        return [info[4][0] for info in infos]

    async def resolve(self, host: str, port: int, db: str = "") -> str:
        """The address to connect to: every address of HOST checked, IPv4
        preferred. Raises PolicyError, or Z3950Error kind dns."""
        reason = self.refusal(host, port, db)
        if reason:
            raise PolicyError(f"{host}:{port} refused by policy: {reason}")
        literal = _literal(host.strip())
        if literal is not None:
            return str(literal)
        try:
            addresses = await asyncio.wait_for(self._lookup(host, port), self.dns_timeout)
        except asyncio.TimeoutError as exc:
            raise Z3950Error(f"{host}: no address in {self.dns_timeout:g}s", phase="connect", kind="dns") from exc
        except (socket.gaierror, OSError, UnicodeError) as exc:
            raise Z3950Error(f"{host}: name not found ({exc})", phase="connect", kind="dns") from exc
        if not addresses:
            raise Z3950Error(f"{host}: name not found", phase="connect", kind="dns")
        for a in addresses:
            reason = address_refusal(ipaddress.ip_address(a.split("%")[0]), self._allowed)
            if reason:
                raise PolicyError(f"{host}:{port} refused by policy: {reason}")
        return next((a for a in addresses if ":" not in a), addresses[0])
