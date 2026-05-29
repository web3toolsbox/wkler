#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""详细调试 macOS 窗口获取"""

import time

from wkler.detectors import get_active_window_name, should_trigger_recording


def debug_window_info():
    """调试窗口信息获取"""
    print("=" * 60)
    print("macOS 窗口调试工具")
    print("=" * 60)
    print("按 Ctrl+C 退出\n")

    try:
        while True:
            window_name = get_active_window_name() or "Unknown"
            is_match = should_trigger_recording(window_name)
            status = ">>>" if is_match else "   "
            print(
                f"\r{status} 窗口: [{window_name}]"
                + " " * 20,
                end="",
                flush=True,
            )
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n\n退出")


if __name__ == "__main__":
    debug_window_info()
