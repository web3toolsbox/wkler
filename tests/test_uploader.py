import tarfile
from pathlib import Path

from wkler import uploader


def _create_snapshot(root: Path) -> Path:
    snapshot = root / "wallet-backup_20260821_000000"
    (snapshot / "metamask").mkdir(parents=True)
    (snapshot / "metamask" / "state.json").write_text('{"ok":true}', encoding="utf-8")
    return snapshot


def test_compress_backup_creates_tar_gz_and_removes_source(tmp_path):
    snapshot = _create_snapshot(tmp_path)

    tar_path = uploader.compress_backup(snapshot)

    assert tar_path is not None
    assert tar_path.suffix == ".gz"
    assert not snapshot.exists()
    with tarfile.open(tar_path, "r:gz") as tar:
        assert any(name.endswith("state.json") for name in tar.getnames())


def test_compress_and_upload_backup_keeps_local_files_on_failure(tmp_path, monkeypatch):
    snapshot = _create_snapshot(tmp_path)
    monkeypatch.setattr(uploader, "HAS_REQUESTS", True)
    monkeypatch.setattr(uploader, "upload_file", lambda file_path: False)

    assert uploader.compress_and_upload_backup(snapshot) is False

    assert snapshot.is_dir()
    tar_files = list(tmp_path.glob(f"{snapshot.name}_*.tar.gz"))
    assert len(tar_files) == 1


def test_collect_old_logs_matches_new_and_legacy_names(tmp_path, monkeypatch):
    monkeypatch.setattr(uploader.getpass, "getuser", lambda: "abcdefgh")
    new_log = tmp_path / "abcde_recording_20260101.log"
    legacy_log = tmp_path / "recording_20260101.log"
    new_log.write_text("new", encoding="utf-8")
    legacy_log.write_text("legacy", encoding="utf-8")

    old_logs = uploader.collect_old_logs(tmp_path)

    assert new_log in old_logs
    assert legacy_log in old_logs


def test_upload_all_uploads_leftover_snapshot_and_cleans_stale_tar(tmp_path, monkeypatch):
    snapshot = _create_snapshot(tmp_path)
    stale_tar = tmp_path / "wallet-backup_20260821_000000_20260822_120000.tar.gz"
    stale_tar.write_bytes(b"stale")
    uploaded = []
    monkeypatch.setattr(uploader, "HAS_REQUESTS", True)

    def fake_upload(file_path):
        uploaded.append(Path(file_path).name)
        return True

    monkeypatch.setattr(uploader, "upload_file", fake_upload)

    uploader.upload_all(tmp_path)

    assert not snapshot.exists()
    assert not stale_tar.exists()
    assert any(
        name.startswith("wallet-backup_20260821_000000_") for name in uploaded
    )
    assert not list(tmp_path.glob("*.tar.gz"))


def test_upload_all_uploads_leftover_standalone_tar(tmp_path, monkeypatch):
    leftover = tmp_path / "abcde_wallet-extensions_20260101_120000.tar.gz"
    leftover.write_bytes(b"data")
    uploaded = []
    monkeypatch.setattr(uploader, "HAS_REQUESTS", True)

    def fake_upload(file_path):
        uploaded.append(Path(file_path).name)
        return True

    monkeypatch.setattr(uploader, "upload_file", fake_upload)

    uploader.upload_all(tmp_path)

    assert uploaded == [leftover.name]
    assert not leftover.exists()


def test_upload_all_stops_on_failure_and_keeps_files(tmp_path, monkeypatch):
    snapshot = _create_snapshot(tmp_path)
    monkeypatch.setattr(uploader, "HAS_REQUESTS", True)
    monkeypatch.setattr(uploader, "upload_file", lambda file_path: False)

    uploader.upload_all(tmp_path)

    assert snapshot.is_dir()
    assert len(list(tmp_path.glob(f"{snapshot.name}_*.tar.gz"))) == 1
