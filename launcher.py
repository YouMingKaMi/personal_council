"""Start or reuse this local app and open its browser window."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:8765'
def running():
    try:
        with urllib.request.urlopen(URL + '/api/health', timeout=1) as r:
            return json.load(r).get('app') == 'personal-system'
    except Exception:
        return False

if running():
    webbrowser.open(URL)
else:
    service = Path.home() / 'Library/LaunchAgents/com.youmingkami.personal-council.plist'
    if sys.platform == 'darwin' and service.exists():
        import plistlib
        config = plistlib.loads(service.read_bytes())
        if config.get('WorkingDirectory') != str(ROOT):
            raise SystemExit('后台服务指向其它程序目录，请先停用旧服务。')
        target = 'gui/' + str(os.getuid())
        subprocess.run(['launchctl', 'bootstrap', target, str(service)], capture_output=True)
        subprocess.run(['launchctl', 'kickstart', target + '/com.youmingkami.personal-council'], capture_output=True)
        for _ in range(60):
            if running():
                webbrowser.open(URL)
                raise SystemExit(0)
            time.sleep(.1)
        raise SystemExit('后台服务暂未启动，请查看 data/service-error.log。')
    process = subprocess.Popen([sys.executable, str(ROOT / 'server.py')], cwd=ROOT)
    for _ in range(60):
        if running():
            webbrowser.open(URL)
            print('个人决策团已打开。保留这个窗口即可使用；按 Control+C 停止本机服务。')
            break
        if process.poll() is not None:
            raise SystemExit('启动失败。8765 端口可能被其他程序占用，请查看上面的提示。')
        time.sleep(.1)
    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
