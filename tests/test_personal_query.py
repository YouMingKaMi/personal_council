import copy
import json
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from personal_query import Query, dispatch


def sample():
    return {'schemaVersion': 8, 'tasks': [
        {'id': 'task-1', 'date': '2020-01-01', 'title': '虚构任务', 'done': True},
        {'id': 'task-2', 'date': '2020-01-02', 'title': '虚构任务二', 'done': False},
    ], 'habits': [{'id': 'habit', 'versions': [{'fromDate': '2019-01-01', 'kind': 'check'}],
                  'entries': {'2020-01-01': {'checked': True}, '2020-01-02': {'checked': False}}}],
        'notes': [{'id': 'note', 'body': '原文\n  保留空格', 'period': '2020-01',
                   'updatedAt': '2020-01-01T18:00:00Z'},
                  {'id': 'trash', 'body': '回收站虚构内容', 'trashed': True}],
        'expenses': {'entries': [
            {'id': 'e1', 'date': '2020-01-02', 'amountCents': 1001, 'kind': 'expense',
             'categoryId': 'coffee', 'necessity': 'necessary'},
            {'id': 'r1', 'date': '2020-01-03', 'amountCents': 201, 'kind': 'refund',
             'categoryId': 'coffee', 'necessity': 'necessary', 'refundOf': 'older-month'},
            {'id': 'e2', 'date': '2020-01-04', 'amountCents': 999, 'kind': 'expense',
             'categoryId': 'other', 'necessity': 'optional'},
            {'id': 'removed', 'date': '2020-01-02', 'amountCents': 90000, 'kind': 'expense',
             'categoryId': 'coffee', 'necessity': 'necessary', 'deleted': True}],
            'categories': [{'id': 'food', 'name': '餐饮'},
                           {'id': 'coffee', 'name': '咖啡', 'parentId': 'food'},
                           {'id': 'other', 'name': '其他'}],
            'budgets': {'2020-01': {'total': 10000, 'optional': None}},
            'subscriptions': [{'id': 'unpaid', 'amountCents': 200000}]}}


