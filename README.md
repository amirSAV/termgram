# termgram

> A terminal client (TUI + CLI) and browser client for **Telegram bots** — send, manage, monitor, bridge, and even create managed bots directly from your terminal or browser.

`termgram` is a single-file, menu-driven TUI written in pure Python. It talks to the Telegram **Bot API** over HTTPS (via `requests`) and supports **SOCKS5 / HTTP proxies** out of the box (via `PySocks`). All received messages are stored locally in SQLite for later browsing. Since v1.1.0 it also ships with a **non-interactive CLI mode**; since v1.2.0 with a built-in **API Server** that can act as a full proxy/bridge in front of the Telegram Bot API; and since **v1.3.0** with a full **web UI** (browser client) and **Managed Bots** support (create and manage other bots via a shareable deeplink).

> 🌐 **فارسی‌زبان هستید؟** نسخه‌ی کامل فارسی این راهنما در دسترس است: [README.fa.md](README.fa.md)
---

## ✨ Features

### 📨 Send every message type

Text · Photo · Animation (GIF) · Video · Document · Audio · Voice · Video note · Sticker · Location · Contact · Poll · Dice · Reaction

### 🖥 Four ways to drive it

- **Interactive TUI** — numbered menu, prompt-driven, ideal for exploring the API by hand.
- **CLI mode** — one-shot subcommands for scripting, cron jobs, or quick sends from the shell. Run `python3 termgram.py --help` to see every subcommand.
- **API Server** — a built-in HTTP bridge (menu option **52**) that listens on `host:port` with its own token and proxies `/bot<token>/<method>` calls to the real Telegram Bot API. `getUpdates` payloads are persisted into `tg.db` **before** the response is returned.
- **Web UI** — a browser client with a login wall, chat list, message viewer, reactions, saved media (stickers/animations), member search, mention batching, file upload, and optional **background poller** that keeps `tg.db` fresh. Launch with `python3 termgram.py web` (see below).

### 🔗 Inline URL buttons

Attach **inline keyboard buttons** under any message you send. Buttons are laid out row by row; each row can hold one or more URL buttons. After choosing content in any `send_*` flow, `termgram` asks whether you want to add buttons — just paste a label and a URL for each.

```
Row 1 — number of buttons: 2
  button 1 — text: 🌐 Website   url: https://example.com
  button 2 — text: 📢 Channel   url: https://t.me/mychannel
Row 2 — number of buttons: 1
  button 1 — text: 💬 Support   url: https://t.me/support
Row 3 — number of buttons:            ← empty = finish
```

> ⚠️ `sendVideoNote` does **not** support buttons (Telegram API limitation), so that one flow skips the prompt.

### 💬 Quote-reply (reply_parameters)

Reply to a **specific fragment** of an existing message using Telegram's `reply_parameters.quote`. Any send flow that goes through the common prompt now asks:

```
reply_to_message_id (empty = no reply): 12913
  ↳ cross-chat reply (source msg in another chat)? [y/N]: n
  ↳ quote a specific part of the message? [y/N]: y
  ↳ quote text (must be an exact substring of the original): hello world
```

Works identically across TUI, Monitor mode (`r` command), Web UI, and CLI (`--quote "..."`). The quote **must be an exact substring** of the source message's text/caption, otherwise Telegram returns `QUOTE_TEXT_INVALID`.

### 🔀 Cross-chat reply — **native, no copy**

Replying to a message that lives in **another chat** is fully native. `termgram` uses Telegram's `reply_parameters` with an embedded `chat_id`:

```json
{
  "reply_parameters": {
    "message_id": 42,
    "chat_id": -1001234567890,
    "quote": "optional fragment"
  }
}
```

No more `copyMessage` round-trip. The reply appears **directly under the original message**, even across chats. If the source and target chats are the same, `reply_to_message_id` is used for simplicity.

- **TUI:** every send flow (text, photo, dice, …) — the `reply_to_message_id` prompt now offers a cross-chat branch.
- **CLI:** `--reply-to <id> --reply-to-chat <chat> [--quote "..."]`, or the dedicated `reply` subcommand.

