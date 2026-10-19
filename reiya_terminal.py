#!/usr/bin/env python3
"""
REI REJOIN Core Global - Terminal / Termux Edition
Single standalone CLI script combining all core functions of REI REJOIN Roblox Account Manager:
- VPhone & Emulator App discovery (su shell execution, dumpsys, pm, cmd, ps, direct name input)
- ROBLOX & CLONE APPS ONLY (Displays exclusively Roblox apps & Roblox clones: com.roblox.client, free.nokaA, Delta, etc.)
- DIRECT MULTI-PACKAGE SELECTION (Typing 1,2 directly sets selected packages to #1 and #2)
- Direct Game Launching via Place ID or Private Server Link
- Exact Match REI REJOIN ASCII Dashboard UI (2-line REI REJOIN block logo + clean settings & live stats table)
- Home Page Rejoin (re-sends the game link to the running app; never force-stops Roblox)
- Direct ActivityProtocolLaunch Component Invocation (Bypasses Home screen to connect directly into game place)
- Instant Home Page & App Exit Re-launch (Triggers immediate rejoin if app is closed or on Home Page)
- Complete Terminal Screen Buffer Flush (os.system('clear') prevents duplicate terminal headers)
- Multi-Window dumpsys inspection (Accurately checks RobloxActivity across side-by-side windows even when Termux is focused)
- System monitoring (CPU, RAM, Uptime, Screenshots)
- Discord Webhook reporting with screenshot attachments
- Automatic Rejoin loop (Retry, Cooldown, Sequential, Cache clear)
- Autoexecute script management
"""

import os
import sys
import time
import json
import re
import argparse
import subprocess
import threading
import shutil
import shlex
import urllib.request
import urllib.parse
import select
import base64
import copy
import math

# Script version & timestamp
BUILD_VERSION = "v6.9.26-REI-REJOIN"
BUILD_TIME = "2026-10-19 UTC"

# ==============================================================================
# DEFAULT PRESETS & CONFIGURATION
# ==============================================================================

PRESET_GAMES = [
    ('The Forge',          '76558904092080'),
    ('Anime Origin',       '129932912185311'),
    ('Anime Expedition',   '84515722934860'),
    ('Run a Restaurant',   '77843161404023'),
    ('World Zero',         '2727067538'),
    ('Blue Heater 2',         '16893821047'),
    ('Grow a Garden 2',       '126884695'),
    ('Steal an Egg',          '107778070777162'),
    ('Anime Astral Simulator','102072869879193'),
    ('Anime Dice',             '113290951185459'),
    ('Ride a Pet',             '124216119978534'),
    ('Slayer 2',             '16205713724'),
    ('Pet Simulator',        '8737899170'),
]

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'config.json')

DEFAULT_CONFIG = {
    'offline_wait': 15,
    'retry_count': 3,
    'retry_delay': 30,
    'check_interval': 10,
    'activity_check_interval': 30,
    'dashboard_refresh_interval': 2,
    'app_ram_refresh_interval': 30,
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
    'package_account_names': {},
    'webhook_url': '',
    'webhook_interval': 60,
    'autoexecute_path': '/sdcard/Delta/Autoexecute',
    'home_rejoin_enabled': True,
    'auto_sort': True,  # tile the Noka clone windows into a screen-filling grid after (re)launch
    # Grace period before a running package stuck on 'Unknown' is force-stopped and
    # relaunched. 0 = rejoin on the first Unknown reading (Home Rejoin turns it off).
    'unknown_stall_seconds': 0,
    'dashboard_width': 40,  # live dashboard table width in columns; user-tunable via Option 6.4
}

# Global config state
config = copy.deepcopy(DEFAULT_CONFIG)

PKG_RE = re.compile(r'[A-Za-z0-9._]+')

def valid_pkg(package):
    return bool(PKG_RE.fullmatch(str(package or '')))

_CONFIG_RANGES = {
    'check_interval': (1.0, 300.0),
    'activity_check_interval': (5.0, 600.0),
    'dashboard_refresh_interval': (0.5, 60.0),
    'app_ram_refresh_interval': (10.0, 3600.0),
    'launch_wait': (0.0, 300.0),
    'offline_wait': (0.0, 300.0),
    'retry_delay': (1.0, 3600.0),
    'rejoin_cooldown': (1.0, 3600.0),
    'webhook_interval': (10.0, 86400.0),
    'dashboard_width': (30, 300),
    'retry_count': (1, 100),
    'unknown_stall_seconds': (0.0, 3600.0),
}

def validate_config(values):
    """Return a normalized config while retaining forward-compatible keys."""
    clean = copy.deepcopy(DEFAULT_CONFIG)
    if isinstance(values, dict):
        clean.update(values)

    for key, (minimum, maximum) in _CONFIG_RANGES.items():
        default = DEFAULT_CONFIG[key]
        try:
            number = float(clean.get(key, default))
            number = max(minimum, min(maximum, number))
            clean[key] = int(number) if isinstance(default, int) and not isinstance(default, bool) else number
        except (TypeError, ValueError):
            clean[key] = default

    value = clean.get('selected_packages')
    if not isinstance(value, list):
        value = []
    clean['selected_packages'] = list(dict.fromkeys(str(pkg) for pkg in value if valid_pkg(pkg)))

    for key in ('package_games', 'package_game_names', 'package_account_names'):
        if not isinstance(clean.get(key), dict):
            clean[key] = {}

    if clean.get('game_method') not in ('all', 'each'):
        clean['game_method'] = 'all'

    # v6.8.96 shipped a 90s wait as the Unknown-rejoin default; v6.8.97 rejoins
    # immediately instead, so drop the old default that got written to disk.
    if clean.get('unknown_stall_seconds') == 90:
        clean['unknown_stall_seconds'] = 0
    clean.pop('rejoin_interval', None)  # retired legacy field
    clean.pop('ram_refresh_interval', None)  # retired 30-second system RAM cache
    clean.pop('system_ram_refresh_interval', None)  # live dumpsys sampling has no cache
    return clean

