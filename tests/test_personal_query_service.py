import json
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from personal_query_service import agent_config, ensure_runtime


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        runtime = self.root / 'runtime'
        runtime.mkdir(mode=0o700)
        key = runtime / 'control-plane.key'
        key.write_text('synthetic-test-only-not-a-real-key')
        key.chmod(0o600)
        (runtime / 'connection.json').write_text(json.dumps({'tunnelId': 'tunnel_' + 'a' * 32}))

    @patch('personal_query_service.subprocess.run')
    def test_healthy_runtime_is_not_duplicated(self, run):
        run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(
            {'process_running': True, 'healthy': True, 'ready': True}))
        self.assertFalse(ensure_runtime(self.root)['started'])
        self.assertEqual(run.call_count, 1)

    @patch('personal_query_service.subprocess.run')
    def test_missing_process_restarts_with_file_reference(self, run):
        run.side_effect = [SimpleNamespace(returncode=0, stdout=json.dumps({'process_running': False})),
                           SimpleNamespace(returncode=0, stdout=json.dumps(
                               {'process_running': True, 'healthy': True, 'ready': True}))]
        self.assertTrue(ensure_runtime(self.root)['started'])
        args = run.call_args.args[0]
        self.assertIn('connect', args)
        self.assertIn('file:' + str(self.root / 'runtime/control-plane.key'), args)
        self.assertNotIn('synthetic-test-only-not-a-real-key', str(run.call_args))

    @patch('personal_query_service.subprocess.run')
    def test_uncertain_status_does_not_start_another_process(self, run):
        run.return_value = SimpleNamespace(returncode=0, stdout='{}')
        with self.assertRaises(ValueError):
            ensure_runtime(self.root)
        self.assertEqual(run.call_count, 1)

    @patch('personal_query_service.subprocess.run')
    def test_overbroad_credential_permissions_are_rejected(self, run):
        (self.root / 'runtime/control-plane.key').chmod(0o644)
        with self.assertRaises(ValueError):
            ensure_runtime(self.root)
        run.assert_not_called()

    def test_login_agent_has_no_credential_contents(self):
        config = plistlib.loads(plistlib.dumps(agent_config(self.root)))
        self.assertTrue(config['RunAtLoad'])
        self.assertEqual(config['StartInterval'], 60)
        self.assertNotIn('EnvironmentVariables', config)
        self.assertNotIn('synthetic-test-only-not-a-real-key', str(config))


if __name__ == '__main__':
    unittest.main()
