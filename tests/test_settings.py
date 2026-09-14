import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from maxrunway import settings


class SettingsTests(unittest.TestCase):
    def test_provider_urls_require_https_and_no_embedded_credentials(self):
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            settings.validate_settings({'omegaEndpoint': 'http://api.example.test/v1'})
        with self.assertRaisesRegex(ValueError, 'embedded credentials'):
            settings.validate_settings({'runwayEndpoint': 'https://user:pass@example.test/mcp'})

    def test_non_secret_settings_file_never_contains_api_key(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'settings.json'
            with patch.object(settings, 'settings_path', return_value=target):
                clean = settings.save_settings({'omegaModel': 'omega-plus'})
                stored = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(stored, clean)
            self.assertNotIn('key', json.dumps(stored).lower())

    def test_run_codex_uses_argument_list_without_shell(self):
        completed = type('Result', (), {'returncode': 0, 'stdout': 'Logged in using ChatGPT', 'stderr': ''})()
        with patch.object(settings, 'codex_path', return_value=r'C:\Tools\codex.exe'), \
             patch.object(settings.subprocess, 'run', return_value=completed) as run:
            code, text = settings.run_codex(['login', 'status'])
        self.assertEqual((code, text), (0, 'Logged in using ChatGPT'))
        self.assertEqual(run.call_args.args[0], [r'C:\Tools\codex.exe', 'login', 'status'])
        self.assertFalse(run.call_args.kwargs.get('shell', False))

    def test_mcp_name_rejects_command_characters(self):
        with self.assertRaisesRegex(ValueError, 'Runway MCP name'):
            settings.validate_settings({'runwayServer': 'runway & whoami'})


if __name__ == '__main__':
    unittest.main()
