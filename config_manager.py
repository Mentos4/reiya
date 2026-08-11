import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'config.json')

DEFAULT_CONFIG = {
    # Timing
    'rejoin_interval': 9999999,
    'offline_wait': 15,
    'retry_count': 3,
    'retry_delay': 30,
    'check_interval': 10,
    'launch_wait': 15,
    'rejoin_cooldown': 10,
    'trigger': 'completed',
    'rejoin_timeout': 120,
    'check_ui_delay': 120,
    # Toggles
    'sequential_join': False,
    'clear_cache': False,
    'webhook_enabled': False,
    # Packages
    'selected_packages': [],
    # Game setup
    'game_method': 'all',
    'game_id': '',
    'game_name': '',
    'package_games': {},
    # Webhook
    'webhook_url': '',
    'webhook_interval': 60,
    # Autoexecute
    'autoexecute_path': '/sdcard/Delta/Autoexecute',
}

# Module-level dict — imported directly by all screens
config = DEFAULT_CONFIG.copy()


def load_config():
    global config
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved = json.load(f)
            config.update(saved)
        except Exception:
            pass
    return config


def save_config():
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2, default=str)
