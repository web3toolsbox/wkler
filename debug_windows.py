#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""详细调试 Windows 窗口获取"""

import ctypes
import ctypes.wintypes
import time

def debug_window_info():
    """调试窗口信息获取"""

    # Windows API
    user32 = ctypes.windll.user32

    print("=" * 60)
    print("Windows 窗口调试工具")
    print("=" * 60)
    print("按 Ctrl+C 退出\n")

    try:
        while True:
            hwnd = user32.GetForegroundWindow()

            if hwnd:
                # 获取标题
                title_len = user32.GetWindowTextLengthW(hwnd)
                title = ""
                if title_len > 0:
                    buffer = ctypes.create_unicode_buffer(title_len + 1)
                    user32.GetWindowTextW(hwnd, buffer, title_len + 1)
                    title = buffer.value

                # 获取类名
                class_buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, class_buf, 256)
                class_name = class_buf.value

                # 获取进程 ID
                pid = ctypes.wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

                print(f"\r[HWND:{hwnd}] 类:{class_name} 标题:'{title}' PID:{pid.value} ", end="", flush=True)

            time.sleep(0.2)

    except KeyboardInterrupt:
        print("\n\n退出")

if __name__ == "__main__":
    debug_window_info()
