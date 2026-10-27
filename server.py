#!/usr/bin/env python3
"""Offline, loopback-only personal workspace. Python standard library only."""
import argparse
import csv
import io
import json
import mimetypes
import re
import sys
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from repository import Repository, Conflict
from domain import validate
from migrations import upgrade
from market import MarketService, effective_price

ROOT = Path(__file__).resolve().parent


def archive(state):
    stream = io.BytesIO()
    folders = {x['id']: x for x in state['folders']}
    def clean(s):
        return re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', s).strip('. ')[:100] or '未命名'
    def path(f):
        parts = []
        while f:
            item = folders[f]
            parts.insert(0, clean(item['name']))
            f = item.get('parent')
        return '/'.join(parts)
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('personal-system.json', json.dumps(state, ensure_ascii=False, indent=2))
        for n in state['notes']:
            # ID suffix prevents collisions without changing the original text.
            z.writestr(f"笔记/{path(n['folder'])}/{clean(n['title'])}--{clean(n['id'])}.md", n['body'])
        chronicle = state.get('chronicle', {})
        months = sorted({e['date'][:7] for e in chronicle.get('events', []) if not e.get('deleted')})
        for month in months:
            events = [e for e in chronicle['events'] if not e.get('deleted') and e['date'].startswith(month)]
            text = '# ' + month + ' 编年史\n\n'
            for day in sorted({e['date'] for e in events}):
                text += '## ' + day + '\n\n'
                for event in (e for e in events if e['date'] == day):
                    prefix = '[' + day + ' — ' + event['endDate'] + '] ' if event.get('endDate') else ''
                    text += '- ' + prefix + event['text'].replace('\n','\n  ') + '\n'
                text += '\n'
            z.writestr('编年史/' + month + '.md', text)
        treasury = state.get('treasury', {})
        csv_data = io.StringIO()
        writer = csv.writer(csv_data)
        writer.writerow(['资产','分类','账户','数量或金额','单位','人民币单价','估值日期','状态'])
        def safe_cell(value):
            text = str(value) if value is not None else ''
            return "'" + text if text.startswith(('=', '+', '-', '@', '\t', '\r')) else text
        for asset in treasury.get('assets', []):
            for account in treasury.get('accounts', []):
                if account['assetId'] == asset['id']:
                    writer.writerow([safe_cell(v) for v in [asset['name'],asset['category'],account['name'],account['amount'],asset['unit'],*effective_price(treasury,asset), '已归档' if asset['archived'] or account['archived'] else '使用中']])
        z.writestr('国库/当前账户明细.csv', '\ufeff' + csv_data.getvalue())
        for snapshot in treasury.get('snapshots', []):
            z.writestr('国库/盘点/' + snapshot['date'] + '--' + snapshot['id'] + '.json', json.dumps(snapshot,ensure_ascii=False,indent=2))
        a=state.get('advancement',{})
        for d in a.get('domains',[]):
            lines=['# '+d['name'],d.get('goal',''),'']
            for p in (p for p in a.get('issues',[]) if p['domainId']==d['id']):
                lines.extend(['## '+p['title'],'状态：'+p['status']+('（回收站）' if p.get('deleted') else ''),p['body'],'下一步：'+p['next'],'结论：'+p['conclusion']])
                for q in (q for q in a.get('plans',[]) if q['problemId']==p['id']):
                    lines.extend(['### 方案：'+q['title'],'状态：'+q['status']+('（已移除）' if q.get('deleted') else ''),q.get('body','')])
                    lines.extend(u['date']+' · '+u['body'] for u in a.get('updates',[]) if u.get('planId')==q['id'])
                lines.extend(u['date']+' · '+u['body'] for u in a.get('updates',[]) if u.get('problemId')==p['id'] and not u.get('planId'))
            z.writestr('个人推进台/'+clean(d['name'])+'--'+d['id']+'.md','\n\n'.join(lines))
        z.writestr('说明.txt', 'personal-system.json 是完整恢复文件。笔记目录为可独立阅读的 Markdown 正文。任务、习惯、字段和布局保存在 JSON 中。国库目录含当前账户明细与固定盘点副本。外部附件尚未迁移。')
    return stream.getvalue()


