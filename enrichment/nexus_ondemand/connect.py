"""The only way on-demand enrichment opens a connection: the policy's
checked address, then a z3950.Session to that address (the host name
stays in messages and in the Init)."""

from __future__ import annotations

from nexus_gateway.z3950 import Session, Timeouts

from .policy import Policy
from .targets import Address, Target

IMPLEMENTATION = "koha.nexus on-demand"


async def open_session(target: Target, address: Address, policy: Policy, timeouts: Timeouts | None = None,
                       version: str = "1") -> Session:
    """An open Session (connected and Init done) to ADDRESS of TARGET.
    Raises PolicyError or Z3950Error; nothing is contacted when the
    policy refuses the name or any of its addresses."""
    ip = await policy.resolve(address.host, address.port, address.db)
    session = Session(address.host, address.port, user=target.user, password=target.password,
                      timeouts=timeouts or Timeouts(), address=ip, name=IMPLEMENTATION, version=version)
    await session.open()
    return session