def load_config():
    global config
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    saved = {}
    for candidate in (CONFIG_FILE, CONFIG_FILE + '.bak'):
        if not os.path.exists(candidate):
            continue
        try:
            with open(candidate, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            break
        except Exception as e:
            print(f"[!] Warning loading config from {candidate}: {e}")
    config = validate_config(saved)
    return config

def save_config():
    global config
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    config = validate_config(config)
    temp_path = CONFIG_FILE + '.tmp'
    backup_path = CONFIG_FILE + '.bak'
    try:
        with open(temp_path, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(config, f, indent=2, default=str)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(CONFIG_FILE):
            shutil.copy2(CONFIG_FILE, backup_path)
        os.replace(temp_path, CONFIG_FILE)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

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

def check_su_works():
    out = run_cmd("su -c 'id'", timeout=2).stdout
    return 'uid=0' in out or 'root' in out.lower()

def clear_terminal_screen():
    """Clear terminal screen completely preventing duplicate overlapping headers."""
    try:
        os.system('clear' if os.name == 'posix' else 'cls')
    except Exception:
        print("[H[2J[3J", end="")

def prompt(text=''):
    try:
        if os.name == 'posix':
            import termios
            termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except Exception:
        pass
    return input(text)

def _parse_pm_lines(text):
    return {line.strip()[8:].strip() for line in (text or '').splitlines() if line.strip().startswith('package:')}

def get_installed_packages():
    """Discover installed packages. Tries cheap strategies first and stops at
    the first one that yields results, so only one or two shells are forked."""
    packages = set()

    # Strategies 1-3: package listings (root first, then plain shell)
    for cmd in ("su -c 'pm list packages'", 'pm list packages -3', 'pm list packages',
                'cmd package list packages', '/system/bin/pm list packages'):
        packages |= _parse_pm_lines(run_cmd(cmd, timeout=5).stdout)
        if packages:
            break

    # Strategy 4: dumpsys package dump
    if not packages:
        out = run_cmd("su -c 'dumpsys package packages'", timeout=5).stdout
        packages |= set(re.findall(r'Package \[([^\]]+)\]', out))

    # Strategy 5: app data dirs and running process names
    if not packages:
        for line in run_cmd("su -c 'ls /data/data'", timeout=5).stdout.splitlines():
            pkg = line.strip()
            if pkg and '.' in pkg and not pkg.startswith('/'):
                packages.add(pkg)
        for line in run_cmd('ps -A', timeout=5).stdout.splitlines():
            parts = line.split()
            name = parts[-1] if parts else ''
            if '.' in name and not name.startswith(('[', '/')):
                packages.add(name)

    # Strategy 6: hard fallback when the package scanner is completely blocked
    if not packages:
        for known in ('com.roblox.client', 'free.nokaA', 'free.nokaB', 'free.nokaC', 'com.delta.client'):
            if "versionName=" in run_cmd(f"dumpsys package {known}", timeout=2).stdout:
                packages.add(known)

    return sorted(packages)

_ROBLOX_KEYWORDS = (
    'roblox', 'noka', 'blox', 'delta', 'arceus', 'executor',
    'codex', 'fluxus', 'trigon', 'vegas', 'hydrogen', 'evon', 'krnl',
)
_roblox_pkg_cache = (0.0, [])
ROBLOX_PKG_CACHE_TTL = 30  # seconds; full package scans fork several shells

def get_roblox_packages(force=False):
    """Installed Roblox apps, clones and executors plus any saved selection.
    Cached briefly because callers poll it and each scan spawns shells."""
    global _roblox_pkg_cache
    now = time.time()
    if not force and _roblox_pkg_cache[1] and now - _roblox_pkg_cache[0] < ROBLOX_PKG_CACHE_TTL:
        return list(_roblox_pkg_cache[1])
    found = {p for p in get_installed_packages() if any(k in p.lower() for k in _ROBLOX_KEYWORDS)}
    found.update(config.get('selected_packages', []))
    _roblox_pkg_cache = (now, sorted(found))
    return list(_roblox_pkg_cache[1])

def get_target_packages(cfg):
    """Selected packages, or every detected Roblox package when none are selected."""
    return list(cfg.get('selected_packages') or get_roblox_packages())

def get_running_packages(packages):
    """Live packages via one su call, or None if the probe itself failed.

    None (timeout / su error) must never be read as "nothing is running": on a
    loaded phone that would relaunch every healthy game.
    """
    packages = [p for p in packages if valid_pkg(p)]
    if not packages:
        return set()
    cmd = f"su -c 'for p in {' '.join(packages)}; do if pidof \"$p\" >/dev/null; then echo \"$p\"; fi; done'"
    res = run_cmd(cmd, timeout=6)
    return set(res.stdout.split()) if res.returncode == 0 else None

def is_app_running(package):
    """True only if pidof reports a real process (error text is never parsed as a PID)."""
    return package in (get_running_packages([package]) or ())

def get_active_package_tasks(packages):
    """Return packages that still own a live Activity, or None when the dump is unavailable.

    A clone may keep a cached process after its window closes, so pidof alone
    cannot prove there is still a game window to monitor. `dumpsys activity
    top` is NOT used: it omits freeform/split-screen clone windows, which made
    healthy games look closed. `dumpsys activity activities` lists every live
    ActivityRecord ("Run #n: ActivityRecord{... pkg/Activity ...}") and drops
    the record as soon as the window is closed.
    """
    if not packages:
        return set()
    res = run_cmd("su -c 'dumpsys activity activities'", timeout=8)
    output = res.stdout or ''
    if res.returncode != 0 or 'ACTIVITY MANAGER ACTIVITIES' not in output:
        return None
    active = set(re.findall(r'Run #\d+: ActivityRecord\{\S+ u\d+ ([A-Za-z0-9._]+)/', output))
    return active.intersection(packages)

def get_screen_size():
    """Screen (width, height), always landscape. `wm size` fails for the Termux user on
    some devices, so ask through su first and only then fall back to a plain call."""
    for cmd in ("su -c 'wm size'", 'wm size'):
        # `wm size` prints physical first and active override second. Cloud
        # phones commonly use an override, so the last size is the live one.
        matches = re.findall(r'(\d+)x(\d+)', run_cmd(cmd, timeout=3).stdout or '')
        if matches:
            w, h = (int(value) for value in matches[-1])
            return max(w, h), min(w, h)
    return 1280, 720

def _build_launch_urls(game_id):
    """Return (roblox:// url, web url) for a place ID / game link / private server link, or None."""
    game_id = str(game_id).strip() or '2753915549'
    link_code = None
    if game_id.startswith('http'):
        parsed = urllib.parse.urlparse(game_id)
        host = (parsed.hostname or '').lower()
        match = re.search(r'/games/(\d+)', parsed.path)
        if parsed.scheme not in ('http', 'https') or not (host == 'roblox.com' or host.endswith('.roblox.com')) or not match:
            return None
        place_id = match.group(1)
        ps_match = re.search(r'privateServerLinkCode=([^&]+)', game_id)
        if ps_match:
            link_code = urllib.parse.unquote(ps_match.group(1))
    elif '?privateServerLinkCode=' in game_id:
        head, tail = game_id.split('?privateServerLinkCode=', 1)
        place_match = re.search(r'(?:/games/)?(\d+)', head)
        place_id = place_match.group(1) if place_match else ''
        link_code = tail.split('&', 1)[0]
    elif game_id.isdigit():
        place_id = game_id
    else:
        return None

    if not place_id or (link_code is not None and not re.fullmatch(r'[A-Za-z0-9_-]+', link_code)):
        return None
    if link_code:
        return (f'roblox://placeId={place_id}&linkCode={link_code}',
                f'https://www.roblox.com/games/{place_id}?privateServerLinkCode={link_code}')
    return f'roblox://placeId={place_id}', f'https://www.roblox.com/games/{place_id}'

# ------------------------------------------------------------------------------
# Window sorting. Noka clones draw their own floating window inside a fullscreen
# task, so Android's `am task resize` can't move them. Each window is a game surface
# with a 128px title bar above it and 64px transparent resize strips just outside
# its edges: dragging the title moves it, dragging the right/bottom strip resizes it.
# ------------------------------------------------------------------------------
NOKA_TITLE_H = 128
NOKA_STRIP = 64
STATUS_BAR_H = 48
SORT_TOLERANCE = 12

def sort_targets(count, width, height):
    """Game-surface rects (x, y, w, h), one per window, tiling the screen in the
    rows x cols grid whose surfaces come closest to 16:10 (6 -> 3x2, 8 -> 4x2)."""
    usable = height - STATUS_BAR_H
    best = None
    for cols in range(1, count + 1):
        rows = -(-count // cols)
        surface_h = usable / rows - NOKA_TITLE_H
        if surface_h < 100:
            continue
        cost = abs(math.log(width / cols / surface_h / 1.6)) + 0.15 * (cols * rows - count)
        if best is None or cost < best[0]:
            best = (cost, cols, rows)
    cols, rows = (best[1], best[2]) if best else (count, 1)
    cell_w, cell_h = width // cols, usable // rows
    w = min(cell_w, width - NOKA_STRIP)  # the right strip must stay on screen to be dragged
    return [((i % cols) * cell_w, STATUS_BAR_H + (i // cols) * cell_h + NOKA_TITLE_H, w, cell_h - NOKA_TITLE_H)
            for i in range(count)]

_WINDOW_BLOCK = r'(?:(?!\n  Window #).)*?'

def get_noka_frames(packages):
    """{package: (x, y, w, h)} of each clone's floating game surface that is on screen,
    from one `dumpsys window`. A window hidden behind a fullscreen app or collapsed into
    its bubble reports isReadyForDisplay()=false and is left out."""
    out = run_cmd("su -c 'dumpsys window windows'", timeout=8).stdout or ''
    frames = {}
    for m in re.finditer(r'Window\{\w+ u\d+ ([\w.]+)/[\w.$]*ActivityNativeMain\}:' + _WINDOW_BLOCK +
                         r'isReadyForDisplay\(\)=true' + _WINDOW_BLOCK +
                         r'mFrame=\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]', out, re.S):
        if m.group(1) in packages:
            x1, y1, x2, y2 = (int(m.group(i)) for i in range(2, 6))
            frames[m.group(1)] = (x1, y1, x2 - x1, y2 - y1)
    return frames

def restore_collapsed_window(package):
    """Tap the floating bubble a collapsed Noka window leaves behind. True if there was one."""
    out = run_cmd("su -c 'dumpsys window windows'", timeout=8).stdout or ''
    m = re.search(r'Window\{\w+ u\d+ ' + re.escape(package) + r'\}:' + _WINDOW_BLOCK + r'ty=APPLICATION_OVERLAY' +
                  _WINDOW_BLOCK + r'mFrame=\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]', out, re.S)
    if not m:
        return False
    x1, y1, x2, y2 = (int(m.group(i)) for i in range(1, 5))
    run_cmd(f"su -c 'input tap {(x1 + x2) // 2} {(y1 + y2) // 2}'", timeout=5)
    time.sleep(1.5)
    return True

def set_window_prefs(package, rect):
    """Write the grid cell into the clone's App Cloner floating-window prefs (left/top/right/
    bottom of the game surface). A window STARTED afterwards opens exactly there, so a fresh
    launch needs no dragging at all. A running app keeps its in-memory position and ignores
    the edit until its next start, which is why place_window() still exists for those."""
    if not valid_pkg(package):
        return False
    path = f"/data/data/{package}/shared_prefs/{package}_preferences.xml"
    xml = run_cmd(f"su -c 'cat {path}'", timeout=5).stdout or ''
    if 'app_cloner_current_window_left' not in xml:
        return False  # not an App Cloner floating clone (e.g. com.roblox.client)
    x, y, w, h = rect
    for side, value in (('left', x), ('top', y), ('right', x + w), ('bottom', y + h)):
        xml = re.sub(rf'(app_cloner_current_window_{side}" value=")\d+', rf'\g<1>{value}', xml)
    # Overwrite in place (cat >) so the file keeps the app's owner and permissions.
    try:
        subprocess.run(['su', '-c', f'cat > {path}'], input=xml, text=True, timeout=5, check=True)
    except Exception:
        return False
    return True

def _drag(x1, y1, x2, y2):
    run_cmd(f"su -c 'input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} 400'", timeout=6)
    time.sleep(0.7)

def place_window(package, target, width, height):
    """Move/resize one clone window until its game surface matches `target`. True on success."""
    if not valid_pkg(package):
        return False
    tx, ty, tw, th = target
    raise_cmd = f"su -c 'am start -f 0x10020000 -n {package}/com.roblox.client.ActivityNativeMain'"  # task to front
    run_cmd(raise_cmd, timeout=5)
    time.sleep(1)
    for _ in range(10):
        frame = get_noka_frames([package]).get(package)
        if frame is None and restore_collapsed_window(package):
            run_cmd(raise_cmd, timeout=5)
            time.sleep(1)
            frame = get_noka_frames([package]).get(package)
        if frame is None or (frame[2] >= width - 4 and frame[3] >= height - 80):
            return False  # not on screen, or maximized (no title/strips to grab)
        x, y, w, h = frame
        dw, dh = tw - w, th - h
        if max(abs(dw), abs(dh), abs(tx - x), abs(ty - y)) <= SORT_TOLERANCE:
            return True
        grab_x, grab_y = x + 100, y - NOKA_TITLE_H // 2  # on the title bar, clear of its buttons
        edge = NOKA_STRIP // 2
        if abs(dw) > SORT_TOLERANCE or abs(dh) > SORT_TOLERANCE:
            horizontal = abs(dw) > SORT_TOLERANCE
            sx, sy = (x + w + edge, y + h // 2) if horizontal else (x + w // 2, y + h + edge)
            ex, ey = (sx + dw, sy) if horizontal else (sx, sy + dh)
            if sx <= width - 2 and sy <= height - 2 and 4 <= ex <= width - 2 and STATUS_BAR_H <= ey <= height - 2:
                _drag(sx, sy, ex, ey)
                continue
            # The strip (or where the drag would end) is off screen: move the window up/left first.
            nx = max(0, min(x, width - 2 - edge - max(w, tw)))
            ny = max(NOKA_TITLE_H, min(y, height - 2 - edge - max(h, th)))
            if (nx, ny) == (x, y):
                return False
            tx_move, ty_move = nx - x, ny - y
        else:
            tx_move, ty_move = tx - x, ty - y
        _drag(grab_x, grab_y, grab_x + tx_move, grab_y + ty_move)
    return False

def sort_windows(packages, only=None):
    """Tile the clone windows of `packages` into the grid (slot = position in the list).
    `only` limits which ones are touched. Returns {package: placed_ok}."""
    width, height = get_screen_size()
    return {pkg: place_window(pkg, target, width, height)
            for pkg, target in zip(packages, sort_targets(len(packages), width, height))
            if only is None or pkg in only}

def launch_game(package, game_id, prefer='component'):
    """Launch Roblox game directly into place ID for targeted clone package.

    A running Roblox (e.g. stuck on its home page) ignores one of the two intent
    forms, and which one depends on its state: the component intent
    (ActivityProtocolLaunch) or the plain VIEW intent addressed by package. The
    ignored one still exits 0 (sometimes with "Activity not started ... delivered
    to currently running top-most instance", sometimes silently), so the caller
    alternates `prefer` between attempts and checks the Roblox log for a join.
    A cold start works with either form.
    """
    package = str(package).strip()
    if not valid_pkg(package):
        return False
    urls = _build_launch_urls(game_id)
    if not urls:
        return False
    url, web_url = urls

    # FLAG_ACTIVITY_NEW_TASK only (0x10000000) — never CLEAR_TASK (0x14000000), which
    # terminates the whole activity stack and restarts Roblox instead of navigating.
    view = "-f 0x10000000 -a android.intent.action.VIEW"
    by_component = f"su -c 'am start -f 0x10000000 -n {package}/com.roblox.client.ActivityProtocolLaunch -a android.intent.action.VIEW -d \"{url}\"'"
    by_package = f"su -c 'am start {view} -p {package} -d \"{url}\"'"
    by_web = f"su -c 'am start {view} -p {package} -d \"{web_url}\"'"
    no_root = f"am start {view} -p {package} -d '{url}'"
    intents = ([by_package, by_component] if prefer == 'package' else [by_component, by_package]) + [by_web, no_root]

    for cmd in intents:
        res = run_cmd(cmd, timeout=6)
        # rc is 0 even when a running Roblox ignores the intent ("Warning: Activity not
        # started, intent has been delivered to currently running top-most instance"),
        # and which form it ignores depends on the app's state, so fall through to the next.
        if res.returncode == 0 and "Error" not in res.stdout and "not started" not in res.stdout:
            return True
    return False

def _resolve_package_game_id(pkg, cfg):
    """Resolve active Game ID or Private Server Link for a specific package."""
    if cfg.get('game_method', 'all') == 'each':
        return cfg.get('package_games', {}).get(pkg, cfg.get('game_id', ''))
    return cfg.get('game_id', '')

def _place_label(gid):
    return f"Place:{gid[:12]}" if gid else 'No Game Set'

def _resolve_package_game_name(pkg, cfg):
    """Resolve display name of the configured game for a specific package."""
    if cfg.get('game_method', 'all') == 'each':
        name = cfg.get('package_game_names', {}).get(pkg)
        if name:
            return name
        gid = cfg.get('package_games', {}).get(pkg, '')
        if gid:
            return next((gname for gname, pid in PRESET_GAMES if pid == gid), _place_label(gid))
    return cfg.get('game_name') or _place_label(cfg.get('game_id'))

_roblox_username_cache = {}

def _newest_logs_sh(package, count=1):
    """Shell expression listing the `count` newest Roblox log files, as full paths.

    Each directory needs its own glob: `ls -t dirA dirB/*` only globs the last
    directory and prints bare names for the rest, which later commands can't open.
    """
    dirs = ' '.join((f"/data/data/{package}/files/appData/logs", f"/data/data/{package}/files/logs",
                     f"/sdcard/Android/data/{package}/files/appData/logs", f"/sdcard/Android/data/{package}/files/logs"))
    return f'$(ls -t $(for d in {dirs}; do ls -d $d/*.log 2>/dev/null; done) 2>/dev/null | head -n {count})'

def _extract_roblox_identity(text):
    """Read a Roblox username or user ID from logs, preferences, or JSON data (from commit f55b982)."""
    if not text:
        return '', ''

    username_patterns = [
        r'name=["\'](?:username|user_name|UserName|last_username|account_name|logged_in_user|ROBLOX_USERNAME)["\'][^>]*>\s*([A-Za-z0-9_]{3,20})\s*</',
        r'["\']?(?:username|user_name|UserName|last_username|account_name|logged_in_user|ROBLOX_USERNAME)["\']?\s*[:=]\s*["\']([A-Za-z0-9_]{3,20})["\']',
        r'\b(?:Username|user_name|UserName|Logged\s+in\s+as|LocalPlayer\s+UserName)\s*[:=]?\s*["\']?([A-Za-z0-9_]{3,20})["\']?',
        r'\[FLog::[^\]]+\]\s*(?:Username|User):\s*([A-Za-z0-9_]{3,20})',
    ]
    for pattern in username_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            uname = match.group(1).strip()
            if uname.lower() not in ('system', 'null', 'undefined', 'default', 'unknown', 'true', 'false', 'none', 'string', 'userid', 'username'):
                return uname, ''

    user_id_patterns = [
        r'name=["\'](?:userId|user_id|UserId|ROBLOX_USER_ID)["\'][^>]*>\s*(\d{4,15})\s*</',
        r'name=["\'](?:userId|user_id|UserId|ROBLOX_USER_ID)["\'][^>]*value=["\'](\d{4,15})["\']',
        r'["\']?(?:userId|user_id|UserId|ROBLOX_USER_ID)["\']?\s*[:=]\s*["\']?(\d{4,15})["\']?',
        r'\b(?:User\s*ID|userId|user_id)\s*[:=]?\s*["\']?(\d{4,15})["\']?',
    ]
    for pattern in user_id_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            uid = match.group(1).strip()
            if uid != '0':
                return '', uid

    return '', ''

def get_roblox_username(package):
    """Detect the logged-in Roblox account for a clone from its Player logs and shared_prefs (from commit f55b982)."""
    if not valid_pkg(package):
        return ''

    now = time.time()
    cached = _roblox_username_cache.get(package)
    if cached:
        name, ts = cached
        ttl = 3600 if name else 10
        if now - ts < ttl:
            return name

    prefs_dir = f"/data/data/{package}/shared_prefs"

    cmd = (
        f"su -c '"
        f"LOGFILES={_newest_logs_sh(package, 3)}; "
        f"if [ -n \"$LOGFILES\" ]; then tail -n 800 $LOGFILES 2>/dev/null; fi; "
        f"if [ -d \"{prefs_dir}\" ]; then grep -h -E -i \"(user(name|_name)|user(id|_id))\" {prefs_dir}/*.xml 2>/dev/null | head -n 200; fi"
        f"'"
    )

    res = run_cmd(cmd, timeout=4)
    combined_text = res.stdout or ''

    username, user_id = _extract_roblox_identity(combined_text)

    if username:
        _roblox_username_cache[package] = (username, now)
        return username

    if user_id:
        try:
            req = urllib.request.Request(
                f'https://users.roblox.com/v1/users/{urllib.parse.quote(user_id)}',
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                api_name = str(json.loads(response.read().decode('utf-8')).get('name') or '').strip()
            if api_name:
                _roblox_username_cache[package] = (api_name, now)
                return api_name
        except Exception:
            pass

    _roblox_username_cache[package] = ('', now)
    return ''

def get_package_username(package, cfg, idx):
    """Resolve active Roblox username for package using commit f55b982 logic."""
    custom = cfg.get('package_account_names', {}).get(package)
    if custom:
        return custom

    detected = get_roblox_username(package)
    if detected:
        return detected

    parts = package.split('.')
    short_alias = parts[-1] if len(parts) > 1 else package
    if short_alias.lower() == 'client' and len(parts) > 1:
        short_alias = parts[-2]
    if short_alias.lower() == 'roblox':
        short_alias = 'Roblox'
    return short_alias if len(short_alias) >= 2 else f"Acc_{idx:02d}"


def clear_app_cache(package):
    """Clear all app data using Android `pm clear` (legacy function name)."""
    return valid_pkg(package) and run_cmd(f"su -c 'pm clear {package}'", timeout=10).returncode != -1

_DISCONNECT_RE = r'error code: ?(288|277)|disconnected from the experience|disconnectreason'
_JOIN_RE = r'game_join_loadtime|Connection accepted'
_LEAVE_RE = r'NetworkClient\] Client:Disconnect|Disconnection Notification'
_LOGIN_RE = r'SingleSurfaceApp\] userDidLogin'
LOG_SETTLE_SECONDS = 3  # quiet time after the home surface reloads before we trust it

def _log_seconds(raw):
    """App-relative timestamp (seconds) of a grep'd or tailed Player log line."""
    m = re.search(r'Z,(\d+(?:\.\d+)?),', raw or '')
    return float(m.group(1)) if m else None

def get_roblox_log_state(package):
    """Classify the current Roblox session from its newest Player log.

    Every launch writes a fresh Player log, so the newest file is the live
    session. The activity name can't tell home from in-game (both are
    ActivityNativeMain), but the log can:
      'disconnected' - Error 277/288 or a disconnect-from-experience notice
      'ingame'       - a join marker with no later leave marker
      'home'         - not in a game and the home surface (userDidLogin) reloaded after the
                       last join attempt: a torn-down join or a left game ends there
      'loading'      - not in a game, but the home surface hasn't reloaded yet. A failed join
                       can sit connecting for ~25s before giving up, and a game link sent
                       during that wait is swallowed when the app resets to home
      None           - unknown (no su / no log); callers must not act on it
    """
    if not valid_pkg(package):
        return None
    script = (
        f'F={_newest_logs_sh(package)}; [ -n "$F" ] || exit 3; '
        f"echo D=$(tail -n 800 \"$F\" | grep -a -c -i -E '{_DISCONNECT_RE}'); "
        f"echo J=$(grep -a -n -E '{_JOIN_RE}' \"$F\" | tail -n 1 | cut -c1-90); "
        f"echo L=$(grep -a -n -E '{_LEAVE_RE}' \"$F\" | tail -n 1 | cut -c1-90); "
        f"echo T=$(tail -n 1 \"$F\" | cut -c1-70); "
        f"echo K=$(grep -a -n -E '{_LOGIN_RE}' \"$F\" | tail -n 1 | cut -c1-90)"
    )
    res = run_cmd(f"su -c {shlex.quote(script)}", timeout=6)
    found = dict(re.findall(r'^([DJLTK])=(.*)$', res.stdout or '', re.MULTILINE))
    if res.returncode != 0 or 'D' not in found:
        return None
    if int(found['D'] or 0) > 0:
        return 'disconnected'
    join_line, leave_line, login_line = (int((re.match(r'(\d+):', found.get(k, '')) or [0, 0])[1]) for k in 'JLK')
    if join_line and join_line > leave_line:
        return 'ingame'
    if login_line <= join_line:  # home surface hasn't come back since the last join attempt
        return 'loading'
    last_event = max(filter(None, (_log_seconds(found.get(k)) for k in 'JLK')), default=None)
    now_t = _log_seconds(found.get('T'))
    settled = None not in (last_event, now_t) and now_t - last_event >= LOG_SETTLE_SECONDS
    return 'home' if settled else 'loading'

# ==============================================================================
# 2. DEVICE & SYSTEM STATISTICS
# ==============================================================================

_prev_idle = None
_prev_total = None
_prev_stat_content = None
_last_cpu_pct = 0.0
_proc_read_mode = {}   # path -> 'direct' | 'su' | 'unavailable', decided once per path
_proc_su_cache = {}    # path -> (content, timestamp) — last successful su read

SU_READ_MIN_INTERVAL = 5  # seconds between su re-reads of the same /proc path — matches the dashboard's 5s redraw cadence so stats actually refresh on screen instead of appearing frozen for multiple frames

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

_last_ram_usage = (0.0, 0.0)
_last_ram_time = 0.0
RAM_CACHE_TTL = 15.0  # seconds

def _kb_to_gb(kb):
    return round(kb / 1024 / 1024, 2)

def _ram_from_proc_meminfo():
    """(used_kb, total_kb) from /proc/meminfo, or None. Cheap: no process spawn when readable."""
    content = _read_proc_file('/proc/meminfo') or ''
    meminfo = {}
    for line in content.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            meminfo[parts[0].rstrip(':')] = int(parts[1])
    total_kb = meminfo.get('MemTotal', 0)
    if total_kb <= 0:
        return None
    avail_kb = meminfo.get('MemAvailable') or (meminfo.get('MemFree', 0) + meminfo.get('Buffers', 0) + meminfo.get('Cached', 0))
    return max(0, total_kb - avail_kb), total_kb

def _ram_from_dumpsys():
    """(used_kb, total_kb) from `dumpsys meminfo`, or None. Heavy: only a fallback."""
    for dump_cmd in ("su -c 'dumpsys meminfo'", 'dumpsys meminfo'):
        res = run_cmd(dump_cmd, timeout=3)
        if res.returncode != 0 or not res.stdout.strip():
            continue
        values = {}
        for label in ('Total RAM', 'Free RAM', 'Used RAM'):
            m = re.search(rf'{label}:\s*([\d,]+)\s*K', res.stdout)
            values[label] = int(m.group(1).replace(',', '')) if m else 0
        total_kb = values['Total RAM']
        if total_kb > 0:
            used_kb = values['Used RAM'] or max(0, total_kb - values['Free RAM'])
            return used_kb, total_kb
    return None

def get_ram_usage():
    """Live system RAM (used_gb, total_gb), cached for RAM_CACHE_TTL seconds.
    /proc/meminfo is tried first because `dumpsys meminfo` is expensive and,
    when polled every dashboard frame, crashes constrained Android shells."""
    global _last_ram_usage, _last_ram_time
    now = time.time()
    if now - _last_ram_time < RAM_CACHE_TTL and _last_ram_usage[1] > 0:
        return _last_ram_usage
    try:
        reading = _ram_from_proc_meminfo() or _ram_from_dumpsys()
        if reading:
            _last_ram_usage = (_kb_to_gb(reading[0]), _kb_to_gb(reading[1]))
    except Exception:
        pass
    _last_ram_time = now  # also throttle failures so a broken reader isn't retried every frame
    return _last_ram_usage

_process_ram_cache = {}  # package -> (ram_mb | None, timestamp)

def _parse_process_ram_kb(content):
    """Parse aggregate PSS in kB from human-readable or CSV dumpsys output."""
    if not content:
        return None

    match = re.search(r'\bTOTAL\s+PSS:\s*([\d,]+)', content, re.IGNORECASE)
    if match:
        return int(match.group(1).replace(',', ''))

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.lower().startswith('total,'):
            fields = [field.strip().replace(',', '') for field in line.split(',')]
            for field in fields[1:]:
                if field.isdigit():
                    return int(field)
        match = re.match(r'^TOTAL\s*:?[ \t]+([\d,]+)\b', line, re.IGNORECASE)
        if match:
            return int(match.group(1).replace(',', ''))
    return None

def get_process_ram(package, force=False):
    """Return total app-process memory in MB, preferring aggregate PSS."""
    package = str(package or '').strip()
    if not valid_pkg(package):
        return None

    now = time.time()
    refresh = max(10.0, float(config.get('app_ram_refresh_interval', 30)))
    cached = _process_ram_cache.get(package)
    if cached and not force and (now - cached[1]) < refresh:
        return cached[0]

    ram_kb = None
    for command in (
        f"su -c 'dumpsys meminfo {package}'",
        f'dumpsys meminfo {package}',
        f"su -c 'dumpsys meminfo {package} -c'",
    ):
        result = run_cmd(command, timeout=5)
        if result.returncode == 0 and result.stdout:
            ram_kb = _parse_process_ram_kb(result.stdout)
            if ram_kb is not None:
                break

    if ram_kb is None:
        # Kernel fallback: sum PSS for every process owned by this package.
        # VmRSS is used only on kernels without smaps_rollup.
        script = (
            f'for p in $(pidof {package} 2>/dev/null); do '
            'if [ -r /proc/$p/smaps_rollup ]; then '
            "awk '/^Pss:/{print $2; exit}' /proc/$p/smaps_rollup 2>/dev/null; "
            'else '
            "awk '/^VmRSS:/{print $2; exit}' /proc/$p/status 2>/dev/null; "
            'fi; done'
        )
        for command in (f'su -c {shlex.quote(script)}', script):
            result = run_cmd(command, timeout=5)
            values = [int(value) for value in result.stdout.split() if value.isdigit()]
            if values:
                ram_kb = sum(values)
                break

    ram_mb = max(1, round(ram_kb / 1024)) if ram_kb and ram_kb > 0 else None
    _process_ram_cache[package] = (ram_mb, now)
    return ram_mb

def format_process_ram(ram_mb):
    return f'{int(ram_mb)} MB' if isinstance(ram_mb, (int, float)) and ram_mb > 0 else 'N/A'

_device_name_cache = None

def get_device_name():
    global _device_name_cache
    if _device_name_cache is None:
        _device_name_cache = run_cmd('getprop ro.product.model', timeout=3).stdout.strip() or 'Unknown'
    return _device_name_cache

def format_uptime(seconds):
    h, rem = divmod(int(seconds), 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}h:{m:02d}m:{sec:02d}s"

def take_screenshot(output_path=None):
    """Capture as root, then copy the PNG into a Termux-owned file."""
    output_path = output_path or os.path.join(os.path.expanduser('~'), '.rei_rejoin_screenshot.png')
    root_path = '/sdcard/rei_rejoin_webhook.png'
    try:
        command = f"su -c 'screencap -p {root_path} && base64 {root_path}'"
        result = subprocess.run(command, shell=True, capture_output=True, timeout=15)
        image_data = base64.b64decode(result.stdout, validate=False)
        if result.returncode == 0 and image_data.startswith(b'\x89PNG\r\n\x1a\n'):
            with open(output_path, 'wb') as image_file:
                image_file.write(image_data)
            return output_path
        print(f'[!] Screenshot capture did not produce a PNG (exit {result.returncode}).')
    except Exception as e:
        print(f'[!] Screenshot capture error: {e}')
    return None

def normalize_webhook_url(webhook_url):
    """Normalize pasted webhook links and reject malformed URLs."""
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
    used_ram, total_ram = get_ram_usage()
    device = get_device_name()
    uptime_sec = time.time() - (start_time or time.time())
    uptime = format_uptime(uptime_sec)

    app_lines = ''
    if statuses:
        parts = []
        for i, (pkg, info) in enumerate(statuses.items(), 1):
            status = info.get('status', 'Unknown')
            ram = format_process_ram(info.get('ram_mb'))
            parts.append(
                f'**{i}.** {status} | `{pkg}`\n'
                f'    App RAM: {ram}'
            )
        if parts:
            app_lines = '\n'.join(parts)

    description = (
        f'**Device:** {device}\n'
        f'**Monitor Uptime:** {uptime}\n'
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
    has_shot = bool(screenshot_path and os.path.exists(screenshot_path))
    if has_shot:
        embed['image'] = {'url': 'attachment://screenshot.png'}
        payload['attachments'] = [{'id': 0, 'filename': 'screenshot.png'}]

    sent = _post_webhook_curl(webhook_url, payload, screenshot_path if has_shot else None)
    if not sent:
        sent = _post_webhook_urllib(webhook_url, payload, screenshot_path if has_shot else None)
    if sent:
        print('[+] Webhook sent with screenshot.' if has_shot else '[+] Webhook JSON sent.')

def _post_webhook_curl(webhook_url, payload, screenshot_path):
    """curl is the most reliable Discord transport on Termux."""
    args = ['curl', '--noproxy', '*', '-sS', '-o', '/dev/null', '-w', '%{http_code}', '-X', 'POST',
            '-F', 'payload_json=' + json.dumps(payload)]
    if screenshot_path:
        args += ['-F', 'files[0]=@' + screenshot_path + ';type=image/png']
    args.append(webhook_url)
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip().startswith('2'):
            return True
        print(f"[!] curl webhook send failed: {result.stderr.strip() or result.stdout.strip()}")
    except Exception as e:
        print(f"[!] curl webhook send error: {e}")
    return False

def _post_webhook_urllib(webhook_url, payload, screenshot_path):
    """Fallback transport: multipart when a screenshot exists, otherwise plain JSON."""
    # Ignore malformed Android/Termux proxy environment variables.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        if screenshot_path:
            boundary = '----ReiRejoinBoundary7MA4YWxkTrZu0gW'
            with open(screenshot_path, 'rb') as f:
                img_data = f.read()
            body = b'\r\n'.join([
                f'--{boundary}'.encode(),
                b'Content-Disposition: form-data; name="payload_json"',
                b'Content-Type: application/json',
                b'',
                json.dumps(payload).encode('utf-8'),
                f'--{boundary}'.encode(),
                b'Content-Disposition: form-data; name="files[0]"; filename="screenshot.png"',
                b'Content-Type: image/png',
                b'',
                img_data,
                f'--{boundary}--'.encode(),
                b'',
            ])
            content_type = f'multipart/form-data; boundary={boundary}'
        else:
            body, content_type = json.dumps(payload).encode('utf-8'), 'application/json'
        req = urllib.request.Request(webhook_url, data=body, headers={'Content-Type': content_type}, method='POST')
        opener.open(req, timeout=20).close()
        return True
    except Exception as e:
        print(f"[!] Webhook send error: {e}")
        return False

class WebhookThread(threading.Thread):
    def __init__(self, webhook_url, interval, get_status_fn, start_time):
        super().__init__(daemon=True)
        self.webhook_url = webhook_url
        self.interval = interval
        self.get_status_fn = get_status_fn
        self.start_time = start_time
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.is_set():
            try:
                send_discord_webhook(self.webhook_url, self.get_status_fn(), self.start_time)
            except Exception as e:
                print(f"[!] Webhook thread error: {e}")
            self.stop_event.wait(max(10, self.interval))

    def stop(self):
        self.stop_event.set()

class AppRamThread(threading.Thread):
    """Sample per-app RAM away from the dashboard and rejoin loops."""
    def __init__(self, packages, interval, set_ram_fn):
        super().__init__(daemon=True)
        self.packages = list(packages)
        self.interval = max(10.0, float(interval))
        self.set_ram_fn = set_ram_fn
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.is_set():
            cycle_started = time.monotonic()
            any_value = False
            for package in self.packages:
                if self.stop_event.is_set():
                    return
                ram_mb = get_process_ram(package, force=True)
                any_value = any_value or ram_mb is not None
                self.set_ram_fn(package, ram_mb)
                if self.stop_event.wait(0.1):
                    return
            elapsed = time.monotonic() - cycle_started
            next_interval = self.interval if any_value else min(5.0, self.interval)
            self.stop_event.wait(max(1.0, next_interval - elapsed))

    def stop(self):
        self.stop_event.set()

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
        self.app_ram_thread = None
        self.recent_logs = []
        self.sort_thread = None
        self.stop_event = None
        self.state_lock = threading.RLock()

    def log(self, msg):
        ts = time.strftime('%H:%M:%S')
        entry = f"[{ts}] {msg}"
        with self.state_lock:
            self.recent_logs.append(entry)
            if len(self.recent_logs) > 15:
                self.recent_logs.pop(0)

    def set_status(self, pkg, status_str, **details):
        with self.state_lock:
            current = dict(self.status.get(pkg, {}))
            current.update({'status': status_str, 'time': time.time()})
            current.update(details)
            self.status[pkg] = current

    def get_status(self):
        with self.state_lock:
            return {pkg: dict(info) for pkg, info in self.status.items()}

    def set_app_ram(self, pkg, ram_mb):
        with self.state_lock:
            self.status.setdefault(pkg, {}).update(ram_mb=ram_mb, ram_time=time.time())

    def recent_log_lines(self, count):
        with self.state_lock:
            return self.recent_logs[-count:]

    def start(self, cfg):
        if self.running or (self.thread and self.thread.is_alive()):
            print("[!] Auto rejoin is already running.")
            return False

        packages = get_target_packages(cfg)
        if not packages:
            self.log("No Roblox packages selected or detected! Please select packages in Option 2.")
            return False

        self.running = True
        self.start_time = time.time()
        self.stop_event = threading.Event()

        self.app_ram_thread = AppRamThread(
            packages,
            float(cfg.get('app_ram_refresh_interval', 30)),
            self.set_app_ram,
        )
        self.app_ram_thread.start()

        if cfg.get('webhook_enabled') and cfg.get('webhook_url'):
            self.webhook_thread = WebhookThread(
                cfg.get('webhook_url'),
                float(cfg.get('webhook_interval', 60)),
                self.get_status,
                self.start_time
            )
            self.webhook_thread.start()

        self.thread = threading.Thread(
            target=self._run_loop,
            args=(list(packages), dict(cfg), self.stop_event),
            daemon=True
        )
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        if self.stop_event:
            self.stop_event.set()
        if self.webhook_thread:
            self.webhook_thread.stop()
            if self.webhook_thread is not threading.current_thread():
                self.webhook_thread.join(timeout=2)
            self.webhook_thread = None
        if self.app_ram_thread:
            self.app_ram_thread.stop()
            if self.app_ram_thread is not threading.current_thread():
                self.app_ram_thread.join(timeout=6)
            self.app_ram_thread = None
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=8)
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
        STATUS_STYLES = {
            'Ingame': (GREEN, 'Ingame'), 'Rejoining': (RED, 'Rejoining'), 'Rejoining Game': (RED, 'Rejoining'),
            'Launching': (CYAN, 'Launching'), 'Retry Wait': (YELLOW, 'Wait'),
            'Launch Failed': (RED, 'Failed'), 'Unknown': (YELLOW, 'Unknown'), 'Home Page': (YELLOW, 'Home'),
        }

        pkgs = get_target_packages(cfg)  # resolved once; per-frame package scans spawn many shells
        frame_lines = []

        def strip(s):
            return re.sub(r'\033\[[0-9;]*m', '', s)

        def out(s=""):
            """print() relies on the terminal translating '\\n' to CRLF (moving
            the cursor back to column 0). On a pty/terminal where that
            translation isn't happening, '\\n' only moves down a row and each
            line starts wherever the previous one's cursor ended up, producing
            a diagonal staircase effect. Writing '\\r\\n' explicitly makes the
            column-0 return independent of the terminal's line-ending mode.

            Lines are collected and written as ONE frame (see draw_frame) so the
            screen is never half-drawn and nothing scrolls into the scrollback."""
            frame_lines.append(str(s))

        def draw_frame():
            """Home the cursor, repaint every line (clearing to end of line) and clear below.
            The dashboard runs on the alternate screen, which has no scrollback, but a frame
            taller than the terminal would still scroll it, so keep only the bottom rows that fit
            (the table and activity log, not the title banner)."""
            try:
                rows = os.get_terminal_size().lines
            except OSError:
                rows = 24
            lines = frame_lines[-max(1, rows - 1):]
            sys.stdout.write("\033[H" + "".join(line + "\033[K\r\n" for line in lines) + "\033[J")
            sys.stdout.flush()

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
            N = 6
            budget = max(20, target_w - (3 * N + 1))
            no_w, user_w, stat_w, ram_w = 1, 4, 10, 5
            remaining = max(8, budget - no_w - user_w - stat_w - ram_w)
            pkg_w  = max(4, remaining * 2 // 5)
            game_w = max(4, remaining - pkg_w)
            # Short header labels so they never overflow a narrow column on their own.
            cols = [("N", no_w), ("Usr", user_w), ("Pkg", pkg_w), ("Stat", stat_w), ("RAM", ram_w), ("Game", game_w)]
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

            # Two stat columns sized to sum to total_w: for N cells, overhead
            # is 3*N+1 (each cell is width+2 chars, plus N+1 pipes).
            stat_w = total_w - (3 * 2 + 1)
            cpu_w  = stat_w // 2
            ram_w  = stat_w - cpu_w

            return cols, total_w, cell, pipe_row, table_row, sep, table_sep, cpu_w, ram_w

        input_fd = None
        saved_terminal_mode = None
        termios_module = None
        try:
            if os.name == 'posix':
                import termios
                import tty
                candidate_fd = sys.stdin.fileno()
                if os.isatty(candidate_fd):
                    saved_terminal_mode = termios.tcgetattr(candidate_fd)
                    tty.setcbreak(candidate_fd)
                    input_fd = candidate_fd
                    termios_module = termios

            # Alternate screen: no scrollback, so frames can't pile up in history; the menu comes back intact.
            sys.stdout.write("\033[?1049h\033[?25l")
            sys.stdout.flush()
            while self.running:
                frame_started = time.monotonic()
                frame_lines.clear()

                target_w = detect_width(cfg.get('dashboard_width', 40))
                COLS, TOTAL_W, cell, pipe_row, table_row, SEP, TABLE_SEP, cpu_w, ram_w = build_layout(target_w)

                w_st = f"{GREEN}Enable{RESET}"  if cfg.get('webhook_enabled')       else f"{RED}Disable{RESET}"
                c_st = f"{GREEN}Enable{RESET}"  if cfg.get('clear_cache')           else f"{RED}Disable{RESET}"
                game_mode = game_mode_label(cfg)

                cpu = get_cpu_usage()
                used_ram, total_ram = get_ram_usage()
                uptime = format_uptime(time.time() - (self.start_time or time.time()))

                # ── Header ────────────────────────────────────────
                title = "REI REJOIN"
                pad = max(0, (TOTAL_W - len(f">>> {title} <<<")) // 2)
                out(f"{BOLD}{CYAN}{' ' * pad}>>> {title} <<<{RESET}")
                out(f"{BLUE}Discord: discord.gg/5G3cStpbcx{RESET}")
                out(f"{BLUE}By seisen_{RESET}")
                out(f"{CYAN}GAME MODE: {game_mode}{RESET}")
                out(f"WEBHOOK: {w_st}")
                out(f"CLEAR CACHE: {c_st}")
                out(f"UPTIME: {uptime}")
                out(SEP)

                # ── Stats ──────────────────────────────────────────
                out(pipe_row([(f"Cpu usage: {cpu} %", cpu_w), (f"Ram usage: {used_ram:.2f} / {total_ram:.2f} GB", ram_w)]))
                
                if getattr(self, '_su_broken', False):
                    out(f"{RED}{BOLD}  [!] ROOT (SU) IS BROKEN/JAMMED! RESTART TERMUX OR REBOOT PHONE!{RESET}")
                
                out(SEP)

                # ── Table ──────────────────────────────────────────
                out(f"{BOLD}{table_row([label for label, _ in COLS])}{RESET}")
                out(TABLE_SEP)

                statuses = self.get_status()
                for idx, p in enumerate(pkgs, 1):
                    info_d = statuses.get(p, {})
                    st = info_d.get('status', 'Launching')
                    ram_mb = info_d.get('ram_mb')
                    ram_short = f"{int(ram_mb)}M" if isinstance(ram_mb, (int, float)) and ram_mb > 0 else "N/A"
                    color, label = STATUS_STYLES.get(st, ('', st[:9]))
                    out(table_row([idx, get_package_username(p, cfg, idx), p, f"{color}{label}{RESET}" if color else label,
                                   ram_short, _resolve_package_game_name(p, cfg)]))

                out(SEP)
                out(f"{BOLD}[Recent Activity Log]{RESET}")
                logs_to_show = self.recent_log_lines(3) or ["[i] Monitoring active packages..."]
                for l in logs_to_show:
                    out(f"  {l}")
                out(SEP)
                out(f"{BOLD}[Enter] Stop & Main Menu{RESET}")
                draw_frame()

                refresh_interval = max(0.5, float(cfg.get('dashboard_refresh_interval', 2)))
                deadline = frame_started + refresh_interval
                while self.running and time.monotonic() < deadline:
                    wait_time = min(0.1, max(0.0, deadline - time.monotonic()))
                    if input_fd is not None:
                        rlist, _, _ = select.select([input_fd], [], [], wait_time)
                        if rlist and os.read(input_fd, 1) in (b'\r', b'\n'):
                            self.stop()
                            break
                    elif os.name == 'posix':
                        rlist, _, _ = select.select([sys.stdin], [], [], wait_time)
                        if rlist:
                            sys.stdin.readline()
                            self.stop()
                            break
                    else:
                        time.sleep(wait_time)

        except KeyboardInterrupt:
            pass
        except Exception as e:
            self.log(f"[!] Dashboard error: {e}")
        finally:
            sys.stdout.write("\033[?25h\033[?1049l")  # show cursor, leave the alternate screen
            sys.stdout.flush()
            if input_fd is not None and saved_terminal_mode is not None:
                try:
                    termios_module.tcsetattr(input_fd, termios_module.TCSADRAIN, saved_terminal_mode)
                except Exception:
                    pass

    def _run_loop(self, packages, cfg, stop_event):
        """Thread entry: show a crash in the dashboard log instead of dying silently."""
        try:
            self._loop(packages, cfg, stop_event)
        except Exception as e:
            self.log(f"[!] Engine crashed: {e!r}")

    @staticmethod
    def _scan_logs_due(st, now, interval):
        """True at most once per interval per package (the log scan shells out as root)."""
        if now - st['log_at'] < interval:
            return False
        st['log_at'] = now
        return True

    def _loop(self, packages, cfg, stop_event):
        self._su_broken = not check_su_works()

        launch_wait  = float(cfg.get('launch_wait', 15))
        cooldown     = max(float(cfg.get('offline_wait', 15)), float(cfg.get('rejoin_cooldown', 10)))
        retry_limit  = int(cfg.get('retry_count', 3))
        retry_delay  = float(cfg.get('retry_delay', 30))
        grace        = float(cfg.get('launch_grace', 25))   # seconds after a launch before status checks begin
        join_wait    = max(grace, float(cfg.get('join_wait', 60)))  # no login marker by now: treat 'loading' as stuck
        home_enabled = cfg.get('home_rejoin_enabled', True)
        auto_sort    = cfg.get('auto_sort', True)
        poll         = min(float(cfg.get('check_interval', 2)), 5)
        sequential   = cfg.get('sequential_join', False)
        auto_clear   = cfg.get('clear_cache', False)
        WINDOW_CHECK = 5    # seconds between activity dumps
        LOG_CHECK    = 8    # seconds between log scans while in a game
        FAST_CHECK   = 3    # ...and while not in a game, so a stuck home page is caught quickly
        # attempts: launches since last healthy; next: earliest next rejoin;
        # missed: consecutive checks with no live window; log_at: last log scan;
        # state: last Roblox log state; relinks: game links re-sent since the last healthy state
        state = {pkg: {'attempts': 0, 'next': 0.0, 'missed': 0, 'log_at': 0.0, 'state': 'loading', 'relinks': 0} for pkg in packages}
        last_window_check = 0.0
        sorted_for = {}   # pkg -> launch timestamp whose window is already sorted (or given up on)
        sort_tries = {}
        SORT_DELAY = 6    # seconds after a launch before its window exists to be dragged

        def maybe_sort(now, running):
            """Tile windows of freshly (re)launched packages, in a thread so rejoin checks keep running."""
            if not auto_sort or (self.sort_thread and self.sort_thread.is_alive()):
                return
            pending = {pkg: self.last_launch.get(pkg, 0) for pkg in packages
                       if pkg in running and now - self.last_launch.get(pkg, 0) >= SORT_DELAY
                       and sorted_for.get(pkg) != self.last_launch.get(pkg)}
            if not pending:
                return

            def work():
                results = sort_windows(packages, only=set(pending))
                for pkg, launched in pending.items():
                    sort_tries[pkg] = sort_tries.get(pkg, 0) + 1
                    if results.get(pkg) or sort_tries[pkg] >= 3:
                        sorted_for[pkg], sort_tries[pkg] = launched, 0
                if any(results.values()):
                    self.log(f"Windows sorted: {sum(results.values())}/{len(results)} placed")

            self.sort_thread = threading.Thread(target=work, daemon=True)
            self.sort_thread.start()

        def launch(pkg, reason, prefer='component', cold=False):
            st = state[pkg]
            now = time.time()
            self.last_launch[pkg] = now
            if auto_sort and cold:  # a process about to START reads its window position: pre-place it
                width, height = get_screen_size()
                set_window_prefs(pkg, sort_targets(len(packages), width, height)[packages.index(pkg)])
            ok = launch_game(pkg, _resolve_package_game_id(pkg, cfg), prefer=prefer)
            st.update(attempts=st['attempts'] + 1, next=now + cooldown, missed=0, state='loading')
            self.set_status(pkg, 'Launching' if ok else 'Launch Failed',
                            attempts=st['attempts'], next_retry=st['next'], last_result=reason)
            self.log(f"[{pkg}] {reason}: {'accepted' if ok else 'failed'}")

        # Initial launch. Nothing is ever force-stopped: a running Roblox is simply sent the game
        # link, because force-stopping a clone's window makes Android close other apps too.
        already_running = get_running_packages(packages) or set()
        for i, pkg in enumerate(packages):
            if stop_event.is_set():
                break
            launch(pkg, 'Initial launch', cold=pkg not in already_running)
            if sequential and i < len(packages) - 1 and stop_event.wait(launch_wait):
                break

        if stop_event.wait(8):
            for pkg in packages:
                self.set_status(pkg, 'Stopped')
            return

        while self.running and not stop_event.is_set():
            try:
                now = time.time()
                running = get_running_packages(packages)
                if running is None:  # probe failed; keep current state and retry next cycle
                    stop_event.wait(poll)
                    continue

                # A closed window can leave a cached PID. Confirm its absence
                # twice before relaunching; an unavailable dump never counts.
                if now - last_window_check >= WINDOW_CHECK:
                    last_window_check = now
                    windows = get_active_package_tasks(packages)
                    for pkg, st in state.items():
                        settled = now - self.last_launch.get(pkg, 0) >= grace
                        gone = windows is not None and pkg in running and settled and pkg not in windows
                        st['missed'] = st['missed'] + 1 if gone else 0

                for pkg in packages:
                    if stop_event.is_set():
                        break
                    st = state[pkg]
                    window_closed = pkg in running and st['missed'] >= 2

                    if pkg not in running or window_closed:
                        reason = 'Window closed' if window_closed else 'Process not running'
                        if now < st['next']:
                            self.set_status(pkg, 'Retry Wait', attempts=st['attempts'], next_retry=st['next'], last_result=reason)
                        elif st['attempts'] >= retry_limit:
                            st.update(attempts=0, next=now + retry_delay)
                            self.log(f"[{pkg}] Retry batch exhausted; waiting {int(retry_delay)}s")
                            self.set_status(pkg, 'Retry Wait', attempts=retry_limit, next_retry=st['next'],
                                            last_result='Retry batch exhausted')
                        else:
                            self.set_status(pkg, 'Rejoining', attempts=st['attempts'] + 1)
                            if auto_clear:  # user opted in: wipes app data, which also stops the app
                                clear_app_cache(pkg)
                            launch(pkg, f"Rejoin attempt {st['attempts'] + 1}/{retry_limit} ({reason})", cold=pkg not in running)
                        continue

                    # Process and window are alive.
                    st.update(attempts=0, next=0.0)
                    since_launch = now - self.last_launch.get(pkg, 0)
                    if since_launch < grace:
                        self.set_status(pkg, 'Launching', attempts=0,
                                        last_result=f"Waiting for load ({int(grace - since_launch)}s)")
                    elif st['missed']:
                        self.set_status(pkg, 'Unknown', attempts=0, last_result='Window missing; confirming')
                    else:
                        if self._scan_logs_due(st, now, LOG_CHECK if st['state'] == 'ingame' else FAST_CHECK):
                            log_state = get_roblox_log_state(pkg)
                            if log_state == 'loading' and since_launch >= join_wait:
                                log_state = 'home'  # never joined and never settled: treat as stuck
                            if log_state is not None:  # unknown never changes anything
                                st['state'] = log_state
                                if log_state == 'ingame':
                                    st['relinks'] = 0
                            stuck_home = home_enabled and log_state == 'home'
                            if stuck_home or log_state == 'disconnected':
                                # Re-send the game link to the running app. It joins from the home page or
                                # a disconnect screen without restarting or force-stopping anything.
                                reason = 'Stuck on Home page' if stuck_home else 'Disconnected from server'
                                st['relinks'] += 1
                                self.log(f"[{pkg}] {reason} (per Roblox log); re-sending game link (#{st['relinks']})")
                                launch(pkg, reason, prefer='component' if st['relinks'] % 2 else 'package')
                                continue
                        if st['state'] == 'home':
                            self.set_status(pkg, 'Home Page', attempts=0, last_result='On Roblox home page')
                        else:
                            self.set_status(pkg, 'Ingame', attempts=0, last_result='Process running')
                maybe_sort(now, running)
            except Exception as e:
                self.log(f"[!] Rejoin cycle error (continuing): {e}")

            stop_event.wait(poll)

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
    print(f"Game Mode: {game_mode_label(config)}")

    roblox_pkgs = get_roblox_packages(force=True)
    running_now = get_running_packages(roblox_pkgs) or set()
    print(f"\nDetected Roblox & Executor Packages ({len(roblox_pkgs)}):")
    for pkg in roblox_pkgs:
        running = pkg in running_now
        status_str = "RUNNING" if running else "STOPPED"
        ram = format_process_ram(get_process_ram(pkg)) if running else 'N/A'
        selected = "*" if pkg in config.get('selected_packages', []) else " "
        pkg_gname = _resolve_package_game_name(pkg, config)
        print(f" [{selected}] {pkg:<30} [{status_str:<7}] Game: {pkg_gname:<18} RAM: {ram}")
    print("=" * 60)

def pause():
    prompt("\nPress Enter to return to menu...")

def game_mode_label(cfg):
    return 'CUSTOM PER PACKAGE' if cfg.get('game_method') == 'each' else 'SAME GAME FOR ALL'

def set_selected_packages(packages):
    config['selected_packages'] = list(dict.fromkeys(packages))
    save_config()

def ask_int(label, key):
    """Prompt for an integer setting; blank or invalid input keeps the current value."""
    value = prompt(f"{label} [{config.get(key, DEFAULT_CONFIG.get(key))}]: ").strip()
    if value.isdigit():
        config[key] = int(value)

def ask_bool(label, key):
    value = prompt(f"{label} (y/n) [{config.get(key, False)}]: ").strip().lower()
    if value in ('y', 'n'):
        config[key] = (value == 'y')

def pick_game(header, allow_skip=False, id_width=15):
    """Show preset games and read a choice. Returns (name, id), or None when skipped."""
    print(header)
    for idx, (gname, gid) in enumerate(PRESET_GAMES, 1):
        print(f"  {idx}. {gname} (ID: {gid})")
    print("  C. Custom Place ID or Private Server Link")
    if allow_skip:
        print("  S. Skip (keep current setting)")
    while True:
        choice = prompt("Choice: ").strip()
        if allow_skip and (choice.upper() == 'S' or not choice):
            return None
        if choice.upper() == 'C':
            gid = prompt("  Enter Place ID / Link: ").strip()
            if not gid:
                print("  [!] No Place ID / Link entered. Try again.")
                continue
            return (f"Game ({gid[:id_width]}...)" if len(gid) > id_width else f"Game ({gid})"), gid
        if choice.isdigit() and 1 <= int(choice) <= len(PRESET_GAMES):
            return PRESET_GAMES[int(choice) - 1]
        print(f"  [!] Invalid choice '{choice}'. Enter 1-{len(PRESET_GAMES)}, C{', or S' if allow_skip else ''}.")

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
        print("6. Dashboard Width Configuration")
        print("7. Autoexecute Script Manager")
        print("8. START Auto Rejoin Loop & Live Dashboard")
        print("9. STOP Auto Rejoin Loop")
        print("10. Test Launch Selected Package Now")
        print("11. Send Manual Discord Webhook Test")
        print("12. Sort / Tile Roblox Windows Now")
        print("0. Exit CLI")
        choice = prompt("\nSelect option: ").strip()

        if choice == '1':
            show_status()
            pause()
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
                print("  - Type 'U' to set custom account names / usernames per package")
                print("  - Press Enter to keep current selection")
                indices = prompt("\nChoice: ").strip()

                cmd = indices.upper()
                selected = config.get('selected_packages', [])
                if cmd == 'ALL':
                    set_selected_packages(roblox_pkgs)
                elif cmd == 'CLEAR':
                    set_selected_packages([])
                elif cmd == 'U':
                    pkgs = selected or roblox_pkgs
                    print("\n[+] Configure custom account name / username for package:")
                    for p_i, p_name in enumerate(pkgs, 1):
                        print(f"  {p_i}. {p_name:<32} -> Current Name: {get_package_username(p_name, config, p_i)}")
                    uch = prompt("\nSelect Package Number: ").strip()
                    if uch.isdigit() and 1 <= int(uch) <= len(pkgs):
                        target_p = pkgs[int(uch) - 1]
                        new_u = prompt(f"Enter Account Username / Nickname for '{target_p}': ").strip()
                        if new_u:
                            config['package_account_names'][target_p] = new_u
                            save_config()
                            print(f"[+] Account name for {target_p} set to '{new_u}'")
                elif cmd == 'M':
                    custom_pkg = prompt("\nEnter exact Package Name (e.g. com.noka.client or free.nokaA): ").strip()
                    if valid_pkg(custom_pkg):
                        set_selected_packages(selected + [custom_pkg])
                    elif custom_pkg:
                        print("[!] Invalid package name.")
                elif indices:
                    chosen = list(selected)
                    for item in indices.split(','):
                        item = item.strip()
                        if '.' in item and valid_pkg(item):
                            chosen.append(item)
                        elif item.isdigit() and 0 <= int(item) - 1 < len(roblox_pkgs):
                            chosen.append(roblox_pkgs[int(item) - 1])
                    set_selected_packages(chosen)

                print("\n--- [ CURRENT SELECTED PACKAGES ] ---")
                if config.get('selected_packages'):
                    for p in config.get('selected_packages'):
                        print(f"  ✓ {p}")
                else:
                    print("  (None selected)")

                again = prompt("\nAdd/change another package now? (y/n, default n): ").strip().lower()
                if again != 'y':
                    break
            pause()

        elif choice == '3':
            while True:
                print("\n--- [ CONFIGURE GAME SETUP ] ---")
                print(f"Current Game Mode: {game_mode_label(config)}")
                print(f"Global Game Setting: {config.get('game_name', 'None')} ({config.get('game_id', 'N/A')})")
                print("\nSetup Options:")
                print("  1. Apply Same Game to ALL Packages")
                print("  2. Assign Custom Game PER Package (Roblox 1 -> Game A, Roblox 2 -> Game B)")
                gmode = prompt("\nSelect Mode (1 or 2, default 1): ").strip()

                if gmode == '2':
                    config['game_method'] = 'each'
                    pkgs = get_target_packages(config)
                    if not pkgs:
                        print("  [!] No Roblox packages detected or selected. Please select packages in Option 2 first!")
                    else:
                        print(f"\n[+] Configuring individual games for {len(pkgs)} package(s):")
                        for p_idx, pkg in enumerate(pkgs, 1):
                            print("\n" + "-" * 50)
                            print(f"[{p_idx}/{len(pkgs)}] Package: {pkg}")
                            print(f"Current Game: {_resolve_package_game_name(pkg, config)}")
                            picked = pick_game("Select Game for this package:", allow_skip=True, id_width=12)
                            if picked:
                                config['package_game_names'][pkg], config['package_games'][pkg] = picked
                    save_config()
                    print("\n[+] Per-Package Game Configurations Saved:")
                    for pkg in get_target_packages(config):
                        print(f"  ✓ {pkg:<30} -> {_resolve_package_game_name(pkg, config)}")
                else:
                    config['game_method'] = 'all'
                    config['game_name'], config['game_id'] = pick_game("\nPreset Games (Applies to ALL packages):")
                    save_config()
                    print(f"\n[+] Active Game ID / Link Set for ALL packages: {config.get('game_name')} ({config.get('game_id')})")

                again = prompt("\nConfigure another game/package now? (y/n, default n): ").strip().lower()
                if again != 'y':
                    break
            pause()

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
            pause()

        elif choice == '5':
            print("\nTiming Settings:")
            ask_int("Check Interval seconds", 'check_interval')
            ask_int("Offline Wait seconds", 'offline_wait')
            ask_int("Max Retries", 'retry_count')
            ask_bool("Sequential Join?", 'sequential_join')
            ask_bool("Auto-sort Roblox windows into a grid after launch?", 'auto_sort')
            ask_int("Retry Batch Delay seconds", 'retry_delay')
            ask_int("Minimum Rejoin Cooldown seconds", 'rejoin_cooldown')
            ask_int("Per-App RAM Refresh seconds", 'app_ram_refresh_interval')
            ask_bool("Clear ALL App Data on Rejoin (pm clear; may sign out accounts)?", 'clear_cache')
            ask_int("Launch Grace Period (hide Launching status after X seconds)", 'launch_grace')
            save_config()
            print("\n[+] Timing settings updated.")
            pause()

        elif choice == '6':
            print("\n--- [ DASHBOARD WIDTH ] ---")
            print(f"Current Dashboard Table Width: {config.get('dashboard_width', 40)} columns")
            print("\nThe live dashboard draws a fixed-width table. Run 'stty size' in Termux")
            print("(second number = columns) to find your real width, then set a table width")
            print("a few columns narrower (e.g. columns=50 -> try 44).")
            wch = prompt(f"Dashboard table width in columns [{config.get('dashboard_width', 40)}]: ").strip()
            if wch.isdigit() and int(wch) >= 30:
                config['dashboard_width'] = int(wch)
                print(f"[+] Dashboard table width set to: {config['dashboard_width']} columns")
            elif wch:
                print("[!] Ignored — enter a number of 30 or higher.")
            save_config()
            pause()

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
            pause()

        elif choice == '8':
            rejoin_engine.start(config)
            rejoin_engine.render_live_dashboard(config)
            rejoin_engine.stop()
            try:
                import termios
                termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
                if os.name == 'posix':
                    os.system('stty sane 2>/dev/null')
            except Exception:
                pass
            print("\n[+] Stopped Auto Rejoin and returned to Main Menu.")
            time.sleep(0.5)

        elif choice == '9':
            rejoin_engine.stop()
            print("\n[+] Auto Rejoin Engine stopped.")
            pause()

        elif choice == '10':
            pkgs = get_target_packages(config)
            if not pkgs:
                print("[!] Please select packages first.")
            else:
                for p in pkgs:
                    gid = _resolve_package_game_id(p, config)
                    gname = _resolve_package_game_name(p, config)
                    if not gid:
                        print(f"[!] No Game ID configured for {p}. Skipping.")
                        continue
                    print(f"Launching {p} into '{gname}' (ID: {gid})...")
                    launch_game(p, gid)
            pause()

        elif choice == '11':
            wurl = config.get('webhook_url')
            if not wurl:
                print("[!] No webhook URL set!")
            else:
                print("Sending test webhook...")
                send_discord_webhook(wurl, rejoin_engine.get_status(), time.time())
            pause()

        elif choice == '12':
            pkgs = get_target_packages(config)
            if not pkgs:
                print("[!] Please select packages first.")
            else:
                print(f"Sorting {len(pkgs)} window(s) into a grid (needs the games to be open)...")
                for pkg, ok in sort_windows(pkgs).items():
                    print(f"  {'OK  ' if ok else 'FAIL'} {pkg}")
            pause()

        elif choice == '0':
            if rejoin_engine.running:
                rejoin_engine.stop()
            if os.name == 'posix':
                os.system('stty sane 2>/dev/null')
            print("Exiting REI REJOIN CLI. Goodbye!")
            sys.exit(0)

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="REI REJOIN Roblox Account Manager - Global Termux Core Script")
    parser.add_argument("--daemon", action="store_true", help="Run auto-rejoin immediately in headless daemon mode")
    parser.add_argument("--scan", action="store_true", help="Scan installed Roblox packages and list them")
    args = parser.parse_args()

    load_config()

    if args.scan:
        show_status()
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
