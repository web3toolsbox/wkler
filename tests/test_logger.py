from datetime import datetime

from wkler import logger


def test_create_log_file_uses_user_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(logger.getpass, "getuser", lambda: "abcdefgh")

    log_file = logger.create_log_file(tmp_path)
    date_str = datetime.now().strftime("%Y%m%d")

    assert log_file.name == f"abcde_recording_{date_str}.log"
    assert log_file.exists()
