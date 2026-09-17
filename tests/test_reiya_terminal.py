import importlib.util
import json
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / 'reiya_terminal.py'
spec = importlib.util.spec_from_file_location('reiya_enhanced', MODULE_PATH)
reiya = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reiya)


class EnhancementTests(unittest.TestCase):
    def test_version_and_preset(self):
        self.assertEqual(reiya.BUILD_VERSION, 'v6.8.89-REI-REJOIN')
        self.assertIn(('Anime Dice', '113290951185459'), reiya.PRESET_GAMES)

    def test_config_validation(self):
        clean = reiya.validate_config({
            'check_interval': -5,
            'retry_count': '500',
            'window_mode': 'broken',
            'selected_packages': ['com.roblox.client', 'bad;command', 'com.roblox.client'],
            'rejoin_interval': 1,
        })
        self.assertEqual(clean['check_interval'], 1)
        self.assertEqual(clean['retry_count'], 100)
        self.assertEqual(clean['window_mode'], 'left_stack')
        self.assertEqual(clean['selected_packages'], ['com.roblox.client'])
        self.assertNotIn('rejoin_interval', clean)

    def test_atomic_config_and_backup_recovery(self):
        old_path, old_config = reiya.CONFIG_FILE, reiya.config
        try:
            with tempfile.TemporaryDirectory() as td:
                reiya.CONFIG_FILE = str(Path(td) / 'config.json')
                reiya.config = {'check_interval': 9, 'selected_packages': ['com.roblox.client']}
                reiya.save_config()
                reiya.config['check_interval'] = 11
                reiya.save_config()
                Path(reiya.CONFIG_FILE).write_text('{broken', encoding='utf-8')
                loaded = reiya.load_config()
                self.assertEqual(loaded['check_interval'], 9)
                self.assertFalse(Path(reiya.CONFIG_FILE + '.tmp').exists())
        finally:
            reiya.CONFIG_FILE, reiya.config = old_path, old_config

    def test_grid_and_stack_bounds(self):
        self.assertEqual(reiya.calculate_window_bounds(0, 2, 1000, 800, 'left_stack'), (500, 0, 1000, 400))
        self.assertEqual(reiya.calculate_window_bounds(3, 4, 1000, 800, 'grid'), (500, 400, 1000, 800))

    def test_activity_tri_state(self):
        home = 'TASK x com.roblox.client\n  ReactRootView homeactivity'
        game = 'TASK x com.roblox.client\n  SurfaceView renderview'
        self.assertIs(reiya.get_app_activity_state('com.roblox.client', home), False)
        self.assertIs(reiya.get_app_activity_state('com.roblox.client', game), True)
        self.assertIsNone(reiya.get_app_activity_state('com.roblox.client', ''))
        self.assertIsNone(reiya.get_app_activity_state('com.roblox.client', 'TASK unrelated'))

    def test_launch_validation_and_window_apply(self):
        ok = subprocess.CompletedProcess('cmd', 0, 'Starting: Intent', '')
        with mock.patch.object(reiya, 'run_cmd', return_value=ok) as run_cmd, \
             mock.patch.object(reiya, 'apply_window_bounds', return_value=True) as resize:
            self.assertTrue(reiya.launch_game('com.roblox.client', '12345', (0, 0, 100, 100), True))
            resize.assert_called_once_with('com.roblox.client', (0, 0, 100, 100))
            self.assertFalse(reiya.launch_game('bad;package', '12345'))
            self.assertFalse(reiya.launch_game('com.roblox.client', '123;rm'))
            self.assertEqual(run_cmd.call_count, 1)

    def test_stop_joins_worker_and_prevents_revival(self):
        engine = reiya.TerminalRejoinLoop()
        engine.running = True
        engine.stop_event = threading.Event()
        event = engine.stop_event
        engine.thread = threading.Thread(target=lambda: event.wait(5))
        engine.thread.start()
        engine.stop()
        self.assertTrue(event.is_set())
        self.assertFalse(engine.thread.is_alive())
        self.assertFalse(engine.running)


if __name__ == '__main__':
    unittest.main(verbosity=2)
