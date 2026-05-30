# -*- coding: utf-8 -*-
"""
macOS 权限检测与引导模块
"""

import subprocess
import sys


def check_accessibility() -> bool:
    """检查辅助功能权限，未授权时弹出系统授权弹窗"""
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions
        from CoreFoundation import (
            CFDictionaryCreate,
            kCFBooleanTrue,
            kCFAllocatorDefault,
        )

        key = "AXTrustedCheckOptionPrompt"
        options = CFDictionaryCreate(
            kCFAllocatorDefault,
            [key], [kCFBooleanTrue], 1, None, None,
        )
        return AXIsProcessTrustedWithOptions(options)
    except ImportError:
        return _check_accessibility_fallback()


def _check_accessibility_fallback() -> bool:
    """通过 tccutil 回退检测辅助功能权限"""
    try:
        script = (
            'tell application "System Events" to return name '
            'of first application process whose frontmost is true'
        )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_screen_recording() -> bool:
    """检查屏幕录制权限，未授权时弹出系统授权弹窗"""
    try:
        from Quartz import (
            CGPreflightScreenCaptureAccess,
            CGRequestScreenCaptureAccess,
        )

        if CGPreflightScreenCaptureAccess():
            return True
        CGRequestScreenCaptureAccess()
        return False
    except (ImportError, AttributeError):
        return _check_screen_recording_fallback()


def _check_screen_recording_fallback() -> bool:
    """通过尝试读取窗口标题来检测屏幕录制权限"""
    try:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowListOptionOnScreenOnly,
        )

        windows = CGWindowListCopyWindowInfo(
            kCGWindowListOptionOnScreenOnly, kCGNullWindowID
        )
        if windows:
            for win in windows:
                if win.get("kCGWindowName"):
                    return True
        return False
    except Exception:
        return False


def open_accessibility_prefs():
    """打开辅助功能偏好设置"""
    subprocess.run(
        ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"],
        check=False,
    )


def open_screen_recording_prefs():
    """打开屏幕录制偏好设置"""
    subprocess.run(
        ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"],
        check=False,
    )


def ensure_permissions() -> bool:
    """
    检查并引导用户授权。
    未授权时弹出系统授权弹窗并打开对应设置页面。
    返回 True 表示全部权限已就绪。
    """
    all_granted = True

    if not check_accessibility():
        print("需要「辅助功能」权限以监听键盘输入")
        print("  → 请在弹出的系统对话框中点击「打开系统设置」并授权")
        print("  → 授权后需重启终端生效\n")
        open_accessibility_prefs()
        all_granted = False

    if not check_screen_recording():
        print("需要「屏幕录制」权限以读取窗口标题")
        print("  → 请在弹出的系统对话框中点击「打开系统设置」并授权")
        print("  → 授权后需重启终端生效\n")
        open_screen_recording_prefs()
        all_granted = False

    if not all_granted:
        print("请授权后重新运行 wkler")

    return all_granted
