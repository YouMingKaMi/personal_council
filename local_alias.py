"""Retired development URL: redirect navigation, never forward stale writes."""
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse

TARGET='http://127.0.0.1:8765/'
class AliasHandler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def respond(self,status,body=b'',location=None):
        self.send_response(status)
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        if location:self.send_header('Location',location)
        self.end_headers()
        if self.command!='HEAD':self.wfile.write(body)
    def do_GET(self):
        if urlparse(self.path).path=='/':return self.respond(303,location=TARGET)
        return self.respond(410,json.dumps({'error':'旧开发入口已停用，请打开 http://127.0.0.1:8765/；这里不再保存数据。'},ensure_ascii=False).encode())
    do_HEAD=do_GET
    def do_POST(self):
        # Old open tabs must never replay independent-copy revisions into the real DB.
        self.respond(409,json.dumps({'error':'8766 已停用，当前修改尚未保存。请保留输入并打开 http://127.0.0.1:8765/。'},ensure_ascii=False).encode())
    do_PUT=do_POST
    do_DELETE=do_POST

def create_alias(port=8766):return ThreadingHTTPServer(('127.0.0.1',port),AliasHandler)
