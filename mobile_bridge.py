"""Mac initiates outbound requests; the relay never gets workspace read/write access."""
import json
import threading
import urllib.request
import urllib.parse
from pathlib import Path
from capture_contract import now

class MobileBridge:
    def __init__(self, inbox):
        self.inbox = inbox
        self.config_path = inbox.repo.root / 'mobile-bridge.json'
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.last_success = None
        self.error = None

    def status(self):
        url = None
        if self.config_path.exists():
            try: url = self.read_config()['url']
            except Exception: self.error = '中转站连接配置无效，请检查本机配置。'
        return {'configured': self.config_path.exists(), 'lastSuccess': self.last_success,
                'error': self.error, 'phoneUrl': url}

    def read_config(self):
        conf = json.loads(self.config_path.read_text())
        url = urllib.parse.urlparse(conf['url'])
        if url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in ('localhost','127.0.0.1')):
            raise ValueError('中转站须使用 HTTPS')
        if url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
            raise ValueError('中转站地址格式错误')
        if not isinstance(conf.get('desktopToken'), str) or len(conf['desktopToken']) < 32:
            raise ValueError('电脑凭证无效')
        return conf

    def request(self, conf, path, body=None):
        req = urllib.request.Request(conf['url'].rstrip('/') + path,
            data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,
            headers={'Authorization':'Bearer '+conf['desktopToken'],'Content-Type':'application/json'})
        # Do not follow a redirect with an authorization header.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs): return None
        with urllib.request.build_opener(NoRedirect).open(req, timeout=12) as response:
            return json.loads(response.read(2_000_000))

    def sync(self):
        if not self.config_path.exists(): return self.status()
        if not self.lock.acquire(blocking=False): return self.status()
        try:
            conf = self.read_config()
            self.request(conf,'/bridge/config',self.inbox.config())
            rows = self.request(conf,'/bridge/pending')['items']
            for row in rows: self.inbox.receive(row)
            receipts = self.inbox.receipts([r['id'] for r in rows])
            if receipts: self.request(conf,'/bridge/receipts',{'items':receipts})
            self.last_success, self.error = now(), None
        except Exception:
            # URLs, server errors and credentials must never leak into UI or logs.
            self.error = '中转站暂时未连接成功；待处理记录保留，将自动重试。'
        finally: self.lock.release()
        return self.status()

    def start(self):
        def run():
            while not self.stop_event.is_set():
                self.sync()
                self.stop_event.wait(20)
        threading.Thread(target=run,daemon=True,name='mobile-inbox').start()

    def close(self): self.stop_event.set()
