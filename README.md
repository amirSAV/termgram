# termgram

> A terminal client (TUI + CLI) and browser client for **Telegram bots** — send, manage, monitor, bridge, and even create managed bots directly from your terminal or browser.

`termgram` is a single-file, menu-driven TUI written in pure Python. It talks to the Telegram **Bot API** over HTTPS (via `requests`) and supports **SOCKS5 / HTTP proxies** out of the box (via `PySocks`). All received messages are stored locally in SQLite for later browsing.

**Version history**

- **v1.1.0** — non-interactive **CLI mode**
- **v1.2.0** — built-in **API Server** (proxy/bridge)
- **v1.3.0** — full **Web UI** + **Managed Bots**
- **v1.4.0** — **responsive TUI**, **in-place progress bars**, **exclusive `getUpdates` lock**, **Settings submenu**, **profile audios browser**

> 🌐 **فارسی‌زبان هستید؟** نسخه‌ی کامل فارسی: [README.fa.md](README.fa.md)

---

## ✨ Features

### 📨 Send every message type

Text · Photo · Animation (GIF) · Video · Document · Audio · Voice · Video note · Sticker · Location · Contact · Poll · Dice · Reaction

### 🖥 Four ways to drive it

- **Interactive TUI** — numbered menu, prompt-driven, ideal for exploring the API by hand.
- **CLI mode** — one-shot subcommands for scripting, cron jobs, or quick sends. Run `python3 termgram.py --help`.
- **API Server** — a built-in HTTP bridge (Settings → API server) that listens on `host:port` and proxies `/bot<token>/<method>` calls to the real Telegram Bot API.
- **Web UI** — a browser client with login wall, chat list, message viewer, reactions, saved media, member search, mention batching, file upload, and an optional background poller.

### 🎨 Responsive TUI with two-phase animation

The interactive menu adapts to your terminal width: **1 to 5 columns**, recomputed on every redraw. Everything fits cleanly whether you're in an 80-col SSH session or a 240-col widescreen.

- The **title line** prints with a subtle typewriter effect.
- **Menu rows** fade in one by one — fast enough to feel instant, smooth enough to avoid flashes.
- Speed is configurable via `MENU_SPEED` in `config.json`: `off` · `fast` (default) · `normal` · `slow`.
- The screen (including **scrollback history**) is cleared before each redraw using `\033[H\033[2J\033[3J`.
- **Enter on an empty prompt** reloads the menu.
- After any action runs, the app pauses with `Press Enter to return to main menu...` before redrawing.

### 📊 In-place progress bars

Every file download and upload shows a live single-line bar that rewrites itself:

```
⬇ [████████████░░░░░░░░░░░░░░░░░░░░]  38.4%  1.8MB/4.7MB  420.5KB/s ETA 7s
```

- Adaptive width based on terminal size.
- Shows **done / total**, **throughput**, and **ETA** — or a spinner when the server doesn't return `Content-Length`.
- Automatically **disabled when stdout is not a TTY** (safe for pipes and redirects).
- Used by: interactive file downloads (menu 37), profile audio downloads (menu 60), CLI `download`/`upload`, and every interactive `send_*` file flow.

### 🔒 Exclusive `getUpdates` lock (apt-style)

Telegram allows **only one active `getUpdates` per bot**. `termgram` enforces this with a cross-platform `flock`-based lock (`.getupdates.lock`):

- **Monitor mode**, **Silent fetch**, the **Web UI background poller**, and the **API Server** each take the lock when they need it.
- If one is already running, the others fail fast with a clear message:

  ```
  ✘ Cannot start Monitor Mode
    ✘ getUpdates lock held by: api-server (pid 12345, age 8s)
  ```

- The lock file **persists on disk** — the OS releases the actual `flock` automatically on process exit or crash, so stale locks are impossible. Never delete it manually unless the file itself is corrupted.
- `acquire_getupdates_lock()` and `release_getupdates_lock()` are exposed for scripting.

### 🔗 Inline URL buttons

Attach **inline keyboard buttons** under any message you send. Buttons are laid out row by row; each row can hold one or more URL buttons.

```
Row 1 — number of buttons: 2
  button 1 — text: 🌐 Website   url: https://example.com
  button 2 — text: 📢 Channel   url: https://t.me/mychannel
Row 2 — number of buttons: 1
  button 1 — text: 💬 Support   url: https://t.me/support
Row 3 — number of buttons:            ← empty = finish
```

> ⚠️ `sendVideoNote` does **not** support buttons (Telegram API limitation).

### 💬 Quote-reply (`reply_parameters`)

