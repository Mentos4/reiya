import subprocess
import time

PRESET_GAMES = [
    ('Blox Fruits',              '2753915549'),
    ('Sailor Piece',             '16232032796'),
    ('King Legacy',              '5032219830'),
    ('Bee Swarm Simulator',      '1537690962'),
    ('Pet Simulator 99',         '8737899170'),
    ('Attack on Titan Revolution', '13822889351'),
    ('Grow a Garden 2',          '126884695'),
]


def get_installed_packages():
    try:
        result = subprocess.run(
            ['pm', 'list', 'packages'],
            capture_output=True, text=True, timeout=10
        )
        packages = []
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if line.startswith('package:'):
                packages.append(line[8:])
        return sorted(packages)
    except Exception:
        return []


def get_roblox_packages():
    all_pkgs = get_installed_packages()
    keywords = ['roblox', 'noka', 'blox', 'delta', 'arceus']
    return [p for p in all_pkgs
            if any(k in p.lower() for k in keywords)]


def is_app_running(package):
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
    try:
        res = subprocess.run(['wm', 'size'], capture_output=True, text=True, timeout=3)
        match = re.search(r'(\d+)x(\d+)', res.stdout)
        if match:
            return int(match.group(1)), int(match.group(2))
    except Exception:
        pass
    return 1280, 720


def calculate_window_bounds(index, total_apps, screen_w=None, screen_h=None, mode='left_stack'):
    import math
    if not screen_w or not screen_h:
        screen_w, screen_h = get_screen_size()
    total_apps = max(1, total_apps)

    if mode == 'left_stack':
        half_w = int(screen_w * 0.5)
        cell_h = int(screen_h / total_apps)
        return 0, index * cell_h, half_w, (index + 1) * cell_h

    cols = math.ceil(math.sqrt(total_apps))
    rows = math.ceil(total_apps / cols)
    cell_w = int(screen_w / cols)
    cell_h = int(screen_h / rows)
    r, c = index // cols, index % cols
    return c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h


def launch_game(package, game_id, bounds=None, freeform=True):
    game_id = str(game_id).strip()
    # Private server link format: PLACE_ID?privateServerLinkCode=LINK_CODE
    if '?privateServerLinkCode=' in game_id:
        parts = game_id.split('?privateServerLinkCode=', 1)
        place_id = parts[0]
        link_code = parts[1]
        url = f'roblox://placeId={place_id}&linkCode={link_code}'
    elif game_id.startswith('http'):
        # Extract place ID from URL
        import re
        match = re.search(r'/games/(\d+)', game_id)
        place_id = match.group(1) if match else game_id
        # Check for private server in URL
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
    except Exception:
        pass

    try:
        result = subprocess.run(
            ['am', 'start', '-a', 'android.intent.action.VIEW', '-d', url],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass

    # Fallback: monkey launcher
    try:
        subprocess.run(
            ['monkey', '-p', package, '-c',
             'android.intent.category.LAUNCHER', '1'],
            capture_output=True, timeout=10
        )
        return True
    except Exception:
        return False


def force_stop_app(package):
    try:
        subprocess.run(['am', 'force-stop', package], timeout=5)
        return True
    except Exception:
        return False


def clear_app_cache(package):
    try:
        subprocess.run(['pm', 'clear', package], timeout=10)
        return True
    except Exception:
        return False
