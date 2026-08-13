# REI REJOIN — Changelog

> **Project:** `Mentos4/reiya` — `reiya_terminal.py`
> **Stack:** Python · Termux · Android (VPhone) · Roblox clone packages
>
> **How to update on device:**
> ```bash
> rm -f ~/reiya_terminal.py && curl -sL "https://raw.githubusercontent.com/Mentos4/reiya/main/reiya_terminal.py?t=" -o ~/reiya_terminal.py && python ~/reiya_terminal.py
> ```
>
> **How to push changes:**
> ```bash
> git add reiya_terminal.py && git commit -m "message" && git push origin main
> ```

---

## Architecture Notes

| Component | Location | Purpose |
|---|---|---|
| `is_app_running(pkg)` | ~L205 | Checks process alive via `pidof` (validates digits only) + `ps -A` grep fallback |
| `is_app_in_game(pkg)` | ~L230 | `dumpsys activity top` HOME_SIGNALS vs GAME_SIGNALS |
| `launch_game(pkg, gid)` | ~L320 | `am start -f 0x10000000` with `roblox://placeId=` deeplink |
| `TerminalRejoinLoop._loop()` | ~L790 | Main loop: grace period -> running check -> in_game check -> rejoin |
| `render_live_dashboard()` | ~L652 | Live terminal UI, uses `stty size` for real terminal width |

### Key Constants in `_loop()`
- `LAUNCH_GRACE = 20` — seconds after launch before checking state
- `check_interval = 8` — seconds between loop cycles

### Status Flow
```
Start       → Launching   (during LAUNCH_GRACE)
Process up  → Ingame      (is_app_in_game = True)
            → Home Page → Rejoining (is_app_in_game = False + home_rejoin_enabled)
Process down→ Rejoining   (force-stop then relaunch)
```

---

## Changelog

### 2026-08-13 — Session 1
- Renamed all labels to REI REJOIN
- Removed AUTO BYPASS and AUTO CHANGE ACCOUNT settings

### 2026-08-13 — Session 2
**Fix:** Removed force_stop_app from Home Screen rejoin (was crashing Termux)
```bash
git commit -m "Remove force_stop_app from Home Screen rejoin" && git push origin main
```

### 2026-08-13 — Session 3
**Fix:** Replaced mCurrentFocus (always shows Termux in split-screen) with dumpsys activity top
- Removed broken block ASCII art
- Removed blue decorative lines
```bash
git commit -m "Use dumpsys activity top for detection, remove broken ASCII art" && git push origin main
```

### 2026-08-13 — Session 4
**Fix:** Grace period + force-stop on Home Screen
- LAUNCH_GRACE = 20s
- Home Screen: force-stop + relaunch
- home_rejoin_enabled flag respected
- Startup wait 4s → 8s
```bash
git commit -m "Grace period 20s, force-stop on Home Screen, home_rejoin_enabled flag" && git push origin main
```

### 2026-08-13 — Session 5
**Fix:** Stuck Ingame bug — pidof returned error text, old code treated any output as running
- is_app_running: validates output is digits only (real PIDs)
- is_app_in_game fallback: False instead of is_app_running()
- Added GAME_SIGNALS list (gameactivity, robloxactivity, renderview)
```bash
git commit -m "Fix stuck Ingame: validate pidof PIDs, is_app_in_game fallback=False" && git push origin main
```

### 2026-08-13 — Session 6
**Fix:** UI broken in split-screen — shutil.get_terminal_size() returned full screen width
- Now uses stty size for real terminal width
- All layout lines capped to actual W chars
```bash
git commit -m "Fix UI: use stty size for real terminal width" && git push origin main
```

---

## Config Keys Reference

| Key | Default | Effect |
|---|---|---|
| `home_rejoin_enabled` | True | Enable Home Screen auto-rejoin |
| `auto_sort` | True | Enable window tiling |
| `webhook_enabled` | False | Webhook pings |
| `clear_cache` | False | Clear cache before rejoin |
| `check_interval` | 8 | Loop interval seconds |
| `launch_wait` | 15 | Wait between sequential launches |
| `game_id` | — | Roblox place ID or URL |