Reply to a **specific fragment** of an existing message using Telegram's `reply_parameters.quote`:

```
reply_to_message_id (empty = no reply): 12913
  ↳ cross-chat reply (source msg in another chat)? [y/N]: n
  ↳ quote a specific part of the message? [y/N]: y
  ↳ quote text (must be an exact substring of the original): hello world
```

Works identically across TUI, Monitor mode (`r` command), Web UI, and CLI (`--quote "..."`). The quote **must be an exact substring** of the source message's text/caption, otherwise Telegram returns `QUOTE_TEXT_INVALID`.

### 🔀 Cross-chat reply — native, no copy

Replying to a message that lives in **another chat** is fully native via `reply_parameters` with an embedded `chat_id`:

```json
{
  "reply_parameters": {
    "message_id": 42,
    "chat_id": -1001234567890,
    "quote": "optional fragment"
  }
}
```

No `copyMessage` round-trip. The reply appears **directly under the original message**, even across chats.

> ⚠️ Telegram only accepts cross-chat replies when the bot has access to the source message. Otherwise you get `MESSAGE_TO_BE_REPLIED_NOT_FOUND`.

### 💬 Custom reactions

`termgram` ships with a **built-in list of 61 Telegram reactions** stored in `config.json`. Manage them via **Settings → Manage reactions** (main menu 54 → 4):

```json
{ "emoji": "👍", "label": "Thumbs Up" }
```

- `emoji` is sent to Telegram.
- `label` is the display description shown in the picker.
- Changes saved in `config.json` reload dynamically.

In the **Web UI**, reaction usage is tracked in the `reaction_usage` table so the most-used emojis appear first.

### 🔑 Bot token management & server verification

Manage your bot token from **Settings → Manage bot token** (menu 54 → 3):

- View the masked or full token.
- Update the token with instant Telegram API verification (`getMe`).
- Test connectivity without leaving the client.
- Set a **custom Base URL** (via Settings → Set Base URL).

On startup, `termgram` validates your token directly with Telegram's servers. If invalid, it prompts for a valid token, a custom Base URL, a proxy, or a clean exit.

### 🌐 Custom Base URL

If `api.telegram.org` is blocked, set a custom root URL from **Settings → Set Base URL** (menu 54 → 2), from the startup error prompt, or directly in `config.json`:

```json
{ "base_url": "https://tg-bridge.example.com" }
```

`termgram` then calls `https://tg-bridge.example.com/bot<token>/<method>`. Leaving `base_url` empty restores the default.

### 🛡 Zero-crash bootstrapping

Even if `termgram.py` is executed standalone in an empty directory, it automatically creates `config.json` and initializes `tg.db` without crashing.

### 🤖 Bot profile

Read your bot's current identity and profile in one shot:

- **`getMe`** — id, name, username, capabilities
- **`getMyName`** — global display name (Bot API 9.0+)
- **`getMyDescription`** — bio shown on the profile page
- **`getMyShortDescription`** — short blurb shown in shared chats
- **`getUserProfilePhotos`** — the current profile photo set

And change them all:

Set name · Set bio · Set short bio · Set / remove profile photo

- **TUI:** menu option **36) Get current profile**
- **CLI:** `python3 termgram.py profile`

The **set profile photo** flow (menu 34) supports **static** (JPG/PNG, recommended 512×512) and **animated** (MP4) profile photos via `setMyProfilePhoto`.

### 👤 User account info

Look up any user's public profile using **menu option 50**:

- **`getUserProfilePhotos`** — latest profile photo + `file_id` of the largest size
- **`getUserProfileAudios`** — the user's profile songs (Bot API 7.0+)
- **`getChat`** — general account info (works if the bot has a private chat with the user)

### 🎵 Profile audios browser

A **dedicated menu for user profile songs** (main menu **60**, or accessed from **50**) with a built-in downloader:

```
--- 3 profile audio(s) ---
    1) 🎵 Love Story — Taylor Swift
         duration=235s  size=3520123B
    2) 🎵 Blinding Lights — The Weeknd
         duration=200s  size=2988771B
    3) 🎵 Shape of You — Ed Sheeran
         duration=233s  size=3412345B

  type a number to download that song
  a) Download all   j) Export JSON   0) Back
```

- Choose an output directory **once** per session.
- Type a **song number** to download directly. After each download, the list is redrawn, so you can grab several songs back-to-back.
- **`a`** — download everything, with per-file progress and a final summary.
- **`j`** — dump the raw `getUserProfileAudios` metadata to a timestamped JSON file.
- Uses the same in-place progress bar with byte-accurate throughput and ETA.