> ⚠️ Telegram only accepts cross-chat replies when the bot has access to the source message (member of the source chat, or the source message was authored by the bot or another bot with shared access). Otherwise you get `MESSAGE_TO_BE_REPLIED_NOT_FOUND`.

### 💬 Custom reactions

`termgram` ships with a **built-in list of 61 Telegram reactions** (👍 ❤️ 🔥 …) stored in `config.json`. You can manage reactions interactively via **menu option 51) Manage reactions** (list, add, remove, or reset to standard Telegram reactions), or edit `config.json` directly.

Reactions are structured as clean JSON entries:

```json
{
  "emoji": "👍",
  "label": "Thumbs Up"
}
```

- The `emoji` field is sent to Telegram.
- The `label` is the display description shown in the picker.
- Changes saved in `config.json` reload dynamically without restarting `termgram`.

In the **Web UI**, reaction usage is tracked in the `reaction_usage` table so the most-used emojis appear first.

### 🔑 Bot token management & server verification

Manage your bot token at any time using **menu option 50) Manage bot token**:
- View the masked or full token.
- Update the token with instant Telegram API verification (`getMe`).
- Test connectivity and identity without leaving the client.
- Set a **custom Base URL** (for use behind a self-hosted API proxy).

On startup, `termgram` validates your token directly with Telegram's servers. If the token is invalid or missing, it alerts you immediately (confirming Telegram API's `401 Unauthorized` response) and prompts for a valid token, a custom Base URL, or a clean exit.

### 🌐 Custom Base URL

If `api.telegram.org` is blocked (or you want to route traffic through your own bridge), set a custom root URL from **menu option 50 → 4**, from the startup error prompt, or directly in `config.json`:

```json
{ "base_url": "https://tg-bridge.example.com" }
```

`termgram` then calls `https://tg-bridge.example.com/bot<token>/<method>`. Leaving `base_url` empty restores the default Telegram endpoint.

### 🛡 Zero-crash bootstrapping

Even if `termgram.py` is executed standalone in an empty directory, it automatically creates `config.json` and initializes `tg.db` SQLite schema without crashing or raising missing-file errors.

### 🤖 Bot profile

Read your bot's current identity and profile in one shot:

- **`getMe`** — id, name, username, capabilities
- **`getMyName`** — global display name (Bot API 9.0+)
- **`getMyDescription`** — bio shown on the bot's profile page
- **`getMyShortDescription`** — short blurb shown in shared chats
- **`getUserProfilePhotos`** — the current profile photo set

And of course you can *change* all of them:

Set name · Set bio (description) · Set short bio · Set / remove profile photo

- **TUI:** menu option **49) Get current profile**
- **CLI:** `python3 termgram.py profile`

The **set profile photo** flow (menu option 35) supports **static** (JPG/PNG, recommended 512×512) and **animated** (MP4) profile photos via `setMyProfilePhoto`.

### 👤 User account info

Look up any user's public profile using **menu option 59**:

- **`getUserProfilePhotos`** — latest profile photo + `file_id` of the largest size
- **`getUserProfileAudios`** — the user's profile songs/audios (Bot API 7.0+)
- **`getChat`** — general account info (works only if the bot has a private chat with the user)

Minimal by design — just the essentials, nothing noisy.

### 🛠 Message management

Edit · Delete (single **or** range) · Pin · Unpin · Forward · Chat actions (typing / uploading)

**Range delete** — pick a `chat_id` from DB (or type it) and specify `from → to` `message_id`. `termgram` sends a `deleteMessage` for every id, honors flood-control (`429 retry_after`), and reports a full summary:

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

All received messages land in `tg.db`. To keep it lean, **menu option 54** offers:

1. Purge a **specific chat** (picks from DB)
2. Purge **by chat type** (private / group / supergroup / channel)
3. Purge **by date range** (unix timestamps)
4. Purge **by message_id range** inside a chat (picks from DB)
5. **Cleanup orphans** — entities / `chat_users` rows with zero messages

### 👥 Chat members (from DB)

**Menu option 57** lists every known member of a group/supergroup, aggregated from incoming messages (`chat_users`):

