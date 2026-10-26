"""koha.nexus local gateway: the SRU server Koha's Z39.50/SRU search talks to
on 127.0.0.1:5000. It answers from static.db, then from learned.db (live
answers kept from earlier searches), then live from the targets that speak
a native protocol (Z39.50 or SRU), within a fixed budget. Only the server
gateway (NEXUS_GATEWAY_ZEUS_URL set) also searches Catálogo Zeus pages.
"""

__version__ = "0.2.0"