### 🛠 Message management

Edit · Delete (single **or** range) · Pin · Unpin · Forward · Chat actions (typing / uploading)

**Range delete** — pick a `chat_id` from DB (or type it) and specify `from → to` `message_id`. Honors flood-control (`429 retry_after`) and reports a full summary:

```
============================================
  DELETE SUMMARY
============================================
  Range       : 12900..12920  (21 msgs)
  Deleted     : 18
  Skipped     : 2  (not found / undeletable)
  Failed      : 1
  Failed IDs  : 12915
============================================
```

### 💾 Local DB management

All received messages land in `tg.db`. **Menu option 53** offers:

1. Purge a **specific chat** (picks from DB)
2. Purge **by chat type** (private / group / supergroup / channel)
3. Purge **by date range** (unix timestamps)
4. Purge **by message_id range** inside a chat
5. **Cleanup orphans** — entities / `chat_users` rows with zero messages

### 👥 Chat members (from DB)

**Menu option 48** lists every known member of a group/supergroup, aggregated from incoming messages (`chat_users`):

```
--- Members of chat -1001234567890 (12) ---
  1) id=8195921211    Sarina            @Sarina_girl_bot   msgs=42   last=2026-...
  2) id=123456789     Ali Rezaei        @ali_reza          msgs=120  last=2026-...
  d) Delete one   r) Reset all   e) Export JSON   0) Back
```

- `d` — remove one user from the DB member list (does **not** kick them)
- `r` — reset the whole member list for that chat
- `e` — export to `members_<chat>_<ts>.json`

> ⚠️ **Members are only collected from incoming messages.** Users who never sent a message while `termgram` was running won't appear. Telegram doesn't expose full member lists to bots.

### 📣 Mention members in batches

**Menu option 49** lets you @-mention members from the DB:

- **All members** or **a custom list** (`123, @ali, 456` — ids and usernames mixed)
- Split automatically into multiple messages by **batch size** (default 30) and **character limit** (3800)
- Uses HTML `<a href="tg://user?id=...">` so it works **even for users without a username**
- Optional header text, optional reply (with cross-chat support)
- Summary: members mentioned / messages sent / failures

The **Web UI** exposes the same batching via `POST /api/chats/<id>/mention`.

### 🧭 Chat-ID lock

**Settings → Lock / Unlock chat_id** (menu 54 → 5) pins a `chat_id` globally. Once locked:

- Every prompt that would ask for `chat_id` uses the locked value silently.
- The current lock appears at the top of the main menu: `Locked chat_id: -1001   Guest: OFF   API: OFF`
- Lock manually, pick from DB, or clear.

### 👻 Guest chat mode (Monitor)

**Settings → Toggle guest chat mode** (menu 54 → 6) flips Monitor mode into a **guest-chat-only** filter. Only messages that arrive via business connections / guest bots (detected via `business_connection_id`, `sender_business_bot`, `via_bot`, `sender_boost_count`) are displayed; everything else is silently stored but not shown. Status appears in the menu header as `Guest: ON` / `Guest: OFF`.

### 📡 Mention/reply detection in Silent Fetch

When a `Silent fetch` run ends, `termgram` scans every stored message for:

- **@-mentions of the bot** (via Telegram entities or raw `@username` text)
- **Replies to the bot's own messages**

At the end:

```
=======================================================
  FETCH SUMMARY
=======================================================
  Duration       : 00:02:15
  Updates seen   : 340
  Messages saved : 312
  Edits detected : 3
  Files captured : 8
  New offset     : 12045
  Saved to       : tg.db
  Mentions/replies to you: 2
=======================================================
```

Choosing `y` opens each message and lets you reply inline. The **Web UI** stores these in `mention_flags` and shows an **Unseen mentions** badge.

### 🤖 Bot management mode (local registry)

**Menu option 51** keeps a local registry of every bot you manage:

- List every managed bot with id, username, `added_at`, `last_seen_at`
- View the stored token
- View / inspect stored permissions per chat
- Delete a bot's row (and its permissions) from the DB
- **Add new bot** — generates a shareable deeplink

### 🆕 Managed Bots (Bot API 9.6+)

`termgram` supports Telegram's **Managed Bots** feature. A bot with `can_manage_bots: true` (enabled via **Bot Management Mode** in `@BotFather`) can create and manage other bots on behalf of users — **without ever opening `@BotFather`**.

**How it works**

1. **Menu option 52) Managed bot link** — or **51 → a** — generates a shareable link:
   ```
   https://t.me/newbot/<manager_bot_username>/<suggested_username>?name=<suggested_display_name>
   ```
   Built **locally** using `urllib.parse.quote`.

