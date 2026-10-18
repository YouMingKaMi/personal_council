"""Per-user macOS launchd service; app data remains in the local program directory."""
import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import json
import time
import urllib.request

LABEL = 'com.youmingkami.personal-council'
ROOT = Path(__file__).resolve().parent

def configuration(root, python):
    root = Path(root).resolve()
    return {'Label': LABEL, 'ProgramArguments': [str(python), '-u', str(root / 'server.py'), '--port', '8765'],
            'WorkingDirectory': str(root), 'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 10, 'ExitTimeOut': 20, 'ProcessType': 'Background',
            'StandardOutPath': str(root / 'data' / 'service.log'),
            'StandardErrorPath': str(root / 'data' / 'service-error.log'),
            'EnvironmentVariables': {'PYTHONUNBUFFERED': '1'}}

def healthy():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=1) as response:
            return json.load(response).get('app') == 'personal-system'
    except Exception:
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--disable', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        raise SystemExit('后台常驻功能需要 macOS。')
    target = Path.home() / 'Library' / 'LaunchAgents' / (LABEL + '.plist')
    domain = 'gui/' + str(os.getuid())
    if target.exists():
        old = plistlib.loads(target.read_bytes())
        if old.get('Label') != LABEL or old.get('WorkingDirectory') != str(ROOT):
            raise SystemExit('发现另一个目录的后台服务，请先停用旧目录的服务。')
    if args.disable:
        subprocess.run(['launchctl', 'bootout', domain + '/' + LABEL], capture_output=True)
        if target.exists(): target.unlink()
        print('后台常驻已停用，数据保持不变。')
        return
    managed = subprocess.run(['launchctl', 'print', domain + '/' + LABEL], capture_output=True).returncode == 0
    if healthy() and not managed:
        raise SystemExit('请先关闭原来的网站启动窗口，再启用后台常驻；数据不会丢失。')
    python = Path('/opt/homebrew/bin/python3')
    if not python.exists(): python = Path(sys.executable)
    (ROOT / 'data').mkdir(exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = plistlib.dumps(configuration(ROOT, python))
    # Stop the existing owned service before updating its configuration.
    subprocess.run(['launchctl', 'bootout', domain + '/' + LABEL], capture_output=True)
    temporary = target.with_suffix('.plist.tmp')
    temporary.write_bytes(content)
    temporary.chmod(0o600)
    temporary.replace(target)
    # launchd can finish bootout asynchronously; allow the old registration to release.
    for _ in range(30):
        result = subprocess.run(['launchctl', 'bootstrap', domain, str(target)], capture_output=True, text=True)
        if result.returncode == 0: break
        time.sleep(.5)
    if result.returncode:
        raise SystemExit('后台启动失败：' + result.stderr.strip())
    for _ in range(100):
        if healthy(): break
        time.sleep(.1)
    else:
        raise SystemExit('后台服务已注册但尚未就绪，请查看 data/service-error.log；若位于文稿目录，请先迁到应用数据目录。')
    print('后台常驻已启用：登录自动启动，意外退出自动重启。')
    print('网站：http://127.0.0.1:8765/')

if __name__ == '__main__':
    main()
