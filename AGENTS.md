# Agent & Developer Guidelines - REI REJOIN Core

## 1. Versioning & Build Timestamp Rule
Whenever making ANY changes or bug fixes to `reiya_terminal.py`, you **MUST** update the build version and timestamp at the top of the file:
- **`BUILD_VERSION`**: Increment version number (e.g., `v6.7.5-REI-REJOIN` -> `v6.7.6-REI-REJOIN`).
- **`BUILD_TIME`**: Update to the current UTC timestamp (e.g., `2026-08-18 16:54:00 UTC`).

---

## 2. User Installation & Update Command
When answering user queries about how to download, update, or run the script in Termux / Android, **ALWAYS** provide the following one-line command:

```bash
rm -f ~/reiya_terminal.py && curl -sL "https://raw.githubusercontent.com/Mentos4/reiya/main/reiya_terminal.py?t=$(date +%s)" -o ~/reiya_terminal.py && python ~/reiya_terminal.py
```

This command bypasses local GitHub CDN caching (`?t=$(date +%s)`), ensures old versions are removed (`rm -f`), downloads the latest `reiya_terminal.py`, and launches it immediately in Python.
