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
- System monitoring (CPU, Uptime, Screenshots)
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
BUILD_VERSION = "v6.8.20-REI-REJOIN"
BUILD_TIME = "2026-08-31 20:27:54 UTC"

# ==============================================================================
# DEFAULT PRESETS & CONFIGURATION
# ==============================================================================

PRESET_GAMES = [
    ('The Forge',          '76558904092080'),
    ('Anime Origin',       '129932912185311'),
    ('Anime Expedition',   '84515722934860'),
    ('Run a Restaurant',   '77843161404023'),
    ('World Zero',         '2727067538'),
    ('Blue Heater 2',      '16893821047'),
    ('Grow a Garden 2',    '126884695'),
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
    'package_game_names': {},
    'webhook_url': '',
    'webhook_interval': 60,
    'autoexecute_path': '/sdcard/Delta/Autoexecute',
    'auto_sort': True,
    'window_mode': 'left_stack',  # 'left_stack' (Roblox windows on right 50%) or 'grid'
    'home_rejoin_enabled': True,
    'dashboard_width': 40,  # live dashboard table width in columns; user-tunable via Option 6.4
}

# Global config state
config = DEFAULT_CONFIG.copy()

def _place_id_from_game_value(game_value):
    """Extract a Roblox place ID from an ID, game URL, or private-server link."""
    value = str(game_value or '').strip()
    match = re.search(r'/games/(\d+)|(?:^|[?&])placeId=(\d+)', value)
    if match:
        return match.group(1) or match.group(2)
    numeric_prefix = re.match(r'^(\d+)(?:\?|$)', value)
    return numeric_prefix.group(1) if numeric_prefix else ''

def lookup_roblox_game_name(game_value):
    """Fetch a Roblox experience name for the dashboard; fall back to its place ID."""
    place_id = _place_id_from_game_value(game_value)
    fallback = f"Game ({place_id[:15]}...)" if len(place_id) > 15 else f"Game ({place_id})"
    if not place_id:
        return fallback
    try:
        headers = {'User-Agent': 'REI-REJOIN/1.0'}
        universe_request = urllib.request.Request(
            f'https://apis.roblox.com/universes/v1/places/{urllib.parse.quote(place_id)}/universe',
            headers=headers
        )
        with urllib.request.urlopen(universe_request, timeout=8) as response:
            universe_id = json.loads(response.read().decode('utf-8')).get('universeId')
        if not universe_id:
            return fallback
        game_request = urllib.request.Request(
            'https://games.roblox.com/v1/games?universeIds=' + urllib.parse.quote(str(universe_id)),
            headers=headers
        )
        with urllib.request.urlopen(game_request, timeout=8) as response:
            games = json.loads(response.read().decode('utf-8')).get('data', [])
        if games and games[0].get('name'):
            return str(games[0]['name'])
    except Exception:
        pass
    return fallback
def _is_generated_game_name(name):
    return bool(re.match(r'^(Game \(|Place:)', str(name or '')))

def load_config():
    global config
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved = json.load(f)
            config.update(saved)
            renamed = False
            if config.get('game_id') and _is_generated_game_name(config.get('game_name')):
                config['game_name'] = lookup_roblox_game_name(config['game_id'])
                renamed = True
            package_games = config.get('package_games', {})
            package_names = config.setdefault('package_game_names', {})
            for package, game_value in package_games.items():
                if _is_generated_game_name(package_names.get(package)):
                    package_names[package] = lookup_roblox_game_name(game_value)
                    renamed = True
            if renamed:
                save_config()
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

def run_cmd(cmd, timeout=5):
    """Thin subprocess.run(shell=True, timeout=N) wrapper, kept deliberately
    simple. Two earlier attempts at making this "smarter" — start_new_session
    (setsid) and then process_group=0 — each broke su in a different way on
    real devices (setsid detached the controlling terminal/session that su
    needs to grant root; process_group=0 then caused the dashboard to hang
    before its first frame). Both were chasing a minor problem (orphaned
    grandchild processes on the rare timeout) by risking a much worse one
    (su silently failing, or the whole UI stalling). Plain subprocess.run is
    what reliably worked before any of that, so that's what this stays as —
    do not reintroduce process-group/session tricks here without testing
    directly against a real su binary first."""
    try:
        res = subprocess.run(
            cmd, shell=True,
            capture_output=True, text=True, timeout=timeout,
        )
        return res
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, -1, '', '')
    except Exception:
        return subprocess.CompletedProcess(cmd, -1, '', '')

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
            run_cmd(c, timeout=2)
        except Exception:
            pass

def clear_terminal_screen():
    """Redraw from the top without spawning ``clear``/``cls`` every frame."""
    # Direct ANSI control codes work in Termux and avoid a shell subprocess
    # stealing the terminal while the live dashboard is refreshing.
    sys.stdout.write("\033[H\033[2J\033[3J")
    sys.stdout.flush()

def prompt(text):
    return input(text)

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
    for cmd in [f"su -c 'pidof {package}'", f"pidof {package}"]:
        try:
            res = run_cmd(cmd, timeout=3)
            out = res.stdout.strip()
            # Must be non-empty AND all parts must be numeric (actual PIDs)
            if out and all(part.isdigit() for part in out.split()):
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

def get_activity_top_dump():
    """Fetch 'dumpsys activity top' once. This is a system-wide dump (same
    content regardless of which package you're checking), so callers
    monitoring multiple packages should fetch it ONCE per poll cycle and
    reuse it for every package — calling it per-package multiplies an
    already-heavy su+dumpsys invocation by the package count, which was a
    major source of the CPU/battery load causing slowdowns on constrained
    Termux/VPhone devices."""
    for cmd in ["su -c 'dumpsys activity top'", 'dumpsys activity top']:
        try:
            res = run_cmd(cmd, timeout=4)
            if res.stdout.strip():
                return res.stdout
        except Exception:
            pass
    return ''