```
--- Members of chat -1001234567890 (12) ---
  1) id=8195921211    Sarina            @Sarina_girl_bot   msgs=42   last=2026-...
  2) id=123456789     Ali Rezaei        @ali_reza          msgs=120  last=2026-...
  d) Delete one   r) Reset all   e) Export JSON   0) Back
```

- `d` — remove one user from the DB member list (does **not** kick them from the real group)
- `r` — reset the whole member list for that chat
- `e` — export to `members_<chat>_<ts>.json`

### 📣 Mention members in batches

**Menu option 58** lets you @-mention members from the DB:

- **All members** or **a custom list** (`123, @ali, 456` — ids and usernames mixed)
- Split automatically into multiple messages by **batch size** (default 30) and **character limit** (3800)
- Uses HTML `<a href="tg://user?id=...">` so it works **even for users without a username**
- Optional header text, optional reply (works with **cross-chat** reply too)
- Summary at the end: members mentioned / messages sent / failures

The **Web UI** exposes the same batching via `POST /api/chats/<id>/mention` with `{text, all, user_ids, batch_size, reply_to}`.

### 🧭 Chat-ID lock

**Menu option 55** pins a `chat_id` globally. Once locked:
- Every prompt that would ask for `chat_id` (send, edit, delete, forward, pin, …) uses the locked value silently.
- The current lock is shown at the top of the main menu: `Locked chat_id: -1001   Guest: OFF   API: OFF`
- Lock manually, pick from DB, or clear.

### 👻 Guest chat mode (Monitor)

**Menu option 56** flips Monitor mode into a **guest-chat-only** filter. Only messages that arrive via business connections / guest bots (detected via `business_connection_id`, `sender_business_bot`, `via_bot`, `sender_boost_count`) are displayed; everything else is silently stored but not shown. Status appears in the menu header as `Guest: ON` / `Guest: OFF`.

### 📡 Mention/reply detection in Silent Fetch

When you finish a `Silent fetch` run, `termgram` now scans every stored message for:
- **@-mentions of the bot** (via Telegram entities or raw `@username` text)
- **Replies to the bot's own messages**

At the end it reports:

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

Choosing `y` opens each message and lets you reply inline — no need to jump back to Monitor.

The **Web UI** stores these in `mention_flags` and shows an **Unseen mentions** badge in the sidebar.

### 🤖 Bot management mode (local registry)

**Menu option 53** keeps a local registry of every bot you manage:

- List every managed bot with id, username, `added_at`, `last_seen_at`
- View the stored token
- View / inspect stored permissions per chat
- Delete a bot's row (and its permission rows) from the DB
- **Add new bot** — generates a shareable deeplink (see Managed Bots below)

### 🆕 Managed Bots (Bot API 9.6+)

Since v1.3.0, `termgram` supports Telegram's **Managed Bots** feature. A bot with the `can_manage_bots` flag (enabled via **Bot Management Mode** in `@BotFather`) can create and manage other bots on behalf of users — **without ever opening `@BotFather`**.

**How it works**

1. **Menu option 60) Managed bot link** — or **menu 53 → a** — generates a shareable link:
   ```
   https://t.me/newbot/<manager_bot_username>/<suggested_username>?name=<suggested_display_name>
   ```
   The link is built **locally** (no API call) using `urllib.parse.quote`.

2. Send this link to a user. They open it in the Telegram app, confirm, and a new bot is created under your manager bot.

3. Telegram sends your manager bot an **`updateManagedBot`** update. `termgram` processes it in **all four update loops** (Silent fetch, Monitor, Web UI poller, API Server) and automatically:
   - Prints the new bot's id, username, name, and owner
   - Calls `getManagedBotToken` to fetch the token
   - Stores the new bot in `managed_bots`

4. Manage it from **menu 53 → pick bot**:
   - **`getManagedBotToken`** — fetch/refresh the token
   - **`replaceManagedBotToken`** — rotate the token (old one is invalidated)
   - **`bots.getAccessSettings`** / **`bots.editAccessSettings`** — view or change the bot's permission set
   - **`bots.exportBotToken`** — MTProto-level token export

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

