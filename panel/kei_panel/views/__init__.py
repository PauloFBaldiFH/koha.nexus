"""The right-hand side of the main screen: one view per sidebar entry."""

from .ai import AIView
from .backup import BackupView
from .base import SectionView
from .dashboard import DashboardView
from .database import DatabaseView

VIEWS = {
    "section": SectionView,
    "dashboard": DashboardView,
    "backup": BackupView,
    "database": DatabaseView,
    "ai": AIView,
}

__all__ = ["VIEWS", "SectionView", "DashboardView", "BackupView", "DatabaseView", "AIView"]
