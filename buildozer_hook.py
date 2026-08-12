import subprocess
import sys

def init_python_for_android():
    """Fix pip compatibility issues before building."""
    venv_python = sys.executable
    try:
        # Upgrade pip to a compatible version
        subprocess.check_call([
            venv_python, '-m', 'pip', 'install', 
            '--upgrade', 'pip<24.1'
        ])
        print("✓ Pip upgraded successfully")
    except Exception as e:
        print(f"⚠ Pip upgrade failed: {e}")

if __name__ == '__main__':
    init_python_for_android()
