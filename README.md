# termgram

> A terminal client (TUI + CLI) for **Telegram bots** — send, manage, and monitor your bot directly from the command line.

`termgram` is a single-file, menu-driven TUI written in pure Python. It talks to the Telegram **Bot API** over HTTPS (via `requests`) and supports **SOCKS5 / HTTP proxies** out of the box (via `PySocks`). All received messages are stored locally in SQLite for later browsing. Since v1.1.0 it also ships with a **non-interactive CLI mode** for scripting and quick one-shot commands.

---

## ✨ Features

### 📨 Send every message type

Text · Photo · Animation (GIF) · Video · Document · Audio · Voice · Video note · Sticker · Location · Contact · Poll · Dice · Reaction

### 🖥 Two ways to drive it

- **Interactive TUI** — numbered menu, prompt-driven, ideal for exploring the API by hand.
- **CLI mode** — one-shot subcommands for scripting, cron jobs, or quick sends from the shell. Run `python3 termgram.py --help` to see every subcommand.

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

On startup, `termgram` validates your token directly with Telegram's servers. If the token is invalid or missing, it alerts you immediately (confirming Telegram API's `401 Unauthorized` response) and prompts for a valid token or allows a clean exit.

### 🛡 Zero-crash bootstrapping

Even if `termgram.py` is executed standalone in an empty directory, it automatically creates `config.json` and initializes `tg.db` SQLite schema without crashing or raising missing-file errors.

### 🔀 Cross-chat reply

Replying to a message that lives in **another chat** is supported natively. Since Telegram does **not** allow `reply_to_message_id` to cross chat boundaries, `termgram` handles this in two steps behind the scenes:

1. `copyMessage` copies the source message into the target chat (creating a new message there).
2. `sendMessage` replies to that newly created copy.

The end result: the target chat sees a copy of the original message with your reply attached underneath it. If source and target chats are the **same**, the copy step is skipped and a plain reply is used.

- **TUI:** menu option **40) Reply other chat**
- **CLI:** `python3 termgram.py reply <src_chat> <src_msg_id> <dst_chat> "<text>"`

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

### 🛠 Message management

Edit · Delete · Pin · Unpin · Forward · Chat actions (typing / uploading)

### 👥 Chat & member management

Leave chat · Get chat info · Member count · Member info · Ban · Unban · Promote / Demote admin · Set admin title · Set user tag · Set chat title / description · Create invite link

### 📁 Files

Download any file by `file_id` · Upload a local file and get its `file_id`

### 📡 Monitor & automation

Monitor mode (live updates) · Auto-reply · Auto-react · Reply-to-other-chat

### 💾 Local database (SQLite)

Silent fetch · Chat explorer · History viewer — every received message is stored in `tg.db`

### 🌐 Proxy support

`socks5://` and `http://` — configured via `config.json` or interactively in **menu option 17) Configure proxy**.

### 🧭 Zero-config TUI & smooth menu cascade

Everything is numbered. No flags to memorize for interactive use. Config and database files are auto-created on first run. When the interactive menu opens, it animates with a smooth, rapid cascade to avoid abrupt screen flashes.

### 🎨 Version banner

On interactive startup `termgram` prints a tidy banner:

```
╔════════════════════════════════════════════════════╗
║  📡 termgram  v1.1.0                              ║
║  Terminal client for Telegram bots                 ║
╚════════════════════════════════════════════════════╝
```

In **CLI mode** the banner is collapsed to a single short line, so it never pollutes shell output:

```
termgram v1.1.0
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

All configuration—bot token, proxy, and custom reactions—is stored in a single `config.json` file. You can create it from the provided template:

```bash
cp config.json.example config.json
```

Or simply launch `termgram` directly (`python3 termgram.py`): `termgram` will auto-generate `config.json` and `tg.db` on first run and interactively prompt you to enter a valid bot token!

Example `config.json`:

```json
{
  "token": "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ",
  "proxy": "socks5://127.0.0.1:10808",
  "reactions": [
    {
      "emoji": "👍",
      "label": "Thumbs Up"
    },
    {
      "emoji": "👎",
      "label": "Thumbs Down"
    },
    {
      "emoji": "❤️",
      "label": "Red Heart"
    },
    {
      "emoji": "🔥",
      "label": "Fire"
    }
  ]
}
```

1. **Bot token**: Get your token from [@BotFather](https://t.me/BotFather).
2. **Proxy (optional)**: Supported schemes: `socks5://`, `http://`, `https://`. Set to `""` for direct connection.
3. **Reactions**: Curated list of emoji reactions. Can be configured directly via **menu option 51) Manage reactions**.

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
║  📡 termgram  v1.1.0                               ║
║  Terminal client for Telegram bots                 ║
╚════════════════════════════════════════════════════╝
Connecting to Telegram API...
Using proxy: socks5://127.0.0.1:10808
✔ Bot connected: @YourBot (My Bot)

=============== Telegram Bot Sender ===============
   1) Text message              2) Photo
   3) Animation (GIF)           4) Video
   ...
  50) Manage bot token         51) Manage reactions
   ...
   0) Exit
```

Just pick a number and follow the prompts.

#### Example: sending a text message with buttons

```
choice: 1

--- Common fields ---
chat_id (number or @username): @my_channel
reply_to_message_id (empty = no reply):
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

# Cross-chat reply (copy + reply, handled automatically)
python3 termgram.py reply @news 100 -1001234567890 "this is important"

# Same-chat reply (no copy, direct reply)
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
termgram v1.0.1
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
| `config.json.example` | Configuration template (token, proxy, reactions) | ✅              |
| `config.json`         | Your real configuration & secrets                | ❌ (gitignored) |
| `tg.db`               | Local message database                           | ❌ (gitignored) |

---

## 🤝 Contributing

Contributions are welcome from **invited collaborators**. If you'd like to help, open an issue first to discuss what you'd like to change.

---

## 📜 License

[MIT](LICENSE)