> 💡 **Note:** `bots.createBot` is an MTProto method and is **never** called directly by `termgram`. Bot creation always happens **client-side** when the user opens the deeplink in their Telegram app. `termgram` only generates the link and reacts to the resulting `updateManagedBot` — exactly as Telegram intends.

> ⚠️ **Prerequisite:** Enable **Bot Management Mode** in `@BotFather` for your manager bot. Otherwise `getMe` returns `can_manage_bots: false` and all Managed Bot calls fail.

### 🛰 API Server (bridge / proxy)

**Menu option 52** starts a self-contained HTTP server that behaves like `api.telegram.org`:

- Listens on `api_server_host:api_server_port` (default `127.0.0.1:8080`)
- Accepts calls at `/bot<token>/<method>`
- Uses `api_server_token` from `config.json`, or falls back to the active bot token
- Forwards every request to the upstream Bot API (proxying via `PROXY` / `HTTPS_PROXY` if set)
- **Persists every `getUpdates` response** into `tg.db` (messages, edits, files, reactions, entities) **before** returning it to the caller
- Safe to leave running in the background; started automatically on launch if `api_server_enabled` is `true`

### 🌐 Web UI (browser client)

Since **v1.3.0**, `termgram` ships with a full browser client under `web-ui/`. Launch it with:

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
- **Mentions** — batch mention members using the same HTML `tg://user` logic as menu 58
- **Saved media** — save/star/send stickers and animations (`saved_media` table)
- **Chat info** — live `getChat` + member count + admin list (cached in `chat_admins`)
- **Member search** — cached `chat_users` with message counts
- **Reactions** — sorted by usage (`reaction_usage`), sent through `setMessageReaction`
- **Avatars** — cached on disk under `cache/avatars/` and `cache/chat_avatars/`
- **File cache** — downloaded files under `cache/files/` with disk cap (`--cache-max-mb`)
- **Poller (optional)** — a **Sync & auto-refresh** toggle starts a background thread that calls `getUpdates` and writes to `tg.db`, so the UI stays live. Disable with `--no-poller`.

**Security**

- All state-changing endpoints (`POST`) require a `X-CSRF-Token` header matching the session's CSRF token.
- Login is rate-limited (5 attempts/minute/IP).
- Session cookies are `HttpOnly; SameSite=Strict`.
- Pass `--https-cert` and `--https-key` to enable HTTPS; binding to `0.0.0.0` without HTTPS triggers a confirmation prompt.

**Routes (for the curious)**

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

### 💾 Local database (SQLite)

Silent fetch · Chat explorer · History viewer · Purge / cleanup — every received message is stored in `tg.db`

The schema includes tables for `messages`, `message_files`, `message_edits`, `message_reactions`, `entities`, `chat_users`, `chat_admins`, `chat_photos`, `user_photos`, `mention_flags`, `saved_media`, `reaction_usage`, `file_cache`, `web_sessions`, `managed_bots`, `bot_permissions`, and `state`.

### 🌐 Proxy support

`socks5://` and `http://` — configured via `config.json`, interactively in **menu option 17**, **and** used automatically by the built-in API Server and Web UI file downloads.

### 🧭 Zero-config TUI & smooth menu cascade

Everything is numbered. No flags to memorize for interactive use. Config and database files are auto-created on first run. When the interactive menu opens, it animates with a smooth, rapid cascade to avoid abrupt screen flashes.

### 🎨 Version banner

On interactive startup `termgram` prints a tidy banner:

```
╔════════════════════════════════════════════════════╗
║  📡 termgram  v1.3.0                              ║
║  Terminal client for Telegram bots                 ║
╚════════════════════════════════════════════════════╝
```

In **CLI mode** the banner is collapsed to a single short line, so it never pollutes shell output:

```
termgram v1.3.0
```

---

## 📋 Requirements

- **Python 3.10+** (tested on 3.14.x)
- `requests`
- `PySocks`

Optional (for HTTPS on the web UI):
- `ssl` — built into CPython; just supply `--https-cert` and `--https-key`

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

