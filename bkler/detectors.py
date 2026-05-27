# -*- coding: utf-8 -*-
"""
Windows 窗口检测模块
"""

import threading
import time
from typing import Optional


# 浏览器识别模式（进程名或窗口标题）
BROWSER_PATTERNS = [
    "chrome", "Google Chrome",
    "firefox", "Firefox",
    "msedge", "Microsoft Edge",
    "opera", "Opera",
    "brave", "Brave",
    "chromium"
]

# 浏览器扩展识别模式（扩展窗口通常不包含浏览器名，但有这些关键词）
EXTENSION_PATTERNS = [
    # 钱包扩展
    "OKX", "MetaMask", "Wallet", "Phantom", "Rainbow",
    "Coinbase", "Trust Wallet", "Binance", "Exodus",
    # 其他常见扩展
    "Extension", "Chrome Extension", "Add-on", "Plugin",
    # 浏览器相关关键词
    "Chrome Web Store", "Extension Settings"
]

# 活动窗口缓存
_active_window_cache: Optional[str] = None
_cache_lock = threading.Lock()
_cache_time = 0
CACHE_TTL = 0.1  # 缓存100ms

# 钱包扩展关键词列表（可扩展）
WALLET_PATTERNS = [
    "OKX Wallet",
    "MetaMask",
    "Rabby Wallet",
    "Phantom",
    # 可在此添加更多钱包关键词
    # "Rainbow", "Coinbase Wallet", "Trust Wallet", etc.
]


def is_wallet_window(window_name: Optional[str] = None) -> bool:
    """判断当前窗口是否为钱包扩展窗口"""
    if window_name is None:
        window_name = get_active_window_name()
    if not window_name:
        return False

    window_name_lower = window_name.lower()
    for pattern in WALLET_PATTERNS:
        if pattern.lower() in window_name_lower:
            return True
    return False


def get_active_window_windows() -> Optional[str]:
    """获取Windows活动窗口标题"""
    try:
        import ctypes
        from ctypes import wintypes

        # Windows API 定义
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.argtypes = []
        user32.GetForegroundWindow.restype = wintypes.HWND

        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.restype = wintypes.INT

        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, wintypes.INT]
        user32.GetWindowTextW.restype = wintypes.INT

        user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetClassNameW.restype = ctypes.c_int

        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None

        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            return buffer.value

        # 标题为空时，尝试获取窗口类名
        class_buf = ctypes.create_unicode_buffer(256)
        if user32.GetClassNameW(hwnd, class_buf, 256) > 0:
            class_name = class_buf.value
            # 过滤通用类名
            if class_name and class_name not in ("Chrome_WidgetWin_1", "MozillaWindowClass", "WindowClass"):
                return class_name

        # 尝试获取进程名
        try:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value:
                import psutil
                process = psutil.Process(pid.value)
                return process.name()
        except ImportError:
            pass
        except Exception:
            pass

        return None
    except Exception:
        return None


def get_active_window_name() -> Optional[str]:
    """获取当前活动窗口名称（带缓存）"""
    global _active_window_cache, _cache_time

    now = time.time()
    if now - _cache_time < CACHE_TTL and _active_window_cache is not None:
        return _active_window_cache

    window_name = get_active_window_windows()

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

    # 检查浏览器模式
    for pattern in BROWSER_PATTERNS:
        if pattern.lower() in window_name_lower:
            return True

    # 检查浏览器扩展模式
    for pattern in EXTENSION_PATTERNS:
        if pattern.lower() in window_name_lower:
            return True

    return False
