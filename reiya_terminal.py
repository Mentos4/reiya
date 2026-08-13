#!/usr/bin/env python3
"""
Reiya Core Global - Terminal / Termux Edition
Single standalone CLI script combining all core functions of Reiya Roblox Account Manager:
- VPhone & Emulator App discovery (su shell execution, dumpsys, pm, cmd, ps, direct name input)
- Game launching (Roblox intents & link parsing)
- Freeform Window Tiling & Auto-Sorting on screen
- System monitoring (CPU, RAM, Uptime, Screenshots)
- Discord Webhook reporting with screenshot attachments
- Automatic Rejoin loop (Retry, Cooldown, Sequential, Cache clear, Auto-Sort)
- Autoexecute script management
"""

import os
import sys
import time
import json
import re
import math
import argparse
import subprocess
import threading
import urllib.request
import urllib.parse
import mimetypes

# ==============================================================================
# DEFAULT PRESETS & CONFIGURATION
# ==============================================================================

PRESET_GAMES = [
    ('Blox Fruits',                '2753915549'),
    ('Sailor Piece',               '16232032796'),
    ('King Legacy',                '5032219830'),
    ('Bee Swarm Simulator',        '1537690962'),
    ('Pet Simulator 99',           '8737899170'),
    ('Attack on Titan Revolution', '13822889351'),
    ('Grow a Garden 2',            '126884695'),
]

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'config.json')

DEFAULT_CONFIG = {
    'rejoin_interval': 9999999,
    'offline_wait': 15,
    'retry_count': 3,
    'retry_delay': 30,
    'check_interval': 10,
    'launch_wait': 15,
    'rejoin_cooldown': 10,
    'sequential_join': False,
    'clear_cache': False,
    'webhook_enabled': False,
    'selected_packages': [],
    'game_method': 'all',
    'game_id': '',
    'game_name': '',
    'package_games': {},
    'webhook_url': '',
    'webhook_interval': 60,
    'autoexecute_path': '/sdcard/Delta/Autoexecute',
    'auto_sort': True,
    'window_mode': 'left_stack',  # 'left_stack' (vertical stack on left) or 'grid' (2x2 grid)
}

# Global config state
config = DEFAULT_CONFIG.copy()

def load_config():
    global config
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved = json.load(f)
            config.update(saved)
        except Exception as e:
            print(f"[!] Warning loading config: {e}")
    return config

def save_config():
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2, default=str)
    print(f"[+] Configuration saved to {CONFIG_FILE}")

# ==============================================================================
# 1. APP LAUNCHER, WINDOW TILING & PACKAGE MANAGEMENT
# ==============================================================================

def get_installed_packages():
    """
    Discover all installed packages on Android / VPhone / Emulators.
    Uses shell execution with su root fallbacks for maximum compatibility.
    """
    packages = set()

    # Strategy 1: Try su shell pm list packages (VPhone / Rooted Emulators)
    try:
        res = subprocess.run('su -c "pm list packages"', shell=True, capture_output=True, text=True, timeout=5)
        for line in res.stdout.strip().split('\n'):
            line = line.strip()
            if line.startswith('package:'):
                packages.add(line[8:].strip())
    except Exception:
        pass

    # Strategy 2: Try su shell dumpsys package packages
    if not packages:
        try:
            res = subprocess.run('su -c "dumpsys package packages"', shell=True, capture_output=True, text=True, timeout=5)
            for line in res.stdout.strip().split('\n'):
                match = re.search(r'Package \[([^\]]+)\]', line)
                if match:
                    packages.add(match.group(1).strip())
        except Exception:
            pass

    # Strategy 3: Standard pm commands
    if not packages:
        for cmd in ['pm list packages -3', 'pm list packages', 'cmd package list packages', '/system/bin/pm list packages']:
            try:
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                for line in res.stdout.strip().split('\n'):
                    line = line.strip()
                    if line.startswith('package:'):
                        packages.add(line[8:].strip())
            except Exception:
                pass

    # Strategy 4: Try su -c "ls /data/data"
    try:
        res = subprocess.run('su -c "ls /data/data"', shell=True, capture_output=True, text=True, timeout=5)
        for line in res.stdout.strip().split('\n'):
            pkg = line.strip()
            if pkg and '.' in pkg and not pkg.startswith('/'):
                packages.add(pkg)
    except Exception:
        pass

    # Strategy 5: Extract running process names via ps -A
    try:
        res = subprocess.run('ps -A', shell=True, capture_output=True, text=True, timeout=5)
        for line in res.stdout.strip().split('\n'):
            parts = line.strip().split()
            if parts:
                name = parts[-1]
                if '.' in name and not name.startswith('[') and not name.startswith('/'):
                    packages.add(name)
    except Exception:
        pass

    return sorted(list(packages))

