"""The right-hand side of the main screen: one view per sidebar entry."""

from .addresses import AddressesView
from .ai import AIView
from .backups import BackupCenterView
from .base import SectionView, UnavailableView
from .crons import CronView
from .dashboard import DashboardView
from .enrich import AuthEnrichView, EnrichView
from .database import DatabaseView
from .hub import HubView
from .languages import LanguagesView
from .ondemand import OnDemandView
from .opac import OpacView
from .schedules import SchedulesView
from .platform import PlatformHomeView, PlatformSectionView
from .vpn import VpnView
from .z3950 import Z3950View

VIEWS = {
    "section": SectionView,
    "addresses": AddressesView,
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
    "languages": LanguagesView,
    "crons": CronView,
    "schedules": SchedulesView,
    "vpn": VpnView,
    "platform-home": PlatformHomeView,
    "platform-section": PlatformSectionView,
}

__all__ = ["VIEWS", "AddressesView", "SectionView", "DashboardView", "BackupCenterView", "DatabaseView", "AIView", "Z3950View", "EnrichView", "OnDemandView", "OpacView",
           "HubView", "LanguagesView", "CronView", "SchedulesView", "VpnView", "PlatformHomeView", "PlatformSectionView", "UnavailableView"]