def is_app_in_game(package, content=None):
    """
    Check if package is in-game vs on Roblox Home Screen using dumpsys activity top.
    Rule-compliant: Checks HOME_SIGNALS vs GAME_SIGNALS, fallbacks to False if package not found in dump.
    `content` may be passed in (a dump already fetched via get_activity_top_dump())
    to avoid re-running the heavy dumpsys command per package; if omitted, it is
    fetched here for backwards compatibility.
    """
    HOME_SIGNALS = [
        'mainactivity', 'splashactivity', 'loginactivity', 'welcomeactivity',
        'titleactivity', 'lobbyactivity', 'loadingactivity', 'bootstrapactivity',
        'loginview', 'landingview', 'authactivity', 'appshell', 'for you',
        'charts', 'recommended for', 'moments', 'reactrootview', 'reactviewgroup',
        'reactframelayout', 'activityprotocollaunch', 'homeactivity', 'hometab'
    ]
    # Note: 'robloxactivity' is excluded because RobloxActivity hosts React Home UI as well as game view
    GAME_SIGNALS = [
        'renderview', 'nativemain', 'gameactivity', 'surfaceview', 'glsurfaceview'
    ]

    if content is None:
        content = get_activity_top_dump()

    if content.strip():
        pkg_lines = get_package_activity_dump(package, content)
        if not pkg_lines:
            pkg_lines = [line for line in content.split('\n') if package in line]
        if pkg_lines:
            block_text = '\n'.join(pkg_lines).lower()
            # 1. Check for explicit Home Screen / React UI signals FIRST
            if any(sig in block_text for sig in HOME_SIGNALS):
                return False
            # 2. Check for explicit 3D Game rendering signals
            if any(sig in block_text for sig in GAME_SIGNALS):
                return True
            # 3. Default fallback if ambiguous
            return False

    # Default fallback when package is not found in activity dump: False (safe rejoin as mandated by AGENTS.md)
    return False



def get_screen_size():
    """Get screen resolution width and height via wm size."""
    try:
        res = run_cmd('wm size', timeout=3)
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
            res = run_cmd(cmd, timeout=6)
            if res.returncode == 0 and "Error" not in res.stdout:
                return True
        except Exception:
            pass

    return False

def _resolve_package_game_id(pkg, cfg):
    """Resolve active Game ID or Private Server Link for a specific package."""
    method = cfg.get('game_method', 'all')
    if method == 'each':
        pkg_games = cfg.get('package_games', {})
        return pkg_games.get(pkg, cfg.get('game_id', ''))
    return cfg.get('game_id', '')

def _resolve_package_game_name(pkg, cfg):
    """Resolve display name of the configured game for a specific package."""
    method = cfg.get('game_method', 'all')
    if method == 'each':
        pkg_names = cfg.get('package_game_names', {})
        if pkg in pkg_names and pkg_names[pkg]:
            return pkg_names[pkg]
        gid = cfg.get('package_games', {}).get(pkg, '')
        if gid:
            for gname, pid in PRESET_GAMES:
                if pid == gid:
                    return gname
            return f"Place:{gid[:12]}"
    gname = cfg.get('game_name')
    if gname:
        return gname
    gid = cfg.get('game_id')
    return f"Place:{gid[:12]}" if gid else 'No Game Set'

def auto_sort_windows(packages=None, game_id=None, mode='left_stack'):
    """Auto-arrange/tile running Roblox app windows on screen."""
    set_landscape_orientation()
    if packages is None:
        packages = config.get('selected_packages', [])
    if not packages:
        packages = get_roblox_packages()

    w, h = get_screen_size()
    total = len(packages)
    print(f"[+] Auto-sorting {total} window(s) on screen ({w}x{h}, landscape)...")

    for idx, pkg in enumerate(packages):
        bounds = calculate_window_bounds(idx, total, w, h, mode=mode)
        print(f"  -> Positioning {pkg} bounds: {bounds}")
        pkg_gid = game_id or _resolve_package_game_id(pkg, config)
        launch_game(pkg, pkg_gid, bounds=bounds, freeform=True)
        time.sleep(1)

def force_stop_app(package):
    """Force stop an application using am force-stop."""
    try:
        run_cmd(f"su -c 'am force-stop {package}'", timeout=5)
        return True
    except Exception as e:
        print(f"[!] Force stop error: {e}")
        return False

def clear_app_cache(package):
    """Clear app data/cache using pm clear."""
    try:
        run_cmd(f"su -c 'pm clear {package}'", timeout=10)
        return True
    except Exception as e:
        print(f"[!] Clear cache error: {e}")
        return False

# ==============================================================================
# 2. DEVICE & SYSTEM STATISTICS
# ==============================================================================

_prev_idle = None
_prev_total = None
_prev_stat_content = None
_last_cpu_pct = 0.0
_proc_read_mode = {}   # path -> 'direct' | 'su' | 'unavailable', decided once per path
_proc_su_cache = {}    # path -> (content, timestamp) — last successful su read

SU_READ_MIN_INTERVAL = 1  # Keep the fallback cache brief; each 5s dashboard redraw requests a fresh /proc sample.

