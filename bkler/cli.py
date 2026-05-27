# -*- coding: utf-8 -*-
"""
命令行入口模块
"""

import sys

from .logger import KeyLogger, create_log_file


def main():
    """主函数"""
    # 创建日志文件
    log_file = create_log_file()

    # 启动键盘记录器
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