def get_roblox_packages():
    """Detect all installed packages dynamically."""
    return get_installed_packages()

def is_app_running(package):
    """Check if process is currently running using pidof and ps -A."""
    try:
        result = subprocess.run(
            ['pidof', package],
            capture_output=True, text=True, timeout=3
        )
        if result.stdout.strip():
            return True
    except Exception:
        pass
    try:
        result = subprocess.run(
            ['ps', '-A'], capture_output=True, text=True, timeout=5
        )
        return package in result.stdout
    except Exception:
        return False

def get_screen_size():
    """Get screen resolution width and height via wm size."""
    try:
        res = subprocess.run(['wm', 'size'], capture_output=True, text=True, timeout=3)
        match = re.search(r'(\d+)x(\d+)', res.stdout)
        if match:
            return int(match.group(1)), int(match.group(2))
    except Exception:
        pass
    return 1280, 720

def calculate_window_bounds(index, total_apps, screen_w=None, screen_h=None, mode='left_stack'):
    """
    Calculate (left, top, right, bottom) bounds for window tiling.
    Modes:
    - 'left_stack': Stacks windows vertically on the left half of screen (matching multi-instance layout)
    - 'grid': Tiles windows in an even N x M grid across the screen
    """
    if not screen_w or not screen_h:
        screen_w, screen_h = get_screen_size()

    total_apps = max(1, total_apps)

    if mode == 'left_stack':
        half_w = int(screen_w * 0.5)
        cell_h = int(screen_h / total_apps)
        left = 0
        top = index * cell_h
        right = half_w
        bottom = (index + 1) * cell_h
        return left, top, right, bottom

    # Default 'grid' mode
    cols = math.ceil(math.sqrt(total_apps))
    rows = math.ceil(total_apps / cols)
    cell_w = int(screen_w / cols)
    cell_h = int(screen_h / rows)

    r = index // cols
    c = index % cols

    left = c * cell_w
    top = r * cell_h
    right = (c + 1) * cell_w
    bottom = (r + 1) * cell_h
    return left, top, right, bottom

