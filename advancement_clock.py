"""Confirm desktop time on the local server, independent of browser JS timers.

An owning page holds a same-origin streaming connection. Short reloads reconnect;
closing that page stops confirmation. A stalled/sleeping server or restart pauses
at the last durable confirmation rather than inventing the missing interval.
"""
from contextlib import contextmanager
import logging
import threading
from advancement_service import command


class AdvancementClock:
    def __init__(self, repo, interval=10):
        self.repo=repo
        self.interval=interval
        self.stopped=threading.Event()
        self._lock=threading.Lock()
        self._pages={}
        self._thread=None

    @contextmanager
    def watch(self, space, owner):
        key=(space,owner)
        with self._lock:self._pages[key]=self._pages.get(key,0)+1
        try:yield
        finally:
            with self._lock:
                count=self._pages[key]-1
                if count:self._pages[key]=count
                else:del self._pages[key]

    def tick(self, *, clock=None, interrupt=False):
        with self.repo.connect() as db:
            spaces=[row[0] for row in db.execute('SELECT name FROM spaces')]
        for space in spaces:
            r=self.repo.read(space)['state'].get('advancement',{}).get('active')
            if not r or r['status']!='running':continue
            with self._lock:connected=bool(self._pages.get((space,r['owner'])))
            command(self.repo,space,{'op':'clock-interrupt' if interrupt else 'clock-pulse',
                    'id':r['id'],'owner':r['owner'],'connected':connected},clock=clock)

    def start(self):
        # Persisted timers cannot prove that the previous process remained awake.
        self.tick(interrupt=True)
        def run():
            while not self.stopped.wait(self.interval):
                try:self.tick()
                except Exception:logging.exception('本机计时确认失败')
        self._thread=threading.Thread(target=run,name='advancement-clock',daemon=True)
        self._thread.start()

    def close(self):
        self.stopped.set()
        if self._thread:self._thread.join(timeout=3)
