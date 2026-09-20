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
        self.assertEqual(reiya.BUILD_VERSION, 'v6.8.91-REI-REJOIN')
        self.assertIn(('Anime Dice', '113290951185459'), reiya.PRESET_GAMES)

    def test_config_validation(self):
        clean = reiya.validate_config({
            'check_interval': -5,
            'retry_count': '500',
            'window_mode': 'broken',
            'selected_packages': ['com.roblox.client', 'bad;command', 'com.roblox.client'],
            'rejoin_interval': 1,
            'ram_refresh_interval': 30,
        })
        self.assertEqual(clean['check_interval'], 1)
        self.assertEqual(clean['retry_count'], 100)
        self.assertEqual(clean['window_mode'], 'left_stack')
        self.assertEqual(clean['selected_packages'], ['com.roblox.client'])
        self.assertNotIn('rejoin_interval', clean)
        self.assertNotIn('ram_refresh_interval', clean)

    def test_system_ram_refreshes_after_five_seconds(self):
        old_config = reiya.config
        old_usage = reiya._last_ram_usage
        old_check = reiya._last_ram_check_time
        try:
            reiya.config = {'system_ram_refresh_interval': 5}
            reiya._last_ram_usage = (0.0, 0.0)
            reiya._last_ram_check_time = 0.0
            samples = [
                'MemTotal: 4194304 kB\nMemAvailable: 1048576 kB\n',
                'MemTotal: 4194304 kB\nMemAvailable: 2097152 kB\n',
            ]
            with mock.patch.object(reiya.time, 'time', side_effect=[100.0, 103.0, 106.0]), \
                 mock.patch.object(reiya, '_read_proc_file', side_effect=samples) as proc_read:
                self.assertEqual(reiya.get_ram_usage(), (3.0, 4.0))
                self.assertEqual(reiya.get_ram_usage(), (3.0, 4.0))
                self.assertEqual(reiya.get_ram_usage(), (2.0, 4.0))
            self.assertEqual(proc_read.call_count, 2)
        finally:
            reiya.config = old_config
            reiya._last_ram_usage = old_usage
            reiya._last_ram_check_time = old_check

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

    def test_process_ram_parsers(self):
        self.assertEqual(reiya._parse_process_ram_kb('TOTAL PSS: 345,678 TOTAL RSS: 400000'), 345678)
        self.assertEqual(reiya._parse_process_ram_kb(' TOTAL  123456  42  9'), 123456)
        self.assertEqual(reiya._parse_process_ram_kb('total,654321,2,3'), 654321)
        self.assertIsNone(reiya._parse_process_ram_kb('No process found'))

    def test_process_ram_pss_and_cache(self):
        reiya._process_ram_cache.clear()
        output = subprocess.CompletedProcess('cmd', 0, 'TOTAL PSS: 204800 TOTAL RSS: 250000', '')
        with mock.patch.object(reiya, 'run_cmd', return_value=output) as run_cmd:
            self.assertEqual(reiya.get_process_ram('com.roblox.client', force=True), 200)
            self.assertEqual(reiya.get_process_ram('com.roblox.client'), 200)
            self.assertEqual(run_cmd.call_count, 1)
        self.assertEqual(reiya.format_process_ram(200), '200 MB')
        self.assertEqual(reiya.format_process_ram(None), 'N/A')

    def test_process_ram_proc_fallback(self):
        reiya._process_ram_cache.clear()
        failed = subprocess.CompletedProcess('cmd', 1, '', '')
        proc_values = subprocess.CompletedProcess('cmd', 0, '102400\n51200\n', '')
        with mock.patch.object(reiya, 'run_cmd', side_effect=[failed, failed, failed, proc_values]):
            self.assertEqual(reiya.get_process_ram('com.roblox.client', force=True), 150)

    def test_app_ram_sampler_updates_status(self):
        samples = []
        worker = None
        def receive(package, ram_mb):
            samples.append((package, ram_mb))
            worker.stop()
        worker = reiya.AppRamThread(['com.roblox.client'], 10, receive)
        with mock.patch.object(reiya, 'get_process_ram', return_value=321):
            worker.start()
            worker.join(timeout=2)
        self.assertEqual(samples, [('com.roblox.client', 321)])
        self.assertFalse(worker.is_alive())

    def test_webhook_contains_uptime_and_cached_app_ram(self):
        statuses = {'com.roblox.client': {'status': 'Ingame', 'ram_mb': 321}}
        sent = subprocess.CompletedProcess('curl', 0, '204', '')
        with mock.patch.object(reiya, 'get_cpu_usage', return_value=12.5), \
             mock.patch.object(reiya, 'get_ram_usage', return_value=(2.0, 4.0)), \
             mock.patch.object(reiya, 'get_device_name', return_value='Device'), \
             mock.patch.object(reiya, 'take_screenshot', return_value=None), \
             mock.patch.object(reiya.subprocess, 'run', return_value=sent) as curl:
            reiya.send_discord_webhook('https://discord.com/api/webhooks/1/token', statuses, time.time() - 3661)
        payload_arg = next(arg for arg in curl.call_args.args[0] if arg.startswith('payload_json='))
        self.assertIn('Monitor Uptime', payload_arg)
        self.assertIn('01h:01m:01s', payload_arg)
        self.assertIn('App RAM: 321 MB', payload_arg)

    def test_dashboard_contains_uptime_and_app_ram(self):
        import io
        from contextlib import redirect_stdout
        engine = reiya.TerminalRejoinLoop()
        engine.running = True
        engine.start_time = time.time() - 3661
        engine.set_status('com.roblox.client', 'Ingame', ram_mb=321)
        cfg = dict(reiya.DEFAULT_CONFIG, selected_packages=['com.roblox.client'], dashboard_refresh_interval=0.5)
        output = io.StringIO()
        with mock.patch.object(reiya, 'clear_terminal_screen'), \
             mock.patch.object(reiya, 'get_cpu_usage', return_value=12.5), \
             mock.patch.object(reiya, 'get_ram_usage', return_value=(2.0, 4.0)), \
             mock.patch.object(reiya, 'get_package_username', return_value='User'), \
             redirect_stdout(output):
            thread = threading.Thread(target=engine.render_live_dashboard, args=(cfg,))
            thread.start()
            time.sleep(0.1)
            engine.running = False
            thread.join(timeout=2)
        rendered = output.getvalue()
        self.assertIn('UPTIME: 01h:01m:', rendered)
        self.assertIn('Stat/RAM', rendered)
        self.assertIn('In/321M', rendered)


if __name__ == '__main__':
    unittest.main(verbosity=2)
