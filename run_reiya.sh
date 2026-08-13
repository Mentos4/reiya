#!/data/data/com.termux/files/usr/bin/bash

# Script to run Reiya Core Global in Termux Terminal

echo "=================================================="
echo "    Launching Reiya Core Global in Termux...      "
echo "=================================================="

# Ensure Python is installed
if ! command -v python &> /dev/null
then
    echo "[!] Python not found in Termux. Installing python..."
    pkg update -y && pkg install python -y
fi

# Ensure storage permission if required
if [ ! -d "/sdcard" ]; then
    echo "[!] Requesting Android storage permission..."
    termux-setup-storage
fi

# Run the python global core script
python reiya_terminal.py "$@"