class QueryTest(unittest.TestCase):
    def setUp(self):
        self.state = sample()
        self.query = Query()
        self.query.load = lambda: {'state': self.state, 'revision': 7}

    def test_read_only_and_protocol(self):
        initialized = dispatch(self.query, {'jsonrpc': '2.0', 'id': 1,
            'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}})
        self.assertEqual(initialized['result']['protocolVersion'], '2025-06-18')
        tools = dispatch(self.query, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
        self.assertTrue(all(t['annotations']['readOnlyHint'] for t in tools['result']['tools']))
        self.assertIsNone(dispatch(self.query, {'jsonrpc': '2.0', 'method': 'notifications/initialized'}))
        forbidden = dispatch(self.query, {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
            'params': {'name': 'save_state', 'arguments': {}}})
        self.assertTrue(forbidden['result']['isError'])
        self.assertIn('error', dispatch(self.query, []))

    def test_revision_pagination_and_no_mutation(self):
        before = copy.deepcopy(self.state)
        first = self.query.call('council_read', {'section': 'tasks', 'limit': 1})
        self.assertEqual(first['nextOffset'], 1)
        second = self.query.call('council_read', {'section': 'tasks', 'offset': 1, 'revision': 7})
        self.assertEqual(second['records'][0]['id'], 'task-2')
        with self.assertRaises(ValueError):
            self.query.call('council_read', {'section': 'tasks', 'revision': 6})
        self.assertEqual(before, self.state)

    def test_habits_keep_rules_filter_entries(self):
        result = self.query.call('council_read', {'section': 'habits', 'start_date': '2020-01-02'})
        self.assertEqual(list(result['records'][0]['entries']), ['2020-01-02'])
        self.assertEqual(len(result['records'][0]['versions']), 1)
        self.assertEqual(len(self.state['habits'][0]['entries']), 2)

    def test_exact_notes_dates_and_trash(self):
        result = self.query.call('council_read', {'section': 'notes'})
        self.assertEqual(result['records'][0]['body'], '原文\n  保留空格')
        self.assertEqual(len(result['records']), 1)
        undated = self.query.call('council_read', {'section': 'notes', 'start_date': '2020-01-01'})
        self.assertEqual(undated['excludedUndated'], 1)
        period = self.query.call('council_read', {'section': 'notes', 'start_date': '2020-01-15',
                                                 'date_field': 'period'})
        self.assertEqual(len(period['records']), 1)
        local_date = self.query.call('council_read', {'section': 'notes', 'start_date': '2020-01-02',
                                                     'end_date': '2020-01-02', 'date_field': 'updatedAt'})
        self.assertEqual(len(local_date['records']), 1)

    def test_strict_arguments_and_loopback(self):
        for url in ('https://example.com', 'http://evil:8765', 'http://127.0.0.1:8765/private',
                    'http://user:pass@127.0.0.1:8765', 'http://127.0.0.1:8765?space=lab'):
            with self.assertRaises(ValueError):
                Query(url)
        for args in ({'section': 'tasks', 'limit': True}, {'section': 'tasks', 'limit': 51},
                     {'section': 'tasks', 'space': 'lab'}, {'section': '../secrets'},
                     {'section': 'notes', 'ids': 'not-array'}, {'section': 'tasks', 'query': []}):
            with self.assertRaises(ValueError):
                self.query.call('council_read', args)

    def test_complete_financial_totals_refunds_and_descendants(self):
        result = self.query.call('council_expenses_summary', {'month': '2020-01', 'category_id': 'food'})
        self.assertEqual(result['netCents'], 800)
        self.assertEqual(result['grossCents'], 1001)
        self.assertEqual(result['refundCents'], 201)
        self.assertEqual(result['recordedDays'], 2)
        self.assertEqual(result['calendarDays'], 31)
        self.assertEqual(result['dailyAverageYuan'], '0.26')
        self.assertEqual(result['recordedDayAverageYuan'], '4.00')
        self.assertEqual(sum(d['netCents'] for d in result['days']), 800)
        all_rows = self.query.call('council_expenses_summary', {'month': '2020-01'})
        self.assertEqual(all_rows['netCents'], 1799)
        optional = self.query.call('council_expenses_summary', {'month': '2020-01', 'necessity': 'optional'})
        self.assertEqual(optional['netCents'], 999)

    def test_missing_is_not_zero_balance_and_unknown_sections(self):
        status = self.query.call('council_status', {})
        self.assertFalse(status['sections']['treasury_accounts']['available'])
        self.assertNotIn('虚构任务', json.dumps(status, ensure_ascii=False))
        self.state['treasury'] = {'accounts': [{'id': 'a', 'amount': None}]}
        result = self.query.call('council_read', {'section': 'treasury_accounts'})
        self.assertIsNone(result['records'][0]['amount'])

    def test_get_only_transport_and_real_stdio(self):
        seen = []
        payload = {'revision': 7, 'state': self.state}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                seen.append((self.command, self.path))
                body = json.dumps(payload).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = 'http://127.0.0.1:' + str(server.server_port)
            with patch.dict('os.environ', {'http_proxy': 'http://not-a-proxy.invalid:9'}):
                self.assertEqual(Query(url).call('council_status', {})['revision'], 7)
            lines = [json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}),
                     json.dumps({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                                 'params': {'name': 'council_status', 'arguments': {}}})]
            proc = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'personal_query.py'),
                '--base-url', url], input='\n'.join(lines) + '\n', text=True, capture_output=True, timeout=10)
            self.assertEqual(proc.returncode, 0)
            responses = [json.loads(line) for line in proc.stdout.splitlines()]
            self.assertFalse(responses[1]['result']['isError'])
            self.assertEqual(seen, [('GET', '/api/state?space=main')] * 2)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_redirect_is_rejected(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.send_response(302)
                self.send_header('Location', 'https://example.com/private')
                self.end_headers()
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            from urllib.error import HTTPError
            with self.assertRaises(HTTPError):
                Query('http://127.0.0.1:' + str(server.server_port)).load()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