2. Send this link to a user. They open it in the Telegram app, confirm, and a new bot is created under your manager bot.

3. Telegram sends your manager bot an **`updateManagedBot`** update. `termgram` processes it in **all four update loops** (Silent fetch, Monitor, Web UI poller, API Server) and automatically:
   - Prints the new bot's id, username, name, and owner
   - Calls `getManagedBotToken` to fetch the token
   - Stores the new bot in `managed_bots`

4. Manage it from **menu 51 → pick bot**:
   - **`getManagedBotToken`** — fetch/refresh the token
   - **`replaceManagedBotToken`** — rotate the token
   - **`bots.getAccessSettings`** / **`bots.editAccessSettings`** — view / change permissions
   - **`bots.exportBotToken`** — MTProto token export

**Supported API methods**

| Method | Purpose |
|---|---|
| `bots.checkUsername` | Validate a proposed username |
| `bots.createBot` | (via deeplink only — see below) |
| `getManagedBotToken` | Fetch the token |
| `replaceManagedBotToken` | Rotate the token |
| `bots.getAccessSettings` | Read the access set |
| `bots.editAccessSettings` | Update the access set |
| `bots.exportBotToken` | MTProto token export |
| `updateManagedBot` | Update type received on creation / change |

> 💡 **Note:** `bots.createBot` is an MTProto method and is **never** called directly by `termgram`. Bot creation always happens **client-side** when the user opens the deeplink. `termgram` only generates the link and reacts to the resulting `updateManagedBot`.

> ⚠️ **Prerequisite:** Enable **Bot Management Mode** in `@BotFather` for your manager bot.

### 🛰 API Server (bridge / proxy)

**Settings → API server** (main menu **54 → 7**) starts a self-contained HTTP server that behaves like `api.telegram.org`:

- Listens on `api_server_host:api_server_port` (default `127.0.0.1:8080`)
- Accepts Bot API calls at `/bot<token>/<method>` and file downloads at `/file/bot<token>/<file_path>`
- Uses `api_server_token` from `config.json`, or falls back to the bot token
- Forwards every request to the upstream Bot API (proxying via `PROXY` / `HTTPS_PROXY` if set)
- **Multipart uploads are forwarded raw** — `sendDocument`, `sendPhoto`, `sendVideo`, `sendAudio`, `sendVoice`, `sendAnimation`, `sendSticker`, `sendVideoNote` all work through the proxy without corrupting the file body.
- **File downloads work** — `getFile` returns a `file_path`, which you can immediately fetch via `http://host:port/file/bot<token>/<file_path>` (streamed, no size limit beyond Telegram's).
- **Persists every `getUpdates` response** into `tg.db` (messages, edits, files, reactions, entities, mention flags) **before** returning it to the caller. It also advances `state.offset` so a later Monitor / Silent-fetch run doesn't reprocess the same updates.
- **Persists every response that contains a Message** (e.g. `sendMessage`, `editMessageText`, `forwardMessage`) into `tg.db`, so messages sent through the proxy show up in the Web UI exactly like native sends.
- Respects the **exclusive `getUpdates` lock** — if Monitor or the Web poller is active, `getUpdates` through the proxy returns `503` with the holder's owner and PID.
- Safe to leave running in the background; auto-starts on launch if `api_server_enabled` is `true`.

### 🌐 Web UI (browser client)

A full browser client under `web-ui/`:

```bash
python3 termgram.py web \
    --host 127.0.0.1 \
    --port 8081 \
    --password "your-secret" \
    --session-ttl 86400 \
    --cache-max-mb 512
```

Then open `http://127.0.0.1:8081/` and log in.

**What you get**

- **Sidebar** — every chat in `tg.db`, with unread mention badges
- **Message viewer** — bubbles, reply preview, forwarded-from, sender admin badge, reactions inline
- **Send** — text, reactions, forward, upload (photo/video/document/audio/voice/animation/sticker/video_note)
- **Mentions** — batch mention members using the same HTML `tg://user` logic
- **Saved media** — save/star/send stickers and animations (`saved_media` table)
- **Chat info** — live `getChat` + member count + admin list (cached in `chat_admins`)
- **Member search** — cached `chat_users` with message counts
- **Reactions** — sorted by usage (`reaction_usage`), sent through `setMessageReaction`
- **Avatars** — cached on disk under `cache/avatars/` and `cache/chat_avatars/`
- **File cache** — downloaded files under `cache/files/` with disk cap
- **Poller (optional)** — the **Sync & auto-refresh** toggle starts a background thread that calls `getUpdates`

**Security**

- All state-changing endpoints (`POST`) require a `X-CSRF-Token` header
- Login is rate-limited (5 attempts/minute/IP)
- Session cookies are `HttpOnly; SameSite=Strict`
- `--https-cert` and `--https-key` enable HTTPS

**Routes**

```
POST /api/login            GET  /api/me
POST /api/logout           GET  /api/chats
GET  /api/chats/:id/messages
POST /api/chats/:id/send
POST /api/chats/:id/forward
POST /api/chats/:id/upload
POST /api/chats/:id/mention
POST /api/chats/:id/messages/:mid/react
GET  /api/chats/:id/info      GET  /api/chats/:id/members
GET  /api/chats/:id/admins    GET  /api/chats/:id/mentions
GET  /api/users/:id/profile   GET  /api/users/:id/photo
GET  /api/chats/:id/photo     GET  /api/reactions
GET  /api/media/saved         POST /api/media/saved
POST /api/media/saved/:id/send
POST /api/media/saved/:id/favorite
GET  /api/mentions/unseen
POST /api/poller/start        POST /api/poller/stop
GET  /api/files/:unique_id    (cached, immutable)
```

### 📡 Monitor & automation

Monitor mode (live updates) · Auto-reply · Auto-react · Reactions inline editing

Monitor mode is protected by the **exclusive `getUpdates` lock** — no two components can poll simultaneously.

### 💾 Local database (SQLite)

Silent fetch · Chat explorer · History viewer · Purge / cleanup — every received message is stored in `tg.db`.

Tables: `messages`, `message_files`, `message_edits`, `message_reactions`, `entities`, `chat_users`, `chat_admins`, `chat_photos`, `user_photos`, `mention_flags`, `saved_media`, `reaction_usage`, `file_cache`, `web_sessions`, `managed_bots`, `bot_permissions`, `state`.

### 🌐 Proxy support

`socks5://` and `http://` — configured via `config.json`, interactively in **Settings → Configure proxy** (menu 54 → 1), **and** used automatically by the built-in API Server and Web UI file downloads.

### ⚙️ Consolidated Settings submenu

All non-messaging configuration lives under **menu option 54) Settings & Config**:

