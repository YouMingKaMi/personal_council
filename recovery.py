#!/usr/bin/env python3
"""Offline verified recovery; never overwrite an existing database."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import zipfile
from cloud_backup import inspect_database, FORMAT, atomic_json

ROOT = Path(__file__).resolve().parent

def restore(bundle, destination, verify_only=False):
    bundle, destination = Path(bundle).expanduser().resolve(), Path(destination).expanduser().resolve()
    if not verify_only and destination.exists() and any(destination.iterdir()):
        raise ValueError('目标数据目录不是空的。为保护现有记录，请使用一个新的空目录。')
    with tempfile.TemporaryDirectory(prefix='council-recovery-') as tmp:
        db = Path(tmp) / 'personal.sqlite3'
        with zipfile.ZipFile(bundle) as z:
            names = z.namelist()
            if len(names) != len(set(names)) or sum(i.file_size for i in z.infolist()) > 1_000_000_000:
                raise ValueError('备份文件重复或超出大小限制')
            manifest = json.loads(z.read('manifest.json'))
            if manifest.get('format') != FORMAT or manifest.get('app') != 'personal-council':
                raise ValueError('无法识别这个备份格式')
            data = z.read('personal.sqlite3')
            if hashlib.sha256(data).hexdigest() != manifest.get('databaseSha256'):
                raise ValueError('备份校验失败，文件可能损坏，请选择另一份')
            db.write_bytes(data)
            states = inspect_database(db)
            actual = {k: {'revision': v['revision']} for k, v in states.items()}
            if actual != manifest.get('spaces'):
                raise ValueError('备份版本清单与数据库不一致')
            for space, value in states.items():
                if json.loads(z.read(space + '.json')) != value['state']:
                    raise ValueError('便携数据与数据库不一致')
        if not verify_only:
            destination.mkdir(parents=True, exist_ok=True)
            # No replacement: an existing database (even created by another process)
            # must make this operation fail. Transfer to the target filesystem first.
            temporary = destination / '.restore-partial'
            try:
                with temporary.open('xb') as f:
                    f.write(db.read_bytes())
                    f.flush()
                    os.fsync(f.fileno())
                os.link(temporary, destination / 'personal.sqlite3')
            finally:
                temporary.unlink(missing_ok=True)
    return manifest

def configure_cloud(data_dir, destination=None):
    cloud_root = Path.home() / 'Library/Mobile Documents/com~apple~CloudDocs'
    target = Path(destination).expanduser().resolve() if destination else cloud_root / '个人决策团备份'
    if not target.parent.is_dir():
        raise ValueError('iCloud Drive 路径不存在，请先在系统设置中登录 iCloud 并启用 iCloud Drive')
    target.mkdir(exist_ok=True)
    atomic_json(Path(data_dir) / 'backup-config.json', {'destination': str(target)})
    return target

def main():
    p = argparse.ArgumentParser(description='校验并恢复个人决策团备份，不覆盖现有数据')
    p.add_argument('backup', nargs='?')
    p.add_argument('--data', default=str(ROOT / 'data'))
    p.add_argument('--verify', action='store_true')
    p.add_argument('--configure-cloud', action='store_true')
    p.add_argument('--cloud-dir')
    a = p.parse_args()
    try:
        if a.configure_cloud:
            target = configure_cloud(a.data, a.cloud_dir)
            print('自动备份目录已配置：', target)
            print('启动程序后自动生成备份；实际上传状态请在 Finder 查看。')
            return
        text = a.backup or input('把 iCloud 中的 council-…zip 备份拖进此窗口，再按回车：\n').strip()
        # Finder may paste shell-escaped spaces, or quote the full path.
        path = Path(text)
        if not path.exists():
            import shlex
            parts = shlex.split(text)
            if len(parts) != 1:
                raise ValueError('请选择一个备份 ZIP 文件')
            path = Path(parts[0])
        info = restore(path, a.data, a.verify)
        print('校验通过。备份时间：', info['createdAt'])
        print('空间及记录版本：', info['spaces'])
        if not a.verify:
            print('数据已恢复到：', Path(a.data).resolve())
            print('现在可双击“启动个人决策团.command”。')
            print('若需继续 iCloud 自动备份，再双击“配置云盘备份.command”。')
    except Exception as e:
        print('未完成：' + str(e))
        raise SystemExit(1)

if __name__ == '__main__':
    main()
