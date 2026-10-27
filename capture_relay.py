#!/usr/bin/env python3
"""Private single-user capture relay. Deploy behind HTTPS; contains no desktop DB.

The two random credentials have separate roles. Phone can submit/read its inbox;
Mac can publish form options, fetch pending records and acknowledge receipts only.
"""
import argparse
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from capture_contract import envelope, canonical, now, identifier

ROOT = Path(__file__).resolve().parent

class Relay:
    def __init__(self, root, origin):
        self.root = Path(root); self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.origin = origin.rstrip('/')
        parsed = urlparse(self.origin)
        if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username:
            raise ValueError('需要完整中转站源地址')
        if parsed.scheme == 'http' and parsed.hostname not in ('127.0.0.1','localhost'):
            raise ValueError('对外服务必须使用 HTTPS')
        path = self.root / 'credentials.json'
        if not path.exists():
            fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
            with os.fdopen(fd,'w') as f: json.dump({k:secrets.token_urlsafe(32) for k in ('phoneToken','desktopToken')},f)
        if path.is_symlink(): raise ValueError('凭证文件不能是链接')
        self.tokens = json.loads(path.read_text())
        if any(not isinstance(self.tokens.get(k),str) or len(self.tokens[k])<32 for k in ('phoneToken','desktopToken')):
            raise ValueError('凭证格式错误')
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, body TEXT NOT NULL, status TEXT NOT NULL, received TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, body TEXT NOT NULL)')

    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.root/'inbox.sqlite3',timeout=10)
        try:
            with c: yield c
        finally: c.close()

    def receive(self, value):
        envelope(value); body=canonical(value)
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT body,status FROM items WHERE id=?',(value['id'],)).fetchone()
            if old:
                if old[0]!=body: raise ValueError('相同提交标识的内容不同，请保留原稿并联系处理')
                return {'id':value['id'],'status':old[1]}
            if c.execute("SELECT count(*) FROM items WHERE status='pending'").fetchone()[0]>=500:
                raise ValueError('待处理收件箱已满，请先在电脑确认')
            c.execute('INSERT INTO items VALUES (?,?,?,?)',(value['id'],body,'pending',now()))
        return {'id':value['id'],'status':'pending'}

