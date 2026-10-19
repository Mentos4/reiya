# REI REJOIN — Agent Guidelines & Repository Context

## Project Overview
- **Repository:** Mentos4/reiya (`d:\Apps\Layer\reiya_terminal.py`)
- **Project Name:** Strictly **REI REJOIN** (Do NOT rename to anything else).
- **Target Environment:** Android / Termux (VPhone / VM / rooted/userland devices) running Roblox clone packages (e.g., `free.nokaA`, `com.roblox.client`).

---

## 🚨 MANDATORY AGENT WORKFLOW
Whenever you modify, fix, or update any code in this repository:
1. **Commit and Push Immediately:** Always run git commit and `git push origin main` after completing edits.
2. **Provide Update Command:** Always end your turn by giving the user the exact Termux update command:
```bash
rm -f ~/reiya_terminal.py && curl -sL "https://raw.githubusercontent.com/Mentos4/reiya/main/reiya_terminal.py?t=$(date +%s)" -o ~/reiya_terminal.py && python ~/reiya_terminal.py
```
3. **Include Date & Summary:** Document what changed in the response with the timestamp.

---

## 📐 Key Architecture & Code Rules

### 1. Process & App Status Detection
- **`is_app_running(package)` (~L205):** Checks pidof output. **MUST validate that output consists ONLY of numeric digits** (`all(part.isdigit() for part in out.split())`). On Android, pidof often prints error text (e.g., `pidof: free.nokaA: not found`) which must NOT be parsed as a running process!
- **`is_app_in_game(package)` (~L230):** Uses `dumpsys activity top` (NOT `dumpsys window windows` or `mCurrentFocus`, because `mCurrentFocus` always points to Termux when Termux is active in split screen).
  - Checks for `HOME_SIGNALS` (`nativemain`, `mainactivity`, `splashactivity`, `loginactivity`, etc.).
  - Checks for `GAME_SIGNALS` (`gameactivity`, `robloxactivity`, `renderview`).
  - If package is not found in the activity dump, fallback to `False` (safe rejoin).

### 2. Main Loop (`TerminalRejoinLoop._loop`) (~L790)
- **`LAUNCH_GRACE = 20`**: 20-second grace period after launching before status checks begin. Prevents false "Home Page" triggers while Roblox is loading.
- **`home_rejoin_enabled`**: Guard flag from cfg. If `False`, show `Home Page` status but do NOT re-send the game link.
- **Home Screen Rejoin:** NEVER force-stop the clone. Force-stopping a freeform clone window makes Android close other apps too (Termux included). Home/disconnect state comes from `get_roblox_log_state()` (newest Player log). Recovery re-sends the game link to the running app via `launch_game(..., prefer=...)`, alternating between the `ActivityProtocolLaunch` component intent and `am start -p {package}` on successive attempts, because a running Roblox silently ignores one of the two (exit code 0 either way) depending on its state.

### 3. Launch Intents (`launch_game`) (~L320)
- Uses `am start -f 0x10000000` (`FLAG_ACTIVITY_NEW_TASK`).
- Do NOT use `0x14000000` (`CLEAR_TASK`) as it forces process termination on some Android builds.

### 4. Terminal Dashboard UI (`render_live_dashboard`) (~L692)
- **Use `out(s)`, never bare `print()`, for every line in this function.** `out()` writes `s + "\r\n"` explicitly instead of relying on the terminal to translate `print()`'s `"\n"` into CRLF. On some Android/Termux ptys that translation doesn't happen, so `"\n"` only moves the cursor down a row without returning it to column 0 — each subsequent line then starts wherever the previous line's cursor ended up, producing a diagonal "staircase" of increasingly indented lines that eventually wrap mid-word. This was the actual root cause behind several rounds of "the dashboard is still misaligned" reports that earlier width/rotation fixes didn't touch.
- Pipe-bordered table layout (`| col | col |`), one setting per line — NOT two colored strings packed onto one shared line. The old half-width-per-line packing (`rpad` + string concatenation) was fragile with ANSI codes and was a separate source of misalignment; don't reintroduce it.
- `detect_width()` re-probes `stty size` / `tput cols` on EVERY refresh cycle (every 5s, inside the `while self.running` loop) — not once at startup. `set_landscape_orientation()` needs root/`su` and silently no-ops otherwise, so the terminal can keep rotating under the script; re-detecting every frame means the next redraw realigns instead of staying broken until restart. `cfg['dashboard_width']` (default 40, Option 6 → 4) is only the fallback used if detection fails. `build_layout(target_w)` derives `COLS`/`cell`/`pipe_row`/`table_row`/etc. fresh from whatever width was just detected — these are NOT precomputed once outside the loop.
- Header labels are deliberately short (`No`/`User`/`Pkg`/`Stat`/`Game`) so they never overflow even the narrowest allowed column widths, and `cell()` truncates any value longer than its column as a safety net — this prevents one long value from pushing every column after it out of alignment.
- `cell(val, width)` pads to `width+2` visible chars (ANSI codes excluded via `strip()`) to exactly match `TABLE_SEP`'s `'-' * (width+2)` segments. `pipe_row(cells_and_widths)` composes one bordered row from `(value, width)` pairs — for N cells the total overhead is `3*N+1` chars (each cell is `width+2`, plus `N+1` pipes). Keep any new bordered row (e.g. the CPU/RAM stats line) consistent with this math or the pipes will drift out of alignment with the table below it.

---

## 🔒 Preserved Preferences & Constraints
- **Design & Branding:** Branding is `REI REJOIN`. Author credit: `seisen_`. Discord: `discord.gg/5G3cStpbcx`.
- **Features:** Keep Webhook, Sort Tab, Home Rejoin, Clear Cache. Do NOT remove core tabs or options.

### 5. Window Sorting (Sort Tab)
- Noka clones draw their own floating window (128px title bar + game surface + 64px transparent edge strips), so `am task resize` does NOT work. `place_window()` raises the task with `am start -f 0x10020000 -n pkg/com.roblox.client.ActivityNativeMain` (no restart), then drags the title bar to move and the right/bottom strips to resize, via `su -c 'input swipe ...'`.
- `sort_targets(count, w, h)` picks the rows x cols grid whose game surfaces are closest to 16:10 (6 -> 3x2, 8 -> 4x2). Frames come from `dumpsys window windows`; only windows with `isReadyForDisplay()=true` are trusted.
- `get_screen_size()` MUST go through `su -c 'wm size'` first: plain `wm size` fails for the Termux user and the old fallback (1280x720) silently produced a wrong grid.
- Menu 12 = sort now; config `auto_sort` (Option 5) sorts each package in a background thread ~6s after every (re)launch.
- Test as the real Termux user (type into Termux over adb), not as root with a fake `su`: that hid the `wm size` bug.
- **Pre-placement (no gestures):** the clones are App Cloner apps; their floating window reads `app_cloner_current_window_{left,top,right,bottom}` from `/data/data/<pkg>/shared_prefs/<pkg>_preferences.xml` ONLY when the process starts. `set_window_prefs()` writes the grid cell there (in place via `cat >`, keeps owner/mode) before any COLD launch (process not running), so the window opens already in its slot. Running windows ignore prefs edits, so the gesture sorter stays as the fallback.
