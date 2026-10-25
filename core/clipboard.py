"""Real-Time Windows Clipboard Monitor for Instant URL Sniffing.
Reverse-Engineered from IDM's Automatic Clipboard Catcher.
"""

from __future__ import annotations

import ctypes
import re
import threading
import time
from typing import Callable, Optional

# Supported downloadable patterns
URL_REGEX = re.compile(
    r"^(?:https?|ftp)://[^\s/$.?#].[^\s]*$", re.IGNORECASE
)
MAGNET_REGEX = re.compile(r"^magnet:\?[^\s]+", re.IGNORECASE)


def get_clipboard_text() -> str:
    """Safely retrieve text from Windows clipboard without external dependencies."""
    u32 = ctypes.windll.user32
    k32 = ctypes.windll.kernel32

    if not u32.OpenClipboard(None):
        return ""

    try:
        CF_UNICODETEXT = 13
        h_clip_mem = u32.GetClipboardData(CF_UNICODETEXT)
        if not h_clip_mem:
            return ""

        p_clip_mem = k32.GlobalLock(h_clip_mem)
        if not p_clip_mem:
            return ""

        try:
            text = ctypes.c_wchar_p(p_clip_mem).value or ""
            return text
        finally:
            k32.GlobalUnlock(h_clip_mem)
    finally:
        u32.CloseClipboard()


class ClipboardWatcher:
    """Background thread watching for new URLs in clipboard."""

    def __init__(self, on_url_detected: Callable[[str], None], poll_interval: float = 0.8):
        self.on_url_detected = on_url_detected
        self.poll_interval = poll_interval
        self._last_content = ""
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._stop_event.clear()
        self._last_content = get_clipboard_text().strip()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="SDM_ClipboardWatcher")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                current = get_clipboard_text().strip()
                if current and current != self._last_content:
                    self._last_content = current
                    if URL_REGEX.match(current) or MAGNET_REGEX.match(current):
                        self.on_url_detected(current)
            except Exception:
                pass
            time.sleep(self.poll_interval)