All configuration—bot token, proxy, custom Base URL, API server settings, guest-mode flag, chat-ID lock, and custom reactions—is stored in a single `config.json` file. You can create it from the provided template:

```bash
cp config.json.example config.json
```

Or simply launch `termgram` directly (`python3 termgram.py`): `termgram` will auto-generate `config.json` and `tg.db` on first run and interactively prompt you to enter a valid bot token!

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
  "reactions": [
    { "emoji": "👍", "label": "Thumbs Up" },
    { "emoji": "👎", "label": "Thumbs Down" },
    { "emoji": "❤️", "label": "Red Heart" },
    { "emoji": "🔥", "label": "Fire" }
  ]
}
```

1. **Bot token**: Get your token from [@BotFather](https://t.me/BotFather). For **Managed Bots**, enable **Bot Management Mode** in `@BotFather`.
2. **Proxy (optional)**: Supported schemes: `socks5://`, `http://`, `https://`. Set to `""` for direct connection.
3. **Reactions**: Curated list of emoji reactions. Can be configured directly via **menu option 51) Manage reactions**.
4. **`base_url`** (optional): custom root URL for the Bot API (default `https://api.telegram.org`).
5. **`api_server_*`** (optional): enable the built-in bridge server, choose host/port, and optionally set a dedicated `api_server_token` (empty = reuse bot token). Menu option **52**.
6. **`guest_chat_mode`** (optional): restrict Monitor to guest/business messages only. Menu option **56**.
7. **`locked_chat_id`** (optional): pin a chat ID so every prompt that would otherwise ask for one uses this silently. Menu option **55**.

> 💡 **Automatic upgrade & migration**: If upgrading from an older version, `termgram` automatically reads existing `token.txt`, `proxy.txt`, and `reactions.txt`, migrates their settings into `config.json`, and cleans up the legacy files.

---

## ▶️ Usage

### Interactive TUI

```bash
python3 termgram.py
```

You'll see:

```
╔════════════════════════════════════════════════════╗
║  📡 termgram  v1.3.0                               ║
║  Terminal client for Telegram bots                 ║
╚════════════════════════════════════════════════════╝
Connecting to Telegram API...
✔ Bot connected: @YourBot (My Bot)

=============== Telegram Bot Sender ===============
  Locked chat_id: (none)   Guest: OFF   API: OFF
   1) Text message              2) Photo
   3) Animation (GIF)           4) Video
   ...
  49) Get current profile
  50) Manage bot token         51) Manage reactions
--- Chat Management -------------------------------
  19) Leave chat               20) Get chat info
  ...
--- Monitor ---------------------------------------
  39) Monitor mode
--- Data / DB -------------------------------------
  46) Silent fetch             47) Chat explorer
  48) History viewer
--- Advanced -------------------------------------
  52) API Server               53) Bot management
  54) Purge DB data            55) Lock/Unlock chat_id
  56) Toggle guest chat mode
  57) Chat members (DB)        58) Mention members
  59) User account info        60) Managed bot link

   0) Exit
```

Just pick a number and follow the prompts.

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
```

#### Example: creating a managed bot

```
choice: 60

--- Create Managed Bot Invite Link ---
Suggested username for new bot (e.g. MyCoolBot): MyShopBot
Suggested display name (optional): My Shop Assistant

✔ Link generated:
  https://t.me/newbot/MyManagerBot/MyShopBot?name=My%20Shop%20Assistant

Share this link with users so they can create a bot managed by you.
```

When a user opens that link and confirms, your manager bot receives `updateManagedBot`, and `termgram` prints the new bot's info plus its token automatically.

---

### CLI mode

Any argument after the script name switches `termgram` into non-interactive mode. Every subcommand returns a shell exit code (`0` = success, non-zero = failure), so it composes well with scripts.

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
  web         start the browser client (see examples)

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

Each subcommand also has its own `--help`:

```bash
python3 termgram.py photo --help
python3 termgram.py ban --help
python3 termgram.py reply --help
python3 termgram.py web --help
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
python3 termgram.py unpin  -1001234567890            # unpin all
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
# local-only, HTTP, password = bot token
python3 termgram.py web

