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

`termgram` ships with a **built-in list of 61 Telegram reactions** (👍 ❤️ 🔥 …). On first run it auto-creates a `reactions.txt` file seeded with that list. Edit the file to keep only the reactions you care about — for example the ones your bot has unlocked, or a curated shortlist.

Each line defines one reaction. The **first character is the emoji**, followed by a **space**, and then the **name/description** you want shown in the menu:

```
👍 Like
❤️ Love
🔥 Fire
🎉 Party
😢 Sad
```

- The first character (emoji) is what gets sent to Telegram.
- Everything after the first space is just a label shown in the numbered menu.
- Lines starting with `#` are treated as comments and ignored.

> 💡 **Hot-reload:** `reactions.txt` is re-read automatically when its contents change — no restart needed. Delete the file and the built-in list is used again until you recreate it.

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

`socks5://` and `http://` — configured via `proxy.txt`

### 🧭 Zero-config TUI

Everything is numbered. No flags to memorize for interactive use. Config files are auto-created on first run.

### 🎨 Version banner

On interactive startup `termgram` prints a tidy banner:

```
╔════════════════════════════════════════════════════╗
║  📡 termgram  v1.0.1                              ║
║  Terminal client for Telegram bots                 ║
╚════════════════════════════════════════════════════╝
```

In **CLI mode** the banner is collapsed to a single short line, so it never pollutes shell output:

```
termgram v1.0.1
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

### 1. Bot token

Create a file named `token.txt` in the project root and put your bot token in it (single line):

```
123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
```

Get a token from [@BotFather](https://t.me/BotFather).

### 2. Proxy (optional)

Create `proxy.txt` and put the proxy URL on a single line:

```
socks5://127.0.0.1:10808
```

Supported schemes: `socks5://`, `http://`, `https://`.
If the file is missing or empty, `termgram` connects directly.

> 💡 On first run, `termgram` will auto-create `token.txt`, `proxy.txt`, `reactions.txt`, and `tg.db` if they don't exist.

### 3. Custom reactions (optional)

You don't need to create `reactions.txt` manually — `termgram` writes it on first run, seeded with the full built-in Telegram reaction list.

To narrow it down, just edit `reactions.txt` (while the program is running is fine — it reloads on change):

```
👍 Like
❤️ Love
🔥 Fire
🎉 Party
😢 Sad
```

- The first token is the emoji that gets sent to Telegram.
- Everything after the first space is a label shown in the numbered menu.
- Lines starting with `#` are comments.
- Delete the file and `termgram` falls back to the built-in list until you recreate it.

---

## ▶️ Usage

### Interactive TUI

```bash
python3 termgram.py
```

You'll see:

```
╔════════════════════════════════════════════════════╗
║  📡 termgram  v1.0.1                              ║
║  Terminal client for Telegram bots                 ║
╚════════════════════════════════════════════════════╝
✔ Created reactions.txt with 61 reactions
Connecting to Telegram API...
Using proxy: socks5://127.0.0.1:10808
✔ Bot connected: @YourBot (My Bot)

=============== Telegram Bot Sender ===============
          termgram v1.0.1
   1) Text message              2) Photo
   3) Animation (GIF)           4) Video
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

| File                    | Purpose                       | Committed?     |
| ----------------------- | ----------------------------- | -------------- |
| `termgram.py`           | Main program                  | ✅              |
| `requirements.txt`      | Python dependencies           | ✅              |
| `README.md`             | This file                     | ✅              |
| `LICENSE`               | MIT license                   | ✅              |
| `token.txt.example`     | Token template                | ✅              |
| `proxy.txt.example`     | Proxy template                | ✅              |
| `reactions.txt.example` | Reactions template            | ✅              |
| `token.txt`             | Your real token               | ❌ (gitignored) |
| `proxy.txt`             | Your real proxy               | ❌ (gitignored) |
| `reactions.txt`         | Your reactions (auto-created) | ❌ (gitignored) |
| `tg.db`                 | Local message database        | ❌ (gitignored) |

---

## 🤝 Contributing

Contributions are welcome from **invited collaborators**. If you'd like to help, open an issue first to discuss what you'd like to change.

---

## 📜 License

[MIT](LICENSE)