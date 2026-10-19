# termgram

> A terminal client (TUI + CLI) for **Telegram bots** — send, manage, monitor, and bridge your bot directly from the command line.

`termgram` is a single-file, menu-driven TUI written in pure Python. It talks to the Telegram **Bot API** over HTTPS (via `requests`) and supports **SOCKS5 / HTTP proxies** out of the box (via `PySocks`). All received messages are stored locally in SQLite for later browsing. Since v1.1.0 it also ships with a **non-interactive CLI mode** for scripting and quick one-shot commands, and since v1.2.0 with a built-in **API Server** that can act as a full proxy/bridge in front of the Telegram Bot API (persisting every `getUpdates` payload into `tg.db`).

---

## ✨ Features

### 📨 Send every message type

Text · Photo · Animation (GIF) · Video · Document · Audio · Voice · Video note · Sticker · Location · Contact · Poll · Dice · Reaction

### 🖥 Three ways to drive it

- **Interactive TUI** — numbered menu, prompt-driven, ideal for exploring the API by hand.
- **CLI mode** — one-shot subcommands for scripting, cron jobs, or quick sends from the shell. Run `python3 termgram.py --help` to see every subcommand.
- **API Server** — a built-in HTTP bridge (menu option **52**) that listens on `host:port` with its own token and proxies `/bot<token>/<method>` calls to the real Telegram Bot API. `getUpdates` payloads are persisted into `tg.db` **before** the response is returned. (Upstream calls still use HTTPS to Telegram.)

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

Works identically across TUI, monitor mode (`r` command), and CLI (`--quote "..."`). The quote **must be an exact substring** of the source message's text/caption, otherwise Telegram returns `QUOTE_TEXT_INVALID`.

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

### 🔀 Cross-chat reply — **native, no copy**

Replying to a message that lives in **another chat** is now fully native. `termgram` uses Telegram's `reply_parameters` with an embedded `chat_id`:

```json
{
  "reply_parameters": {
    "message_id": 42,
    "chat_id": -1001234567890,
    "quote": "optional fragment"
  }
}
```

No more `copyMessage` round-trip. The reply appears **directly under the original message**, even across chats — exactly as a normal Telegram client would render it. If the source and target chats are the same, `reply_to_message_id` is used for simplicity.

- **TUI:** every send flow (text, photo, dice, …) — the `reply_to_message_id` prompt now offers a cross-chat branch.
- **CLI:** `--reply-to <id> --reply-to-chat <chat> [--quote "..."]`, or the dedicated `reply` subcommand.

> ⚠️ Telegram only accepts cross-chat replies when the bot has access to the source message (member of the source chat, or the source message was authored by the bot or another bot with shared access). Otherwise you get `MESSAGE_TO_BE_REPLIED_NOT_FOUND`.

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
5. **Cleanup orphans** — entities / `chat_users` rows with zero messages (leftovers from earlier purges)

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

📢 You were mentioned or replied to in 2 message(s).
  1) [MENTION] My Group  #12913  hey @YourBot can you check?
  2) [REPLY]   My Group  #12920  ...

View and reply to these now? [y/N]:
```

Choosing `y` opens each message and lets you reply inline — no need to jump back to Monitor.

### 🤖 Bot management mode

**Menu option 53** keeps a local registry of every bot you manage (from `getMe` + optional add-by-token):

- List every managed bot with id, username, `added_at`, `last_seen_at`
- View the stored token
- View / inspect stored permissions per chat
- Delete a bot's row (and its permission rows) from the DB

### 🛰 API Server (bridge / proxy)

**Menu option 52** starts a self-contained HTTP server that behaves like `api.telegram.org`:

- Listens on `api_server_host:api_server_port` (default `127.0.0.1:8080`)
- Accepts calls at `/bot<token>/<method>`
- Uses `api_server_token` from `config.json`, or falls back to the active bot token
- Forwards every request to the upstream Bot API (proxying via `PROXY` / `HTTPS_PROXY` if set)
- **Persists every `getUpdates` response** into `tg.db` (messages, edits, files, reactions, entities) **before** returning it to the caller
- Safe to leave running in the background; started automatically on launch if `api_server_enabled` is `true`

### 📡 Monitor & automation

Monitor mode (live updates) · Auto-reply · Auto-react · Reactions inline editing

### 💾 Local database (SQLite)

Silent fetch · Chat explorer · History viewer · Purge / cleanup — every received message is stored in `tg.db`

### 🌐 Proxy support

`socks5://` and `http://` — configured via `config.json`, interactively in **menu option 17**, **and** used automatically by the built-in API Server.

### 🧭 Zero-config TUI & smooth menu cascade

Everything is numbered. No flags to memorize for interactive use. Config and database files are auto-created on first run. When the interactive menu opens, it animates with a smooth, rapid cascade to avoid abrupt screen flashes.

