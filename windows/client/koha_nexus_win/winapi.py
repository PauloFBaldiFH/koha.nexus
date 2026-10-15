"""The few Win32 calls the client needs, through ctypes (no pywin32).

Every function returns a safe default off Windows, so the modules that
import this one still load in the Linux tests.
"""

from __future__ import annotations

import ctypes
import os
from typing import Optional

ERROR_ALREADY_EXISTS = 183


class NamedMutex:
    """A named mutex held while this process runs, the same names as the
    PowerShell tray and window (Local\\KohaEasyTray, Local\\KohaEasyWindow),
    so the old and the new one never run together."""

    def __init__(self, name: str):
        self.name = name
        self.handle: Optional[int] = None

    def acquire(self) -> bool:
        if os.name != "nt":
            return True
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        k32.CreateMutexW.restype = ctypes.c_void_p
        h = k32.CreateMutexW(None, True, self.name)
        if not h:
            return False
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:  # type: ignore[attr-defined]
            k32.CloseHandle(ctypes.c_void_p(h))
            return False
        self.handle = h
        return True

    def release(self) -> None:
        if self.handle and os.name == "nt":
            k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            k32.ReleaseMutex(ctypes.c_void_p(self.handle))
            k32.CloseHandle(ctypes.c_void_p(self.handle))
        self.handle = None


def ui_culture() -> str:
    """The Windows display language as a culture name (pt-BR), as
    (Get-UICulture).Name gives it to the PowerShell tools; "" off Windows."""
    if os.name != "nt":
        return ""
    try:
        k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        lang = k32.GetUserDefaultUILanguage()
        buf = ctypes.create_unicode_buffer(85)
        if k32.LCIDToLocaleName(lang, buf, 85, 0):
            return buf.value
    except (AttributeError, OSError):
        pass
    return ""


def uptime_ms() -> int:
    """Milliseconds since Windows started (GetTickCount64)."""
    if os.name != "nt":
        return 0
    k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    k32.GetTickCount64.restype = ctypes.c_ulonglong
    return int(k32.GetTickCount64())


MB_YESNO = 0x4
MB_ICONQUESTION = 0x20
MB_SETFOREGROUND = 0x10000
IDYES = 6


def ask(question: str, title: str = "Koha") -> bool:
    """A Yes/No message box; True off Windows (tests)."""
    if os.name != "nt":
        return True
    u32 = ctypes.windll.user32  # type: ignore[attr-defined]
    return u32.MessageBoxW(None, question, title, MB_YESNO | MB_ICONQUESTION | MB_SETFOREGROUND) == IDYES


SYNCHRONIZE = 0x00100000
EVENT_MODIFY_STATE = 0x0002
WAIT_OBJECT_0 = 0


class NamedEvent:
    """An auto-reset named event: a second start of the app sets it, and the
    running app (wait()) shows its window. Off Windows, signal() reports
    that no app is running and wait() returns False."""

    def __init__(self, name: str):
        self.name = name
        self.handle: Optional[int] = None

    def create(self) -> bool:
        if os.name != "nt":
            return False
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        k32.CreateEventW.restype = ctypes.c_void_p
        self.handle = k32.CreateEventW(None, False, False, self.name)
        return bool(self.handle)

    def signal(self) -> bool:
        """Sets the event of the app already running; False when none is."""
        if os.name != "nt":
            return False
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        k32.OpenEventW.restype = ctypes.c_void_p
        h = k32.OpenEventW(EVENT_MODIFY_STATE | SYNCHRONIZE, False, self.name)
        if not h:
            return False
        try:
            return bool(k32.SetEvent(ctypes.c_void_p(h)))
        finally:
            k32.CloseHandle(ctypes.c_void_p(h))

    def wait(self, timeout_ms: int = 1000) -> bool:
        if os.name != "nt" or not self.handle:
            return False
        k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        return k32.WaitForSingleObject(ctypes.c_void_p(self.handle), timeout_ms) == WAIT_OBJECT_0

    def close(self) -> None:
        if self.handle and os.name == "nt":
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self.handle))  # type: ignore[attr-defined]
        self.handle = None