```
--- Settings & Config ---
--- Network --------------------------------------
   1) Configure proxy / retry    2) Set Base URL
--- Bot ------------------------------------------
   3) Manage bot token           4) Manage reactions
--- Chat Behavior --------------------------------
   5) Lock / Unlock chat_id      6) Toggle guest chat mode
--- Server ---------------------------------------
   7) API server

   0) Back to main menu
```

Uses the **same responsive renderer and animation** as the main menu. Enter on an empty prompt reloads it; after any action it pauses with `Press Enter to return...`.

### 🎨 Version banner

On interactive startup:

```
╔════════════════════════════════════════════════════╗
║  📡 termgram  v1.4.0                              ║
║  Terminal client for Telegram bots                 ║
╚════════════════════════════════════════════════════╝
```

In **CLI mode** the banner collapses to a single line:

```
termgram v1.4.0
```

---

## 📋 Requirements

- **Python 3.10+** (tested on 3.14.x)
- `requests`
- `PySocks`

Optional (for HTTPS on the web UI): `ssl` — built into CPython; just supply `--https-cert` and `--https-key`.

---

## 🚀 Installation

```bash
git clone https://github.com/amirSAV/termgram.git
cd termgram

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

---

## ⚙️ Setup

### Unified configuration (`config.json`)

All configuration — bot token, proxy, custom Base URL, API server settings, guest-mode flag, chat-ID lock, custom reactions, and menu animation speed — is stored in a single `config.json`. Create it from the template:

```bash
cp config.json.example config.json
```

Or launch `termgram` directly (`python3 termgram.py`) — it auto-generates `config.json` and `tg.db` on first run and prompts for a valid bot token.

Example `config.json`:

```json
{
  "token": "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ",
  "proxy": "socks5://127.0.0.1:10808",
  "base_url": "",
  "api_server_enabled": false,
  "api_server_host": "127.0.0.1",
  "api_server_port": 8080,
  "api_server_token": "",
  "guest_chat_mode": false,
  "locked_chat_id": "",
  "menu_speed": "fast",
  "reactions": [
    { "emoji": "👍", "label": "Thumbs Up" },
    { "emoji": "👎", "label": "Thumbs Down" },
    { "emoji": "❤️", "label": "Red Heart" },
    { "emoji": "🔥", "label": "Fire" }
  ]
}
```

1. **Bot token** — get it from [@BotFather](https://t.me/BotFather). For **Managed Bots**, enable **Bot Management Mode** in `@BotFather`.
2. **Proxy (optional)** — `socks5://`, `http://`, `https://`. Set to `""` for direct.
3. **Reactions** — curated list. Configure from **Settings → Manage reactions** (menu 54 → 4).
4. **`base_url`** (optional) — custom root URL.
5. **`api_server_*`** (optional) — enable the built-in bridge server.
6. **`guest_chat_mode`** (optional) — restrict Monitor to guest messages.
7. **`locked_chat_id`** (optional) — pin a chat ID silently.
8. **`menu_speed`** (optional) — `off` / `fast` / `normal` / `slow`.

