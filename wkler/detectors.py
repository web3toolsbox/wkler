# -*- coding: utf-8 -*-
"""
macOS 窗口检测模块
"""

import subprocess
import threading
import time
from typing import Optional


BROWSER_PATTERNS = [
    "chrome", "Google Chrome",
    "firefox", "Firefox",
    "msedge", "Microsoft Edge",
    "opera", "Opera",
    "brave", "Brave",
    "chromium", "Arc",
    "safari", "Safari",
]

_BROWSER_PATTERNS_LOWER = [p.lower() for p in BROWSER_PATTERNS]

EXTENSION_PATTERNS = [
    "OKX", "MetaMask", "Wallet", "Phantom", "Rainbow",
    "Coinbase", "Trust Wallet", "Binance", "Exodus",
    "Extension", "Chrome Extension", "Add-on", "Plugin",
    "Chrome Web Store", "Extension Settings",
]

_EXTENSION_PATTERNS_LOWER = [p.lower() for p in EXTENSION_PATTERNS]

_active_window_cache: Optional[str] = None
_cache_lock = threading.Lock()
_cache_time = 0
CACHE_TTL = 0.1

CHECK_INTERVAL = 0.2


def should_trigger_recording(window_name: Optional[str] = None) -> bool:
    """判断当前窗口是否应该触发记录（Unknown 或包含钱包关键词）"""
    if window_name is None:
        window_name = get_active_window_name()

    if window_name is None or window_name == "Unknown":
        return True

    window_name_lower = window_name.lower()
    for pattern in _EXTENSION_PATTERNS_LOWER:
        if pattern in window_name_lower:
            return True

    return False


def is_unknown_window(window_name: Optional[str] = None) -> bool:
    """判断当前窗口是否为未知窗口"""
    if window_name is None:
        window_name = get_active_window_name()
    return window_name is None or window_name == "Unknown"


def get_active_window_macos() -> Optional[str]:
    """获取 macOS 活动窗口标题"""
    try:
        from AppKit import NSWorkspace
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowListOptionOnScreenOnly,
        )

        active_app = NSWorkspace.sharedWorkspace().activeApplication()
        if not active_app:
            return None

        app_name = active_app.get("NSApplicationName", "")
        pid = active_app.get("NSApplicationProcessIdentifier", 0)

        is_browser = any(p in app_name.lower() for p in _BROWSER_PATTERNS_LOWER)

        windows = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly, kCGNullWindowID
        )
        if windows:
            for win in windows:
                if win.get("kCGWindowOwnerPID") != pid:
                    continue
                if win.get("kCGWindowLayer", 0) != 0:
                    continue
                title = win.get("kCGWindowName", "")
                if title:
                    return title
                # 前台窗口无标题：浏览器中通常是扩展弹窗
                if is_browser:
                    return None
                return app_name or None

        return app_name or None
    except ImportError:
        return _get_active_window_applescript()
    except Exception:
        return _get_active_window_applescript()


def _get_active_window_applescript() -> Optional[str]:
    """AppleScript 回退方案获取活动窗口标题"""
    try:
        script = '''
        tell application "System Events"
            set frontApp to first application process whose frontmost is true
            set appName to name of frontApp
            try
                set winTitle to name of front window of frontApp
                return winTitle
            on error
                return appName
            end try
        end tell
        '''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except Exception:
        return None


def get_active_window_name() -> Optional[str]:
    """获取当前活动窗口名称（带缓存）"""
    global _active_window_cache, _cache_time

    now = time.time()
    if now - _cache_time < CACHE_TTL and _active_window_cache is not None:
        return _active_window_cache

    window_name = get_active_window_macos()

    with _cache_lock:
        _active_window_cache = window_name
        _cache_time = now

    return window_name


def is_browser_active() -> bool:
    """判断当前活动窗口是否为浏览器"""
    window_name = get_active_window_name()
    if not window_name:
        return False

    window_name_lower = window_name.lower()

    for pattern in _BROWSER_PATTERNS_LOWER:
        if pattern in window_name_lower:
            return True

    for pattern in _EXTENSION_PATTERNS_LOWER:
        if pattern in window_name_lower:
            return True

    return False