def _read_proc_file(path, timeout=2):
    """Reads a /proc file, remembering which method actually works so we
    don't keep re-trying a failing one. The dashboard calls this every ~5s
    for as long as it's open — if a path needs su and su ALSO fails (or
    isn't granted), retrying su every single frame forever was itself the
    likely cause of the dashboard appearing to hang/not show up: repeated
    su invocations can trigger root-manager prompts or delays that steal
    focus from Termux. Once a path is confirmed 'unavailable' we stop
    invoking su for it entirely instead of retrying forever, and even when
    su DOES work we throttle re-invoking it to once every
    SU_READ_MIN_INTERVAL seconds (reusing the last reading in between)
    rather than shelling out to su on every single dashboard frame."""
    mode = _proc_read_mode.get(path)

    if mode != 'su':
        try:
            with open(path) as f:
                content = f.read()
            _proc_read_mode[path] = 'direct'
            return content
        except Exception:
            pass

    if mode != 'unavailable':
        cached = _proc_su_cache.get(path)
        if cached and (time.time() - cached[1]) < SU_READ_MIN_INTERVAL:
            return cached[0]
        res = run_cmd(f"su -c 'cat {path}'", timeout=timeout)
        if res.stdout:
            _proc_read_mode[path] = 'su'
            _proc_su_cache[path] = (res.stdout, time.time())
            return res.stdout
        if cached:
            return cached[0]

    _proc_read_mode[path] = 'unavailable'
    return None

def get_cpu_usage():
    """Reads /proc/stat's aggregate 'cpu' line and diffs it against the
    previous read to get a % since last call. Direct open() fails with
    PermissionError on many Android 8+ devices — /proc/stat is restricted
    to root for non-privileged apps (Termux included) by SELinux/hidepid —
    which silently swallowed the exception and made CPU sit frozen at
    0.0% forever.

    _read_proc_file() throttles su-based reads and reuses the last content
    string in between (see SU_READ_MIN_INTERVAL). Diffing against that same
    unchanged content would produce a 0 delta and report 0% on every one of
    those repeated calls, so this only recomputes the percentage when the
    underlying content actually changed, holding the last real reading
    otherwise instead of flickering to 0%."""
    global _prev_idle, _prev_total, _prev_stat_content, _last_cpu_pct
    try:
        content = _read_proc_file('/proc/stat')
        if not content:
            return _last_cpu_pct
        if content == _prev_stat_content:
            return _last_cpu_pct
        _prev_stat_content = content

        line = content.split('\n', 1)[0]
        fields = line.split()
        idle = int(fields[4])
        total = sum(int(x) for x in fields[1:8])
        if _prev_idle is None:
            _prev_idle, _prev_total = idle, total
            return _last_cpu_pct
        idle_diff = idle - _prev_idle
        total_diff = total - _prev_total
        _prev_idle, _prev_total = idle, total
        if total_diff == 0:
            return _last_cpu_pct
        _last_cpu_pct = round((1.0 - idle_diff / total_diff) * 100, 1)
        return _last_cpu_pct
    except Exception:
        return _last_cpu_pct

def get_ram_usage():
    """Returns live physical RAM usage as (percent, used, total) MiB.

    Android can keep MemAvailable nearly unchanged after an app closes because
    released pages become reclaimable cache. MemFree is the live free-page
    counter, so total minus it reflects physical RAM currently occupied by the
    system, cache, and applications at each dashboard refresh.
    """
    try:
        content = _read_proc_file('/proc/meminfo')
        if not content:
            return 0.0, 0, 0
        values = {}
        for line in content.splitlines():
            key, _, value = line.partition(':')
            parts = value.split()
            if parts and parts[0].isdigit():
                values[key] = int(parts[0])  # /proc/meminfo values are KiB

        total_kib = values.get('MemTotal', 0)
        free_kib = values.get('MemFree', values.get('MemAvailable', 0))
        if total_kib <= 0:
            return 0.0, 0, 0
        used_kib = max(0, min(total_kib, total_kib - free_kib))
        return round(used_kib * 100.0 / total_kib, 1), round(used_kib / 1024), round(total_kib / 1024)
    except Exception:
        return 0.0, 0, 0
def get_device_name():
    try:
        result = run_cmd('getprop ro.product.model', timeout=3)
        return result.stdout.strip() or 'Unknown'
    except Exception:
        return 'Unknown'

def format_uptime(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}h:{m:02d}m:{s:02d}s"

def take_screenshot(output_path=None):
    """Capture through screencap stdout so the Termux process owns the PNG file."""
    output_path = output_path or os.path.join(os.path.expanduser('~'), '.rei_rejoin_screenshot.png')
    for command in ("su -c 'screencap -p'", 'screencap -p'):
        try:
            result = subprocess.run(command, shell=True, capture_output=True, timeout=8)
            if result.returncode == 0 and result.stdout.startswith(b'\x89PNG\r\n\x1a\n'):
                with open(output_path, 'wb') as image_file:
                    image_file.write(result.stdout)
                return output_path
        except Exception:
            pass
    return None

def normalize_webhook_url(webhook_url):
    """Correct a common pasted `https>` typo and reject malformed webhook URLs."""
    url = str(webhook_url or '').strip().replace('https>://', 'https://').replace('http>://', 'http://').replace('https>', 'https:').replace('http>', 'http:')
    markdown_match = re.fullmatch(r'\[(https?://[^\]]+)\]\(https?://[^)]+\)', url)
    if markdown_match:
        url = markdown_match.group(1)
    parsed = urllib.parse.urlparse(url)
    return url if parsed.scheme in ('https', 'http') and parsed.netloc else ''
# ==============================================================================
# 3. DISCORD WEBHOOK SENDER
# ==============================================================================