> 💡 **Automatic migration**: If upgrading from an older version, `termgram` reads existing `token.txt`, `proxy.txt`, and `reactions.txt`, migrates their settings, and cleans up the legacy files.

---

## ▶️ Usage

### Interactive TUI

```bash
python3 termgram.py
```

```
╔════════════════════════════════════════════════════╗
║  📡 termgram  v1.4.0                              ║
║  Terminal client for Telegram bots                 ║
╚════════════════════════════════════════════════════╝
Connecting to Telegram API...
✔ Bot connected: @YourBot (My Bot)

=============== Telegram Bot Sender ===============
  Locked chat_id: (none)   Guest: OFF   API: OFF

--- Send Messages ---------------------------------
   1) Text message              2) Photo
   3) Animation (GIF)           4) Video
   5) Document / File           6) Audio
   7) Voice                     8) Video note
   9) Sticker                  10) Location
  11) Contact                  12) Poll
  13) Dice                     14) Reaction
  15) Edit message             16) Delete message
--- Chat Management -------------------------------
  17) Leave chat               18) Get chat info
  19) Member count             20) Pin message
  21) Unpin message            22) Forward message
  23) Chat action              24) Ban user
  25) Unban user               26) Set chat title
  27) Set chat desc            28) Set admin title
  29) Set bot name             30) Create invite link
--- Bot Profile -----------------------------------
  31) Bot info (getMe)         32) Set bio (desc)
  33) Set short bio            34) Set profile photo
  35) Remove photo             36) Get current profile
--- Files -----------------------------------------
  37) Download by id           38) Upload & get id
--- Monitor & Data --------------------------------
  39) Monitor mode             40) Silent fetch
  41) Chat explorer            42) History viewer
--- Admin & Members -------------------------------
  43) Member info              44) Promote admin
  45) Demote admin             46) Set user title
  47) Set member tag           48) Chat members (DB)
  49) Mention members          50) User account info
--- Bot Management --------------------------------
  51) Bot management           52) Managed bot link
  53) Purge DB data
--- Settings --------------------------------------
  54) Settings & Config

   0) Exit
choice:
```

The menu is **fully responsive** — if your terminal is wide enough, the columns expand from 2 to 5 automatically. Press Enter on an empty prompt to reload.

#### Example: sending a text message with buttons

```
choice: 1

--- Common fields ---
chat_id (number or @username): @my_channel
reply_to_message_id (empty = no reply): 12913
  ↳ cross-chat reply (source msg in another chat)? [y/N]: n
  ↳ quote a specific part of the message? [y/N]: n
parse_mode [Markdown/HTML/MarkdownV2] (empty = none):
disable_notification? [y/N]: n
protect_content? [y/N]: n

--- Inline URL buttons (optional) ---
Add inline URL buttons under this message? [y/N]: y
Add buttons row by row. Empty row number = finish.

Row 1 — number of buttons (empty = finish): 2
  button 1 — text (e.g. 🌐 Website): 🌐 Website
  button 1 — url  (https://...): https://example.com
  button 2 — text (e.g. 🌐 Website): 📢 Channel
  button 2 — url  (https://...): https://t.me/mychannel
Row 2 — number of buttons (empty = finish):
✔ 2 button(s) in 1 row(s) attached.

text: type [t] directly or read [f] from file? (t/f): t
text: Hello from termgram!

>> sendMessage ...
✔ Sent successfully
📨 message_id: 1234

Press Enter to return to main menu...
```

#### Example: downloading profile audios