def handler(repo, backup=None, mobile=None):
    def capture():
        nonlocal mobile
        if mobile is None:
            from mobile_inbox import MobileInbox
            from mobile_bridge import MobileBridge
            mobile = MobileBridge(MobileInbox(repo))
        return mobile
    market = MarketService(repo)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if args and str(args[1] if len(args) > 1 else '') not in ('200', '304'):
                super().log_message(fmt, *args)

        def send(self, data, status=200, mime='application/json; charset=utf-8', download=None):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            if download:
                self.send_header('Content-Disposition', 'attachment; filename="' + download + '"')
            self.end_headers()
            self.wfile.write(data)

        def route(self):
            expected = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') not in (expected, f'localhost:{self.server.server_port}'):
                raise ValueError('只接受本机访问')
            parsed = urlparse(self.path)
            space = parse_qs(parsed.query).get('space', ['main'])[0]
            if space not in ('main', 'lab'):
                raise ValueError('未知空间')
            return parsed.path, space

        def do_GET(self):
            try:
                path, space = self.route()
                if path == '/api/mobile-inbox':
                    connection = capture()
                    if space != 'main': return self.send({'error':'手机收件箱只连接正式空间'},400)
                    return self.send({'items':connection.inbox.rows(),'config':connection.inbox.config(),'connection':connection.status()})
                if path == '/api/state':
                    return self.send(repo.read(space))
                if path == '/api/backups':
                    return self.send(repo.backups(space))
                if path == '/api/export':
                    return self.send(archive(repo.read(space)['state']), mime='application/zip', download=f'personal-system-{space}.zip')
                if path == '/api/cloud-backup':
                    return self.send(backup.status() if backup else {'configured': False, 'uploadConfirmed': False})
                if path == '/api/health':
                    return self.send({'app': 'personal-system', 'version': '0.9.0'})
                if path == '/':
                    file = ROOT / 'static' / 'index.html'
                elif path.startswith('/static/'):
                    file = (ROOT / path.lstrip('/')).resolve()
                    if not file.is_relative_to(ROOT / 'static'):
                        return self.send({'error': '无权限'}, 403)
                else:
                    return self.send({'error': '页面不存在'}, 404)
                if not file.is_file():
                    return self.send({'error': '文件不存在'}, 404)
                if path=='/' and self.server.server_port!=8765:
                    html=file.read_text().replace('<body>', '<body><aside style="padding:14px;background:#fff0c9;color:#684d18;position:fixed;z-index:20000;bottom:0;left:0;right:0;text-align:center;font:14px sans-serif">开发副本 · 内容独立保存，不是日常数据库。<a href="http://127.0.0.1:8765/">打开日常系统</a></aside>')
                    return self.send(html.encode(),mime='text/html; charset=utf-8')
                return self.send(file.read_bytes(), mime=(mimetypes.guess_type(file)[0] or 'application/octet-stream') + '; charset=utf-8')
            except ValueError as e:
                self.send({'error': str(e)}, 400)

        def do_POST(self):
            try:
                path, space = self.route()
                origin = self.headers.get('Origin')
                if self.headers.get('X-Personal-Client') != '1' or (origin and origin != 'http://' + self.headers.get('Host', '')):
                    return self.send({'error': '请求来源无效'}, 403)
                size = int(self.headers.get('Content-Length', '0'))
                if size <= 0 or size > 25_000_000:
                    return self.send({'error': '请求大小超出限制'}, 413)
                data = json.loads(self.rfile.read(size))
                if path == '/api/advancement':
                    from advancement_service import command
                    return self.send(command(repo,space,data))
                if path.startswith('/api/mobile-inbox/'):
                    connection = capture()
                    if space != 'main': return self.send({'error':'测试空间不能处理手机记录'},403)
                    if path.endswith('/sync'): return self.send(connection.sync())
                    if path.endswith('/approve'):
                        result=connection.inbox.approve(data['id'],data.get('payload'))
                        threading.Thread(target=connection.sync,daemon=True).start()
                        return self.send(result)
                    if path.endswith('/reject'):
                        connection.inbox.reject(data['id'])
                        threading.Thread(target=connection.sync,daemon=True).start()
                        return self.send({'ok':True})
                    return self.send({'error':'接口不存在'},404)
                if path == '/api/cloud-backup':
                    if not backup:
                        return self.send({'error': '尚未配置云盘备份目录'}, 400)
                    result = backup.run()
                    return self.send(result, 500 if result.get('error') else 200)
                if path == '/api/market/refresh':
                    if type(data.get('force',False)) is not bool:raise ValueError('刷新参数无效')
                    return self.send(market.refresh(space,data['revision'],data.get('force',False)))
                if path == '/api/import-backup':
                    state = validate(upgrade(data['state']))
                    revision = repo.save(space, data['revision'], state)
                    return self.send({'revision': revision, 'state': state})
                if path == '/api/state':
                    state=validate(data['state'])
                    if state.get('advancement') is not None:
                        from advancement_folders import synchronize
                        synchronize(state)
                    revision = repo.save(space, data['revision'], validate(state))
                    return self.send({'revision': revision, 'state': state})
                if path == '/api/restore':
                    state = validate(upgrade(repo.snapshot(space, int(data['id']))))
                    revision = repo.save(space, data['revision'], state)
                    return self.send({'revision': revision, 'state': state})
                return self.send({'error': '接口不存在'}, 404)
            except Conflict as e:
                self.send({'error': str(e)}, 409)
            except (ValueError, TypeError, KeyError, AttributeError) as e:
                self.send({'error': '无法保存：' + str(e)}, 400)
            except Exception:
                self.send({'error': '本机保存失败，请保留当前页面并导出备份。'}, 500)
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data', default=str(ROOT / 'data'))
    args = parser.parse_args()
    if args.port==8766:
        parser.error('8766 已保留为日常系统的跳转入口。开发副本请使用其他端口，例如 8877。')
    repo = Repository(args.data)
    backup = None
    config = Path(args.data) / 'backup-config.json'
    if args.port == 8765 and config.exists():
        from cloud_backup import BackupManager
        backup = BackupManager(repo, json.loads(config.read_text())['destination'])
        repo.on_saved = backup.request
        backup.request()
    try:
        from mobile_inbox import MobileInbox
        from mobile_bridge import MobileBridge
        mobile = MobileBridge(MobileInbox(repo))
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(repo, backup, mobile))
        mobile.start()
    except OSError as e:
        print(f'无法启动：{e}', file=sys.stderr)
        if backup: backup.close()
        sys.exit(1)
    alias=None
    if args.port==8765:
        from local_alias import create_alias
        try:
            alias=create_alias()
            threading.Thread(target=alias.serve_forever,daemon=True).start()
        except OSError:
            print('8766 跳转入口暂不可用；日常系统仍请使用 8765。',file=sys.stderr)
    print(f'Local: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
        if alias:alias.shutdown();alias.server_close()
    finally:
        mobile.close()
        if backup: backup.close()
