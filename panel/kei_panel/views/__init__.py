"""The right-hand side of the main screen: one view per sidebar entry."""

from .ai import AIView
from .backup import BackupView
from .base import SectionView
from .crons import CronView
from .dashboard import DashboardView
from .database import DatabaseView
from .hub import HubView
from .opac import OpacView
from .vpn import VpnView
from .z3950 import Z3950View

VIEWS = {
    "section": SectionView,
    "dashboard": DashboardView,
    "backup": BackupView,
    "database": DatabaseView,
    "ai": AIView,
    "z3950": Z3950View,
    "opac": OpacView,
    "hub": HubView,
    "crons": CronView,
    "vpn": VpnView,
}

__all__ = ["VIEWS", "SectionView", "DashboardView", "BackupView", "DatabaseView", "AIView", "Z3950View", "OpacView",
           "HubView", "CronView", "VpnView"]