```
choice: 60

--- User Profile Audios ---
user_id (numeric): 123456789
>> getUserProfileAudios ...
output dir [default: .]: ./songs

--- 3 profile audio(s) ---
    1) 🎵 Love Story — Taylor Swift
         duration=235s  size=3520123B
    2) 🎵 Blinding Lights — The Weeknd
         duration=200s  size=2988771B
    3) 🎵 Shape of You — Ed Sheeran
         duration=233s  size=3412345B

  type a number to download that song
  a) Download all   j) Export JSON   0) Back
choice: 2

⬇  The Weeknd - Blinding Lights.mp3  (2.9MB)
⬇ [████████████████████████████████████] 100.0%  2.9MB/2.9MB  512.3KB/s ETA 0s
✔ saved: ./songs/The Weeknd - Blinding Lights.mp3  (2918.7 KB)

--- 3 profile audio(s) ---
  ...
choice: 0
```

---

### CLI mode

Any argument after the script name switches `termgram` into non-interactive mode. Every subcommand returns a shell exit code.

```bash
python3 termgram.py --help
```

```
usage: termgram [-h] <command> ...

Terminal client for Telegram bots — CLI mode.

Send messages:
  text        send a text message
  photo       send a photo
  document    send a document
  video       send a video
  audio       send an audio
  voice       send a voice message
  animation   send a GIF / animation
  video_note  send a round video note
  sticker     send a sticker
  location    send a location
  contact     send a contact
  dice        send a dice

Message management:
  react       set a reaction on a message
  edit        edit a message's text
  delete      delete a message
  pin         pin a message
  unpin       unpin a message
  forward     forward a message
  reply       reply to a message (works across chats)
  chat-action send a chat action (typing, upload_photo, ...)

Chat & members:
  leave         leave a chat/channel
  chat-info     get chat info
  member-count  get member count
  member-info   get a chat member
  ban           ban a user
  unban         unban a user
  promote       promote a user to admin (all perms)
  demote        remove admin rights
  set-title     set chat title
  set-description  set chat description
  invite-link   create a chat invite link

Bot profile:
  me            getMe
  profile       full profile (name, bio, photo)
  set-name      set global name
  set-bio       set description / bio
  set-short-bio set short description
  remove-photo  remove profile photo

Files:
  download    download a file by file_id
  upload      upload a file and print its file_id

Web UI:
  web         start the browser client

Examples:
  termgram text 123456 "Hello"
  termgram text 123456 --text-file msg.txt --parse-mode Markdown
  termgram photo 123456 pic.jpg --caption "look"
  termgram document @mychan file.pdf --caption-file cap.txt
  termgram react 123456 42 👍
  termgram ban 123456 987654321 --revoke
  termgram download AgACAgQAAxkBAA... --out file.bin
  termgram upload 123456 ./img.png --as photo
  termgram web --host 127.0.0.1 --port 8081 --password "secret"
```

#### CLI examples

```bash
# ── sending ────────────────────────────────────────────────
python3 termgram.py text -1001234567890 "Hello from the shell"
python3 termgram.py text @mychannel "**bold** reply" \
    --parse-mode Markdown --reply-to 42
python3 termgram.py text @mychannel "on it" \
    --reply-to 42 --quote "please check this"
python3 termgram.py text @mych2 "ok!" \
    --reply-to 42 --reply-to-chat @mych1 --quote "please check this"
python3 termgram.py text -1001234567890 --text-file msg.txt
python3 termgram.py photo -1001234567890 ./pic.jpg --caption "look at this"
python3 termgram.py document @mychannel ./archive.zip --caption-file cap.txt
python3 termgram.py video -1001234567890 ./clip.mp4 \
    --caption "🎬" --reply-to 900
python3 termgram.py location -1001234567890 35.6892 51.3890
python3 termgram.py contact  -1001234567890 "+15551234567" "John" --last-name "Doe"
python3 termgram.py dice     -1001234567890 🎲

# ── message management ────────────────────────────────────
python3 termgram.py react  -1001234567890 99 👍
python3 termgram.py edit   -1001234567890 99 "updated text"
python3 termgram.py delete -1001234567890 99
python3 termgram.py pin    -1001234567890 99
python3 termgram.py unpin  -1001234567890
python3 termgram.py forward @src 42 @dst
python3 termgram.py chat-action @mychannel typing
python3 termgram.py reply @news 100 -1001234567890 "this is important"

# ── chat / members ────────────────────────────────────────
python3 termgram.py chat-info    @mychannel
python3 termgram.py member-count @mychannel
python3 termgram.py member-info  @mychannel 123456789
python3 termgram.py ban    @mychannel 987654321 --revoke
python3 termgram.py unban  @mychannel 987654321
python3 termgram.py promote @mychannel 987654321
python3 termgram.py demote  @mychannel 987654321
python3 termgram.py set-title @mychannel "New Title"
python3 termgram.py set-description @mychannel "Welcome!"
python3 termgram.py invite-link @mychannel --name "July" --limit 100
python3 termgram.py leave @mychannel

# ── bot profile ───────────────────────────────────────────
python3 termgram.py me
python3 termgram.py profile
python3 termgram.py set-name "My Cool Bot"
python3 termgram.py set-bio "I help you do X." --lang en
python3 termgram.py set-bio --bio-file bio.txt
python3 termgram.py set-short-bio "Fast & simple."
python3 termgram.py remove-photo

# ── files ─────────────────────────────────────────────────
python3 termgram.py download AgACAgQAAxkBAA... --out pic.jpg
python3 termgram.py upload -1001234567890 ./img.png --as photo

# ── web UI ────────────────────────────────────────────────
python3 termgram.py web
python3 termgram.py web --host 0.0.0.0 --port 9090 --password "s3cr3t"
python3 termgram.py web --host 0.0.0.0 --port 443 \
    --https-cert ./cert.pem --https-key ./key.pem \
    --password "s3cr3t"
python3 termgram.py web --no-poller
```

