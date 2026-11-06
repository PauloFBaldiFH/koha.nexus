"""The right-hand side of the main screen: one view per sidebar entry."""

from .ai import AIView
from .backups import BackupCenterView
from .base import SectionView, UnavailableView
from .crons import CronView
from .dashboard import DashboardView
from .enrich import AuthEnrichView, EnrichView
from .database import DatabaseView
from .hub import HubView
from .ondemand import OnDemandView
from .opac import OpacView
from .platform import PlatformHomeView, PlatformSectionView
from .vpn import VpnView
from .z3950 import Z3950View

VIEWS = {
    "section": SectionView,
    "dashboard": DashboardView,
    "backups": BackupCenterView,
    "database": DatabaseView,
    "ai": AIView,
    "z3950": Z3950View,
    "enrich": EnrichView,
    "enrich-auth": AuthEnrichView,
    "ondemand": OnDemandView,
    "opac": OpacView,
    "hub": HubView,
    "crons": CronView,
    "vpn": VpnView,
    "platform-home": PlatformHomeView,
    "platform-section": PlatformSectionView,
}

__all__ = ["VIEWS", "SectionView", "DashboardView", "BackupCenterView", "DatabaseView", "AIView", "Z3950View", "EnrichView", "OnDemandView", "OpacView",
           "HubView", "CronView", "VpnView", "PlatformHomeView", "PlatformSectionView", "UnavailableView"]
