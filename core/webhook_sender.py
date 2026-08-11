import json
import time
import threading

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from core.device_stats import (
    get_cpu_usage, get_ram_usage, get_device_name,
    format_uptime, take_screenshot
)


class WebhookSender:
    def __init__(self):
        self._thread = None
        self._running = False
        self._start_time = None
        self._get_status = None

    def start(self, webhook_url, interval, get_status_cb=None):
        if self._running:
            return
        self._running = True
        self._start_time = time.time()
        self._get_status = get_status_cb
        self._thread = threading.Thread(
            target=self._loop,
            args=(webhook_url, interval),
            daemon=True
        )
        self._thread.start()

    def stop(self):
        self._running = False

    def is_running(self):
        return self._running

    def _loop(self, webhook_url, interval):
        while self._running:
            try:
                self._send(webhook_url)
            except Exception:
                pass
            time.sleep(max(10, interval))

    def send_now(self, webhook_url):
        threading.Thread(
            target=self._send, args=(webhook_url,), daemon=True
        ).start()

    def _send(self, webhook_url):
        if not HAS_REQUESTS or not webhook_url:
            return

        cpu = get_cpu_usage()
        used_ram, total_ram = get_ram_usage()
        device = get_device_name()
        uptime = format_uptime(time.time() - (self._start_time or time.time()))

        app_lines = ''
        if self._get_status:
            statuses = self._get_status()
            parts = []
            for i, (pkg, info) in enumerate(statuses.items(), 1):
                status = info.get('status', 'Unknown')
                ram = info.get('ram', 0)
                cpu_p = info.get('cpu', 0.0)
                parts.append(
                    f'**{i}.** {status} | `{pkg}`\n'
                    f'    RAM: {ram} MB | CPU: {cpu_p:.1f}%'
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
            'title': 'Wuyx Rejoin',
            'description': description,
            'color': 0x00CCCC,
            'footer': {'text': 'Roblox Manager'},
        }

        payload = {'embeds': [embed]}
        screenshot = take_screenshot()

        if screenshot:
            try:
                with open(screenshot, 'rb') as f:
                    img = f.read()
                requests.post(
                    webhook_url,
                    data={'payload_json': json.dumps(payload)},
                    files={'file': ('screenshot.png', img, 'image/png')},
                    timeout=20
                )
                return
            except Exception:
                pass

        try:
            requests.post(webhook_url, json=payload, timeout=15)
        except Exception:
            pass


webhook_sender = WebhookSender()