##### Text & caption sources

| Subcommand  | Inline form            | File form          |
| ----------- | ---------------------- | ------------------ |
| `text`      | positional `text`      | `--text-file F`    |
| `edit`      | positional `text`      | `--text-file F`    |
| `reply`     | positional `text`      | `--text-file F`    |
| `set-bio`   | positional `description` | `--bio-file F`   |
| `set-short-bio` | positional `description` | `--bio-file F` |

File-based subcommands accept two mutually-exclusive options for the caption:

| Option             | Meaning                                                  |
| ------------------ | -------------------------------------------------------- |
| `--caption TEXT`   | Inline caption string                                    |
| `--caption-file F` | Read the caption from file `F` (UTF-8, multi-line safe)  |

`--caption-file` takes precedence if both are given.

##### Exit codes

| Code | Meaning                                    |
| ---- | ------------------------------------------ |
| `0`  | Success (Telegram returned `ok`)           |
| `1`  | Telegram returned an error                 |
| `2`  | Local usage / file error                   |

---

### Web UI (browser client)

```bash
python3 termgram.py web --host 127.0.0.1 --port 8081 --password "your-secret"
```

Then open **http://127.0.0.1:8081/** and log in.

| Flag | Default | Purpose |
|---|---|---|
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8081` | TCP port |
| `--password` | bot token | Login password |
| `--session-ttl` | `86400` | Session lifetime in seconds |
| `--cache-max-mb` | `512` | Max disk cache for downloaded files |
| `--https-cert` / `--https-key` | — | PEM cert + key to enable HTTPS |
| `--no-poller` | off | Don't start the background poller |

The **web UI requires the `web-ui/` directory** (containing `index.html`, `app.js`, `style.css`, `favicon.svg`) next to `termgram.py`.

---

## 🖥 Platform notes

- ✅ **Linux / macOS**: fully supported.
- ⚠️ **Windows**: Persian/Farsi characters may not render correctly in the default terminal. Use **Windows Terminal** with a font that supports RTL (e.g. *Cascadia Code*, *Vazirmatn*) or run inside **WSL**. The web UI is unaffected.

---

| File                  | Purpose                                          | Committed?     |
| --------------------- | ------------------------------------------------ | -------------- |
| `termgram.py`         | Main program                                     | ✅              |
| `requirements.txt`    | Python dependencies                              | ✅              |
| `README.md`           | This file                                        | ✅              |
| `README.fa.md`        | Persian version                                  | ✅              |
| `LICENSE`             | MIT license                                      | ✅              |
| `config.json.example` | Configuration template                           | ✅              |
| `web-ui/`             | Browser client (`index.html` + `static/`)        | ✅              |
| `config.json`         | Your real configuration & secrets                | ❌ (gitignored) |
| `tg.db`               | Local message database                           | ❌ (gitignored) |
| `cache/`              | File/avatar/media cache for the web UI           | ❌ (gitignored) |
| `.getupdates.lock`    | Cross-process getUpdates lock                    | ❌ (gitignored) |

---

## 🤝 Contributing

Contributions are welcome from **invited collaborators**. If you'd like to help, open an issue first. When testing a patch, please also verify:

- `getUpdates` lock behavior across Monitor / Silent fetch / Web poller / API Server
- multipart file upload through the API Server
- `/file/bot<token>/<path>` streaming download
- responsive menu at several terminal widths (80, 120, 200 cols)

---

## 📜 License

[MIT](LICENSE)