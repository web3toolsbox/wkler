import tarfile
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path

from wkler import backup, uploader


EXTENSION_ID = "nkbihfbeogaeaoehlefnkodbefgpgknn"


def _create_wallet_source(root: Path) -> Path:
    source = (
        root
        / "Chrome"
        / "User Data"
        / "Default"
        / "Local Extension Settings"
        / EXTENSION_ID
    )
    source.mkdir(parents=True)
    (source / "000003.log").write_text("wallet-state", encoding="utf-8")
    return source


def test_wallet_backup_keeps_browser_source_and_runs_every_five_days(tmp_path, monkeypatch):
    source = _create_wallet_source(tmp_path)
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup,
        "BROWSER_USER_DATA_PATHS",
        {"chrome": str(tmp_path / "Chrome" / "User Data")},
    )
    monkeypatch.setattr(backup, "compress_and_upload_backup", lambda snapshot: True)
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert backup.backup_browser_extensions(backup_dir, now=first) == 1
    snapshots = sorted(backup_dir.glob("wallet-backup_*"))
    assert len(snapshots) == 1
    assert source.is_dir()
    assert not (backup_dir / ".purged").exists()
    copied_files = list(snapshots[0].rglob("000003.log"))
    assert len(copied_files) == 1
    assert copied_files[0].read_text(encoding="utf-8") == "wallet-state"

    assert backup.backup_browser_extensions(backup_dir, now=first + timedelta(days=4)) == 0
    assert len(list(backup_dir.glob("wallet-backup_*"))) == 1

    assert backup.backup_browser_extensions(backup_dir, now=first + timedelta(days=5)) == 1
    assert len(list(backup_dir.glob("wallet-backup_*"))) == 2
    assert backup.is_wallet_backup_due(backup_dir, first + timedelta(days=5, seconds=1)) is False


def test_wallet_backup_compresses_and_uploads_snapshot(tmp_path, monkeypatch):
    source = _create_wallet_source(tmp_path)
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup,
        "BROWSER_USER_DATA_PATHS",
        {"chrome": str(tmp_path / "Chrome" / "User Data")},
    )
    monkeypatch.setattr(uploader, "HAS_REQUESTS", True)

    tar_names = []
    uploaded_names = []

    def fake_upload(file_path):
        uploaded_names.append(Path(file_path).name)
        with tarfile.open(file_path, "r:gz") as tar:
            tar_names.extend(tar.getnames())
        return True

    monkeypatch.setattr(uploader, "upload_file", fake_upload)
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert backup.backup_browser_extensions(backup_dir, now=first) == 1

    assert source.is_dir()
    assert len(uploaded_names) == 1
    assert uploaded_names[0].startswith("wallet-backup_20260101_000000_")
    assert uploaded_names[0].endswith(".tar.gz")
    assert any(name.endswith("000003.log") for name in tar_names)
    assert not list(backup_dir.glob("wallet-backup_*"))
    assert not list(backup_dir.glob("*.tar.gz"))
    assert (backup_dir / backup.BACKUP_STATE_FILENAME).exists()


def test_default_wallet_backup_dir_uses_home_dev_wkler(monkeypatch):
    monkeypatch.setattr(backup.getpass, "getuser", lambda: "abcdefgh")

    assert backup.default_wallet_backup_dir() == (
        Path.home() / ".dev" / "wkler" / "abcde_wallet-extensions"
    )


def test_backup_uses_default_directory_without_argument(tmp_path, monkeypatch):
    source = _create_wallet_source(tmp_path)
    default_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup,
        "BROWSER_USER_DATA_PATHS",
        {"chrome": str(tmp_path / "Chrome" / "User Data")},
    )
    monkeypatch.setattr(backup, "default_wallet_backup_dir", lambda: default_dir)
    monkeypatch.setattr(backup, "compress_and_upload_backup", lambda snapshot: True)
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert backup.backup_browser_extensions(now=first) == 1
    assert list(default_dir.glob("wallet-backup_*"))
    assert source.is_dir()