### 🎨 Version banner

On interactive startup `termgram` prints a tidy banner:

```
╔════════════════════════════════════════════════════╗
║  📡 termgram  v1.2.0                              ║
║  Terminal client for Telegram bots                 ║
╚════════════════════════════════════════════════════╝
```

In **CLI mode** the banner is collapsed to a single short line, so it never pollutes shell output:

```
termgram v1.2.0
```

---

## 📋 Requirements

- **Python 3.10+** (tested on 3.14.7)
- `requests`
- `PySocks`

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

1. **Bot token**: Get your token from [@BotFather](https://t.me/BotFather).
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
║  📡 termgram  v1.2.0                               ║
║  Terminal client for Telegram bots                 ║
╚════════════════════════════════════════════════════╝
Connecting to Telegram API...
Using proxy: socks5://127.0.0.1:10808
✔ Bot connected: @YourBot (My Bot)

=============== Telegram Bot Sender ===============
  Locked chat_id: (none)   Guest: OFF   API: OFF
   1) Text message              2) Photo
   3) Animation (GIF)           4) Video
   ...
  50) Manage bot token         51) Manage reactions
   ...
--- Monitor ---------------------------------------
  39) Monitor mode
--- Advanced -------------------------------------
  52) API Server               53) Bot management
  54) Purge DB data            55) Lock/Unlock chat_id
  56) Toggle guest chat mode
  57) Chat members (DB)        58) Mention members
  59) User account info

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

Examples:
  termgram text 123456 "Hello"
  termgram text 123456 --text-file msg.txt --parse-mode Markdown
  termgram photo 123456 pic.jpg --caption "look"
  termgram document @mychan file.pdf --caption-file cap.txt
  termgram react 123456 42 👍
  termgram ban 123456 987654321 --revoke
  termgram download AgACAgQAAxkBAA... --out file.bin
  termgram upload 123456 ./img.png --as photo
```

Each subcommand also has its own `--help`:

```bash
python3 termgram.py photo --help
python3 termgram.py ban --help
python3 termgram.py reply --help
```

#### CLI examples

```bash
# ── sending ────────────────────────────────────────────────
# Plain text
python3 termgram.py text -1001234567890 "Hello from the shell"

# Text with Markdown + reply-to
python3 termgram.py text @mychannel "**bold** reply" \
    --parse-mode Markdown --reply-to 42

# Text with quote-reply (quote must be an exact substring)
python3 termgram.py text @mychannel "on it" \
    --reply-to 42 --quote "please check this"

# Cross-chat reply + quote in one shot
python3 termgram.py text @mych2 "ok!" \
    --reply-to 42 --reply-to-chat @mych1 --quote "please check this"

# Text read from a file (multi-line safe)
python3 termgram.py text -1001234567890 --text-file msg.txt

# Photo with inline caption
python3 termgram.py photo -1001234567890 ./pic.jpg --caption "look at this"

# Document, reading caption from a file
python3 termgram.py document @mychannel ./archive.zip --caption-file cap.txt

# Video with caption + reply-to
python3 termgram.py video -1001234567890 ./clip.mp4 \
    --caption "🎬" --reply-to 900

# Location, contact, dice
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

# Cross-chat reply (native, uses reply_parameters)
python3 termgram.py reply @news 100 -1001234567890 "this is important"

# Cross-chat reply with a quote fragment
python3 termgram.py reply @news 100 -1001234567890 "this is important" \
    --quote "breaking news"

# Same-chat reply (direct)
python3 termgram.py reply -1001234567890 55 -1001234567890 "thanks!"

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
termgram v1.2.0
```

No connectivity prompt, no "press any key" — a single-shot command runs, prints its result, and exits.

---

## 🖥 Platform notes

- ✅ **Linux / macOS**: fully supported.
- ⚠️ **Windows**: Persian/Farsi characters may not render correctly in the default terminal. Use **Windows Terminal** with a font that supports RTL (e.g. *Cascadia Code*, *Vazirmatn*) or run inside **WSL**.

---

| File                  | Purpose                                          | Committed?     |
| --------------------- | ------------------------------------------------ | -------------- |
| `termgram.py`         | Main program                                     | ✅              |
| `requirements.txt`    | Python dependencies                              | ✅              |
| `README.md`           | This file                                        | ✅              |
| `LICENSE`             | MIT license                                      | ✅              |
| `config.json.example` | Configuration template (token, proxy, base_url, API server, guest mode, lock, reactions) | ✅ |
| `config.json`         | Your real configuration & secrets                | ❌ (gitignored) |
| `tg.db`               | Local message database                           | ❌ (gitignored) |

---

## 🤝 Contributing

Contributions are welcome from **invited collaborators**. If you'd like to help, open an issue first to discuss what you'd like to change.

---

## 📜 License

[MIT](LICENSE)