def launch_game(package, game_id, bounds=None, freeform=True):
    """Launch Roblox game via Android Intent with optional freeform windowing and bounds positioning."""
    game_id = str(game_id).strip()
    if '?privateServerLinkCode=' in game_id:
        parts = game_id.split('?privateServerLinkCode=', 1)
        place_id = parts[0]
        link_code = parts[1]
        url = f'roblox://placeId={place_id}&linkCode={link_code}'
    elif game_id.startswith('http'):
        match = re.search(r'/games/(\d+)', game_id)
        place_id = match.group(1) if match else game_id
        ps_match = re.search(r'privateServerLinkCode=([^&]+)', game_id)
        if ps_match:
            url = f'roblox://placeId={place_id}&linkCode={ps_match.group(1)}'
        else:
            url = f'roblox://placeId={place_id}'
    else:
        url = f'roblox://placeId={game_id}'

    cmd = ['am', 'start', '-a', 'android.intent.action.VIEW', '-d', url]
    if freeform:
        cmd.extend(['--windowingMode', '5'])
    if bounds:
        l, t, r, b = bounds
        cmd.extend(['--bounds', f'{l},{t},{r},{b}'])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return True
    except Exception as e:
        print(f"[!] Intent freeform launch failed: {e}")

    # Fallback to standard intent without bounds/freeform
    try:
        result = subprocess.run(
            ['am', 'start', '-a', 'android.intent.action.VIEW', '-d', url],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass

    # Fallback to monkey launcher
    try:
        subprocess.run(
            ['monkey', '-p', package, '-c', 'android.intent.category.LAUNCHER', '1'],
            capture_output=True, timeout=10
        )
        return True
    except Exception as e:
        print(f"[!] Monkey launch failed: {e}")
        return False

def auto_sort_windows(packages=None, game_id=None, mode='left_stack'):
    """Auto-arrange/tile running Roblox app windows on screen."""
    if packages is None:
        packages = config.get('selected_packages', [])
    if not packages:
        print("[!] No packages specified to sort.")
        return

    if not game_id:
        game_id = config.get('game_id', '')

    w, h = get_screen_size()
    total = len(packages)
    print(f"[+] Auto-sorting {total} window(s) on screen ({w}x{h}, mode: {mode})...")

    for idx, pkg in enumerate(packages):
        bounds = calculate_window_bounds(idx, total, w, h, mode=mode)
        print(f"  -> Positioning {pkg} bounds: {bounds}")
        launch_game(pkg, game_id, bounds=bounds, freeform=True)
        time.sleep(1)

def force_stop_app(package):
    """Force stop an application using am force-stop."""
    try:
        subprocess.run(['am', 'force-stop', package], timeout=5)
        return True
    except Exception as e:
        print(f"[!] Force stop error: {e}")
        return False

def clear_app_cache(package):
    """Clear app data/cache using pm clear."""
    try:
        subprocess.run(['pm', 'clear', package], timeout=10)
        return True
    except Exception as e:
        print(f"[!] Clear cache error: {e}")
        return False

# ==============================================================================
# 2. DEVICE & SYSTEM STATISTICS
# ==============================================================================

_prev_idle = None
_prev_total = None

def get_cpu_usage():
    global _prev_idle, _prev_total
    try:
        with open('/proc/stat') as f:
            fields = f.readline().split()
        idle = int(fields[4])
        total = sum(int(x) for x in fields[1:8])
        if _prev_idle is None:
            _prev_idle, _prev_total = idle, total
            return 0.0
        idle_diff = idle - _prev_idle
        total_diff = total - _prev_total
        _prev_idle, _prev_total = idle, total
        if total_diff == 0:
            return 0.0
        return round((1.0 - idle_diff / total_diff) * 100, 1)
    except Exception:
        return 0.0

def get_ram_usage():
    try:
        meminfo = {}
        with open('/proc/meminfo') as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    meminfo[parts[0].rstrip(':')] = int(parts[1])
        total_kb = meminfo.get('MemTotal', 0)
        avail_kb = meminfo.get('MemAvailable', 0)
        used_kb = total_kb - avail_kb
        return used_kb / 1024 / 1024, total_kb / 1024 / 1024  # GB
    except Exception:
        return 0.0, 0.0

def get_process_ram(package):
    try:
        result = subprocess.run(
            ['dumpsys', 'meminfo', package, '-c'],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split('\n'):
            if 'TOTAL' in line:
                parts = line.split(',')
                if len(parts) > 1:
                    return int(parts[1].strip()) // 1024  # MB
        return 0
    except Exception:
        return 0

def get_device_name():
    try:
        result = subprocess.run(
            ['getprop', 'ro.product.model'],
            capture_output=True, text=True, timeout=3
        )
        return result.stdout.strip() or 'Unknown'
    except Exception:
        return 'Unknown'

def format_uptime(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}h:{m:02d}m:{s:02d}s"

def take_screenshot(output_path='/sdcard/roblox_mgr_shot.png'):
    try:
        subprocess.run(['screencap', '-p', output_path], timeout=8)
        if os.path.exists(output_path):
            return output_path
    except Exception:
        pass
    return None

# ==============================================================================
# 3. DISCORD WEBHOOK SENDER
# ==============================================================================

def send_discord_webhook(webhook_url, statuses=None, start_time=None):
    if not webhook_url:
        return

    cpu = get_cpu_usage()
    used_ram, total_ram = get_ram_usage()
    device = get_device_name()
    uptime_sec = time.time() - (start_time or time.time())
    uptime = format_uptime(uptime_sec)

    app_lines = ''
    if statuses:
        parts = []
        for i, (pkg, info) in enumerate(statuses.items(), 1):
            status = info.get('status', 'Unknown')
            ram = get_process_ram(pkg)
            parts.append(
                f'**{i}.** {status} | `{pkg}`\n'
                f'    RAM: {ram} MB'
            )
        if parts:
            app_lines = '\n'.join(parts)

    description = (
        f'**Device:** {device}\n'
        f'**Uptime:** {uptime}\n'
        f'**CPU:** {cpu}% / 100%\n'
        f'**RAM:** {used_ram:.2f} / {total_ram:.2f} GB\n'
    )
    if app_lines:
        description += f'\n**Application Details:**\n{app_lines}'

    embed = {
        'title': 'Wuyx Rejoin (Termux Core)',
        'description': description,
        'color': 0x00CCCC,
        'footer': {'text': 'Roblox Manager CLI'},
    }

    payload = {'embeds': [embed]}
    screenshot_path = take_screenshot()

    if screenshot_path and os.path.exists(screenshot_path):
        try:
            boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
            body = []
            
            body.append(f'--{boundary}'.encode('utf-8'))
            body.append('Content-Disposition: form-data; name="payload_json"'.encode('utf-8'))
            body.append('Content-Type: application/json'.encode('utf-8'))
            body.append(''.encode('utf-8'))
            body.append(json.dumps(payload).encode('utf-8'))

            with open(screenshot_path, 'rb') as f:
                img_data = f.read()

            body.append(f'--{boundary}'.encode('utf-8'))
            body.append('Content-Disposition: form-data; name="file"; filename="screenshot.png"'.encode('utf-8'))
            body.append('Content-Type: image/png'.encode('utf-8'))
            body.append(''.encode('utf-8'))
            body.append(img_data)
            body.append(f'--{boundary}--'.encode('utf-8'))
            body.append(''.encode('utf-8'))

            payload_bytes = b'\r\n'.join(body)

            req = urllib.request.Request(
                webhook_url,
                data=payload_bytes,
                headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
                method='POST'
            )
            urllib.request.urlopen(req, timeout=20)
            print("[+] Webhook sent with screenshot.")
            return
        except Exception as e:
            print(f"[!] Webhook multipart send failed, falling back to JSON: {e}")

    try:
        data_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            webhook_url,
            data=data_bytes,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        urllib.request.urlopen(req, timeout=15)
        print("[+] Webhook JSON sent.")
    except Exception as e:
        print(f"[!] Webhook JSON send error: {e}")

class WebhookThread(threading.Thread):
    def __init__(self, webhook_url, interval, get_status_fn, start_time):
        super().__init__(daemon=True)
        self.webhook_url = webhook_url
        self.interval = interval
        self.get_status_fn = get_status_fn
        self.start_time = start_time
        self.running = True

    def run(self):
        while self.running:
            try:
                send_discord_webhook(self.webhook_url, self.get_status_fn(), self.start_time)
            except Exception as e:
                print(f"[!] Webhook thread error: {e}")
            time.sleep(max(10, self.interval))

    def stop(self):
        self.running = False

# ==============================================================================
# 4. AUTO REJOIN MONITORING LOOP
# ==============================================================================

class TerminalRejoinLoop:
    def __init__(self):
        self.running = False
        self.status = {}
        self.thread = None
        self.start_time = None
        self.webhook_thread = None

    def log(self, msg):
        ts = time.strftime('%H:%M:%S')
        print(f"[{ts}] {msg}")

    def set_status(self, pkg, status_str):
        self.status[pkg] = {'status': status_str, 'time': time.time()}

    def get_status(self):
        return dict(self.status)

    def _get_game_id(self, pkg, cfg):
        method = cfg.get('game_method', 'all')
        if method == 'each':
            pkg_games = cfg.get('package_games', {})
            return pkg_games.get(pkg, cfg.get('game_id', ''))
        return cfg.get('game_id', '')

    def start(self, cfg):
        if self.running:
            print("[!] Auto rejoin is already running.")
            return False

        packages = cfg.get('selected_packages', [])
        if not packages:
            self.log("No packages selected! Use option 2 to select packages.")
            return False

        self.running = True
        self.start_time = time.time()

        if cfg.get('webhook_enabled') and cfg.get('webhook_url'):
            self.webhook_thread = WebhookThread(
                cfg.get('webhook_url'),
                float(cfg.get('webhook_interval', 60)),
                self.get_status,
                self.start_time
            )
            self.webhook_thread.start()

        self.thread = threading.Thread(
            target=self._loop,
            args=(list(packages), dict(cfg)),
            daemon=True
        )
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        if self.webhook_thread:
            self.webhook_thread.stop()
        self.log("Auto rejoin loop stopped.")

    def _loop(self, packages, cfg):
        offline_wait   = float(cfg.get('offline_wait', 15))
        max_retries    = int(cfg.get('retry_count', 3))
        retry_delay    = float(cfg.get('retry_delay', 30))
        check_interval = float(cfg.get('check_interval', 10))
        delay_open_tab = float(cfg.get('launch_wait', 15))
        sequential     = cfg.get('sequential_join', False)
        auto_clear     = cfg.get('clear_cache', False)
        auto_sort      = cfg.get('auto_sort', True)
        window_mode    = cfg.get('window_mode', 'left_stack')

        retries   = {p: 0 for p in packages}
        last_seen = {p: time.time() for p in packages}

        game_name = cfg.get('game_name', 'Unknown')
        self.log(f"Starting auto rejoin — Game: {game_name}")
        self.log(f"Packages ({len(packages)}): {', '.join(packages)}")
        self.log(f"Check interval: {check_interval}s | Offline wait: {offline_wait}s")

        w, h = get_screen_size()
        total_apps = len(packages)

        for i, pkg in enumerate(packages):
            gid = self._get_game_id(pkg, cfg)
            if not gid:
                self.log(f"WARNING: No game set for {pkg}, skipping launch.")
                self.set_status(pkg, 'No game set')
                continue

            bounds = calculate_window_bounds(i, total_apps, w, h, mode=window_mode) if auto_sort else None
            self.log(f"Launching {pkg} -> Place {gid} (Bounds: {bounds})")
            self.set_status(pkg, 'Launching')
            launch_game(pkg, gid, bounds=bounds, freeform=auto_sort)
            if sequential and i < len(packages) - 1:
                time.sleep(delay_open_tab)

        if not sequential and delay_open_tab > 0:
            time.sleep(delay_open_tab)

        while self.running:
            for i, pkg in enumerate(packages):
                if not self.running:
                    break

                gid = self._get_game_id(pkg, cfg)
                running = is_app_running(pkg)

                if running:
                    self.set_status(pkg, 'Ingame')
                    last_seen[pkg] = time.time()
                    retries[pkg] = 0
                else:
                    self.set_status(pkg, 'Waiting')
                    offline_secs = time.time() - last_seen[pkg]

                    if offline_secs >= offline_wait:
                        if retries[pkg] >= max_retries:
                            self.log(f"{pkg}: max retries ({max_retries}) hit! Cooldown {retry_delay}s...")
                            self.set_status(pkg, 'Cooldown')
                            time.sleep(retry_delay)
                            retries[pkg] = 0
                            last_seen[pkg] = time.time()
                        else:
                            retries[pkg] += 1
                            attempt = f"{retries[pkg]}/{max_retries}"
                            self.log(f"{pkg}: Rejoining attempt {attempt}...")
                            if auto_clear:
                                self.log(f"{pkg}: Clearing cache...")
                                clear_app_cache(pkg)
                                time.sleep(2)

                            bounds = calculate_window_bounds(i, total_apps, w, h, mode=window_mode) if auto_sort else None
                            ok = launch_game(pkg, gid, bounds=bounds, freeform=auto_sort) if gid else False
                            if ok:
                                self.log(f"{pkg}: Launch request sent OK.")
                                last_seen[pkg] = time.time()
                            else:
                                self.log(f"{pkg}: Launch request failed!")

            time.sleep(check_interval)

        for pkg in packages:
            self.set_status(pkg, 'Stopped')

rejoin_engine = TerminalRejoinLoop()

# ==============================================================================
# 5. AUTOEXECUTE MANAGEMENT
# ==============================================================================

def list_autoexecute_files(folder_path):
    try:
        os.makedirs(folder_path, exist_ok=True)
        return sorted(os.listdir(folder_path))
    except Exception as e:
        print(f"[!] Error reading autoexecute folder: {e}")
        return []

def add_autoexecute_script(folder_path, filename, code):
    try:
        os.makedirs(folder_path, exist_ok=True)
        full_path = os.path.join(folder_path, filename)
        with open(full_path, 'w') as f:
            f.write(code)
        print(f"[+] Script saved to {full_path}")
        return True
    except Exception as e:
        print(f"[!] Failed to save script: {e}")
        return False

# ==============================================================================
# 6. INTERACTIVE CLI MENU & DAEMON MODE
# ==============================================================================

def print_banner():
    print("\n" + "=" * 60)
    print("      REIYA ROBLOX ACCOUNT MANAGER - TERMUX CLI CORE       ")
    print("=" * 60)

def show_status():
    print("\n--- [ SYSTEM & APP STATUS ] ---")
    device = get_device_name()
    cpu = get_cpu_usage()
    used_ram, total_ram = get_ram_usage()
    w, h = get_screen_size()
    print(f"Device: {device} | Screen Resolution: {w}x{h}")
    print(f"CPU: {cpu}% | RAM: {used_ram:.2f} / {total_ram:.2f} GB")

    roblox_pkgs = get_roblox_packages()
    print(f"\nPackages Installed ({len(roblox_pkgs)}):")
    for pkg in roblox_pkgs:
        running = is_app_running(pkg)
        status_str = "RUNNING" if running else "STOPPED"
        ram = get_process_ram(pkg) if running else 0
        selected = "*" if pkg in config.get('selected_packages', []) else " "
        print(f" [{selected}] {pkg:<35} [{status_str:<7}] RAM: {ram}MB")
    print("=" * 60)

def interactive_menu():
    load_config()
    while True:
        print_banner()
        print("1. View System & Package Status")
        print("2. Scan & Select Roblox Packages")
        print("3. Configure Game Setup (Place ID / Private Server Link)")
        print("4. Configure Webhook Settings")
        print("5. Configure Timing & Auto-rejoin Options")
        print("6. Auto-Sort / Tile Windows Layout Configuration")
        print("7. Autoexecute Script Manager")
        print("8. START Auto Rejoin Loop")
        print("9. STOP Auto Rejoin Loop")
        print("10. Auto-Sort / Tile Open Windows NOW")
        print("11. Test Launch Selected Package Now")
        print("12. Send Manual Discord Webhook Test")
        print("0. Exit CLI")
        choice = input("\nSelect option: ").strip()

        if choice == '1':
            show_status()
            input("\nPress Enter to return to menu...")
        elif choice == '2':
            pkgs = get_roblox_packages()
            print(f"\n--- [ ALL DETECTED INSTALLED PACKAGES ({len(pkgs)}) ] ---")
            if not pkgs:
                print("  [!] No packages automatically detected via sandbox permissions.")
            else:
                for idx, p in enumerate(pkgs, 1):
                    sel = "SELECTED" if p in config.get('selected_packages', []) else "---"
                    print(f"  {idx}. {p} [{sel}]")

            print("\nSelection Options:")
            print("  - Enter numbers (e.g. 1,2) to toggle packages from list")
            print("  - Type package name directly (e.g. com.noka.client or com.roblox.client)")
            print("  - Type 'M' to prompt for custom package name")
            print("  - Press Enter to keep current selection")
            indices = input("\nChoice: ").strip()

            if indices.upper() == 'M':
                custom_pkg = input("\nEnter exact Package Name (e.g. com.noka.client or com.roblox.client): ").strip()
                if custom_pkg:
                    sel_set = set(config.get('selected_packages', []))
                    sel_set.add(custom_pkg)
                    config['selected_packages'] = list(sel_set)
                    save_config()
            elif indices:
                sel_set = set(config.get('selected_packages', []))
                for item in indices.split(','):
                    item = item.strip()
                    if '.' in item: # Direct package name like com.noka.client
                        sel_set.add(item)
                    elif item.isdigit():
                        i = int(item) - 1
                        if 0 <= i < len(pkgs):
                            target = pkgs[i]
                            if target in sel_set:
                                sel_set.remove(target)
                            else:
                                sel_set.add(target)
                config['selected_packages'] = list(sel_set)
                save_config()

            print("\n--- [ CURRENT SELECTED PACKAGES ] ---")
            if config.get('selected_packages'):
                for p in config.get('selected_packages'):
                    print(f"  ✓ {p}")
            else:
                print("  (None selected)")
            input("\nPress Enter to return to menu...")

        elif choice == '3':
            print("\nPreset Games:")
            for idx, (gname, gid) in enumerate(PRESET_GAMES, 1):
                print(f"  {idx}. {gname} (ID: {gid})")
            print("  C. Custom Place ID or Private Server Link")
            gchoice = input("Choice: ").strip()
            if gchoice.upper() == 'C':
                gid = input("Enter Place ID / Link: ").strip()
                gname = input("Enter Game Name: ").strip() or "Custom Game"
                config['game_id'] = gid
                config['game_name'] = gname
            else:
                try:
                    idx = int(gchoice) - 1
                    if 0 <= idx < len(PRESET_GAMES):
                        config['game_name'], config['game_id'] = PRESET_GAMES[idx]
                except ValueError:
                    pass
            save_config()
            print(f"\n[+] Active Game Set: {config.get('game_name')} (ID: {config.get('game_id')})")
            input("\nPress Enter to return to menu...")

        elif choice == '4':
            print(f"\nCurrent Webhook: {config.get('webhook_url', 'None')}")
            wurl = input("Enter Discord Webhook URL (leave empty to keep current): ").strip()
            if wurl:
                config['webhook_url'] = wurl
            wenable = input("Enable Webhook updates? (y/n): ").strip().lower() == 'y'
            config['webhook_enabled'] = wenable
            wint = input("Webhook interval in seconds [default 60]: ").strip()
            if wint.isdigit():
                config['webhook_interval'] = int(wint)
            save_config()
            print(f"\n[+] Webhook Enabled: {config.get('webhook_enabled')} | Interval: {config.get('webhook_interval')}s")
            input("\nPress Enter to return to menu...")

        elif choice == '5':
            print("\nTiming Settings:")
            check_in = input(f"Check Interval seconds [{config.get('check_interval', 10)}]: ").strip()
            if check_in.isdigit(): config['check_interval'] = int(check_in)

            off_w = input(f"Offline Wait seconds [{config.get('offline_wait', 15)}]: ").strip()
            if off_w.isdigit(): config['offline_wait'] = int(off_w)

            ret_c = input(f"Max Retries [{config.get('retry_count', 3)}]: ").strip()
            if ret_c.isdigit(): config['retry_count'] = int(ret_c)

            seq = input(f"Sequential Join? (y/n) [{config.get('sequential_join', False)}]: ").strip().lower()
            if seq in ['y', 'n']: config['sequential_join'] = (seq == 'y')

            clr = input(f"Clear Cache on Rejoin? (y/n) [{config.get('clear_cache', False)}]: ").strip().lower()
            if clr in ['y', 'n']: config['clear_cache'] = (clr == 'y')

            save_config()
            print("\n[+] Timing settings updated.")
            input("\nPress Enter to return to menu...")

        elif choice == '6':
            print("\n--- [ AUTO-SORT / WINDOW TILING LAYOUT ] ---")
            print(f"Current Auto-Sort Enabled: {config.get('auto_sort', True)}")
            print(f"Current Layout Mode: {config.get('window_mode', 'left_stack')}")
            print("\n1. Enable/Disable Auto-Sort")
            print("2. Set Mode: Left Vertical Stack (Matching side-by-side layout)")
            print("3. Set Mode: Grid Layout (Even N x M grid across screen)")
            lch = input("Select option: ").strip()
            if lch == '1':
                config['auto_sort'] = not config.get('auto_sort', True)
                print(f"[+] Auto-Sort set to: {config['auto_sort']}")
            elif lch == '2':
                config['window_mode'] = 'left_stack'
                print("[+] Window mode set to: Left Vertical Stack")
            elif lch == '3':
                config['window_mode'] = 'grid'
                print("[+] Window mode set to: Grid Layout")
            save_config()
            input("\nPress Enter to return to menu...")

        elif choice == '7':
            path = config.get('autoexecute_path', '/sdcard/Delta/Autoexecute')
            files = list_autoexecute_files(path)
            print(f"\nAutoexecute Directory ({path}):")
            for f in files:
                print(f" - {f}")
            print("\n1. Add New Script File")
            print("2. Back")
            ach = input("Select option: ").strip()
            if ach == '1':
                fname = input("Filename (e.g. script.lua): ").strip()
                print("Enter script content (end with EOF on a line by itself):")
                lines = []
                while True:
                    line = input()
                    if line.strip() == 'EOF':
                        break
                    lines.append(line)
                add_autoexecute_script(path, fname, '\n'.join(lines))
            input("\nPress Enter to return to menu...")

        elif choice == '8':
            rejoin_engine.start(config)
            print("\n[+] Auto Rejoin Engine started in background.")
            input("\nPress Enter to return to menu...")

        elif choice == '9':
            rejoin_engine.stop()
            print("\n[+] Auto Rejoin Engine stopped.")
            input("\nPress Enter to return to menu...")

        elif choice == '10':
            auto_sort_windows(mode=config.get('window_mode', 'left_stack'))
            input("\nPress Enter to return to menu...")

        elif choice == '11':
            pkgs = config.get('selected_packages', [])
            gid = config.get('game_id', '')
            if not pkgs or not gid:
                print("[!] Please configure selected packages and game ID first.")
            else:
                for idx, p in enumerate(pkgs):
                    bounds = calculate_window_bounds(idx, len(pkgs), mode=config.get('window_mode', 'left_stack'))
                    print(f"Launching {p} with Game ID {gid} at {bounds}...")
                    launch_game(p, gid, bounds=bounds, freeform=True)
            input("\nPress Enter to return to menu...")

        elif choice == '12':
            wurl = config.get('webhook_url')
            if not wurl:
                print("[!] No webhook URL set!")
            else:
                print("Sending test webhook...")
                send_discord_webhook(wurl, rejoin_engine.get_status(), time.time())
            input("\nPress Enter to return to menu...")

        elif choice == '0':
            if rejoin_engine.running:
                rejoin_engine.stop()
            print("Exiting Reiya CLI. Goodbye!")
            sys.exit(0)

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Reiya Roblox Account Manager - Global Termux Core Script")
    parser.add_argument("--daemon", action="store_true", help="Run auto-rejoin immediately in headless daemon mode")
    parser.add_argument("--scan", action="store_true", help="Scan installed Roblox packages and list them")
    parser.add_argument("--sort", action="store_true", help="Auto-sort and tile open Roblox windows on screen")
    args = parser.parse_args()

    load_config()

    if args.scan:
        show_status()
        return

    if args.sort:
        auto_sort_windows(mode=config.get('window_mode', 'left_stack'))
        return

    if args.daemon:
        print("[+] Starting in Daemon Mode...")
        rejoin_engine.start(config)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            rejoin_engine.stop()
            print("\n[+] Daemon stopped.")
        return

    interactive_menu()

if __name__ == '__main__':
    main()