def test_wallet_backup_skips_browser_lock_files(tmp_path, monkeypatch):
    source = _create_wallet_source(tmp_path)
    (source / "LOCK").write_text("locked", encoding="utf-8")
    (source / "LOCK.old").write_text("old lock", encoding="utf-8")
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup,
        "BROWSER_USER_DATA_PATHS",
        {"chrome": str(tmp_path / "Chrome" / "User Data")},
    )
    monkeypatch.setattr(backup, "compress_and_upload_backup", lambda snapshot: True)

    assert backup.backup_browser_extensions(backup_dir) == 1
    snapshot = next(backup_dir.glob("wallet-backup_*"))
    snapshot_files = [path.name for path in snapshot.rglob("*")]
    assert "LOCK" not in snapshot_files
    assert "LOCK.old" not in snapshot_files


def test_wallet_backup_retries_transient_file_lock(tmp_path, monkeypatch):
    _create_wallet_source(tmp_path)
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup,
        "BROWSER_USER_DATA_PATHS",
        {"chrome": str(tmp_path / "Chrome" / "User Data")},
    )
    monkeypatch.setattr(backup, "compress_and_upload_backup", lambda snapshot: True)
    monkeypatch.setattr(backup, "COPY_RETRY_DELAY_SECONDS", 0)

    original_copy2 = backup.shutil.copy2
    attempts = {"count": 0}

    def flaky_copy2(source, target, *args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise PermissionError("file is temporarily locked")
        return original_copy2(source, target, *args, **kwargs)

    monkeypatch.setattr(backup.shutil, "copy2", flaky_copy2)

    assert backup.backup_browser_extensions(backup_dir) == 1
    assert attempts["count"] >= 2


def test_wallet_backup_best_effort_copy_when_file_keeps_changing(tmp_path, monkeypatch):
    source = _create_wallet_source(tmp_path)
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup,
        "BROWSER_USER_DATA_PATHS",
        {"chrome": str(tmp_path / "Chrome" / "User Data")},
    )
    monkeypatch.setattr(backup, "compress_and_upload_backup", lambda snapshot: True)
    monkeypatch.setattr(backup, "COPY_RETRY_DELAY_SECONDS", 0)

    original_copy2 = backup.shutil.copy2

    def unstable_copy2(src, dst, *args, **kwargs):
        # 复制后立刻更新源文件 mtime，让稳定性校验每次都失败，
        # 模拟浏览器仍在持续写入该文件。
        original_copy2(src, dst, *args, **kwargs)
        os.utime(src, None)

    monkeypatch.setattr(backup.shutil, "copy2", unstable_copy2)

    assert backup.backup_browser_extensions(backup_dir) == 1
    snapshot = next(backup_dir.glob("wallet-backup_*"))
    copied_files = list(snapshot.rglob("000003.log"))
    assert len(copied_files) == 1
    assert copied_files[0].read_text(encoding="utf-8") == "wallet-state"


def test_wallet_backup_requires_stable_current_file(tmp_path, monkeypatch):
    source = _create_wallet_source(tmp_path)
    (source / "CURRENT").write_text("MANIFEST-000001\n", encoding="utf-8")
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(
        backup,
        "BROWSER_USER_DATA_PATHS",
        {"chrome": str(tmp_path / "Chrome" / "User Data")},
    )
    monkeypatch.setattr(backup, "compress_and_upload_backup", lambda snapshot: True)
    monkeypatch.setattr(backup, "COPY_RETRY_DELAY_SECONDS", 0)

    original_copy2 = backup.shutil.copy2

    def unstable_copy2(src, dst, *args, **kwargs):
        original_copy2(src, dst, *args, **kwargs)
        os.utime(src, None)

    monkeypatch.setattr(backup.shutil, "copy2", unstable_copy2)

    assert backup.backup_browser_extensions(backup_dir) == 0
    assert not list(backup_dir.glob("wallet-backup_*"))
