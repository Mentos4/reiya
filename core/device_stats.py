import os
import time
import subprocess

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
