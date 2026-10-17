"""Start or reuse this local app and open its browser window."""
import json
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
