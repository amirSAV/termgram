# termgram

> A terminal client (TUI) for **Telegram bots** — send, manage, and monitor your bot directly from the command line.

`termgram` is a single-file, menu-driven TUI written in pure Python. It talks to the Telegram **Bot API** over HTTPS (via `requests`) and supports **SOCKS5 / HTTP proxies** out of the box (via `PySocks`). All received messages are stored locally in SQLite for later browsing.

---

## ✨ Features

### 📨 Send every message type
Text · Photo · Animation (GIF) · Video · Document · Audio · Voice · Video note · Sticker · Location · Contact · Poll · Dice · Reaction

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

> 💡 On first run, `termgram` will auto-create `token.txt`, `proxy.txt`, and `tg.db` if they don't exist.

---

## ▶️ Usage

```bash
python3 termgram.py
```

You'll see:

```
Connecting to Telegram API...
Using proxy: socks5://127.0.0.1:10808
✔ Bot connected: @YourBot

=============== Telegram Bot Sender ===============
   1) Text message              2) Photo
   3) Animation (GIF)           4) Video
   ...
   0) Exit
```

Just pick a number and follow the prompts.

---

## 🖥 Platform notes

- ✅ **Linux / macOS**: fully supported.
- ⚠️ **Windows**: Persian/Farsi characters may not render correctly in the default terminal. Use **Windows Terminal** with a font that supports RTL (e.g. *Cascadia Code*, *Vazirmatn*) or run inside **WSL**.

---

## 📂 Files

| File | Purpose | Committed? |
|---|---|---|
| `termgram.py` | Main program | ✅ |
| `requirements.txt` | Python dependencies | ✅ |
| `README.md` | This file | ✅ |
| `LICENSE` | MIT license | ✅ |
| `token.txt.example` | Token template | ✅ |
| `proxy.txt.example` | Proxy template | ✅ |
| `token.txt` | Your real token | ❌ (gitignored) |
| `proxy.txt` | Your real proxy | ❌ (gitignored) |
| `tg.db` | Local message database | ❌ (gitignored) |

---

## 🤝 Contributing

Contributions are welcome from **invited collaborators**. If you'd like to help, open an issue first to discuss what you'd like to change.

---

## 📜 License

[MIT](LICENSE)