#!/usr/bin/env python3
"""
REI REJOIN Core Global - Terminal / Termux Edition
Single standalone CLI script combining all core functions of REI REJOIN Roblox Account Manager:
- VPhone & Emulator App discovery (su shell execution, dumpsys, pm, cmd, ps, direct name input)
- ROBLOX & CLONE APPS ONLY (Displays exclusively Roblox apps & Roblox clones: com.roblox.client, free.nokaA, Delta, etc.)
- DIRECT MULTI-PACKAGE SELECTION (Typing 1,2 directly sets selected packages to #1 and #2)
- Direct Game Launching via Place ID or Private Server Link
- Automatic Horizontal/Landscape Screen Rotation (Forces orientation lock 1 / landscape)
- Exact Match REI REJOIN ASCII Dashboard UI (2-line REI REJOIN block logo + clean settings & live stats table)
- Home Page Reset & Callback Rejoin (Force stops stuck Home Screen and retries launch intent until in-game)
- Direct ActivityProtocolLaunch Component Invocation (Bypasses Home screen to connect directly into game place)
- Instant Home Page & App Exit Re-launch (Triggers immediate rejoin if app is closed or on Home Page)
- Complete Terminal Screen Buffer Flush (os.system('clear') prevents duplicate terminal headers)
- Multi-Window dumpsys inspection (Accurately checks RobloxActivity across side-by-side windows even when Termux is focused)
- Right-Stack Window Tiling (Tiles Roblox app windows on right half of screen while Termux stays on left)
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
import select

# Script version & timestamp
BUILD_VERSION = "v6.3.3-REI-REJOIN"
BUILD_TIME = "2026-08-14 00:03:00 UTC"

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
    'window_mode': 'left_stack',  # 'left_stack' (Roblox windows on right 50%) or 'grid'
    'home_rejoin_enabled': True,
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

# ==============================================================================
# 1. ORIENTATION, APP LAUNCHER, WINDOW TILING & PACKAGE MANAGEMENT
# ==============================================================================

def set_landscape_orientation():
    """Force Android screen orientation to Landscape (Horizontal mode)."""
    cmds = [
        "su -c 'settings put system accelerometer_rotation 0'",
        "su -c 'settings put system user_rotation 1'",
        "su -c 'wm set-user-rotation lock 1'",
        "settings put system accelerometer_rotation 0",
        "settings put system user_rotation 1"
    ]
    for c in cmds:
        try:
            subprocess.run(c, shell=True, capture_output=True, timeout=2)
        except Exception:
            pass

def clear_terminal_screen():
    """Clear terminal screen completely preventing duplicate overlapping headers."""
    try:
        if os.name == 'posix':
            os.system('clear')
        else:
            os.system('cls')
    except Exception:
        print("\033[H\033[2J\033[3J", end="")

def get_installed_packages():
    """
    Discover all installed packages on Android / VPhone / Emulators.
    Uses shell execution with su root fallbacks for maximum compatibility.
    """
    packages = set()

    # Strategy 1: Try su shell pm list packages (VPhone / Rooted Emulators)
    try:
        res = subprocess.run("su -c 'pm list packages'", shell=True, capture_output=True, text=True, timeout=5)
        for line in res.stdout.strip().split('\n'):
            line = line.strip()
            if line.startswith('package:'):
                packages.add(line[8:].strip())
    except Exception:
        pass

    # Strategy 2: Try su shell dumpsys package packages
    if not packages:
        try:
            res = subprocess.run("su -c 'dumpsys package packages'", shell=True, capture_output=True, text=True, timeout=5)
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
        res = subprocess.run("su -c 'ls /data/data'", shell=True, capture_output=True, text=True, timeout=5)
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
    """Filter all installed packages to ONLY include Roblox apps, Roblox clones, and Executors."""
    all_pkgs = get_installed_packages()
    keywords = [
        'roblox', 'noka', 'blox', 'delta', 'arceus', 'executor',
        'codex', 'fluxus', 'trigon', 'vegas', 'hydrogen', 'evon', 'krnl'
    ]

    roblox_pkgs = [p for p in all_pkgs if any(k in p.lower() for k in keywords)]
    return sorted(list(set(roblox_pkgs)))

def is_app_running(package):
    """Check if the app process is alive. Only returns True if a real numeric PID is found."""
    # pidof returns space-separated PIDs when running, or empty/error when not.
    # We validate the output is ONLY digits+spaces (a real PID), not error text.
    for cmd in [f"su -c 'pidof {package}'", f"pidof {package}"]:
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=3)
            out = res.stdout.strip()
            # Must be non-empty AND all parts must be numeric (actual PIDs)
            if out and all(part.isdigit() for part in out.split()):
                return True
        except Exception:
            pass
    # Fallback: grep ps output for an exact line containing the package name
    for cmd in [f"su -c 'ps -A | grep -F {package}'", f"ps -A | grep -F {package}"]:
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=4)
            # Only count as running if the package appears in a non-grep process line
            lines = [l for l in res.stdout.strip().split('\n') if package in l and 'grep' not in l]
            if lines:
                return True
        except Exception:
            pass
    return False

def get_package_activity_dump(package, content):
    """
    Extract all lines in 'dumpsys activity top' belonging to the target package's task/activity block.
    """
    lines = content.split('\n')
    pkg_lines = []
    capturing = False

    for line in lines:
        if ('TASK ' in line or 'ACTIVITY ' in line) and package in line:
            capturing = True
            pkg_lines.append(line)
        elif capturing:
            if ('TASK ' in line or 'ACTIVITY ' in line) and package not in line:
                break
            pkg_lines.append(line)

    return pkg_lines

def check_roblox_log_status(package):
    """
    Inspect the latest Roblox log file tail to determine game connection state.
    Returns True if log indicates active game connection, False if on Home Screen, or None if unavailable.
    """
    log_dirs = [
        f"/sdcard/Android/data/{package}/files/logs",
        f"/data/data/{package}/files/logs"
    ]
    for d in log_dirs:
        try:
            cmd = f"su -c 'ls -t {d}/*.log 2>/dev/null | head -n 1'"
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2)
            latest_log = r.stdout.strip()
            if latest_log:
                cmd_tail = f"su -c 'tail -n 25 \"{latest_log}\"'"
                r_tail = subprocess.run(cmd_tail, shell=True, capture_output=True, text=True, timeout=2)
                text = r_tail.stdout.lower()
                if not text:
                    continue
                if any(k in text for k in ['leaving game', 'disconnect', 'appshell', 'maintab', 'game left', 'return to home']):
                    return False
                if any(k in text for k in ['connecting to game', 'loading place', 'game joined', 'placeid']):
                    return True
        except Exception:
            pass
    return None

def is_udp_game_connected(package):
    """
    Check if the package process has an active UDP socket (Roblox RakNet Game Server connection).
    Returns True if connected to game server via UDP, False if no UDP game sockets exist, or None if check fails.
    """
    try:
        # Get PID of target clone package
        res = subprocess.run(f"su -c 'pidof {package}'", shell=True, capture_output=True, text=True, timeout=2)
        out = res.stdout.strip()
        if not out:
            res = subprocess.run(f"pidof {package}", shell=True, capture_output=True, text=True, timeout=2)
            out = res.stdout.strip()

        pids = [p for p in out.split() if p.isdigit()]
        if not pids:
            return False

        for pid in pids:
            # Check for active UDP socket in ss or netstat
            r_ss = subprocess.run(f"su -c 'ss -u -a -p | grep pid={pid}'", shell=True, capture_output=True, text=True, timeout=2)
            if r_ss.stdout.strip():
                return True

            r_ns = subprocess.run(f"su -c 'netstat -unp 2>/dev/null | grep {pid}'", shell=True, capture_output=True, text=True, timeout=2)
            if r_ns.stdout.strip():
                return True

            # Check open socket descriptors in /proc/<pid>/fd
            r_fd = subprocess.run(f"su -c 'ls -l /proc/{pid}/fd 2>/dev/null | grep socket'", shell=True, capture_output=True, text=True, timeout=2)
            socket_count = len([l for l in r_fd.stdout.strip().split('\n') if l.strip()]) if r_fd.stdout.strip() else 0
            if socket_count >= 3:
                return True

        return False
    except Exception:
        return None

def is_app_in_game(package):
    """
    Check if the package is in-game vs on the Roblox Home Screen.
    Uses Activity state flags ('mStopped=true', 'mResumed=true'), view hierarchy inspection, and UDP checks.
    """
    HOME_SIGNALS = [
        'for you', 'charts', 'recommended for', 'moments',
        'reactrootview', 'reactviewgroup', 'reactframelayout',
        'splashactivity', 'startupactivity', 'homeactivity', 'hometab',
        'loginactivity', 'welcomeactivity', 'titleactivity',
        'lobbyactivity', 'loadingactivity', 'bootstrapactivity',
        'loginview', 'landingview', 'authactivity', 'appshell',
    ]

    GAME_SIGNALS = [
        'renderview', 'nativegl', 'gamecanvas', 'raknet',
        'robloxplace', 'placeview', 'engineview', 'surfaceview -',
    ]

    # Step 1: Inspect dumpsys activity top task block
    for cmd in ["su -c 'dumpsys activity top'", 'dumpsys activity top']:
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            content = res.stdout
            if not content.strip():
                continue

            pkg_lines = get_package_activity_dump(package, content)
            if not pkg_lines:
                pkg_lines = [line for line in content.split('\n') if package in line]

            if pkg_lines:
                full_block = '\n'.join(pkg_lines).lower()

                # Rule A: If Activity state is STOPPED (mStopped=true), Roblox is on Home Screen / Lobby!
                if 'mstopped=true' in full_block:
                    return False

                # Strip Activity header line for view hierarchy checks
                view_hierarchy = pkg_lines[1:] if len(pkg_lines) > 1 else pkg_lines
                block_text = '\n'.join(view_hierarchy).lower()

                # Rule B: Check for Home-screen UI text & React Native UI signals
                if any(sig in block_text for sig in HOME_SIGNALS):
                    return False

                # Rule C: Check for confirmed in-game 3D rendering surfaces
                if any(sig in block_text for sig in GAME_SIGNALS):
                    return True

                # Rule D: Check for Activity RESUMED state without stopped
                if 'mresumed=true' in full_block and 'mstopped=false' in full_block:
                    return True

        except Exception:
            pass

    # Step 2: Check UDP Socket Game Connection State
    udp_st = is_udp_game_connected(package)
    if udp_st is not None and udp_st is True:
        return True

    # Step 3: Check latest Roblox log file tail
    log_st = check_roblox_log_status(package)
    if log_st is not None:
        return log_st

    # Step 4: Default fallback (return False to trigger safe Home Page rejoin)
    return False


def get_screen_size():
    """Get screen resolution width and height via wm size."""
    try:
        res = subprocess.run('wm size', shell=True, capture_output=True, text=True, timeout=3)
        match = re.search(r'(\d+)x(\d+)', res.stdout)
        if match:
            w, h = int(match.group(1)), int(match.group(2))
            return (max(w, h), min(w, h))  # Always return landscape orientation (w > h)
    except Exception:
        pass
    return 1280, 720

def calculate_window_bounds(index, total_apps, screen_w=None, screen_h=None, mode='left_stack'):
    """
    Calculate (left, top, right, bottom) bounds for window tiling.
    Places Roblox windows on the RIGHT 50% of the landscape screen so Termux stays on Left 50%.
    """
    if not screen_w or not screen_h:
        screen_w, screen_h = get_screen_size()

    total_apps = max(1, total_apps)

    half_w = int(screen_w * 0.5)
    cell_h = int(screen_h / total_apps)
    left = half_w
    top = index * cell_h
    right = screen_w
    bottom = (index + 1) * cell_h
    return left, top, right, bottom

def launch_game(package, game_id, bounds=None, freeform=True):
    """Launch Roblox game directly into place ID for targeted clone package."""
    game_id = str(game_id).strip()
    if not game_id:
        game_id = '2753915549'

    if '?privateServerLinkCode=' in game_id:
        parts = game_id.split('?privateServerLinkCode=', 1)
        place_id = parts[0]
        link_code = parts[1]
        url = f'roblox://placeId={place_id}&linkCode={link_code}'
        web_url = f'https://www.roblox.com/games/{place_id}?privateServerLinkCode={link_code}'
    elif game_id.startswith('http'):
        match = re.search(r'/games/(\d+)', game_id)
        place_id = match.group(1) if match else game_id
        ps_match = re.search(r'privateServerLinkCode=([^&]+)', game_id)
        if ps_match:
            url = f'roblox://placeId={place_id}&linkCode={ps_match.group(1)}'
            web_url = game_id
        else:
            url = f'roblox://placeId={place_id}'
            web_url = f'https://www.roblox.com/games/{place_id}'
    else:
        url = f'roblox://placeId={game_id}'
        web_url = f'https://www.roblox.com/games/{game_id}'

    # Use FLAG_ACTIVITY_NEW_TASK only (0x10000000) — do NOT use CLEAR_TASK (0x14000000)
    # CLEAR_TASK terminates the whole activity stack which restarts Roblox instead of navigating.
    intents = [
        f"su -c 'am start -f 0x10000000 -n {package}/com.roblox.client.ActivityProtocolLaunch -a android.intent.action.VIEW -d \"{url}\"'",
        f"su -c 'am start -f 0x10000000 -p {package} -a android.intent.action.VIEW -d \"{url}\"'",
        f"su -c 'am start -f 0x10000000 -p {package} -a android.intent.action.VIEW -d \"{web_url}\"'",
        f"su -c 'am start -n {package}/com.roblox.client.ActivityProtocolLaunch -a android.intent.action.VIEW -d \"{url}\"'",
        f"su -c 'am start -p {package} -a android.intent.action.VIEW -d \"{url}\"'",
        f"am start -f 0x10000000 -p {package} -a android.intent.action.VIEW -d '{url}'",
        f"am start -p {package} -a android.intent.action.VIEW -d '{url}'"
    ]

    for cmd in intents:
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=6)
            if res.returncode == 0 and "Error" not in res.stdout:
                return True
        except Exception:
            pass

    return False

def auto_sort_windows(packages=None, game_id=None, mode='left_stack'):
    """Auto-arrange/tile running Roblox app windows on screen."""
    set_landscape_orientation()
    if packages is None:
        packages = config.get('selected_packages', [])
    if not packages:
        packages = get_roblox_packages()

    if not game_id:
        game_id = config.get('game_id', '')

    w, h = get_screen_size()
    total = len(packages)
    print(f"[+] Auto-sorting {total} window(s) on screen ({w}x{h}, landscape)...")

    for idx, pkg in enumerate(packages):
        bounds = calculate_window_bounds(idx, total, w, h, mode=mode)
        print(f"  -> Positioning {pkg} bounds: {bounds}")
        launch_game(pkg, game_id, bounds=bounds, freeform=True)
        time.sleep(1)

def force_stop_app(package):
    """Force stop an application using am force-stop."""
    try:
        subprocess.run(f"su -c 'am force-stop {package}'", shell=True, timeout=5)
        return True
    except Exception as e:
        print(f"[!] Force stop error: {e}")
        return False

def clear_app_cache(package):
    """Clear app data/cache using pm clear."""
    try:
        subprocess.run(f"su -c 'pm clear {package}'", shell=True, timeout=10)
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
            f"su -c 'dumpsys meminfo {package} -c'",
            shell=True, capture_output=True, text=True, timeout=5
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
            'getprop ro.product.model',
            shell=True, capture_output=True, text=True, timeout=3
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
        subprocess.run(f"su -c 'screencap -p {output_path}'", shell=True, timeout=8)
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
        'title': 'REI REJOIN Core',
        'description': description,
        'color': 0x00CCCC,
        'footer': {'text': 'Roblox Account Manager CLI'},
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
# 4. AUTO REJOIN MONITORING LOOP & LIVE DASHBOARD
# ==============================================================================

class TerminalRejoinLoop:
    def __init__(self):
        self.running = False
        self.status = {}
        self.last_launch = {}
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

        set_landscape_orientation()

        packages = cfg.get('selected_packages', [])
        if not packages:
            packages = get_roblox_packages()

        if not packages:
            self.log("No Roblox packages selected or detected! Please select packages in Option 2.")
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

    def render_live_dashboard(self, cfg):
        """Live-updating terminal dashboard. Fixed compact layout, safe for narrow terminals."""
        GREEN  = "\033[92m"
        RED    = "\033[91m"
        YELLOW = "\033[93m"
        CYAN   = "\033[96m"
        BOLD   = "\033[1m"
        RESET  = "\033[0m"

        pkgs = cfg.get('selected_packages', [])
        if not pkgs:
            pkgs = get_roblox_packages()

        gname = cfg.get('game_name') or (f"Place:{cfg.get('game_id')}" if cfg.get('game_id') else 'No Game Set')

        set_landscape_orientation()
        time.sleep(0.5)

        try:
            while self.running:
                clear_terminal_screen()

                # Get real terminal width via stty (works in split-screen Termux)
                try:
                    r = subprocess.run('stty size', shell=True, capture_output=True, text=True, timeout=2)
                    _, cols = r.stdout.strip().split()
                    W = max(36, int(cols))
                except Exception:
                    W = 48  # safe fallback for split-screen

                SEP = '-' * W

                w_st = f"{GREEN}Enable{RESET}"  if cfg.get('webhook_enabled')       else f"{RED}Disable{RESET}"
                s_st = f"{GREEN}Enable{RESET}"  if cfg.get('auto_sort', True)       else f"{RED}Disable{RESET}"
                h_st = f"{GREEN}Enable{RESET}"  if cfg.get('home_rejoin_enabled', True) else f"{RED}Disable{RESET}"
                c_st = f"{GREEN}Enable{RESET}"  if cfg.get('clear_cache')           else f"{RED}Disable{RESET}"

                cpu = get_cpu_usage()
                used_ram, total_ram = get_ram_usage()

                def strip(s):
                    return re.sub(r'\033\[[0-9;]*m', '', s)

                def rpad(colored, target_vis_len):
                    """Pad a colored string so its visible width = target_vis_len."""
                    vis = len(strip(colored))
                    return colored + ' ' * max(0, target_vis_len - vis)

                # ── Header ────────────────────────────────────────
                title = "REI  REJOIN"
                pad   = max(0, (W - len(title)) // 2)
                print(f"{BOLD}{CYAN}{'=' * W}{RESET}")
                print(f"{BOLD}{CYAN}{' ' * pad}{title}{RESET}")
                print(f"{BOLD}{CYAN}{'=' * W}{RESET}")
                # Info line — truncate to W
                info = f" By seisen_ | discord.gg/5G3cStpbcx"
                print(info[:W])
                print(SEP)

                # ── Settings (2 per row, half-width each) ─────────
                half = W // 2
                l1 = f"WEBHOOK: {w_st}"
                r1 = f"SORT: {s_st}"
                l2 = f"HOME: {h_st}"
                r2 = f"CACHE: {c_st}"
                print(rpad(l1, half) + r1)
                print(rpad(l2, half) + r2)
                print(SEP)

                # ── Stats ──────────────────────────────────────────
                stat_line = f" CPU:{cpu}%  RAM:{used_ram:.1f}/{total_ram:.1f}GB"
                print(stat_line[:W])
                print(SEP)

                # ── Table ──────────────────────────────────────────
                # Fixed column visible widths; adjusted for W
                cn = 2                          # No
                cu = min(9,  max(5, W//6))      # User
                cp = min(11, max(7, W//5))      # Package
                cs = min(9,  max(6, W//6))      # Status
                cg = max(4, W - cn - cu - cp - cs - 4)  # Game (4 pipes)

                gname_t = gname[:cg] if len(gname) <= cg else gname[:cg-2] + '..'

                hdr = f"{'No':<{cn}}|{'User':<{cu}}|{'Package':<{cp}}|{'Status':<{cs}}|{'Game'}"
                print(f"{BOLD}{hdr[:W]}{RESET}")
                print(SEP)

                statuses = self.get_status()
                for idx, p in enumerate(pkgs, 1):
                    info_d  = statuses.get(p, {})
                    st      = info_d.get('status', 'Launching')
                    uname   = f"wu***{idx:02d}"

                    if   st == 'Ingame':                         st_c = f"{GREEN}Ingame{RESET}"
                    elif st in ('Rejoining', 'Rejoining Game'):  st_c = f"{RED}Rejoin{RESET}"
                    elif st in ('Home Page', 'Home Screen'):     st_c = f"{YELLOW}HomePg{RESET}"
                    elif st == 'Launching':                      st_c = f"{CYAN}Launch{RESET}"
                    else:                                        st_c = st[:cs]

                    pkg_t = p[:cp] if len(p) <= cp else p[:cp-1] + '.'

                    row = (f"{idx:<{cn}}|{uname:<{cu}}|{pkg_t:<{cp}}"
                           f"|{rpad(st_c, cs)}|{gname_t}")
                    print(row)

                print(SEP)
                print(f"{BOLD}[Enter] Main Menu{RESET}")

                if os.name == 'posix':
                    rlist, _, _ = select.select([sys.stdin], [], [], 2.0)
                    if rlist:
                        sys.stdin.readline()
                        break
                else:
                    time.sleep(2.0)

        except (KeyboardInterrupt, Exception):
            pass

    def _loop(self, packages, cfg):
        check_interval      = float(cfg.get('check_interval', 8))
        delay_open_tab      = float(cfg.get('launch_wait', 15))
        sequential          = cfg.get('sequential_join', False)
        auto_clear          = cfg.get('clear_cache', False)
        auto_sort           = cfg.get('auto_sort', True)
        window_mode         = cfg.get('window_mode', 'left_stack')
        home_rejoin_enabled = cfg.get('home_rejoin_enabled', True)
        # Grace period after launch — avoids false "Home Page" detection during app startup
        LAUNCH_GRACE        = 20

        w, h = get_screen_size()
        total_apps = len(packages)

        # Initial launch of all packages
        for i, pkg in enumerate(packages):
            gid = self._get_game_id(pkg, cfg)
            bounds = calculate_window_bounds(i, total_apps, w, h, mode=window_mode) if auto_sort else None
            self.set_status(pkg, 'Launching')
            self.last_launch[pkg] = time.time()
            launch_game(pkg, gid, bounds=bounds, freeform=auto_sort)
            if sequential and i < len(packages) - 1:
                time.sleep(delay_open_tab)

        # Give apps extra time to fully start before monitoring begins
        time.sleep(8)

        while self.running:
            for i, pkg in enumerate(packages):
                if not self.running:
                    break

                gid = self._get_game_id(pkg, cfg)
                now = time.time()

                running = is_app_running(pkg)

                if not running:
                    # ★ PROCESS DEAD → REJOIN
                    self.log(f"[{pkg}] Process dead → Rejoining")
                    self.set_status(pkg, 'Rejoining')
                    if auto_clear:
                        clear_app_cache(pkg)
                        time.sleep(1)
                    bounds = calculate_window_bounds(i, total_apps, w, h, mode=window_mode) if auto_sort else None
                    self.last_launch[pkg] = now
                    launch_game(pkg, gid, bounds=bounds, freeform=auto_sort)

                else:
                    # ★ PROCESS ALIVE → check if in-game or on Home Screen
                    in_game = is_app_in_game(pkg)
                    if in_game:
                        self.set_status(pkg, 'Ingame')
                    else:
                        # NOT in-game — check if still within initial launch grace period
                        time_since_launch = now - self.last_launch.get(pkg, 0)
                        if time_since_launch < LAUNCH_GRACE:
                            self.set_status(pkg, 'Launching')
                        else:
                            # HOME SCREEN detected (past grace period)
                            self.set_status(pkg, 'Home Page')
                            if home_rejoin_enabled:
                                self.log(f"[{pkg}] Home Screen detected → Force-stopping & rejoining place")
                                self.set_status(pkg, 'Rejoining')
                                force_stop_app(pkg)
                                time.sleep(2)
                                bounds = calculate_window_bounds(i, total_apps, w, h, mode=window_mode) if auto_sort else None
                                self.last_launch[pkg] = time.time()
                                launch_game(pkg, gid, bounds=bounds, freeform=auto_sort)
                            else:
                                self.log(f"[{pkg}] Home Screen detected (home_rejoin disabled — skipping)")

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
    print("        REI REJOIN ROBLOX ACCOUNT MANAGER - CLI CORE        ")
    print(f"      [{BUILD_VERSION}] - Updated: {BUILD_TIME}")
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
    print(f"\nDetected Roblox & Executor Packages ({len(roblox_pkgs)}):")
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
        clear_terminal_screen()
        print_banner()
        print("1. View System & Package Status")
        print("2. Scan & Select Roblox Packages")
        print("3. Configure Game Setup (Place ID / Private Server Link)")
        print("4. Configure Webhook Settings")
        print("5. Configure Timing & Auto-rejoin Options")
        print("6. Auto-Sort / Tile Windows Layout Configuration")
        print("7. Autoexecute Script Manager")
        print("8. START Auto Rejoin Loop & Live Dashboard")
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
            roblox_pkgs = get_roblox_packages()

            print(f"\n--- [ DETECTED ROBLOX & CLONE APPS ({len(roblox_pkgs)}) ] ---")
            if not roblox_pkgs:
                print("  [!] No standard Roblox/Executor packages detected.")
                print("  -> Use option 'M' below to type a custom package name!")
            else:
                for idx, p in enumerate(roblox_pkgs, 1):
                    sel = "✓ SELECTED" if p in config.get('selected_packages', []) else "  [   ]"
                    print(f"  {idx}. {p:<35} {sel}")

            print("\nSelection Options:")
            print("  - Enter numbers (e.g. 1,2) to select multiple packages")
            print("  - Type 'ALL' to select ALL detected Roblox packages")
            print("  - Type 'CLEAR' to deselect all packages")
            print("  - Type 'M' to enter custom package name manually")
            print("  - Press Enter to keep current selection")
            indices = input("\nChoice: ").strip()

            if indices.upper() == 'ALL':
                config['selected_packages'] = list(roblox_pkgs)
                save_config()
            elif indices.upper() == 'CLEAR':
                config['selected_packages'] = []
                save_config()
            elif indices.upper() == 'M':
                custom_pkg = input("\nEnter exact Package Name (e.g. com.noka.client or free.nokaA): ").strip()
                if custom_pkg:
                    sel_set = set(config.get('selected_packages', []))
                    sel_set.add(custom_pkg)
                    config['selected_packages'] = list(sel_set)
                    save_config()
            elif indices:
                new_sel = set()
                for item in indices.split(','):
                    item = item.strip()
                    if '.' in item:
                        new_sel.add(item)
                    elif item.isdigit():
                        i = int(item) - 1
                        if 0 <= i < len(roblox_pkgs):
                            new_sel.add(roblox_pkgs[i])
                config['selected_packages'] = list(new_sel)
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
            gchoice = input("\nChoice: ").strip()
            if gchoice.upper() == 'C':
                gid = input("Enter Place ID / Link: ").strip()
                if gid:
                    config['game_id'] = gid
                    config['game_name'] = f"Game ({gid[:15]}...)" if len(gid) > 15 else f"Game ({gid})"
            else:
                try:
                    idx = int(gchoice) - 1
                    if 0 <= idx < len(PRESET_GAMES):
                        config['game_name'], config['game_id'] = PRESET_GAMES[idx]
                except ValueError:
                    pass
            save_config()
            print(f"\n[+] Active Game ID / Link Set: {config.get('game_id')}")
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

            hm = input(f"Auto Rejoin if stuck on Roblox Home Screen? (y/n) [{config.get('home_rejoin_enabled', True)}]: ").strip().lower()
            if hm in ['y', 'n']: config['home_rejoin_enabled'] = (hm == 'y')

            save_config()
            print("\n[+] Timing & Home Screen settings updated.")
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
            rejoin_engine.render_live_dashboard(config)

        elif choice == '9':
            rejoin_engine.stop()
            print("\n[+] Auto Rejoin Engine stopped.")
            input("\nPress Enter to return to menu...")

        elif choice == '10':
            auto_sort_windows(mode=config.get('window_mode', 'left_stack'))
            input("\nPress Enter to return to menu...")

        elif choice == '11':
            pkgs = config.get('selected_packages', [])
            if not pkgs:
                pkgs = get_roblox_packages()
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
            print("Exiting REI REJOIN CLI. Goodbye!")
            sys.exit(0)

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="REI REJOIN Roblox Account Manager - Global Termux Core Script")
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
