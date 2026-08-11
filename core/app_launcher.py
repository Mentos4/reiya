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


def launch_game(package, game_id):
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

    try:
        result = subprocess.run(
            ['am', 'start', '-a', 'android.intent.action.VIEW', '-d', url],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
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