def handler(relay):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self, value, code=200, mime='application/json; charset=utf-8', cookie=None):
            body=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode()
            self.send_response(code)
            for k,v in {'Content-Type':mime,'Content-Length':str(len(body)),'Cache-Control':'no-store',
                'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
                'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"}.items(): self.send_header(k,v)
            if cookie: self.send_header('Set-Cookie',cookie)
            self.end_headers(); self.wfile.write(body)

        def authorized(self, desktop=False):
            token=self.headers.get('Authorization','').removeprefix('Bearer ')
            if not desktop:
                try:
                    cookies=SimpleCookie(self.headers.get('Cookie',''))
                    token=cookies['capture_session'].value if 'capture_session' in cookies else ''
                except Exception: token=''
            return hmac.compare_digest(token,relay.tokens['desktopToken' if desktop else 'phoneToken'])

        def dispatch(self, post=False):
            if self.headers.get('Host')!=urlparse(relay.origin).netloc:
                return self.send({'error':'访问地址无效'},403)
            path=urlparse(self.path).path
            data=None
            if post:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=500000: return self.send({'error':'提交过大'},413)
                data=json.loads(self.rfile.read(size))
            desktop=path.startswith('/bridge/')
            if post and not desktop and (self.headers.get('X-Capture-Client')!='1' or self.headers.get('Origin') not in (None,relay.origin)):
                return self.send({'error':'请求来源无效'},403)
            if path=='/api/session' and post:
                key=self.client_address[0]; current=time.monotonic()
                with self.server.attempt_lock:
                    history=[x for x in self.server.attempts.get(key,[]) if current-x<60]
                    if len(history)>=8: return self.send({'error':'尝试过于频繁，请稍后重试'},429)
                    self.server.attempts[key]=history+[current]
                token=data.get('token','') if isinstance(data,dict) else ''
                if not isinstance(token,str) or not hmac.compare_digest(token,relay.tokens['phoneToken']):
                    return self.send({'error':'连接码不正确'},401)
                cookie='capture_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000'
                if relay.origin.startswith('https:'): cookie+='; Secure'
                return self.send({'ok':True},cookie=cookie)
            if path.startswith(('/api/','/bridge/')):
                if not self.authorized(desktop): return self.send({'error':'请先连接你的收件箱'},401)
                if path=='/api/logout' and post:
                    return self.send({'ok':True},cookie='capture_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                if path=='/api/submit' and post: return self.send(relay.receive(data))
                with relay.connect() as c:
                    if path=='/bridge/config' and post:
                        if not isinstance(data,dict) or data.get('version')!=1 or not {'version','kinds','categories','habits'}<=set(data)<= {'version','kinds','categories','habits','domains','problems','plans'}:
                            raise ValueError('表单配置不兼容')
                        for field,keys in [('domains',{'id','name'}),('problems',{'id','domainId','title'}),('plans',{'id','domainId','problemId','title'})]:
                            rows=data.get(field,[])
                            if not isinstance(rows,list) or len(rows)>20000 or any(not isinstance(r,dict) or set(r)!=keys or any(not isinstance(v,str) for v in r.values()) for r in rows):raise ValueError('推进表单配置无效')
                        c.execute('INSERT OR REPLACE INTO config VALUES (1,?)',(canonical(data),))
                        return self.send({'ok':True})
                    if path=='/api/config' and not post:
                        row=c.execute('SELECT body FROM config WHERE id=1').fetchone()
                        return self.send(json.loads(row[0]) if row else {'version':1,'kinds':{},'categories':[],'habits':[]})
                    if path in ('/bridge/pending','/api/items') and not post:
                        query="SELECT body,status,received FROM items WHERE status='pending' ORDER BY received LIMIT 100" if desktop else 'SELECT body,status,received FROM items ORDER BY received DESC LIMIT 500'
                        rows=c.execute(query).fetchall()
                        return self.send({'items':[json.loads(r[0]) if desktop else {'submission':json.loads(r[0]),'status':r[1],'receivedAt':r[2]} for r in rows]})
                    if path=='/bridge/receipts' and post:
                        if not isinstance(data,dict) or not isinstance(data.get('items'),list) or len(data['items'])>100: raise ValueError('回执格式错误')
                        for r in data['items']:
                            identifier(r['id'])
                            if r['status'] not in ('imported','rejected'): raise ValueError('回执状态无效')
                            c.execute("UPDATE items SET status=? WHERE id=? AND status='pending'",(r['status'],r['id']))
                        return self.send({'ok':True})
                return self.send({'error':'接口不存在'},404)
            if post: return self.send({'error':'接口不存在'},404)
            files={'/':'mobile/index.html','/sw.js':'mobile/sw.js','/mobile/app.js':'mobile/app.js',
                   '/mobile/style.css':'mobile/style.css','/static/capture-form.js':'static/capture-form.js',
                   '/static/favicon.ico':'static/favicon.ico','/static/icon-32.png':'static/icon-32.png',
                   '/static/icon-180.png':'static/icon-180.png'}
            if path not in files: return self.send({'error':'页面不存在'},404)
            f=ROOT/files[path]
            return self.send(f.read_bytes(),mime=(mimetypes.guess_type(f)[0] or 'text/plain')+'; charset=utf-8')

        def do_GET(self):
            try: self.dispatch()
            except (ValueError,KeyError,TypeError,AttributeError): self.send({'error':'请求格式无效'},400)
            except Exception: self.send({'error':'服务暂时不可用，记录仍保留'},500)
        def do_POST(self):
            try: self.dispatch(True)
            except (ValueError,KeyError,TypeError,AttributeError) as e: self.send({'error':str(e)},400)
            except Exception: self.send({'error':'保存失败，请保留待发送记录后重试'},500)
    return Handler

def make_server(relay, host, port):
    import threading
    server=ThreadingHTTPServer((host,port),handler(relay))
    server.attempt_lock=threading.Lock(); server.attempts={}
    return server

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--data',required=True); p.add_argument('--origin',required=True)
    p.add_argument('--port',type=int,default=8890)
    args=p.parse_args()
    os.umask(0o077)
    relay=Relay(args.data,args.origin)
    make_server(relay,'127.0.0.1',args.port).serve_forever()