def send_discord_webhook(webhook_url, statuses=None, start_time=None):
    webhook_url = normalize_webhook_url(webhook_url)
    if not webhook_url:
        print('[!] Invalid Discord webhook URL. Paste the full https://discord.com/api/webhooks/... URL.')
        return

    cpu = get_cpu_usage()
    ram_pct, ram_used_mib, ram_total_mib = get_ram_usage()
    device = get_device_name()
    uptime_sec = time.time() - (start_time or time.time())
    uptime = format_uptime(uptime_sec)

    app_lines = ''
    if statuses:
        parts = []
        for i, (pkg, info) in enumerate(statuses.items(), 1):
            status = info.get('status', 'Unknown')
            parts.append(f'**{i}.** {status} | `{pkg}`')
        if parts:
            app_lines = '\n'.join(parts)

    description = (
        f'**Device:** {device}\n'
        f'**Uptime:** {uptime}\n'
        f'**CPU:** {cpu}% / 100%\n'
        f'**RAM:** {ram_pct}% ({ram_used_mib}/{ram_total_mib} MiB)\n'
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
    # Ignore malformed device proxy environment variables for direct Discord delivery.
    webhook_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    screenshot_path = take_screenshot()

    # curl avoids urllib's malformed-proxy handling on some Termux environments.
    try:
        curl_args = ['curl', '-sS', '-o', '/dev/null', '-w', '%{http_code}', '-X', 'POST',
                     '-F', 'payload_json=' + json.dumps(payload)]
        if screenshot_path and os.path.exists(screenshot_path):
            curl_args += ['-F', 'file=@' + screenshot_path + ';type=image/png']
        curl_args.append(webhook_url)
        curl_result = subprocess.run(curl_args, capture_output=True, text=True, timeout=30)
        if curl_result.returncode == 0 and curl_result.stdout.strip().startswith('2'):
            print('[+] Webhook sent with screenshot.' if screenshot_path else '[+] Webhook JSON sent.')
            return
        print(f"[!] curl webhook send failed: {curl_result.stderr.strip() or curl_result.stdout.strip()}")
    except Exception as e:
        print(f"[!] curl webhook send error: {e}")

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
            webhook_opener.open(req, timeout=20)
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
        webhook_opener.open(req, timeout=15)
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
        """Writes explicit \\r\\n like render_live_dashboard's out() — this
        runs on the background _loop thread, which keeps emitting log lines
        after the user leaves the dashboard (Option 8 only stops the display,
        not the engine — Option 9 does that). A bare print()'s '\\n' doesn't
        always get translated to CRLF on Termux ptys, so without this the
        background thread's output staircases and corrupts every menu screen
        drawn afterward, making the CLI look frozen/unresponsive."""
        ts = time.strftime('%H:%M:%S')
        sys.stdout.write(f"[{ts}] {msg}\r\n")
        sys.stdout.flush()

    def set_status(self, pkg, status_str):
        self.status[pkg] = {'status': status_str, 'time': time.time()}

    def get_status(self):
        return dict(self.status)

    def _get_game_id(self, pkg, cfg):
        return _resolve_package_game_id(pkg, cfg)

    def _get_game_name(self, pkg, cfg):
        return _resolve_package_game_name(pkg, cfg)

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
        """Live-updating terminal dashboard. Fixed pipe-bordered table layout —
        one setting per line and one cell per column, so nothing depends on
        packing two colored strings onto a shared line (that packing was the
        source of the earlier misalignment). The terminal width is re-measured
        on every refresh (not just once at startup), so rotating the device
        mid-session realigns the layout on the very next redraw instead of
        leaving it broken until the app is restarted."""
        GREEN  = "\033[92m"
        RED    = "\033[91m"
        YELLOW = "\033[93m"
        CYAN   = "\033[96m"
        BLUE   = "\033[94m"
        BOLD   = "\033[1m"
        RESET  = "\033[0m"

        pkgs = cfg.get('selected_packages', [])
        if not pkgs:
            pkgs = get_roblox_packages()

        def strip(s):
            return re.sub(r'\033\[[0-9;]*m', '', s)

        def out(s=""):
            """print() relies on the terminal translating '\\n' to CRLF (moving
            the cursor back to column 0). On a pty/terminal where that
            translation isn't happening, '\\n' only moves down a row and each
            line starts wherever the previous one's cursor ended up, producing
            a diagonal staircase effect. Writing '\\r\\n' explicitly makes the
            column-0 return independent of the terminal's line-ending mode."""
            sys.stdout.write(str(s) + "\r\n")

        def detect_width(fallback):
            """Probe the real terminal width fresh each call. Reserves one
            trailing column: a line that exactly fills the terminal defers its
            wrap, sticking the next print's first char onto the same row.
            Uses os.get_terminal_size() (a plain ioctl syscall) instead of
            shelling out to 'stty size'/'tput cols' — forking a shell every
            5s to re-probe width was expensive enough on constrained
            Termux/VPhone devices to cause noticeable slowdowns/crashes while
            the dashboard was open. Falls back to the subprocess probe only
            if the syscall isn't available (e.g. stdout isn't a real tty)."""
            try:
                val = os.get_terminal_size().columns
                if val > 10:
                    return max(30, val - 1)
            except Exception:
                pass
            for cmd in ['stty size', 'tput cols']:
                try:
                    r = run_cmd(cmd, timeout=1)
                    parts = r.stdout.strip().split()
                    val = parts[-1] if parts else ''
                    if val.isdigit() and int(val) > 10:
                        return max(30, int(val) - 1)
                except Exception:
                    pass
            return fallback

        def build_layout(target_w):
            """Derive column widths + row-building helpers for one frame from
            a target total width. For N pipe-bordered columns, total width =
            sum(width) + 3*N + 1, so the content budget to split across
            columns is target - (3*N + 1)."""
            N = 5
            budget = max(20, target_w - (3 * N + 1))
            no_w, user_w, status_w = 2, 7, 6
            remaining = max(8, budget - no_w - user_w - status_w)
            pkg_w  = max(4, remaining * 2 // 5)
            game_w = max(4, remaining - pkg_w)
            # Short header labels so they never overflow a narrow column on their own.
            cols = [("No", no_w), ("User", user_w), ("Pkg", pkg_w), ("Stat", status_w), ("Game", game_w)]
            total_w = sum(w + 3 for _, w in cols) + 1  # " val " + trailing "|" per col, + leading "|"

            def cell(val, width):
                """' val ' padded so the VISIBLE length (ANSI codes excluded) is
                width+2, matching the separator's '-' * (width+2) segments
                exactly. Truncates as a safety net so a too-long value can
                never push the column (and every column after it) out of
                alignment."""
                s = str(val)
                vis = len(strip(s))
                if vis > width:
                    plain = strip(s)
                    s = (plain[:max(1, width - 1)] + '.') if width >= 1 else ''
                    vis = len(s)
                return f" {s}{' ' * max(0, width - vis)} "

            def pipe_row(cells_and_widths):
                return "|" + "|".join(cell(v, w) for v, w in cells_and_widths) + "|"

            def table_row(values):
                return pipe_row(zip(values, (w for _, w in cols)))

            sep = "-" * total_w
            table_sep = "|" + "|".join("-" * (w + 2) for _, w in cols) + "|"

            return cols, total_w, cell, pipe_row, table_row, sep, table_sep

        input_fd = None
        saved_terminal_mode = None
        termios_module = None
        try:
            # Termux's buffered TextIO stdin can miss readiness notifications
            # after the dashboard has been redrawn. Read the TTY directly in
            # cbreak mode so one Enter key always exits this screen.
            if os.name == 'posix':
                import termios
                import tty
                candidate_fd = sys.stdin.fileno()
                if os.isatty(candidate_fd):
                    saved_terminal_mode = termios.tcgetattr(candidate_fd)
                    tty.setcbreak(candidate_fd)
                    input_fd = candidate_fd
                    termios_module = termios

            while self.running:
                clear_terminal_screen()

                target_w = detect_width(cfg.get('dashboard_width', 40))
                COLS, TOTAL_W, cell, pipe_row, table_row, SEP, TABLE_SEP = build_layout(target_w)

                w_st = f"{GREEN}Enable{RESET}"  if cfg.get('webhook_enabled')       else f"{RED}Disable{RESET}"
                s_st = f"{GREEN}Enable{RESET}"  if cfg.get('auto_sort', True)       else f"{RED}Disable{RESET}"
                h_st = f"{GREEN}Enable{RESET}"  if cfg.get('home_rejoin_enabled', True) else f"{RED}Disable{RESET}"
                c_st = f"{GREEN}Enable{RESET}"  if cfg.get('clear_cache')           else f"{RED}Disable{RESET}"
                game_mode = 'CUSTOM PER PACKAGE' if cfg.get('game_method') == 'each' else 'SAME GAME FOR ALL'

                cpu = get_cpu_usage()
                ram_pct, ram_used_mib, ram_total_mib = get_ram_usage()

                # ── Header ────────────────────────────────────────
                title = "REI REJOIN"
                pad = max(0, (TOTAL_W - len(f">>> {title} <<<")) // 2)
                out(f"{BOLD}{CYAN}{' ' * pad}>>> {title} <<<{RESET}")
                out(f"{BLUE}Discord: discord.gg/5G3cStpbcx{RESET}")
                out(f"{BLUE}By seisen_{RESET}")
                out(f"{CYAN}GAME MODE: {game_mode}{RESET}")
                out(f"WEBHOOK: {w_st}")
                out(f"AUTO SORT: {s_st}")
                out(f"HOME REJOIN: {h_st}")
                out(f"CLEAR CACHE: {c_st}")
                out(SEP)

                # ── Stats ──────────────────────────────────────────
                sampled_at = time.strftime('%H:%M:%S')
                out(pipe_row([(f"CPU {cpu}% | RAM {ram_pct}% ({ram_used_mib}/{ram_total_mib} MiB) | {sampled_at}", TOTAL_W - 3)]))
                out(SEP)

                # ── Table ──────────────────────────────────────────
                out(f"{BOLD}{table_row([label for label, _ in COLS])}{RESET}")
                out(TABLE_SEP)

                statuses = self.get_status()
                for idx, p in enumerate(pkgs, 1):
                    info_d  = statuses.get(p, {})
                    st      = info_d.get('status', 'Launching')
                    uname   = f"wu***{idx:02d}"

                    if   st == 'Ingame':                         st_c = f"{GREEN}Ingame{RESET}"
                    elif st in ('Rejoining', 'Rejoining Game'):  st_c = f"{RED}Rejoin{RESET}"
                    elif st in ('Home Page', 'Home Screen'):     st_c = f"{YELLOW}HomePg{RESET}"
                    elif st == 'Launching':                      st_c = f"{CYAN}Launch{RESET}"
                    else:                                        st_c = st

                    pkg_w = COLS[2][1]
                    pkg_t = p if len(p) <= pkg_w else p[:pkg_w - 1] + '.'
                    game_w = COLS[4][1]
                    pkg_gname = _resolve_package_game_name(p, cfg)
                    gname_t = pkg_gname if len(pkg_gname) <= game_w else pkg_gname[:game_w - 2] + '..'

                    out(table_row([idx, uname, pkg_t, st_c, gname_t]))

                out(SEP)
                out(f"{BOLD}[Enter] Stop Auto Rejoin & Main Menu{RESET}")
                sys.stdout.flush()

                if input_fd is not None:
                    rlist, _, _ = select.select([input_fd], [], [], 5.0)
                    if rlist and os.read(input_fd, 1) in (b'\r', b'\n'):
                        self.stop()
                        break
                elif os.name == 'posix':
                    # Non-TTY fallback, for redirected input only.
                    rlist, _, _ = select.select([sys.stdin], [], [], 5.0)
                    if rlist:
                        sys.stdin.readline()
                        self.stop()
                        break
                else:
                    time.sleep(5.0)

        except (KeyboardInterrupt, Exception):
            pass
        finally:
            if input_fd is not None and saved_terminal_mode is not None:
                try:
                    termios_module.tcsetattr(input_fd, termios_module.TCSADRAIN, saved_terminal_mode)
                except Exception:
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
            try:
                # Fetched once per cycle and reused for every package below —
                # dumpsys activity top is system-wide and identical per package,
                # so calling it per-package multiplied a heavy su+dumpsys call by
                # the package count on every poll.
                activity_dump = get_activity_top_dump()

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
                        in_game = is_app_in_game(pkg, content=activity_dump)
                        if in_game:
                            self.set_status(pkg, 'Ingame')
                        else:
                            # NOT in-game — check if still within launch grace period (20s)
                            time_since_launch = now - self.last_launch.get(pkg, 0)
                            if time_since_launch < LAUNCH_GRACE:
                                self.set_status(pkg, 'Launching')
                            else:
                                # HOME SCREEN detected (past 20s grace period)
                                self.set_status(pkg, 'Home Page')
                                if home_rejoin_enabled:
                                    self.log(f"[{pkg}] Home Screen detected → Force stopping & rejoining place")
                                    self.set_status(pkg, 'Rejoining')
                                    force_stop_app(pkg)
                                    time.sleep(2)
                                    bounds = calculate_window_bounds(i, total_apps, w, h, mode=window_mode) if auto_sort else None
                                    self.last_launch[pkg] = time.time()
                                    launch_game(pkg, gid, bounds=bounds, freeform=auto_sort)
                                else:
                                    self.log(f"[{pkg}] Home Screen detected (home_rejoin disabled — skipping)")
            except Exception as e:
                # A single bad cycle (e.g. an unexpected su/dumpsys hiccup)
                # must not silently kill this daemon thread — that would
                # leave self.running stuck True forever with no rejoin
                # actually happening and no visible sign anything died.
                self.log(f"[!] Rejoin cycle error (continuing): {e}")

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
    ram_pct, ram_used_mib, ram_total_mib = get_ram_usage()
    w, h = get_screen_size()
    print(f"Device: {device} | Screen Resolution: {w}x{h}")
    print(f"CPU: {cpu}%")
    print(f"RAM: {ram_pct}% ({ram_used_mib}/{ram_total_mib} MiB)")
    print(f"Game Mode: {'CUSTOM PER PACKAGE' if config.get('game_method') == 'each' else 'SAME GAME FOR ALL'}")

    roblox_pkgs = get_roblox_packages()
    print(f"\nDetected Roblox & Executor Packages ({len(roblox_pkgs)}):")
    for pkg in roblox_pkgs:
        running = is_app_running(pkg)
        status_str = "RUNNING" if running else "STOPPED"
        selected = "*" if pkg in config.get('selected_packages', []) else " "
        pkg_gname = _resolve_package_game_name(pkg, config)
        print(f" [{selected}] {pkg:<30} [{status_str:<7}] Game: {pkg_gname:<18}")
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
        print("10. Auto-Sort / Tile Open Windows NOW")
        print("11. Test Launch Selected Package Now")
        print("12. Send Manual Discord Webhook Test")
        print("0. Exit CLI")
        choice = prompt("\nSelect option: ").strip()

        if choice == '1':
            show_status()
            prompt("\nPress Enter to return to menu...")
        elif choice == '2':
            while True:
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
                print("  - Enter numbers (e.g. 1,2) to ADD packages to your selection")
                print("  - Type 'ALL' to select ALL detected Roblox packages")
                print("  - Type 'CLEAR' to deselect all packages")
                print("  - Type 'M' to enter custom package name manually")
                print("  - Press Enter to keep current selection")
                indices = prompt("\nChoice: ").strip()

                if indices.upper() == 'ALL':
                    config['selected_packages'] = list(roblox_pkgs)
                    save_config()
                elif indices.upper() == 'CLEAR':
                    config['selected_packages'] = []
                    save_config()
                elif indices.upper() == 'M':
                    custom_pkg = prompt("\nEnter exact Package Name (e.g. com.noka.client or free.nokaA): ").strip()
                    if custom_pkg:
                        sel_set = set(config.get('selected_packages', []))
                        sel_set.add(custom_pkg)
                        config['selected_packages'] = list(sel_set)
                        save_config()
                elif indices:
                    sel_set = set(config.get('selected_packages', []))
                    for item in indices.split(','):
                        item = item.strip()
                        if '.' in item:
                            sel_set.add(item)
                        elif item.isdigit():
                            i = int(item) - 1
                            if 0 <= i < len(roblox_pkgs):
                                sel_set.add(roblox_pkgs[i])
                    config['selected_packages'] = list(sel_set)
                    save_config()

                print("\n--- [ CURRENT SELECTED PACKAGES ] ---")
                if config.get('selected_packages'):
                    for p in config.get('selected_packages'):
                        print(f"  ✓ {p}")
                else:
                    print("  (None selected)")

                again = prompt("\nAdd/change another package now? (y/n, default n): ").strip().lower()
                if again != 'y':
                    break
            prompt("\nPress Enter to return to menu...")

        elif choice == '3':
            while True:
                print("\n--- [ CONFIGURE GAME SETUP ] ---")
                print(f"Current Game Mode: {'CUSTOM PER PACKAGE' if config.get('game_method') == 'each' else 'SAME GAME FOR ALL'}")
                print(f"Global Game Setting: {config.get('game_name', 'None')} ({config.get('game_id', 'N/A')})")
                print("\nSetup Options:")
                print("  1. Apply Same Game to ALL Packages")
                print("  2. Assign Custom Game PER Package (Roblox 1 -> Game A, Roblox 2 -> Game B)")
                gmode = prompt("\nSelect Mode (1 or 2, default 1): ").strip()

                if gmode == '2':
                    config['game_method'] = 'each'
                    pkgs = config.get('selected_packages', [])
                    if not pkgs:
                        pkgs = get_roblox_packages()
                    if not pkgs:
                        print("  [!] No Roblox packages detected or selected. Please select packages in Option 2 first!")
                    else:
                        if 'package_games' not in config: config['package_games'] = {}
                        if 'package_game_names' not in config: config['package_game_names'] = {}

                        print(f"\n[+] Configuring individual games for {len(pkgs)} package(s):")
                        for p_idx, pkg in enumerate(pkgs, 1):
                            curr_game = _resolve_package_game_name(pkg, config)
                            print(f"\n--------------------------------------------------")
                            print(f"[{p_idx}/{len(pkgs)}] Package: {pkg}")
                            print(f"Current Game: {curr_game}")
                            print("Select Game for this package:")
                            for idx, (gname, gid) in enumerate(PRESET_GAMES, 1):
                                print(f"  {idx}. {gname} (ID: {gid})")
                            print("  C. Custom Place ID or Private Server Link")
                            print("  S. Skip (keep current setting)")

                            while True:
                                gchoice = prompt(f"Choice for {pkg}: ").strip()
                                if gchoice.upper() == 'C':
                                    gid = prompt("  Enter Place ID / Link: ").strip()
                                    if not gid:
                                        print("  [!] No Place ID / Link entered. Try again.")
                                        continue
                                    config['package_games'][pkg] = gid
                                    gname = lookup_roblox_game_name(gid)
                                    config['package_game_names'][pkg] = gname
                                    break
                                elif gchoice.upper() == 'S' or not gchoice:
                                    break
                                elif gchoice.isdigit() and 1 <= int(gchoice) <= len(PRESET_GAMES):
                                    gname, gid = PRESET_GAMES[int(gchoice) - 1]
                                    config['package_games'][pkg] = gid
                                    config['package_game_names'][pkg] = gname
                                    break
                                else:
                                    print(f"  [!] Invalid choice '{gchoice}'. Enter 1-{len(PRESET_GAMES)}, C, or S.")
                    save_config()
                    print("\n[+] Per-Package Game Configurations Saved:")
                    for pkg in (config.get('selected_packages') or get_roblox_packages()):
                        print(f"  ✓ {pkg:<30} -> {_resolve_package_game_name(pkg, config)}")

                else:
                    config['game_method'] = 'all'
                    print("\nPreset Games (Applies to ALL packages):")
                    for idx, (gname, gid) in enumerate(PRESET_GAMES, 1):
                        print(f"  {idx}. {gname} (ID: {gid})")
                    print("  C. Custom Place ID or Private Server Link")
                    print("  Enter. Keep the current game")
                    while True:
                        gchoice = prompt("\nChoice: ").strip()
                        if not gchoice:
                            print("[i] No game choice entered; keeping the current game.")
                            break
                        if gchoice.upper() == 'C':
                            gid = prompt("Enter Place ID / Link: ").strip()
                            if not gid:
                                print("[!] No Place ID / Link entered. Try again.")
                                continue
                            config['game_id'] = gid
                            config['game_name'] = lookup_roblox_game_name(gid)
                            break
                        elif gchoice.isdigit() and 1 <= int(gchoice) <= len(PRESET_GAMES):
                            config['game_name'], config['game_id'] = PRESET_GAMES[int(gchoice) - 1]
                            break
                        else:
                            print(f"[!] Invalid choice '{gchoice}'. Enter 1-{len(PRESET_GAMES)} or C.")
                    save_config()
                    print(f"\n[+] Active Game ID / Link Set for ALL packages: {config.get('game_name')} ({config.get('game_id')})")

                again = prompt("\nConfigure another game/package now? (y/n, default n): ").strip().lower()
                if again != 'y':
                    break
            prompt("\nPress Enter to return to menu...")

        elif choice == '4':
            print(f"\nCurrent Webhook: {config.get('webhook_url', 'None')}")
            wurl = prompt("Enter Discord Webhook URL (leave empty to keep current): ").strip()
            if wurl:
                config['webhook_url'] = normalize_webhook_url(wurl)
            wenable = prompt("Enable Webhook updates? (y/n): ").strip().lower() == 'y'
            config['webhook_enabled'] = wenable
            wint = prompt("Webhook interval in seconds [default 60]: ").strip()
            if wint.isdigit():
                config['webhook_interval'] = int(wint)
            save_config()
            print(f"\n[+] Webhook Enabled: {config.get('webhook_enabled')} | Interval: {config.get('webhook_interval')}s")
            prompt("\nPress Enter to return to menu...")

        elif choice == '5':
            print("\nTiming Settings:")
            check_in = prompt(f"Check Interval seconds [{config.get('check_interval', 10)}]: ").strip()
            if check_in.isdigit(): config['check_interval'] = int(check_in)

            off_w = prompt(f"Offline Wait seconds [{config.get('offline_wait', 15)}]: ").strip()
            if off_w.isdigit(): config['offline_wait'] = int(off_w)

            ret_c = prompt(f"Max Retries [{config.get('retry_count', 3)}]: ").strip()
            if ret_c.isdigit(): config['retry_count'] = int(ret_c)

            seq = prompt(f"Sequential Join? (y/n) [{config.get('sequential_join', False)}]: ").strip().lower()
            if seq in ['y', 'n']: config['sequential_join'] = (seq == 'y')

            clr = prompt(f"Clear Cache on Rejoin? (y/n) [{config.get('clear_cache', False)}]: ").strip().lower()
            if clr in ['y', 'n']: config['clear_cache'] = (clr == 'y')

            hm = prompt(f"Auto Rejoin if stuck on Roblox Home Screen? (y/n) [{config.get('home_rejoin_enabled', True)}]: ").strip().lower()
            if hm in ['y', 'n']: config['home_rejoin_enabled'] = (hm == 'y')

            save_config()
            print("\n[+] Timing & Home Screen settings updated.")
            prompt("\nPress Enter to return to menu...")

        elif choice == '6':
            print("\n--- [ AUTO-SORT / WINDOW TILING LAYOUT ] ---")
            print(f"Current Auto-Sort Enabled: {config.get('auto_sort', True)}")
            print(f"Current Layout Mode: {config.get('window_mode', 'left_stack')}")
            print(f"Current Dashboard Table Width: {config.get('dashboard_width', 40)} columns")
            print("\n1. Enable/Disable Auto-Sort")
            print("2. Set Mode: Left Vertical Stack (Matching side-by-side layout)")
            print("3. Set Mode: Grid Layout (Even N x M grid across screen)")
            print("4. Set Dashboard Table Width (fix the live rejoin dashboard's layout)")
            lch = prompt("Select option: ").strip()
            if lch == '1':
                config['auto_sort'] = not config.get('auto_sort', True)
                print(f"[+] Auto-Sort set to: {config['auto_sort']}")
            elif lch == '2':
                config['window_mode'] = 'left_stack'
                print("[+] Window mode set to: Left Vertical Stack")
            elif lch == '3':
                config['window_mode'] = 'grid'
                print("[+] Window mode set to: Grid Layout")
            elif lch == '4':
                print("\nThe live dashboard (Option 8) draws a fixed-width table. If your")
                print("device rotates or the terminal is narrower than the table, it will")
                print("wrap and look broken. Run 'stty size' in Termux (second number = columns)")
                print("to find your real width, then set a table width a few columns")
                print("narrower than that (e.g. columns=50 -> try 44).")
                wch = prompt(f"Dashboard table width in columns [{config.get('dashboard_width', 40)}]: ").strip()
                if wch.isdigit() and int(wch) >= 30:
                    config['dashboard_width'] = int(wch)
                    print(f"[+] Dashboard table width set to: {config['dashboard_width']} columns")
                elif wch:
                    print("[!] Ignored — enter a number of 30 or higher.")
            save_config()
            prompt("\nPress Enter to return to menu...")

        elif choice == '7':
            path = config.get('autoexecute_path', '/sdcard/Delta/Autoexecute')
            files = list_autoexecute_files(path)
            print(f"\nAutoexecute Directory ({path}):")
            for f in files:
                print(f" - {f}")
            print("\n1. Add New Script File")
            print("2. Back")
            ach = prompt("Select option: ").strip()
            if ach == '1':
                fname = prompt("Filename (e.g. script.lua): ").strip()
                print("Enter script content (end with EOF on a line by itself):")
                lines = []
                while True:
                    line = prompt()
                    if line.strip() == 'EOF':
                        break
                    lines.append(line)
                add_autoexecute_script(path, fname, '\n'.join(lines))
            prompt("\nPress Enter to return to menu...")

        elif choice == '8':
            rejoin_engine.start(config)
            rejoin_engine.render_live_dashboard(config)
        elif choice == '10':
            auto_sort_windows(mode=config.get('window_mode', 'left_stack'))
            prompt("\nPress Enter to return to menu...")

        elif choice == '11':
            pkgs = config.get('selected_packages', [])
            if not pkgs:
                pkgs = get_roblox_packages()
            if not pkgs:
                print("[!] Please select packages first.")
            else:
                for idx, p in enumerate(pkgs):
                    gid = _resolve_package_game_id(p, config)
                    gname = _resolve_package_game_name(p, config)
                    if not gid:
                        print(f"[!] No Game ID configured for {p}. Skipping.")
                        continue
                    bounds = calculate_window_bounds(idx, len(pkgs), mode=config.get('window_mode', 'left_stack'))
                    print(f"Launching {p} into '{gname}' (ID: {gid}) at bounds {bounds}...")
                    launch_game(p, gid, bounds=bounds, freeform=True)
            prompt("\nPress Enter to return to menu...")

        elif choice == '12':
            wurl = config.get('webhook_url')
            if not wurl:
                print("[!] No webhook URL set!")
            else:
                print("Sending test webhook...")
                send_discord_webhook(wurl, rejoin_engine.get_status(), time.time())
            prompt("\nPress Enter to return to menu...")

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
