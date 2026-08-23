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
- **`home_rejoin_enabled`**: Guard flag from cfg. If `False`, show `Home Page` status but do NOT trigger force-stop or relaunch.
- **Home Screen Rejoin:** Uses `su -c 'am force-stop {package}'` on the target clone package, then waits 2s and fires `launch_game()`. (Note: `am force-stop` on the target clone package is completely safe and does NOT kill Termux).

### 3. Launch Intents (`launch_game`) (~L320)
- Uses `am start -f 0x10000000` (`FLAG_ACTIVITY_NEW_TASK`).
- Do NOT use `0x14000000` (`CLEAR_TASK`) as it forces process termination on some Android builds.

### 4. Terminal Dashboard UI (`render_live_dashboard`) (~L652)
- `W` is a **fixed constant (48)**, deliberately NOT probed via `tput`/`stty`/`shutil.get_terminal_size()`. Those reported the wrong width around screen rotation and varied by device, which caused recurring wrap/misalignment glitches (a line printed exactly `cols`-wide defers its wrap, sticking the next print's first character onto the same row). Do NOT reintroduce dynamic width detection here — if the layout needs to be wider/narrower, change the constant, don't probe for it.
- Header, settings (2 per line), stats, and table must fit within `W` columns (minimum 36).
- Use `rpad(colored_str, visible_len)` helper for ANSI-escaped string alignment.

---

## 🔒 Preserved Preferences & Constraints
- **Design & Branding:** Branding is `REI REJOIN`. Author credit: `seisen_`. Discord: `discord.gg/5G3cStpbcx`.
- **Features:** Keep Webhook, Sort Tab, Home Rejoin, Clear Cache. Do NOT remove core tabs or options.
