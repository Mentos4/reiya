import threading
import time

from core.app_launcher import (
    is_app_running, launch_game, clear_app_cache
)


class RejoinLoop:
    def __init__(self):
        self._thread = None
        self._running = False
        self._start_time = None
        self._status = {}          # {pkg: {'status': str, 'time': float}}
        self._log_lines = []
        self._log_cb = None
        self._status_cb = None

    def set_log_callback(self, cb):
        self._log_cb = cb

    def set_status_callback(self, cb):
        self._status_cb = cb

    def _log(self, msg):
        ts = time.strftime('%H:%M:%S')
        line = f'[{ts}] {msg}'
        self._log_lines.append(line)
        if len(self._log_lines) > 200:
            self._log_lines = self._log_lines[-200:]
        if self._log_cb:
            self._log_cb(line)

    def _set_status(self, pkg, status):
        self._status[pkg] = {'status': status, 'time': time.time()}
        if self._status_cb:
            self._status_cb(pkg, status)

    def get_status(self):
        return dict(self._status)

    def get_logs(self):
        return list(self._log_lines)

    def is_running(self):
        return self._running

    def get_uptime(self):
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    @property
    def running(self):
        return self._running

    def start(self, config):
        if self._running:
            return False
        packages = config.get('selected_packages', [])
        if not packages:
            self._log('No packages selected. Go to Setup → Package Selection.')
            return False
        self._running = True
        self._start_time = time.time()
        self._thread = threading.Thread(
            target=self._loop,
            args=(list(packages), dict(config)),
            daemon=True
        )
        self._thread.start()
        return True

    def stop(self):
        self._running = False
        self._log('Auto rejoin stopped.')

    def _get_game_id(self, pkg, config):
        method = config.get('game_method', 'all')
        if method == 'each':
            pkg_games = config.get('package_games', {})
            return pkg_games.get(pkg, config.get('game_id', ''))
        return config.get('game_id', '')

    def _loop(self, packages, config):
        offline_wait   = float(config.get('offline_wait', 15))
        max_retries    = int(config.get('retry_count', 3))
        retry_delay    = float(config.get('retry_delay', 30))
        check_interval = float(config.get('check_interval', 10))
        delay_open_tab = float(config.get('launch_wait', 15))
        sequential     = config.get('sequential_join', False)
        auto_clear     = config.get('clear_cache', False)

        retries   = {p: 0 for p in packages}
        last_seen = {p: time.time() for p in packages}

        game_name = config.get('game_name', 'Unknown')
        self._log(f'Starting auto rejoin — game: {game_name}')
        self._log(f'Packages: {len(packages)} | Check every {check_interval}s')

        # Initial launch
        for i, pkg in enumerate(packages):
            gid = self._get_game_id(pkg, config)
            if not gid:
                self._log(f'WARNING: No game set for {pkg}, skipping launch')
                self._set_status(pkg, 'No game set')
                continue
            self._log(f'Launching {pkg} → place {gid}')
            self._set_status(pkg, 'Launching')
            launch_game(pkg, gid)
            if sequential and i < len(packages) - 1:
                time.sleep(delay_open_tab)
        if not sequential and delay_open_tab > 0:
            time.sleep(delay_open_tab)

        while self._running:
            for pkg in packages:
                if not self._running:
                    break

                gid = self._get_game_id(pkg, config)
                running = is_app_running(pkg)

                if running:
                    self._set_status(pkg, 'Ingame')
                    last_seen[pkg] = time.time()
                    retries[pkg] = 0
                else:
                    self._set_status(pkg, 'Waiting')
                    offline_secs = time.time() - last_seen[pkg]

                    if offline_secs >= offline_wait:
                        if retries[pkg] >= max_retries:
                            self._log(f'{pkg}: max retries hit, cooldown {retry_delay}s')
                            self._set_status(pkg, 'Cooldown')
                            time.sleep(retry_delay)
                            retries[pkg] = 0
                            last_seen[pkg] = time.time()
                        else:
                            retries[pkg] += 1
                            attempt = f'{retries[pkg]}/{max_retries}'
                            self._log(f'{pkg}: rejoining attempt {attempt}')
                            if auto_clear:
                                clear_app_cache(pkg)
                                time.sleep(2)
                            ok = launch_game(pkg, gid) if gid else False
                            if ok:
                                self._log(f'{pkg}: launched OK')
                                last_seen[pkg] = time.time()
                            else:
                                self._log(f'{pkg}: launch failed')

            time.sleep(check_interval)

        for pkg in packages:
            self._set_status(pkg, 'Stopped')


rejoin_loop = RejoinLoop()
