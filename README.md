# termgram

> A terminal client (TUI) for **Telegram bots** — send, manage, and monitor your bot directly from the command line.

`termgram` is a single-file, menu-driven TUI written in pure Python. It talks to the Telegram **Bot API** over HTTPS (via `requests`) and supports **SOCKS5 / HTTP proxies** out of the box (via `PySocks`). All received messages are stored locally in SQLite for later browsing.

---

## ✨ Features

### 📨 Send every message type

Text · Photo · Animation (GIF) · Video · Document · Audio · Voice · Video note · Sticker · Location · Contact · Poll · Dice · Reaction

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

### 🛠 Message management

Edit · Delete · Pin · Unpin · Forward · Chat actions (typing / uploading)

### 👥 Chat & member management

Leave chat · Get chat info · Member count · Member info · Ban · Unban · Promote / Demote admin · Set admin title · Set user tag · Set chat title / description · Create invite link

### 🤖 Bot profile

Set name · Set bio (description) · Set short bio · Set / remove profile photo · `getMe`

### 📁 Files

Download any file by `file_id` · Upload a local file and get its `file_id`

### 📡 Monitor & automation

Monitor mode (live updates) · Reply-to-other-chat

### 💾 Local database (SQLite)

Silent fetch · Chat explorer · History viewer — every received message is stored in `tg.db`

### 🌐 Proxy support

`socks5://` and `http://` — configured via `proxy.txt`

### 🧭 Zero-config, menu-driven

Everything is numbered. No CLI flags to memorize. Config files are auto-created on first run.

### 🎨 Version banner

On startup `termgram` prints a tidy banner with its name and version:

```
╔════════════════════════════════════════════════════╗
║  📡 termgram  v1.0.0                              ║
║  Terminal client for Telegram bots                 ║
╚════════════════════════════════════════════════════╝
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

---

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

```bash
python3 termgram.py
```

You'll see:

```
╔════════════════════════════════════════════════════╗
║  📡 termgram  v1.0.0                              ║
║  Terminal client for Telegram bots                 ║
╚════════════════════════════════════════════════════╝
✔ Created reactions.txt with 61 reactions
Connecting to Telegram API...
Using proxy: socks5://127.0.0.1:10808
✔ Bot connected: @YourBot (My Bot)

=============== Telegram Bot Sender ===============
          termgram v1.0.0
   1) Text message              2) Photo
   3) Animation (GIF)           4) Video
   ...
   0) Exit
```

Just pick a number and follow the prompts.

### Example: sending a text message with buttons

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