# custom port + explicit password
python3 termgram.py web --host 0.0.0.0 --port 9090 --password "s3cr3t"

# HTTPS with your own certificate (recommended for public hosts)
python3 termgram.py web --host 0.0.0.0 --port 443 \
    --https-cert ./cert.pem --https-key ./key.pem \
    --password "s3cr3t"

# localhost only, poller disabled (if you run Monitor elsewhere)
python3 termgram.py web --no-poller
```

##### Text & caption sources

Several subcommands accept text either **inline** or **from a file**:

| Subcommand  | Inline form            | File form          |
| ----------- | ---------------------- | ------------------ |
| `text`      | positional `text`      | `--text-file F`    |
| `edit`      | positional `text`      | `--text-file F`    |
| `reply`     | positional `text`      | `--text-file F`    |
| `set-bio`   | positional `description` | `--bio-file F`   |
| `set-short-bio` | positional `description` | `--bio-file F` |

File-based subcommands (photo, document, video, audio, voice, animation) accept two mutually-exclusive options for the caption:

| Option             | Meaning                                                  |
| ------------------ | -------------------------------------------------------- |
| `--caption TEXT`   | Inline caption string.                                   |
| `--caption-file F` | Read the caption from file `F` (UTF-8, multi-line safe). |

`--caption-file` takes precedence if both are given.

##### Exit codes

| Code | Meaning                                    |
| ---- | ------------------------------------------ |
| `0`  | Success (Telegram returned `ok`)           |
| `1`  | Telegram returned an error                 |
| `2`  | Local usage / file error (missing file, …) |

##### CLI banner

In CLI mode the banner is intentionally tiny so it can be piped safely:

```
termgram v1.3.0
```

No connectivity prompt, no "press any key" — a single-shot command runs, prints its result, and exits.

---

### Web UI (browser client)

Start the server:

```bash
python3 termgram.py web --host 127.0.0.1 --port 8081 --password "your-secret"
```

Then open **http://127.0.0.1:8081/** and log in.

| Flag | Default | Purpose |
|---|---|---|
| `--host` | `127.0.0.1` | Bind address (`0.0.0.0` for LAN — requires confirmation) |
| `--port` | `8081` | TCP port |
| `--password` | bot token | Login password — **always set a separate secret for public hosts** |
| `--session-ttl` | `86400` | Session lifetime in seconds |
| `--cache-max-mb` | `512` | Max disk cache for downloaded files |
| `--https-cert` / `--https-key` | — | PEM certificate + private key to enable HTTPS |
| `--no-poller` | off | Don't start the background `getUpdates` poller |

The **web UI requires the `web-ui/` directory** (containing `index.html`, `app.js`, `style.css`, `favicon.svg`) to be present next to `termgram.py`. If you cloned the repo, they're already there.

---

## 🖥 Platform notes

- ✅ **Linux / macOS**: fully supported.
- ⚠️ **Windows**: Persian/Farsi characters may not render correctly in the default terminal. Use **Windows Terminal** with a font that supports RTL (e.g. *Cascadia Code*, *Vazirmatn*) or run inside **WSL**. The web UI is unaffected and works in any browser.

---

| File                  | Purpose                                          | Committed?     |
| --------------------- | ------------------------------------------------ | -------------- |
| `termgram.py`         | Main program                                     | ✅              |
| `requirements.txt`    | Python dependencies                              | ✅              |
| `README.md`           | This file                                        | ✅              |
| `LICENSE`             | MIT license                                      | ✅              |
| `config.json.example` | Configuration template                           | ✅              |
| `web-ui/`             | Browser client (`index.html` + `static/`)        | ✅              |
| `config.json`         | Your real configuration & secrets                | ❌ (gitignored) |
| `tg.db`               | Local message database                           | ❌ (gitignored) |
| `cache/`              | File/avatar/media cache for the web UI           | ❌ (gitignored) |
| `get_updates_py.sh`   | Legacy shell script (superseded by Silent fetch) | ❌              |

---

## 🤝 Contributing

Contributions are welcome from **invited collaborators**. If you'd like to help, open an issue first to discuss what you'd like to change.

---

## 📜 License

[MIT](LICENSE)