#!/usr/bin/env python3
# ================================================================
#  Interactive Telegram Bot Sender  (full Python rewrite of send.sh)
#  + send / edit / delete + reaction
#  + proxy (HTTP/SOCKS5) + leave chat + manage chat
#  + pin/unpin + forward + ban + invite link + ...
#  + getMe + file upload/download + bot profile & bio
#  + Monitor mode (auto-poll getUpdates, auto-reply, auto-react)
# ================================================================

import os
import sys
import json
import time
import sqlite3
import random
import html
import hmac
import re
import secrets
from datetime import datetime, timezone
import argparse
from typing import Optional, Dict, Any, List, Tuple
import atexit

# ============ getUpdates Lock (apt-style) ============
_LOCK_FILE = ".getupdates.lock"
_lock_handle = None
_lock_owner: Optional[str] = None


def _try_flock(fh) -> bool:
    """Try to acquire a non-blocking exclusive lock on an open file handle."""
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (IOError, OSError):
        return False


def _unlock_file(fh) -> None:
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass


def acquire_getupdates_lock(owner: str) -> bool:
    """Acquire the exclusive getUpdates lock.
       owner: 'monitor' | 'silent-fetch' | 'web-poller' | 'api-server'
       Returns True if acquired (or already held by same owner in this process).
    """
    global _lock_handle, _lock_owner
    if _lock_handle is not None:
        return _lock_owner == owner
    try:
        fh = open(_LOCK_FILE, "a+")
    except Exception as e:
        print(f"{Y}⚠ Cannot open lock file: {e}{N}")
        return False
    if not _try_flock(fh):
        fh.close()
        return False
    try:
        fh.seek(0)
        fh.truncate()
        fh.write(json.dumps({
            "owner": owner,
            "pid": os.getpid(),
            "started": time.time(),
        }))
        fh.flush()
    except Exception:
        pass
    _lock_handle = fh
    _lock_owner = owner
    return True


def release_getupdates_lock() -> None:
    """Release the lock if this process holds it."""
    global _lock_handle, _lock_owner
    if _lock_handle is None:
        return
    try:
        _unlock_file(_lock_handle)
        _lock_handle.close()
    except Exception:
        pass
    _lock_handle = None
    _lock_owner = None


def getupdates_lock_holder() -> Optional[dict]:
    """Return who holds the lock (None if free). Uses flock to verify."""
    try:
        if not os.path.exists(_LOCK_FILE):
            return None
        with open(_LOCK_FILE, "a+") as fh:
            if _try_flock(fh):
                _unlock_file(fh)
                return None
            fh.seek(0)
            content = fh.read().strip()
            if not content:
                return {"owner": "?", "pid": "?", "started": 0}
            try:
                return json.loads(content)
            except Exception:
                return {"owner": "?", "pid": "?", "started": 0}
    except Exception:
        return None


def _fmt_age(started: float) -> str:
    if not started:
        return "?"
    age = max(0, time.time() - started)
    if age < 60:
        return f"{int(age)}s"
    m, s = divmod(int(age), 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def print_lock_holder(prefix: str = "") -> None:
    holder = getupdates_lock_holder()
    if not holder:
        print(f"{prefix}{Y}lock is free{N}")
        return
    print(f"{prefix}{R}✘ getUpdates lock held by: "
          f"{holder.get('owner', '?')} "
          f"(pid {holder.get('pid', '?')}, "
          f"age {_fmt_age(holder.get('started', 0))}){N}")


atexit.register(release_getupdates_lock)

# ============ Third-party Dependencies ============
try:
    import requests
except ImportError:
    _r = '\033[31m'
    _y = '\033[33m'
    _c = '\033[36m'
    _n = '\033[0m'
    print(f"\n{_r}✘ Error: Required dependency 'requests' is not installed!{_n}\n")
    print(f"{_y}To run termgram, setting up a Python virtual environment is recommended:{_n}\n")
    print("  1. Create virtual environment:")
    print("     python3 -m venv venv\n")
    print("  2. Activate virtual environment:")
    print("     - Linux / macOS:                source venv/bin/activate")
    print("     - Windows (PowerShell):         venv\\Scripts\\Activate.ps1")
    print("     - Windows (Command Prompt):     venv\\Scripts\\activate.bat\n")
    print("  3. Install dependencies:")
    print("     pip install -r requirements.txt")
    print("     (or manually: pip install requests PySocks)\n")
    sys.exit(1)

# --- Readline enhancements (in-memory only, no history file) ---
try:
    import readline
    readline.parse_and_bind("tab: complete")
    readline.set_history_length(1000)
except ImportError:
    pass

# ============ App info ============
APP_NAME    = "termgram"
APP_VERSION = "1.4.0"
APP_TAGLINE = "Terminal client for Telegram bots"

# ============ Configuration ============
CONFIG_FILE = "config.json"
LEGACY_TOKEN_FILE = "token.txt"
LEGACY_PROXY_FILE = "proxy.txt"
LEGACY_REACTIONS_FILE = "reactions.txt"
DB_FILE = "tg.db"

# ============ Full Telegram reactions (standard set) ============
TELEGRAM_REACTIONS: List[Tuple[str, str]] = [
    ("👍", "Thumbs Up"),            ("👎", "Thumbs Down"),
    ("❤️", "Red Heart"),            ("🔥", "Fire"),
    ("🥰", "Smiling Face w/ Hearts"),("👏", "Clapping Hands"),
    ("😁", "Beaming Face"),         ("🤔", "Thinking Face"),
    ("🤯", "Exploding Head"),       ("😱", "Screaming in Fear"),
    ("🤬", "Symbols on Mouth"),     ("😢", "Crying Face"),
    ("🎉", "Party Popper"),         ("🤩", "Star-Struck"),
    ("🤮", "Face Vomiting"),        ("💩", "Pile of Poo"),
    ("🙏", "Folded Hands"),         ("👌", "OK Hand"),
    ("🕊", "Dove"),                 ("🤡", "Clown Face"),
    ("🥱", "Yawning Face"),         ("🥴", "Woozy Face"),
    ("😍", "Heart-Eyes"),           ("🐳", "Spouting Whale"),
    ("❤️‍🔥", "Heart on Fire"),       ("🌚", "New Moon Face"),
    ("🌭", "Hot Dog"),              ("💯", "Hundred Points"),
    ("🤣", "Rolling Laughing"),     ("⚡️", "High Voltage"),
    ("🍌", "Banana"),               ("🏆", "Trophy"),
    ("💔", "Broken Heart"),         ("🤨", "Raised Eyebrow"),
    ("😐", "Neutral Face"),         ("🍓", "Strawberry"),
    ("🍾", "Popping Cork"),         ("🍿", "Popcorn"),
    ("🙈", "See-No-Evil"),          ("😇", "Halo"),
    ("😜", "Wink + Tongue"),        ("👨‍💻", "Man Technologist"),
    ("📚", "Books"),                ("👾", "Alien Monster"),
    ("💅", "Nail Polish"),          ("🤪", "Zany Face"),
    ("🗿", "Moai"),                 ("🆒", "Cool Button"),
    ("💘", "Heart with Arrow"),     ("🙉", "Hear-No-Evil"),
    ("🦄", "Unicorn"),              ("😘", "Blowing a Kiss"),
    ("💊", "Pill"),                 ("🫡", "Saluting Face"),
    ("🎅", "Santa Claus"),          ("🎄", "Christmas Tree"),
    ("☃️", "Snowman"),              ("🍷", "Wine Glass"),
    ("💸", "Money with Wings"),     ("🫠", "Melting Face"),
    ("😼", "Cat Wry Smile"),        ("🤝", "Handshake"),
]

def load_config() -> Dict[str, Any]:
    """Load configuration from config.json. Auto-creates and migrates legacy files if needed."""
    default_config: Dict[str, Any] = {
        "token": "",
        "proxy": "",
        "base_url": "",
        "api_server_enabled": False,
        "api_server_host": "127.0.0.1",
        "api_server_port": 8080,
        "api_server_token": "",
        "guest_chat_mode": False,
        "locked_chat_id": "",
        "reactions": [
            {"emoji": emoji, "label": name} for emoji, name in TELEGRAM_REACTIONS
        ]
    }

    config: Dict[str, Any] = dict(default_config)

    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                config.update(loaded)
                if "reactions" not in config or not isinstance(config["reactions"], list):
                    config["reactions"] = default_config["reactions"]
        except Exception as e:
            print(f"{Y}⚠ Warning: Could not parse {CONFIG_FILE}: {e}{N}")
    else:
        # Check for legacy files to migrate
        if os.path.isfile(LEGACY_TOKEN_FILE):
            try:
                with open(LEGACY_TOKEN_FILE, "r", encoding="utf-8") as f:
                    t = f.read().strip()
                    if t:
                        config["token"] = t
            except Exception:
                pass
        if os.path.isfile(LEGACY_PROXY_FILE):
            try:
                with open(LEGACY_PROXY_FILE, "r", encoding="utf-8") as f:
                    p = f.read().strip()
                    if p:
                        config["proxy"] = p
            except Exception:
                pass
        if os.path.isfile(LEGACY_REACTIONS_FILE):
            try:
                legacy_reactions = []
                with open(LEGACY_REACTIONS_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split(" ", 1)
                        emoji = parts[0]
                        name = parts[1] if len(parts) > 1 else ""
                        if emoji:
                            legacy_reactions.append({"emoji": emoji, "label": name})
                if legacy_reactions:
                    config["reactions"] = legacy_reactions
            except Exception:
                pass

        # Write the initial / migrated config.json
        save_config(config)

    # Clean up legacy files if present
    for legacy_f in (LEGACY_TOKEN_FILE, LEGACY_PROXY_FILE, LEGACY_REACTIONS_FILE):
        if os.path.isfile(legacy_f):
            try:
                os.remove(legacy_f)
            except Exception:
                pass

    return config


def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to config.json atomically."""
    try:
        tmp_file = f"{CONFIG_FILE}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_file, CONFIG_FILE)
        return True
    except Exception as e:
        print(f"{R}✘ Error saving {CONFIG_FILE}: {e}{N}")
        return False


def get_config_token() -> str:
    cfg = load_config()
    return str(cfg.get("token", "")).strip()


def set_config_token(token: str) -> bool:
    cfg = load_config()
    cfg["token"] = token.strip()
    return save_config(cfg)


def get_config_proxy() -> str:
    cfg = load_config()
    return str(cfg.get("proxy", "")).strip()


def set_config_proxy(proxy: str) -> bool:
    cfg = load_config()
    cfg["proxy"] = proxy.strip()
    return save_config(cfg)

def get_config_base_url() -> str:
    return str(load_config().get("base_url", "")).strip()

def set_config_base_url(url: str) -> bool:
    cfg = load_config()
    cfg["base_url"] = url.strip()
    return save_config(cfg)

def get_locked_chat_id() -> str:
    return str(load_config().get("locked_chat_id", "")).strip()

def set_locked_chat_id(cid: str) -> bool:
    cfg = load_config()
    cfg["locked_chat_id"] = str(cid).strip()
    return save_config(cfg)

def get_guest_chat_mode() -> bool:
    return bool(load_config().get("guest_chat_mode", False))

def set_guest_chat_mode(on: bool) -> bool:
    cfg = load_config()
    cfg["guest_chat_mode"] = bool(on)
    return save_config(cfg)

def ensure_db() -> None:
    """Ensure local SQLite database schema is initialized without error."""
    try:
        conn = sqlite3.connect(DB_FILE)
        db_init(conn)
        conn.close()
    except Exception as e:
        print(f"{Y}⚠ Could not initialize database {DB_FILE}: {e}{N}")

# ============ Colors ============
G = '\033[32m'
Y = '\033[33m'
R = '\033[31m'
B = '\033[36m'
M = '\033[35m'
N = '\033[0m'

# ============ Terminal helpers ============
import shutil

def clear_screen() -> None:
    """Clear the screen AND the scrollback buffer."""
    try:
        # \033[H   — cursor to home
        # \033[2J  — erase visible screen
        # \033[3J  — erase saved lines (scrollback)
        sys.stdout.write("\033[H\033[2J\033[3J")
        sys.stdout.flush()
    except Exception:
        os.system("cls" if os.name == "nt" else "clear")

def _term_size() -> Tuple[int, int]:
    sz = shutil.get_terminal_size(fallback=(80, 24))
    return sz.columns, sz.lines

# ============ Progress helpers ============
def _human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def _format_eta(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def draw_progress(done: int, total: Optional[int],
                  start_time: float,
                  width: Optional[int] = None,
                  prefix: str = "") -> None:
    """One-line in-place progress bar (rewrites the same line with \\r)."""
    if width is None:
        term_w, _ = _term_size()
        # leave room for numbers/speed/ETA around the bar
        width = max(10, min(40, term_w - 60))

    elapsed = max(0.001, time.time() - start_time)
    speed_bps = done / elapsed if done else 0

    if total and total > 0:
        pct = min(1.0, done / total)
        filled = int(width * pct)
        bar = "█" * filled + "░" * (width - filled)
        eta = ""
        if speed_bps > 1 and total > done:
            eta = f" ETA {_format_eta((total - done) / speed_bps)}"
        line = (
            f"{prefix}[{bar}] {pct * 100:5.1f}%  "
            f"{_human_size(done)}/{_human_size(total)}  "
            f"{_human_size(speed_bps)}/s{eta}"
        )
    else:
        # unknown total — spinner
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        spin = frames[int(time.time() * 10) % len(frames)]
        line = (
            f"{prefix}{spin} {_human_size(done)}  "
            f"{_human_size(speed_bps)}/s"
        )

    # pad to terminal width so nothing stale remains
    term_w, _ = _term_size()
    sys.stdout.write("\r" + line.ljust(term_w - 1))
    sys.stdout.flush()


def finish_progress(prefix: str = "") -> None:
    """Print final newline after the progress bar."""
    sys.stdout.write("\n")
    sys.stdout.flush()


class ProgressFileReader:
    """File-like wrapper that reports read progress. Compatible with `requests`
       (multipart upload uses this to track bytes sent)."""

    def __init__(self, path: str):
        self.path = path
        self._f = open(path, "rb")
        self.total = os.path.getsize(path)
        self.done = 0
        self.start = time.time()

    def read(self, size: int = -1) -> bytes:
        chunk = self._f.read(size)
        if chunk:
            self.done += len(chunk)
            draw_progress(self.done, self.total, self.start,
                          prefix="⬆ ")
        return chunk

    def __len__(self) -> int:
        return self.total

    def __iter__(self):
        return iter(lambda: self.read(8192), b"")

    def seek(self, pos: int, whence: int = 0) -> int:
        result = self._f.seek(pos, whence)
        self.done = self._f.tell()
        return result

    def tell(self) -> int:
        return self._f.tell()

    def close(self) -> None:
        self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

# ============ Global state ============
PROXY = ""


# ================================================================
#  TelegramBot – HTTP client (replaces curl)
# ================================================================
class TelegramBot:
    def __init__(self, token: str, proxy_url: str = "", base_url: Optional[str] = None):
        self.token = token
        _root = (base_url or "https://api.telegram.org").rstrip("/")
        self.base_url = f"{_root}/bot{token}"
        self.file_api = f"{_root}/file/bot{token}"
        self.session = requests.Session()
        self.bot_id: Optional[int] = None
        self.bot_info: Optional[dict] = None
        self.ask_retry: bool = True   # Prompt user to retry on transient failures
        self.max_attempts: int = 10   # Safety limit to prevent infinite loops
        if proxy_url:
            self.session.proxies = {"http": proxy_url, "https": proxy_url}

    def set_proxy(self, proxy_url: str):
        global PROXY
        PROXY = proxy_url
        if proxy_url:
            self.session.proxies = {"http": proxy_url, "https": proxy_url}
        else:
            self.session.proxies = {}

    # ---------- low-level helpers ----------
    def post(self, method: str, data: dict = None, files: dict = None,
             ask_retry: Optional[bool] = None) -> Optional[dict]:
        return self._do_request(
            lambda: self.session.post(f"{self.base_url}/{method}",
                                      data=data, files=files, timeout=30),
            method, ask_retry)

    def get(self, method: str, params: dict = None,
            ask_retry: Optional[bool] = None) -> Optional[dict]:
        return self._do_request(
            lambda: self.session.get(f"{self.base_url}/{method}",
                                     params=params, timeout=60),
            method, ask_retry)
    
    def _do_request(self, http_call, method: str,
                    ask_retry: Optional[bool] = None) -> Optional[dict]:
        """Run http_call(); on network failure ask user to retry."""
        ask = self.ask_retry if ask_retry is None else ask_retry
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = http_call()
                result = resp.json()

                # --- server said not ok: retry only for transient errors ---
                if not result.get("ok"):
                    desc = (result.get("description") or "").lower()
                    transient = any(k in desc for k in (
                        "too many requests", "internal server error",
                        "bad gateway", "gateway timeout", "service unavailable",
                        "retry after",
                    ))
                    if not transient:
                        return result
                    print(f"{Y}⚠ Transient error ({method}): "
                          f"{result.get('description')}{N}")
                    if not ask:
                        return result
                    ans = input(f"{B}Retry {method}? [Y/n]: {N}").strip().lower()
                    if ans == "n":
                        print(f"{Y}Giving up on {method}.{N}")
                        return result
                    time.sleep(2)
                    continue

                return result

            except Exception as e:
                print(f"{R}✘ Network error ({method}) "
                      f"[attempt {attempt}]: {e}{N}")
                if not ask:
                    return None
                if attempt >= self.max_attempts:
                    print(f"{R}Max attempts reached for {method}.{N}")
                    return None
                ans = input(f"{B}Retry {method}? [Y/n]: {N}").strip().lower()
                if ans == "n":
                    print(f"{Y}Giving up on {method}.{N}")
                    return None
                time.sleep(1)

    def get_bot_id(self) -> Optional[int]:
        if self.bot_id:
            return self.bot_id
        resp = self.post("getMe")
        if resp and resp.get("ok"):
            self.bot_id = resp["result"]["id"]
            return self.bot_id
        return None
        # ---------- Managed Bots ----------
    def check_managed_bot_username(self, username: str) -> Optional[dict]:
        """Check whether a username is available for a new bot."""
        return self.post("bots.checkUsername", data={"username": username})

    def create_managed_bot(self, user_id: int, username: str, name: str,
                           via_deeplink: bool = False) -> Optional[dict]:
        """Create a new bot managed by this manager bot."""
        data = {
            "user_id": user_id,
            "username": username,
            "name": name,
        }
        if via_deeplink:
            data["via_deeplink"] = "true"
        return self.post("bots.createBot", data=data)

    def get_managed_bot_token(self, user_id: int) -> Optional[dict]:
        """Get the full token of a managed bot."""
        return self.post("getManagedBotToken", data={"user_id": user_id})

    def replace_managed_bot_token(self, user_id: int) -> Optional[dict]:
        """Generate a new token for a managed bot (old token is invalidated)."""
        return self.post("replaceManagedBotToken", data={"user_id": user_id})

    def get_managed_bot_access_settings(self, user_id: int) -> Optional[dict]:
        """Get the access settings of a managed bot."""
        return self.post("bots.getAccessSettings", data={"user_id": user_id})

    def edit_managed_bot_access_settings(self, user_id: int, **settings) -> Optional[dict]:
        """Edit the access settings of a managed bot."""
        data = {"user_id": user_id}
        data.update(settings)
        return self.post("bots.editAccessSettings", data=data)

    def export_managed_bot_token(self, user_id: int) -> Optional[dict]:
        """Export a managed bot token via MTProto (if supported)."""
        return self.post("bots.exportBotToken", data={"user_id": user_id})


# ================================================================
#  SQLite database (same schema as get_updates_py.sh)
# ================================================================
def db_utcnow() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def db_one_line(s: str) -> str:
    if not s:
        return ''
    return ' '.join(s.replace('\t', ' ').split())


def db_shorten(s: str, n: int = 200) -> str:
    s = s or ''
    return (s[:n] + '...') if len(s) > n else s


def db_init(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    PRAGMA journal_mode = WAL;
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS state (
        key   TEXT PRIMARY KEY,
        value TEXT
    );

    CREATE TABLE IF NOT EXISTS entities (
        id             INTEGER PRIMARY KEY,
        kind           TEXT    NOT NULL,
        first_name     TEXT,
        last_name     TEXT,
        username       TEXT,
        title          TEXT,
        is_bot         INTEGER DEFAULT 0,
        language_code  TEXT,
        first_seen_at  TEXT    NOT NULL,
        last_seen_at   TEXT    NOT NULL,
        updated_at     TEXT    NOT NULL
    );

    CREATE TABLE IF NOT EXISTS chat_users (
        chat_id        INTEGER NOT NULL,
        user_id        INTEGER NOT NULL,
        first_seen_at  TEXT    NOT NULL,
        last_seen_at   TEXT    NOT NULL,
        message_count  INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS messages (
        chat_id             INTEGER NOT NULL,
        message_id          INTEGER NOT NULL,
        update_id           INTEGER,
        from_user_id        INTEGER,
        sender_chat_id      INTEGER,
        date                INTEGER,
        content_type        TEXT,
        text                TEXT,
        caption             TEXT,
        reply_to_message_id INTEGER,
        is_edited           INTEGER DEFAULT 0,
        edit_count          INTEGER DEFAULT 0,
        raw_json            TEXT,
        first_seen_at       TEXT    NOT NULL,
        updated_at          TEXT    NOT NULL,
        PRIMARY KEY (chat_id, message_id)
    );

    CREATE TABLE IF NOT EXISTS message_files (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id            INTEGER NOT NULL,
        message_id         INTEGER NOT NULL,
        file_type          TEXT    NOT NULL,
        file_id            TEXT,
        file_unique_id     TEXT,
        file_name          TEXT,
        mime_type          TEXT,
        file_size          INTEGER,
        width              INTEGER,
        height             INTEGER,
        duration           INTEGER,
        performer          TEXT,
        title              TEXT,
        emoji              TEXT,
        set_name           TEXT,
        is_animated        INTEGER DEFAULT 0,
        is_video           INTEGER DEFAULT 0,
        thumbnail_file_id  TEXT,
        first_seen_at      TEXT    NOT NULL,
        updated_at         TEXT    NOT NULL,
        UNIQUE (chat_id, message_id, file_type, file_unique_id)
    );

    CREATE TABLE IF NOT EXISTS message_edits (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id    INTEGER NOT NULL,
        message_id INTEGER NOT NULL,
        update_id  INTEGER,
        old_text   TEXT,
        new_text   TEXT,
        edited_at  TEXT    NOT NULL
    );

    CREATE TABLE IF NOT EXISTS updates (
        update_id    INTEGER PRIMARY KEY,
        kind         TEXT,
        processed_at TEXT NOT NULL,
        raw_json     TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_messages_date   ON messages(date);
    CREATE INDEX IF NOT EXISTS idx_messages_from   ON messages(from_user_id);
    CREATE INDEX IF NOT EXISTS idx_messages_chat   ON messages(chat_id);
    CREATE INDEX IF NOT EXISTS idx_entities_kind   ON entities(kind);
    CREATE INDEX IF NOT EXISTS idx_chat_users_user ON chat_users(user_id);
    CREATE INDEX IF NOT EXISTS idx_edits_msg       ON message_edits(chat_id, message_id);
    CREATE INDEX IF NOT EXISTS idx_files_msg       ON message_files(chat_id, message_id);
    CREATE INDEX IF NOT EXISTS idx_files_uid       ON message_files(file_unique_id);
    CREATE INDEX IF NOT EXISTS idx_files_type      ON message_files(file_type);

    CREATE TABLE IF NOT EXISTS message_reactions (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id        INTEGER NOT NULL,
        message_id     INTEGER NOT NULL,
        user_id        INTEGER,
        actor_chat_id  INTEGER,
        old_reactions  TEXT,
        new_reactions  TEXT,
        is_anonymous   INTEGER DEFAULT 0,
        changed_at     INTEGER,
        first_seen_at  TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_reactions_msg
        ON message_reactions(chat_id, message_id);
    CREATE INDEX IF NOT EXISTS idx_reactions_user
        ON message_reactions(user_id);

    CREATE TABLE IF NOT EXISTS managed_bots (
        bot_id INTEGER PRIMARY KEY,
        username TEXT, first_name TEXT,
        token TEXT,
        added_at TEXT, last_seen_at TEXT, updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS bot_permissions (
        bot_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
        permissions_json TEXT,
        PRIMARY KEY (bot_id, chat_id)
    );

    CREATE TABLE IF NOT EXISTS web_sessions (
        token       TEXT PRIMARY KEY,
        csrf_token  TEXT NOT NULL,
        created_at  TEXT NOT NULL,
        expires_at  TEXT NOT NULL,
        ip          TEXT,
        user_agent  TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_web_sessions_exp ON web_sessions(expires_at);

    CREATE TABLE IF NOT EXISTS file_cache (
        file_unique_id    TEXT PRIMARY KEY,
        file_id           TEXT,
        file_path         TEXT,
        file_size         INTEGER,
        downloaded_at     TEXT NOT NULL,
        last_accessed_at  TEXT NOT NULL,
        access_count      INTEGER DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_file_cache_accessed
        ON file_cache(last_accessed_at);

    CREATE TABLE IF NOT EXISTS user_photos (
        user_id        INTEGER PRIMARY KEY,
        file_unique_id TEXT,
        file_id        TEXT,
        file_path      TEXT,
        file_size      INTEGER,
        fetched_at     TEXT NOT NULL,
        updated_at     TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS reaction_usage (
        emoji        TEXT PRIMARY KEY,
        count        INTEGER DEFAULT 0,
        last_used_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS chat_admins (
        chat_id       INTEGER NOT NULL,
        user_id       INTEGER NOT NULL,
        status        TEXT,
        custom_title  TEXT,
        is_anonymous  INTEGER DEFAULT 0,
        updated_at    TEXT NOT NULL,
        PRIMARY KEY (chat_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS chat_photos (
        chat_id        INTEGER PRIMARY KEY,
        file_unique_id TEXT,
        file_id        TEXT,
        file_path      TEXT,
        file_size      INTEGER,
        fetched_at     TEXT NOT NULL,
        updated_at     TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS mention_flags (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id       INTEGER NOT NULL,
        message_id    INTEGER NOT NULL,
        kind          TEXT NOT NULL,
        from_user_id  INTEGER,
        created_at    TEXT NOT NULL,
        seen          INTEGER DEFAULT 0,
        UNIQUE (chat_id, message_id)
    );
    CREATE INDEX IF NOT EXISTS idx_mention_flags_chat_seen
        ON mention_flags(chat_id, seen);

    CREATE TABLE IF NOT EXISTS saved_media (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        media_type         TEXT NOT NULL,
        file_id            TEXT NOT NULL,
        file_unique_id     TEXT NOT NULL UNIQUE,
        thumbnail_file_id  TEXT,
        emoji              TEXT,
        set_name           TEXT,
        file_name          TEXT,
        saved_at           TEXT NOT NULL,
        is_favorite        INTEGER DEFAULT 0,
        use_count          INTEGER DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_saved_media_type
        ON saved_media(media_type);
    CREATE INDEX IF NOT EXISTS idx_saved_media_fav
        ON saved_media(is_favorite);
    """)
    conn.commit()


def db_state_get(conn, key, default=None):
    row = conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


def db_state_set(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)",
                 (key, str(value)))
    conn.commit()


def db_upsert_entity(conn, eid, *, kind=None, first_name=None, last_name=None,
                     username=None, title=None, is_bot=None, language_code=None,
                     force_kind=True):
    now = db_utcnow()
    exists = conn.execute("SELECT 1 FROM entities WHERE id = ?", (eid,)).fetchone()
    if exists:
        sets, params = ["last_seen_at = ?", "updated_at = ?"], [now, now]
        if force_kind and kind:
            sets.append("kind = ?"); params.append(kind)
        for col, val in (("first_name", first_name), ("last_name", last_name),
                         ("username", username), ("title", title),
                         ("language_code", language_code)):
            if val is not None:
                sets.append(f"{col} = ?"); params.append(val)
        if is_bot is not None:
            sets.append("is_bot = ?"); params.append(1 if is_bot else 0)
        params.append(eid)
        conn.execute(f"UPDATE entities SET {', '.join(sets)} WHERE id = ?", params)
    else:
        conn.execute(
            """INSERT INTO entities
               (id, kind, first_name, last_name, username, title,
                is_bot, language_code, first_seen_at, last_seen_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (eid, kind, first_name, last_name, username, title,
             1 if is_bot else 0, language_code, now, now, now))


def db_register_user(conn, user, force_kind=False):
    if not user or 'id' not in user:
        return
    db_upsert_entity(
        conn, user['id'],
        kind='bot' if user.get('is_bot') else 'user',
        first_name=user.get('first_name'),
        last_name=user.get('last_name'),
        username=user.get('username'),
        is_bot=user.get('is_bot', False),
        language_code=user.get('language_code'),
        force_kind=force_kind,
    )


def db_upsert_chat_user(conn, chat_id, user_id):
    now = db_utcnow()
    row = conn.execute(
        "SELECT 1 FROM chat_users WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id)).fetchone()
    if row:
        conn.execute(
            "UPDATE chat_users SET last_seen_at = ?, message_count = message_count + 1 "
            "WHERE chat_id = ? AND user_id = ?",
            (now, chat_id, user_id))
    else:
        conn.execute(
            "INSERT INTO chat_users "
            "(chat_id, user_id, first_seen_at, last_seen_at, message_count) "
            "VALUES (?, ?, ?, ?, 1)",
            (chat_id, user_id, now, now))


def db_describe_content(msg: dict) -> str:
    for key, desc in (
        ('text', 'text'), ('photo', 'photo'), ('animation', 'animation (GIF)'),
        ('video', 'video'), ('video_note', 'video_note'), ('voice', 'voice'),
        ('audio', 'audio'), ('document', 'document'), ('sticker', 'sticker'),
        ('location', 'location'), ('venue', 'venue'), ('contact', 'contact'),
        ('poll', 'poll'), ('dice', 'dice'),
        ('new_chat_members', 'new_chat_members'),
        ('left_chat_member', 'left_chat_member'),
        ('pinned_message', 'pinned_message'),
    ):
        if key in msg:
            return desc
    return 'unknown'


def db_extract_files(msg: dict) -> list:
    out = []
    if msg.get('photo'):
        for p in msg['photo']:
            out.append({
                'file_type': 'photo', 'file_id': p.get('file_id'),
                'file_unique_id': p.get('file_unique_id'),
                'file_size': p.get('file_size'), 'width': p.get('width'),
                'height': p.get('height'), 'file_name': None, 'mime_type': None,
                'duration': None, 'performer': None, 'title': None, 'emoji': None,
                'set_name': None, 'is_animated': 0, 'is_video': 0,
                'thumbnail_file_id': None,
            })
    simple_types = (
        ('animation', 'animation'), ('video', 'video'), ('video_note', 'video_note'),
        ('voice', 'voice'), ('audio', 'audio'), ('document', 'document'),
        ('sticker', 'sticker'),
    )
    for key, ftype in simple_types:
        f = msg.get(key)
        if not f:
            continue
        thumb = f.get('thumbnail') or f.get('thumb') or {}
        out.append({
            'file_type': ftype, 'file_id': f.get('file_id'),
            'file_unique_id': f.get('file_unique_id'),
            'file_name': f.get('file_name'), 'mime_type': f.get('mime_type'),
            'file_size': f.get('file_size'), 'width': f.get('width'),
            'height': f.get('height'), 'duration': f.get('duration'),
            'performer': f.get('performer'), 'title': f.get('title'),
            'emoji': f.get('emoji'), 'set_name': f.get('set_name'),
            'is_animated': 1 if f.get('is_animated') else 0,
            'is_video': 1 if f.get('is_video') else 0,
            'thumbnail_file_id': thumb.get('file_id') if thumb else None,
        })
    return out


def db_store_update(conn, uid, kind, raw):
    conn.execute(
        "INSERT OR REPLACE INTO updates (update_id, kind, processed_at, raw_json) "
        "VALUES (?, ?, ?, ?)",
        (uid, kind, db_utcnow(), json.dumps(raw, ensure_ascii=False)))


def db_process_message(conn, uid, kind, obj):
    """Store one message update into the DB. Returns a dict describing it (or None)."""
    chat = obj.get('chat', {})
    from_user = obj.get('from')
    sender_chat = obj.get('sender_chat')

    chat_id = chat.get('id')
    chat_type = chat.get('type')

    db_upsert_entity(
        conn, chat_id, kind=chat_type,
        first_name=chat.get('first_name'), last_name=chat.get('last_name'),
        username=chat.get('username'), title=chat.get('title'),
        force_kind=True)
    if from_user:
        db_register_user(conn, from_user, force_kind=False)
    if sender_chat:
        db_upsert_entity(conn, sender_chat['id'], kind='channel',
                         title=sender_chat.get('title'),
                         username=sender_chat.get('username'), force_kind=False)
    for m in obj.get('new_chat_members') or []:
        db_register_user(conn, m, force_kind=False)
    if obj.get('left_chat_member'):
        db_register_user(conn, obj['left_chat_member'], force_kind=False)

    msg_id = obj.get('message_id')
    date_u = obj.get('date', 0)
    text = obj.get('text') or obj.get('caption') or ''
    ctype = db_describe_content(obj)
    from_id = from_user['id'] if from_user else None
    is_bot = bool(from_user.get('is_bot')) if from_user else False

    reply_id = None
    rtm = obj.get('reply_to_message')
    if rtm:
        reply_id = rtm.get('message_id')
        if rtm.get('from'):
            db_register_user(conn, rtm['from'], force_kind=False)

    files = db_extract_files(obj)

    row = conn.execute(
        "SELECT text, edit_count FROM messages WHERE chat_id = ? AND message_id = ?",
        (chat_id, msg_id)).fetchone()
    if row:
        prev_text, prev_edit_count = row[0] or '', row[1] or 0
        is_edit = (kind in ('edited_message', 'edited_channel_post')) or (prev_text != text)
    else:
        prev_text, prev_edit_count = '', 0
        is_edit = kind in ('edited_message', 'edited_channel_post')
    edit_count = prev_edit_count + (1 if is_edit else 0)

    if from_user and chat_type != 'private' and not is_edit:
        db_upsert_chat_user(conn, chat_id, from_id)

    now = db_utcnow()
    sender_id = sender_chat.get('id') if sender_chat else None

    raw_payload = {
        'update_id': uid, 'update_kind': kind, 'processed_at': now,
        'message': obj,
    }
    raw_json = json.dumps(raw_payload, ensure_ascii=False)

    if row:
        conn.execute("""UPDATE messages SET
                          update_id = ?, from_user_id = ?, sender_chat_id = ?,
                          date = ?, content_type = ?, text = ?, caption = ?,
                          reply_to_message_id = ?, is_edited = ?, edit_count = ?,
                          raw_json = ?, updated_at = ?
                        WHERE chat_id = ? AND message_id = ?""",
                     (uid, from_id, sender_id, date_u, ctype,
                      obj.get('text'), obj.get('caption'), reply_id,
                      1 if is_edit else 0, edit_count,
                      raw_json, now, chat_id, msg_id))
    else:
        conn.execute("""INSERT INTO messages
                          (chat_id, message_id, update_id, from_user_id, sender_chat_id,
                           date, content_type, text, caption, reply_to_message_id,
                           is_edited, edit_count, raw_json, first_seen_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (chat_id, msg_id, uid, from_id, sender_id, date_u, ctype,
                      obj.get('text'), obj.get('caption'), reply_id,
                      1 if is_edit else 0, edit_count, raw_json, now, now))

    if files:
        existing = conn.execute(
            "SELECT COUNT(*) FROM message_files WHERE chat_id = ? AND message_id = ?",
            (chat_id, msg_id)).fetchone()[0]
        if existing == 0:
            for fi in files:
                conn.execute(
                    """INSERT OR IGNORE INTO message_files
                       (chat_id, message_id, file_type, file_id, file_unique_id,
                        file_name, mime_type, file_size, width, height, duration,
                        performer, title, emoji, set_name, is_animated, is_video,
                        thumbnail_file_id, first_seen_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (chat_id, msg_id,
                     fi.get('file_type'), fi.get('file_id'), fi.get('file_unique_id'),
                     fi.get('file_name'), fi.get('mime_type'), fi.get('file_size'),
                     fi.get('width'), fi.get('height'), fi.get('duration'),
                     fi.get('performer'), fi.get('title'), fi.get('emoji'),
                     fi.get('set_name'), fi.get('is_animated', 0), fi.get('is_video', 0),
                     fi.get('thumbnail_file_id'), now, now))

    if is_edit:
        conn.execute("""INSERT INTO message_edits
                          (chat_id, message_id, update_id, old_text, new_text, edited_at)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                     (chat_id, msg_id, uid, prev_text, text, now))

    conn.commit()

    return {
        'uid': uid, 'kind': kind, 'is_edit': is_edit,
        'chat_id': chat_id, 'chat_type': chat_type,
        'chat_title': chat.get('title') or chat.get('first_name') or '',
        'chat_username': chat.get('username') or '',
        'message_id': msg_id, 'date': date_u,
        'from_id': from_id,
        'from_first': from_user.get('first_name', '') if from_user else '',
        'from_last': from_user.get('last_name', '') if from_user else '',
        'from_username': from_user.get('username', '') if from_user else '',
        'is_bot': is_bot,
        'content_type': ctype, 'text': obj.get('text'),
        'caption': obj.get('caption'),
        'reply_to_message_id': reply_id,
        'mentions': obj.get('entities') or obj.get('caption_entities') or [],
        'files': files,
    }


# ================================================================
#  Input helpers
# ================================================================
def read_text_or_file(field: str) -> str:
    while True:
        src = input(f"{field}: type [t] directly or read [f] from file? (t/f): ").strip().lower()
        if src in ("t", ""):
            return input(f"{field}: ")
        elif src == "f":
            path = input("path to .txt file: ").strip()
            if not os.path.isfile(path):
                print(f"{R}file not found: {path}{N}")
                continue
            with open(path, encoding="utf-8") as f:
                return f.read()
        else:
            print(f"{R}invalid choice (t/f){N}")

def ask_inline_buttons() -> Optional[str]:
    print(f"\n{B}--- Inline URL buttons (optional) ---{N}")
    ans = input(f"{Y}Add inline URL buttons under this message? [y/N]: {N}").strip().lower()
    if ans != "y":
        return None

    print(f"{B}Add buttons row by row. Empty row number = finish.{N}")
    print(f"{Y}Tip:{N} multiple buttons in one row appear side by side.\n")

    rows: List[List[dict]] = []
    row_num = 1
    while True:
        raw = input(f"{B}Row {row_num} — number of buttons (empty = finish): {N}").strip()
        if not raw:
            break
        if not raw.isdigit() or int(raw) <= 0:
            print(f"{R}enter a positive number or leave empty to finish{N}")
            continue
        n = int(raw)
        row: List[dict] = []
        for i in range(1, n + 1):
            text = input(f"  button {i} — text (e.g. 🌐 Website): ").strip()
            url = input(f"  button {i} — url  (https://...): ").strip()
            if not text or not url:
                print(f"{R}both text and url are required — skipping this button{N}")
                continue
            if not (url.startswith("http://") or url.startswith("https://")
                    or url.startswith("tg://")):
                print(f"{Y}⚠ URL usually should start with http(s):// or tg://{N}")
            row.append({"text": text, "url": url})
        if row:
            rows.append(row)
            row_num += 1

    if not rows:
        return None
    markup = json.dumps({"inline_keyboard": rows}, ensure_ascii=False)
    print(f"{G}✔ {sum(len(r) for r in rows)} button(s) in {len(rows)} row(s) attached.{N}")
    return markup

def read_common(allow_buttons: bool = True) -> Optional[dict]:
    print(f"\n{B}--- Common fields ---{N}")
    locked = get_locked_chat_id()
    if locked:
        chat_id = locked
        print(f"{G}chat_id (locked): {chat_id}{N}")
    else:
        chat_id = input("chat_id (number or @username): ").strip()
        if not chat_id:
            print(f"{R}chat_id is required{N}")
            return None

    reply_to = None
    reply_params = None
    ans = input("reply_to_message_id (empty = no reply): ").strip()
    if ans:
        # cross-chat?
        cross = input("  ↳ cross-chat reply (source msg in another chat)? [y/N]: ").strip().lower()
        src_chat = None
        if cross == "y":
            src_chat = input("  ↳ source chat_id (where the original message lives): ").strip()
            if not src_chat:
                print(f"{R}  source chat_id required — falling back to same-chat reply{N}")
                src_chat = None

        # quote part of message?
        quote = None
        qa = input("  ↳ quote a specific part of the message? [y/N]: ").strip().lower()
        if qa == "y":
            quote = input("  ↳ quote text (must be an exact substring of the original): ")
            if not quote or not quote.strip():
                quote = None
                print(f"{Y}  empty quote — ignoring{N}")

        # build reply primitive
        if quote or src_chat:
            try:
                msg_val = int(ans)
            except ValueError:
                msg_val = ans
            rp: Dict[str, Any] = {"message_id": msg_val}
            if src_chat:
                rp["chat_id"] = (int(src_chat)
                                 if str(src_chat).lstrip('-').isdigit()
                                 else src_chat)
            if quote:
                rp["quote"] = quote
            reply_params = rp
        else:
            reply_to = ans

    parse_mode = input("parse_mode [Markdown/HTML/MarkdownV2] (empty = none): ").strip() or None
    ans = input("disable_notification? [y/N]: ").strip()
    disable_notif = ans.lower() == "y"
    ans = input("protect_content? [y/N]: ").strip()
    protect = ans.lower() == "y"

    reply_markup = ask_inline_buttons() if allow_buttons else None

    return {
        "chat_id": chat_id,
        "reply_to_message_id": reply_to,
        "reply_parameters": reply_params,   # new field
        "parse_mode": parse_mode,
        "disable_notification": disable_notif,
        "protect_content": protect,
        "reply_markup": reply_markup,
    }


def build_data(common: dict, extra: dict = None) -> dict:
    data = {"chat_id": common["chat_id"]}
    if common.get("reply_parameters"):
        data["reply_parameters"] = json.dumps(common["reply_parameters"], ensure_ascii=False)
    elif common.get("reply_to_message_id"):
        data["reply_to_message_id"] = common["reply_to_message_id"]
    if common.get("parse_mode"):
        data["parse_mode"] = common["parse_mode"]
    if common.get("disable_notification"):
        data["disable_notification"] = "true"
    if common.get("protect_content"):
        data["protect_content"] = "true"
    if common.get("reply_markup"):
        data["reply_markup"] = common["reply_markup"]
    if extra:
        data.update(extra)
    return data


def guess_mime(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    mimes = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".mp4": "video/mp4", ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg", ".pdf": "application/pdf",
        ".zip": "application/zip", ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    return mimes.get(ext, "application/octet-stream")


def handle_file_field(field_name: str) -> Tuple[Optional[str], Optional[dict]]:
    value = input(f"input {field_name} (file path / URL / file_id): ").strip()
    if not value:
        print(f"{R}value is empty{N}")
        return None, None
    if os.path.isfile(value):
        mime = guess_mime(value)
        pf = ProgressFileReader(value)
        files = {field_name: (os.path.basename(value), pf, mime)}
        return None, files
    return value, None


def show_send_result(result: Optional[dict]):
    if not result:
        print(f"{R}✘ No response from server{N}")
        return
    if result.get("ok"):
        res = result.get("result")
        if isinstance(res, dict) and "message_id" in res:
            _persist_from_resp(result)
            msg_id = res.get("message_id")
            print(f"{G}✔ Success{N}")
            print(f"{G}📨 message_id: {msg_id}{N}")
            return
        print(f"{G}✔ Success{N}")
    else:
        print(f"{R}✘ Failed:{N}")
        print(json.dumps(result, indent=2, ensure_ascii=False))

def _persist_from_resp(resp: Optional[dict], update_kind: str = "message"):
    """If resp contains a Message object, store it in the DB.
       Safe to call on any API response — silently ignores non-message results."""
    if not resp or not resp.get("ok"):
        return
    result = resp.get("result")
    if not isinstance(result, dict) or "message_id" not in result:
        return
    try:
        conn = sqlite3.connect(DB_FILE)
        db_init(conn)
        db_process_message(conn, 0, update_kind, result)
        conn.close()
    except Exception as e:
        print(f"{Y}⚠ Could not persist sent message: {e}{N}")

def show_info_result(result: Optional[dict]):
    if not result:
        print(f"{R}✘ No response from server{N}")
        return
    if result.get("ok"):
        print(f"{G}✔ Result:{N}")
        print(json.dumps(result.get("result"), indent=2, ensure_ascii=False))
    else:
        print(f"{R}✘ Failed:{N}")
        print(json.dumps(result, indent=2, ensure_ascii=False))

def load_reactions() -> List[Tuple[str, str]]:
    """Load reactions from config.json, fallback to built-in TELEGRAM_REACTIONS."""
    cfg = load_config()
    raw = cfg.get("reactions")
    res: List[Tuple[str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                emoji = str(item.get("emoji", "")).strip()
                label = str(item.get("label", "")).strip()
                if emoji:
                    res.append((emoji, label))
            elif isinstance(item, (list, tuple)) and len(item) > 0:
                emoji = str(item[0]).strip()
                label = str(item[1]).strip() if len(item) > 1 else ""
                if emoji:
                    res.append((emoji, label))
            elif isinstance(item, str) and item.strip():
                res.append((item.strip(), ""))
    if not res:
        res = list(TELEGRAM_REACTIONS)
    return res


def save_reactions(reactions: List[Tuple[str, str]]) -> bool:
    """Save reactions list to config.json."""
    cfg = load_config()
    cfg["reactions"] = [{"emoji": emoji, "label": label} for emoji, label in reactions]
    return save_config(cfg)



def pick_reaction() -> Optional[str]:
    """Let user pick a reaction by number, emoji, or random (Enter)."""
    reactions = load_reactions()
    if not reactions:
        print(f"{R}No reactions available.{N}")
        return None

    # --- display grid: 3 columns per row ---
    print(f"\n{B}--- Pick a reaction ---{N}")
    cols = 3
    per_col = (len(reactions) + cols - 1) // cols
    for row in range(per_col):
        line = "  "
        for c in range(cols):
            i = row + c * per_col
            if i >= len(reactions):
                continue
            emoji, name = reactions[i]
            cell = f"{i + 1:>2}) {emoji}  {name[:22]}"
            line += cell.ljust(34)
        print(line)

    print(f"\n  {Y}⏎ = random   |   type number   |   paste emoji directly{N}")
    sel = input("reaction: ").strip()

    if not sel:
        emoji, name = random.choice(reactions)
        print(f"{G}🎲 random → {emoji}  {name}{N}")
        return emoji

    if sel.isdigit():
        idx = int(sel) - 1
        if 0 <= idx < len(reactions):
            return reactions[idx][0]
        print(f"{R}invalid number{N}")
        return None

    # direct emoji paste — accept as-is
    return sel

# ================================================================
#  Send methods
# ================================================================
def send_message(bot: TelegramBot):
    common = read_common()
    if not common:
        return
    text = read_text_or_file("text")
    if not text:
        print(f"{R}text is empty{N}")
        return
    data = build_data(common, {"text": text})
    print(f"\n{Y}>> sendMessage ...{N}")
    show_send_result(bot.post("sendMessage", data=data))


def send_photo(bot: TelegramBot):
    common = read_common()
    if not common:
        return
    value, files = handle_file_field("photo")
    if value is None and files is None:
        return
    data = build_data(common)
    caption = read_text_or_file("caption")
    if caption:
        data["caption"] = caption
    if value:
        data["photo"] = value
    print(f"\n{Y}>> sendPhoto ...{N}")
    show_send_result(bot.post("sendPhoto", data=data, files=files))


def send_animation(bot: TelegramBot):
    common = read_common()
    if not common:
        return
    value, files = handle_file_field("animation")
    if value is None and files is None:
        return
    data = build_data(common)
    caption = read_text_or_file("caption")
    if caption:
        data["caption"] = caption
    if value:
        data["animation"] = value
    dur = input("duration (seconds, empty = auto): ").strip()
    w = input("width (empty = auto): ").strip()
    h = input("height (empty = auto): ").strip()
    if dur:
        data["duration"] = dur
    if w:
        data["width"] = w
    if h:
        data["height"] = h
    print(f"\n{Y}>> sendAnimation ...{N}")
    show_send_result(bot.post("sendAnimation", data=data, files=files))


def send_video(bot: TelegramBot):
    common = read_common()
    if not common:
        return
    value, files = handle_file_field("video")
    if value is None and files is None:
        return
    data = build_data(common)
    caption = read_text_or_file("caption")
    if caption:
        data["caption"] = caption
    if value:
        data["video"] = value
    dur = input("duration (seconds): ").strip()
    w = input("width: ").strip()
    h = input("height: ").strip()
    ans = input("supports_streaming? [y/N]: ").strip()
    if dur:
        data["duration"] = dur
    if w:
        data["width"] = w
    if h:
        data["height"] = h
    if ans.lower() == "y":
        data["supports_streaming"] = "true"
    print(f"\n{Y}>> sendVideo ...{N}")
    show_send_result(bot.post("sendVideo", data=data, files=files))


def send_document(bot: TelegramBot):
    common = read_common()
    if not common:
        return
    value, files = handle_file_field("document")
    if value is None and files is None:
        return
    data = build_data(common)
    caption = read_text_or_file("caption")
    if caption:
        data["caption"] = caption
    if value:
        data["document"] = value
    print(f"\n{Y}>> sendDocument ...{N}")
    show_send_result(bot.post("sendDocument", data=data, files=files))


def send_audio(bot: TelegramBot):
    common = read_common()
    if not common:
        return
    value, files = handle_file_field("audio")
    if value is None and files is None:
        return
    data = build_data(common)
    caption = read_text_or_file("caption")
    if caption:
        data["caption"] = caption
    if value:
        data["audio"] = value
    perf = input("performer (empty = skip): ").strip()
    title = input("title (empty = skip): ").strip()
    dur = input("duration (seconds): ").strip()
    if perf:
        data["performer"] = perf
    if title:
        data["title"] = title
    if dur:
        data["duration"] = dur
    print(f"\n{Y}>> sendAudio ...{N}")
    show_send_result(bot.post("sendAudio", data=data, files=files))


def send_voice(bot: TelegramBot):
    common = read_common()
    if not common:
        return
    value, files = handle_file_field("voice")
    if value is None and files is None:
        return
    data = build_data(common)
    caption = read_text_or_file("caption")
    if caption:
        data["caption"] = caption
    if value:
        data["voice"] = value
    dur = input("duration (seconds): ").strip()
    if dur:
        data["duration"] = dur
    print(f"\n{Y}>> sendVoice ...{N}")
    show_send_result(bot.post("sendVoice", data=data, files=files))


def send_video_note(bot: TelegramBot):
    common = read_common(allow_buttons=False)
    if not common:
        return
    value, files = handle_file_field("video_note")
    if value is None and files is None:
        return
    data = build_data(common)
    if value:
        data["video_note"] = value
    dur = input("duration (seconds): ").strip()
    length = input("length (diameter, empty = auto): ").strip()
    if dur:
        data["duration"] = dur
    if length:
        data["length"] = length
    print(f"\n{Y}>> sendVideoNote ...{N}")
    show_send_result(bot.post("sendVideoNote", data=data, files=files))


def send_sticker(bot: TelegramBot):
    common = read_common()
    if not common:
        return
    value, files = handle_file_field("sticker")
    if value is None and files is None:
        return
    data = build_data(common)
    if value:
        data["sticker"] = value
    emo = input("emoji (empty = skip): ").strip()
    if emo:
        data["emoji"] = emo
    print(f"\n{Y}>> sendSticker ...{N}")
    show_send_result(bot.post("sendSticker", data=data, files=files))


def send_location(bot: TelegramBot):
    common = read_common()
    if not common:
        return
    lat = input("latitude: ").strip()
    lon = input("longitude: ").strip()
    if not lat or not lon:
        print(f"{R}latitude and longitude are required{N}")
        return
    data = build_data(common, {"latitude": lat, "longitude": lon})
    ha = input("horizontal_accuracy (empty = skip): ").strip()
    if ha:
        data["horizontal_accuracy"] = ha
    print(f"\n{Y}>> sendLocation ...{N}")
    show_send_result(bot.post("sendLocation", data=data))


def send_contact(bot: TelegramBot):
    common = read_common()
    if not common:
        return
    phone = input("phone_number: ").strip()
    fn = input("first_name: ").strip()
    if not phone or not fn:
        print(f"{R}phone_number and first_name are required{N}")
        return
    data = build_data(common, {"phone_number": phone, "first_name": fn})
    ln = input("last_name (empty = skip): ").strip()
    if ln:
        data["last_name"] = ln
    print(f"\n{Y}>> sendContact ...{N}")
    show_send_result(bot.post("sendContact", data=data))


def send_poll(bot: TelegramBot):
    common = read_common()
    if not common:
        return
    question = read_text_or_file("question")
    if not question:
        print(f"{R}question is empty{N}")
        return
    opts_raw = input("options (comma-separated): ").strip()
    opts = [o.strip() for o in opts_raw.split(",") if o.strip()]
    opts_json = json.dumps([{"text": o} for o in opts], ensure_ascii=False)
    ptype = input("type [regular/quiz] (empty = regular): ").strip()
    ans = input("is_anonymous? [y/N]: ").strip()
    data = build_data(common, {
        "question": question,
        "options": opts_json,
        "type": ptype or "regular",
        "is_anonymous": "true" if ans.lower() == "y" else "false",
    })
    if ptype == "quiz":
        coi = input("correct_option_id (0-based index): ").strip()
        data["correct_option_id"] = coi
    print(f"\n{Y}>> sendPoll ...{N}")
    show_send_result(bot.post("sendPoll", data=data))


def send_dice(bot: TelegramBot):
    common = read_common()
    if not common:
        return
    dice_emojis = ["🎲", "🎯", "🏀", "⚽", "🎳", "🎰"]
    dice_names = ["Dice", "Darts", "Basketball", "Football", "Bowling", "Slot Machine"]
    print(f"\n{B}--- Dice emoji ---{N}")
    for i, (e, n) in enumerate(zip(dice_emojis, dice_names)):
        print(f"  {i + 1:2d}) {e}  {n}")
    while True:
        choice = input(f"Select dice [1-{len(dice_emojis)}] (empty = 🎲): ").strip()
        if not choice:
            choice = "1"
        if choice.isdigit() and 1 <= int(choice) <= len(dice_emojis):
            break
        print(f"{R}Invalid selection.{N}")
    data = build_data(common, {"emoji": dice_emojis[int(choice) - 1]})
    print(f"\n{Y}>> sendDice ...{N}")
    show_send_result(bot.post("sendDice", data=data))


def send_reaction(bot: TelegramBot):
    print(f"\n{B}--- Send Reaction ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    msg_id = input("message_id to react to: ").strip()
    if not msg_id:
        print(f"{R}message_id is required{N}")
        return
    emoji = pick_reaction()
    if not emoji:
        print(f"{R}emoji required{N}")
        return
    ans = input("is_big? [y/N]: ").strip()
    is_big = "true" if ans.lower() == "y" else "false"
    reaction_json = json.dumps([{"type": "emoji", "emoji": emoji}])
    data = {"chat_id": chat_id, "message_id": msg_id, "reaction": reaction_json}
    if is_big == "true":
        data["is_big"] = "true"
    print(f"\n{Y}>> setMessageReaction ...{N}")
    show_send_result(bot.post("setMessageReaction", data=data))


# ================================================================
#  Edit / Delete methods
# ================================================================
def edit_message(bot: TelegramBot):
    print(f"\n{B}--- Edit Message ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    msg_id = input("message_id to edit: ").strip()
    if not msg_id:
        print(f"{R}message_id is required{N}")
        return
    print("\nWhat do you want to edit?")
    print(" 1) Text       (editMessageText)")
    print(" 2) Caption    (editMessageCaption)")
    edit_type = input("choice [1/2]: ").strip()
    parse_mode = input("parse_mode [Markdown/HTML/MarkdownV2] (empty = none): ").strip()
    if edit_type == "1":
        content = read_text_or_file("new text")
        if not content:
            print(f"{R}text is empty{N}")
            return
        data = {"chat_id": chat_id, "message_id": msg_id, "text": content}
        if parse_mode:
            data["parse_mode"] = parse_mode
        print(f"\n{Y}>> editMessageText ...{N}")
        show_send_result(bot.post("editMessageText", data=data))
    elif edit_type == "2":
        content = read_text_or_file("new caption")
        if not content:
            print(f"{R}caption is empty{N}")
            return
        data = {"chat_id": chat_id, "message_id": msg_id, "caption": content}
        if parse_mode:
            data["parse_mode"] = parse_mode
        print(f"\n{Y}>> editMessageCaption ...{N}")
        show_send_result(bot.post("editMessageCaption", data=data))
    else:
        print(f"{R}invalid choice{N}")

def _pick_chat_required(conn) -> Optional[int]:
    """Show chats in DB and let user pick one (required — no 'all chats' option).
       Respects locked_chat_id. Returns int chat_id or None (cancelled)."""
    locked = get_locked_chat_id()
    if locked:
        if locked.lstrip('-').isdigit():
            print(f"{G}chat_id (locked): {locked}{N}")
            return int(locked)
        print(f"{G}chat_id (locked, username): {locked}{N}")
        return None  # username locked — caller should handle

    rows = conn.execute(
        """SELECT m.chat_id, COUNT(*) cnt, MAX(m.date) last_date,
                  e.title, e.first_name, e.last_name, e.username, e.kind
             FROM messages m
             LEFT JOIN entities e ON e.id = m.chat_id
            GROUP BY m.chat_id
            ORDER BY last_date DESC""").fetchall()

    print(f"\n{B}--- Chats in DB ---{N}")
    if not rows:
        print(f"{Y}No chats in DB yet. Run Monitor / Silent fetch first, "
              f"or enter an id manually.{N}")
    else:
        for i, r in enumerate(rows, 1):
            cid, cnt, last_date, title, fn, ln, un, kind = r
            label = title or (fn and f"{fn} {ln or ''}".strip()) or str(cid)
            uname = f" @{un}" if un else ""
            print(f"  {i:>3}) {label:<28} [{kind or '?':<10}] "
                  f"id={cid}  msgs={cnt}  last={_fmt_ts(last_date)}{uname}")

    print("    m) Manual chat_id")
    print("    0) Cancel")
    sel = input("\nSelect chat: ").strip().lower()
    if not sel or sel == "0":
        return None
    if sel == "m" or not rows:
        cid = input("chat_id: ").strip()
        if cid.lstrip('-').isdigit():
            return int(cid)
        print(f"{Y}non-numeric chat_id accepted as @username by caller{N}")
        return cid  # type: ignore
    if sel.isdigit() and 1 <= int(sel) <= len(rows):
        return rows[int(sel) - 1][0]
    print(f"{R}invalid selection{N}")
    return None

def delete_message(bot: TelegramBot):
    print(f"\n{B}--- Delete Message(s) ---{N}")
    _conn = sqlite3.connect(DB_FILE); db_init(_conn)
    try:
        chat_id = _pick_chat_required(_conn)
    finally:
        _conn.close()
    if not chat_id:
        print(f"{Y}cancelled.{N}")
        return

    mode = (input("Delete [1] single message or [2] range of message_ids? [1/2]: ")
            .strip() or "1")

    # ======================== RANGE MODE ========================
    if mode == "2":
        start_raw = input("from message_id: ").strip()
        end_raw   = input("to   message_id: ").strip()
        if not (start_raw.isdigit() and end_raw.isdigit()):
            print(f"{R}both must be positive integers{N}")
            return
        start_id, end_id = int(start_raw), int(end_raw)
        if start_id > end_id:
            start_id, end_id = end_id, start_id
        total = end_id - start_id + 1
        if total > 5000:
            print(f"{Y}⚠ {total} messages — this will take a while and may hit rate limits{N}")
        if input(f"Confirm deleting {total} messages ({start_id}..{end_id}) in {chat_id}? "
                 f"[y/N]: ").strip().lower() != "y":
            print(f"{Y}cancelled.{N}")
            return
        try:
            delay = float(input("delay between deletes in seconds (default 0.05): ").strip()
                          or "0.05")
        except ValueError:
            delay = 0.05

        ok = skipped = fail = rate_waits = 0
        failed_ids: List[int] = []

        for mid in range(start_id, end_id + 1):
            r = bot.post("deleteMessage", data={
                "chat_id": chat_id, "message_id": str(mid),
            }, ask_retry=False)

            if r and r.get("ok"):
                ok += 1
                print(f"  {G}✔{N} {mid}")
                time.sleep(delay)
                continue

            desc = (r.get("description") if isinstance(r, dict) else "") or "no response"
            dl   = desc.lower()
            err  = r.get("error_code") if isinstance(r, dict) else None

            # honor flood-control
            if err == 429 or "too many requests" in dl:
                wait = 5
                if isinstance(r, dict):
                    wait = (r.get("parameters") or {}).get("retry_after", 5)
                print(f"  {Y}⚠ rate limited — waiting {wait}s{N}")
                rate_waits += 1
                time.sleep(wait)
                r = bot.post("deleteMessage", data={
                    "chat_id": chat_id, "message_id": str(mid),
                }, ask_retry=False)
                if r and r.get("ok"):
                    ok += 1
                    print(f"  {G}✔{N} {mid} (after wait)")
                    time.sleep(delay)
                    continue
                desc = (r.get("description") if isinstance(r, dict) else "") or "no response"
                dl   = desc.lower()

            # "message to delete not found" / "message can't be deleted" = normal, just skip
            if any(k in dl for k in (
                    "not found", "message to delete",
                    "can't be deleted", "message can't be deleted",
                    "message_id_invalid")):
                skipped += 1
                print(f"  {Y}∅{N} {mid} (skipped — not found / undeletable)")
            else:
                fail += 1
                failed_ids.append(mid)
                print(f"  {R}✘{N} {mid} → {desc}")
            time.sleep(delay)

        print(f"\n{G}{'=' * 44}{N}")
        print(f"{G}  DELETE SUMMARY{N}")
        print(f"{G}{'=' * 44}{N}")
        print(f"  Range       : {start_id}..{end_id}  ({total} msgs)")
        print(f"  Deleted     : {ok}")
        print(f"  Skipped     : {skipped}  (not found / undeletable)")
        print(f"  Failed      : {fail}")
        if rate_waits:
            print(f"  Rate limits : {rate_waits} wait(s)")
        if failed_ids:
            head = ", ".join(str(x) for x in failed_ids[:30])
            tail = " ..." if len(failed_ids) > 30 else ""
            print(f"  Failed IDs  : {head}{tail}")
        print(f"{G}{'=' * 44}{N}")
        return

    # ======================== SINGLE MODE ========================
    msg_id = input("message_id to delete: ").strip()
    if not msg_id:
        print(f"{R}message_id is required{N}")
        return
    if input(f"Confirm delete message {msg_id} in {chat_id}? [y/N]: "
             ).strip().lower() != "y":
        print(f"{Y}cancelled.{N}")
        return
    print(f"\n{Y}>> deleteMessage ...{N}")
    r = bot.post("deleteMessage", data={"chat_id": chat_id, "message_id": msg_id})
    if r and r.get("ok"):
        print(f"{G}✔ Deleted message {msg_id}{N}")
    else:
        desc = (r.get("description") if isinstance(r, dict) else "") or "no response"
        print(f"{R}✘ Failed to delete {msg_id}: {desc}{N}")
        if isinstance(r, dict):
            print(json.dumps(r, indent=2, ensure_ascii=False))


# ================================================================
#  Proxy / Network
# ================================================================
def configure_proxy_menu(bot: TelegramBot):
    global PROXY
    print(f"\n{B}--- Configure proxy / retry ---{N}")
    print(f"  Current proxy  : {PROXY or '(none)'}")
    print(f"  Ask on failure : "
          f"{'ON' if bot.ask_retry else 'OFF'}")
    print("  1) Set proxy")
    print("  2) Clear proxy")
    print("  3) Test current proxy (getMe)")
    print("  4) Toggle 'ask on failure' prompt")
    print("  0) Back")
    c = input("choice: ").strip()
    if c == "1":
        p = input("proxy url (e.g. socks5://127.0.0.1:10808): ").strip()
        if p:
            bot.set_proxy(p)
            set_config_proxy(p)
            print(f"{G}✔ Proxy set and saved to {CONFIG_FILE}{N}")
    elif c == "2":
        bot.set_proxy("")
        set_config_proxy("")
        print(f"{G}✔ Proxy cleared and saved to {CONFIG_FILE}{N}")
    elif c == "3":
        r = bot.post("getMe")
        show_info_result(r)
    elif c == "4":
        bot.ask_retry = not bot.ask_retry
        print(f"{G}Ask on failure → {'ON' if bot.ask_retry else 'OFF'}{N}")


# ================================================================
#  Chat management
# ================================================================
def leave_chat(bot: TelegramBot):
    print(f"\n{B}--- Leave Chat / Channel ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    ans = input(f"Confirm LEAVING {chat_id}? [y/N]: ").strip()
    if ans.lower() != "y":
        print(f"{Y}cancelled.{N}")
        return
    print(f"\n{Y}>> leaveChat ...{N}")
    show_send_result(bot.post("leaveChat", data={"chat_id": chat_id}))


def get_chat_info(bot: TelegramBot):
    print(f"\n{B}--- Get Chat Info ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    print(f"\n{Y}>> getChat ...{N}")
    show_info_result(bot.post("getChat", data={"chat_id": chat_id}))


def get_chat_member_count(bot: TelegramBot):
    print(f"\n{B}--- Get Chat Member Count ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    print(f"\n{Y}>> getChatMemberCount ...{N}")
    show_info_result(bot.post("getChatMemberCount", data={"chat_id": chat_id}))


def set_chat_title(bot: TelegramBot):
    print(f"\n{B}--- Set Chat Title ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    title = input("new title: ").strip()
    if not title:
        print(f"{R}title is required{N}")
        return
    print(f"\n{Y}>> setChatTitle ...{N}")
    show_send_result(bot.post("setChatTitle", data={"chat_id": chat_id, "title": title}))


def set_chat_description(bot: TelegramBot):
    print(f"\n{B}--- Set Chat Description ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    print("Note: leave empty to REMOVE the description.")
    desc = input("new description: ").strip()
    data = {"chat_id": chat_id}
    if desc:
        data["description"] = desc
    print(f"\n{Y}>> setChatDescription ...{N}")
    show_info_result(bot.post("setChatDescription", data=data))


def set_admin_custom_title(bot: TelegramBot):
    print(f"\n{B}--- Set Admin Custom Title ---{N}")
    print(f"{Y}Note:{N} The bot can only set a custom title for administrators it promoted.")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    user_id = input("user_id (empty = the bot itself): ").strip()
    if not user_id:
        bid = bot.get_bot_id()
        if not bid:
            print(f"{R}could not determine bot id{N}")
            return
        user_id = str(bid)
        print(f"bot user_id = {user_id}")
    print("custom_title must be 0-16 characters (empty = remove).")
    title = input("custom_title: ").strip()
    data = {"chat_id": chat_id, "user_id": user_id, "custom_title": title}
    print(f"\n{Y}>> setChatAdministratorCustomTitle ...{N}")
    show_send_result(bot.post("setChatAdministratorCustomTitle", data=data))


def get_chat_member_info(bot: TelegramBot):
    print(f"\n{B}--- Get Chat Member Info (getChatMember) ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    user_id = input("user_id: ").strip()
    if not user_id:
        print(f"{R}user_id is required{N}")
        return
    print(f"\n{Y}>> getChatMember ...{N}")
    show_info_result(bot.post("getChatMember", data={"chat_id": chat_id, "user_id": user_id}))


def _ask_permissions() -> dict:
    print("Permissions (y/N each):")
    perms = {}
    for label, key in (
        ("can_change_info", "can_change_info"),
        ("can_post_messages", "can_post_messages"),
        ("can_edit_messages", "can_edit_messages"),
        ("can_delete_messages", "can_delete_messages"),
        ("can_invite_users", "can_invite_users"),
        ("can_restrict_members", "can_restrict_members"),
        ("can_pin_messages", "can_pin_messages"),
        ("can_promote_members", "can_promote_members"),
        ("can_manage_video_chats", "can_manage_video_chats"),
        ("can_manage_chat", "can_manage_chat"),
        ("can_manage_topics", "can_manage_topics"),
        ("can_post_stories", "can_post_stories"),
        ("can_edit_stories", "can_edit_stories"),
        ("can_delete_stories", "can_delete_stories"),
        ("is_anonymous", "is_anonymous"),
    ):
        ans = input(f"{label}? [y/N]: ").strip()
        if ans.lower() == "y":
            perms[key] = True
        else:
            perms[key] = False
    return perms


def promote_member(bot: TelegramBot):
    print(f"\n{B}--- Promote Member to Admin (promoteChatMember) ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    user_id = input("user_id: ").strip()
    if not user_id:
        print(f"{R}user_id is required{N}")
        return
    data = {"chat_id": chat_id, "user_id": user_id}
    ans = input("Grant ALL admin permissions? [Y/n]: ").strip()
    if ans.lower() != "n":
        data.update({
            "can_change_info": True, "can_post_messages": True,
            "can_edit_messages": True, "can_delete_messages": True,
            "can_invite_users": True, "can_restrict_members": True,
            "can_pin_messages": True, "can_promote_members": True,
            "can_manage_video_chats": True, "can_manage_chat": True,
            "can_manage_topics": True, "can_post_stories": True,
            "can_edit_stories": True, "can_delete_stories": True,
            "is_anonymous": False,
        })
    else:
        data.update(_ask_permissions())
    print(f"\n{Y}>> promoteChatMember ...{N}")
    show_send_result(bot.post("promoteChatMember", data=data))


def demote_member(bot: TelegramBot):
    print(f"\n{B}--- Demote Member (remove admin) ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    user_id = input("user_id: ").strip()
    if not user_id:
        print(f"{R}user_id is required{N}")
        return
    data = {
        "chat_id": chat_id, "user_id": user_id,
        "can_change_info": False, "can_post_messages": False,
        "can_edit_messages": False, "can_delete_messages": False,
        "can_invite_users": False, "can_restrict_members": False,
        "can_pin_messages": False, "can_promote_members": False,
        "can_manage_video_chats": False, "can_manage_chat": False,
        "can_manage_topics": False, "can_post_stories": False,
        "can_edit_stories": False, "can_delete_stories": False,
    }
    print(f"\n{Y}>> promoteChatMember (revoke) ...{N}")
    show_send_result(bot.post("promoteChatMember", data=data))


def set_user_custom_title(bot: TelegramBot):
    print(f"\n{B}--- Set User Custom Title (admin tag) ---{N}")
    print(f"{Y}Note:{N} The bot can only set a custom title for administrators it promoted.")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    user_id = input("user_id: ").strip()
    if not user_id:
        print(f"{R}user_id is required{N}")
        return
    print("custom_title must be 0-16 characters (empty = remove).")
    title = input("custom_title: ").strip()
    data = {"chat_id": chat_id, "user_id": user_id, "custom_title": title}
    print(f"\n{Y}>> setChatAdministratorCustomTitle ...{N}")
    show_send_result(bot.post("setChatAdministratorCustomTitle", data=data))

def set_chat_member_tag(bot: TelegramBot):
    print(f"\n{B}--- Set Chat Member Tag ---{N}")
    print(f"{Y}Note:{N} Available since Bot API 9.0. The bot must be admin in the chat.")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    user_id = input("user_id (empty = the bot itself): ").strip()
    if not user_id:
        bid = bot.get_bot_id()
        if not bid:
            print(f"{R}✘ Could not determine bot id (getMe failed){N}")
            return
        user_id = str(bid)
        print(f"{Y}bot user_id = {user_id}{N}")
    print("tag: 0-16 characters (empty = remove tag).")
    tag = input("tag: ").strip()
    data = {"chat_id": chat_id, "user_id": user_id, "tag": tag}
    print(f"\n{Y}>> setChatMemberTag ...{N}")
    show_info_result(bot.post("setChatMemberTag", data=data))

def silent_fetch(bot: TelegramBot):
    print(f"\n{G}{'=' * 55}{N}")
    print(f"{G}  SILENT FETCH – getUpdates recorder (no output){N}")
    print(f"{G}{'=' * 55}{N}")
    print(f"{Y}All updates are stored silently into {DB_FILE}.{N}")
    print(f"{Y}Press Ctrl+C to stop and see the summary.{N}\n")

    conn = sqlite3.connect(DB_FILE)
    db_init(conn)
    offset = int(db_state_get(conn, 'offset', '0') or '0')

    bot_id = bot.bot_id or 0
    bot_username = ""
    _me = bot.post("getMe", ask_retry=False)
    if _me and _me.get("ok"):
        bot_id = _me["result"].get("id") or bot_id
        bot_username = _me["result"].get("username", "") or ""

    n_updates = 0
    n_messages = 0
    n_files = 0
    n_edits = 0
    mention_hits: List[dict] = []
    started = time.time()

    try:
        while True:
            resp = bot.get(
                "getUpdates",
                params={"offset": offset, "limit": 100, "timeout": 30,
                             "allowed_updates": ["message", "edited_message", "channel_post",
                                                 "edited_channel_post", "message_reaction",
                                                 "message_reaction_count", "managed_bot"]},
                ask_retry=False,
            )
            if not resp or not resp.get("ok"):
                time.sleep(5)
                continue
            updates = resp.get("result", [])
            if not updates:
                continue
            for upd in updates:
                uid = upd.get("update_id", 0)
                offset = uid + 1
                n_updates += 1

                if "message_reaction" in upd:
                    _handle_reaction_update(conn, upd["message_reaction"])
                    db_store_update(conn, uid, "message_reaction", upd)
                    db_state_set(conn, "offset", offset)
                    continue

                if "message_reaction_count" in upd:
                    _handle_reaction_count_update(conn, upd["message_reaction_count"])
                    db_store_update(conn, uid, "message_reaction_count", upd)
                    db_state_set(conn, "offset", offset)
                    continue

                kind = None
                obj = None
                for k in ("message", "edited_message",
                          "channel_post", "edited_channel_post",
                          "managed_bot"):
                    if k in upd:
                        kind, obj = k, upd[k]
                        break

                if obj is None:
                    db_store_update(conn, uid, 'non-message', upd)
                    db_state_set(conn, 'offset', offset)
                    continue

                if kind == "managed_bot":
                    mb = obj
                    db_store_update(conn, uid, "managed_bot", upd)
                    db_state_set(conn, 'offset', offset)
                    print(f"\n{G}📢 New managed bot created!{N}")
                    print(f"  Bot ID   : {mb.get('bot_id')}")
                    print(f"  Username : @{mb.get('username')}")
                    print(f"  Name     : {mb.get('name')}")
                    print(f"  Owner ID : {mb.get('user_id')}")
                    tok_resp = bot.get_managed_bot_token(mb.get('user_id'))
                    if tok_resp and tok_resp.get("ok"):
                        new_token = tok_resp.get("result")
                        print(f"{G}✔ Token received: {new_token}{N}")
                        try:
                            conn.execute(
                                "INSERT OR REPLACE INTO managed_bots "
                                "(bot_id, username, first_name, token, added_at, "
                                " last_seen_at, updated_at) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (mb.get('bot_id'), mb.get('username'), mb.get('name'),
                                 new_token, db_utcnow(), db_utcnow(), db_utcnow()))
                            conn.commit()
                        except Exception as e:
                            print(f"{Y}⚠ Could not save to managed_bots: {e}{N}")
                    else:
                        print(f"{R}✘ Could not fetch token{N}")
                    continue

                db_store_update(conn, uid, kind, upd)
                descr = db_process_message(conn, uid, kind, obj)
                _record_mention_if_needed(conn, descr, bot)
                db_state_set(conn, 'offset', offset)
                if descr:
                    n_messages += 1
                    n_files += len(descr.get('files') or [])
                    if descr.get('is_edit'):
                        n_edits += 1
                    replied_to_bot = False
                    if descr.get('reply_to_message_id'):
                        try:
                            replied_to_bot = _check_reply_to_bot(
                                conn, descr['chat_id'], descr['message_id'], bot_id)
                        except Exception:
                            replied_to_bot = False
                    if (bot_id and _check_mentioned(descr, bot_id, bot_username)) or replied_to_bot:
                        mention_hits.append({
                            'chat_id': descr['chat_id'],
                            'chat_title': descr.get('chat_title') or str(descr['chat_id']),
                            'message_id': descr['message_id'],
                            'text': (descr.get('text') or descr.get('caption') or '')[:200],
                            'replied': replied_to_bot,
                        })
    except KeyboardInterrupt:
        print(f"\n{Y}⏹  Stopping...{N}")

    elapsed = int(time.time() - started)
    h, rem = divmod(elapsed, 3600)
    m, s = divmod(rem, 60)
    print(f"\n{G}{'=' * 55}{N}")
    print(f"{G}  FETCH SUMMARY{N}")
    print(f"{G}{'=' * 55}{N}")
    print(f"  Duration       : {h:02d}:{m:02d}:{s:02d}")
    print(f"  Updates seen   : {n_updates}")
    print(f"  Messages saved : {n_messages}")
    print(f"  Edits detected : {n_edits}")
    print(f"  Files captured : {n_files}")
    print(f"  New offset     : {offset}")
    print(f"  Saved to       : {DB_FILE}")
    print(f"  Mentions/replies to you: {len(mention_hits)}")
    print(f"{G}{'=' * 55}{N}")

    if mention_hits:
        print(f"\n{G}📢 You were mentioned or replied to in {len(mention_hits)} message(s).{N}")
        for i, m in enumerate(mention_hits, 1):
            tag = "REPLY" if m['replied'] else "MENTION"
            print(f"  {i:>3}) [{tag}] {m['chat_title']}  #{m['message_id']}  "
                  f"{(m['text'] or '').replace(chr(10), ' ')[:80]}")
        if input("\nView and reply to these now? [y/N]: ").strip().lower() == "y":
            for m in mention_hits:
                _show_msg_full(conn, m['chat_id'], m['message_id'], show_raw=False)
                rt = input("Reply text (empty = skip): ").strip()
                if rt:
                    r = bot.post("sendMessage", data={
                        "chat_id": str(m['chat_id']),
                        "text": rt,
                        "reply_to_message_id": str(m['message_id']),
                    }, ask_retry=False)
                    print(f"{G}✔ Sent{N}" if r and r.get('ok') else f"{R}✘ Failed{N}")
    conn.close()

def _fmt_ts(ts: Optional[int]) -> str:
    if not ts:
        return "?"
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)

def _pick_chat_for_monitor(conn) -> Optional[int]:
    """Show chats in DB, let user pick one.
       Returns chat_id to watch, or None = watch ALL chats."""
    rows = conn.execute(
        """SELECT m.chat_id, COUNT(*) cnt, MAX(m.date) last_date,
                  e.title, e.first_name, e.last_name, e.username, e.kind
             FROM messages m
             LEFT JOIN entities e ON e.id = m.chat_id
            GROUP BY m.chat_id
            ORDER BY last_date DESC""").fetchall()

    print(f"\n{B}--- Chats known in DB ---{N}")
    if not rows:
        print(f"{Y}No chats in DB yet. Live mode will show ALL incoming messages.{N}")
        return None

    for i, r in enumerate(rows, 1):
        cid, cnt, last_date, title, fn, ln, un, kind = r
        label = title or (fn and f"{fn} {ln or ''}".strip()) or str(cid)
        uname = f" @{un}" if un else ""
        print(f"  {i:>3}) {label:<28} [{kind or '?':<8}] "
              f"id={cid}  msgs={cnt}  last={_fmt_ts(last_date)}{uname}")

    print(f"    0) All chats (no filter)")
    print(f"    m) Manual chat_id")

    sel = input("\nSelect chat: ").strip().lower()
    if sel in ("", "0"):
        return None
    if sel == "m":
        cid = input("chat_id: ").strip()
        try:
            return int(cid)
        except ValueError:
            print(f"{R}invalid id{N}")
            return None
    try:
        idx = int(sel) - 1
        if 0 <= idx < len(rows):
            return rows[idx][0]
    except ValueError:
        pass
    print(f"{R}invalid selection → defaulting to ALL chats{N}")
    return None

def _show_reply_context(conn, chat_id: int, message_id: int,
                        bot_id: Optional[int]) -> bool:
    """Print the replied-to message (from raw_json). Return True if it was the bot's."""
    row = conn.execute(
        "SELECT raw_json FROM messages WHERE chat_id = ? AND message_id = ?",
        (chat_id, message_id)).fetchone()
    if not row or not row[0]:
        return False
    try:
        payload = json.loads(row[0])
    except Exception:
        return False
    rtm = (payload.get("message") or {}).get("reply_to_message")
    if not rtm:
        return False

    r_id = rtm.get("message_id", "?")
    r_from = rtm.get("from") or {}
    r_sender = rtm.get("sender_chat") or {}
    r_text = rtm.get("text") or rtm.get("caption") or ""
    r_type = db_describe_content(rtm)

    is_from_bot = False
    r_name = "?"
    if r_from:
        r_name = " ".join(
            p for p in [r_from.get("first_name"), r_from.get("last_name")] if p
        ).strip() or "?"
        if r_from.get("username"):
            r_name += f" (@{r_from['username']})"
        if bot_id and r_from.get("id") == bot_id:
            is_from_bot = True
    elif r_sender:
        r_name = r_sender.get("title") or "?"
        if bot_id and r_sender.get("id") == bot_id:
            is_from_bot = True

    print(f"  {M}↩ Reply to #{r_id}{N}")
    if is_from_bot:
        print(f"    From : {G}🤖 {r_name} — YOUR OWN MESSAGE{N}")
    else:
        print(f"    From : {r_name}  (id={r_from.get('id') or r_sender.get('id') or '?'})")
    print(f"    Type : {r_type}")
    if r_text:
        snippet = r_text.replace("\n", " ")
        if len(snippet) > 200:
            snippet = snippet[:200] + "…"
        print(f"    Text : {snippet}")
    return is_from_bot

def _check_reply_to_bot(conn, chat_id: int, message_id: int,
                        bot_id: Optional[int]) -> bool:
    """Silent version of _show_reply_context — returns True if replied msg is the bot's."""
    if not bot_id:
        return False
    row = conn.execute(
        "SELECT raw_json FROM messages WHERE chat_id = ? AND message_id = ?",
        (chat_id, message_id)).fetchone()
    if not row or not row[0]:
        return False
    try:
        payload = json.loads(row[0])
    except Exception:
        return False
    rtm = (payload.get("message") or {}).get("reply_to_message")
    if not rtm:
        return False
    r_from = rtm.get("from") or {}
    r_sender = rtm.get("sender_chat") or {}
    if r_from.get("id") == bot_id:
        return True
    if r_sender.get("id") == bot_id:
        return True
    return False

def _show_msg_full(conn, chat_id: int, message_id: int, show_raw: bool = False):
    row = conn.execute(
        """SELECT m.message_id, m.date, m.from_user_id, m.sender_chat_id,
                  m.content_type, m.text, m.caption, m.reply_to_message_id,
                  m.is_edited, m.edit_count, m.raw_json,
                  e.first_name, e.last_name, e.username, e.is_bot
             FROM messages m
             LEFT JOIN entities e ON e.id = m.from_user_id
            WHERE m.chat_id = ? AND m.message_id = ?""",
        (chat_id, message_id)).fetchone()
    if not row:
        print(f"{R}✘ message {message_id} not found in chat {chat_id}{N}")
        return
    (mid, date, from_id, sender_chat_id, ctype, text, caption, reply_id,
     is_edited, edit_count, raw_json,
     fn, ln, un, is_bot) = row

    name = " ".join(p for p in [fn, ln] if p).strip() or "?"
    print(f"\n{M}┌─ message_id = {mid}  (chat_id = {chat_id}) ─────{N}")
    print(f"  Date       : {_fmt_ts(date)}  (unix={date})")
    print(f"  Type       : {ctype}")
    if sender_chat_id:
        print(f"  Sender chat: {sender_chat_id}")
    else:
        uname = f" (@{un})" if un else ""
        flag = f" {Y}[bot]{N}" if is_bot else ""
        print(f"  From       : {name}{uname}{flag}  (id = {from_id})")
    if reply_id:
        print(f"  Reply to   : {reply_id}")
    if is_edited:
        print(f"  {Y}Edited     : yes (count={edit_count}){N}")
    if text:
        print(f"  Text       : {text}")
    if caption:
        print(f"  Caption    : {caption}")

    files = conn.execute(
        """SELECT file_type, file_id, file_unique_id, file_name, mime_type,
                  file_size, width, height, duration, performer, title,
                  emoji, set_name, thumbnail_file_id
             FROM message_files
            WHERE chat_id = ? AND message_id = ?""",
        (chat_id, mid)).fetchall()
    if files:
        print(f"  {M}Files ({len(files)}):{N}")
        for (ftype, fid, fuid, fname, mime, fsize, w, h, dur,
             performer, ftitle, emoji, setname, thumb) in files:
            print(f"    {M}▸ {ftype}{N}")
            print(f"       file_id        : {fid}")
            print(f"       file_unique_id : {fuid}")
            if fname:      print(f"       name           : {fname}")
            if mime:       print(f"       mime           : {mime}")
            if fsize is not None: print(f"       size           : {fsize}B")
            if w and h:    print(f"       dims           : {w}x{h}")
            if dur:        print(f"       duration       : {dur}s")
            if performer:  print(f"       performer      : {performer}")
            if ftitle:     print(f"       title          : {ftitle}")
            if emoji:      print(f"       emoji          : {emoji}")
            if setname:    print(f"       set            : {setname}")
            if thumb:      print(f"       thumbnail_id   : {thumb}")

    if show_raw and raw_json:
        print(f"  {Y}Raw JSON   :{N}")
        try:
            print(json.dumps(json.loads(raw_json), indent=2, ensure_ascii=False))
        except Exception:
            print(raw_json)
    print(f"{M}└───────────────────────────────────────────────{N}")

def chat_explorer(bot: TelegramBot):
    conn = sqlite3.connect(DB_FILE)
    db_init(conn)

    try:
        while True:
            # --- Step 1: list chats ---
            rows = conn.execute(
                """SELECT m.chat_id,
                          COUNT(*)    AS msg_count,
                          MAX(m.date) AS last_date,
                          e.title, e.first_name, e.last_name, e.username, e.kind
                     FROM messages m
                     LEFT JOIN entities e ON e.id = m.chat_id
                    GROUP BY m.chat_id
                    ORDER BY last_date DESC""").fetchall()
            if not rows:
                print(f"{R}✘ No chats in DB. Run Monitor or Silent Fetch first.{N}")
                return

            print(f"\n{B}--- Chats in DB ({len(rows)}) ---{N}")
            for i, r in enumerate(rows, 1):
                cid, cnt, last_date, title, fn, ln, un, kind = r
                label = title or (fn and f"{fn} {ln or ''}".strip()) or str(cid)
                uname = f" @{un}" if un else ""
                print(f"  {i:>3}) {label:<28} [{kind or '?':<8}] "
                      f"id={cid}  msgs={cnt}  last={_fmt_ts(last_date)}{uname}")
            sel = input("\nSelect chat # (empty=back): ").strip()
            if not sel:
                return
            try:
                idx = int(sel) - 1
                if idx < 0 or idx >= len(rows):
                    print(f"{R}invalid index{N}"); continue
            except ValueError:
                print(f"{R}invalid{N}"); continue
            chat_id = rows[idx][0]

            # --- Step 2: filters ---
            while True:
                print(f"\n{B}--- Chat {chat_id} – choose filter ---{N}")
                print("  1) Last N messages")
                print("  2) By message_id")
                print("  3) By sender (user_id or @username)")
                print("  4) By media/content type")
                print("  5) Search keyword in text/caption")
                print("  6) By date range")
                print("  7) List senders in chat")
                print("  8) List all files in chat")
                print("  9) Quick full dump (all messages)")
                print("  0) Back to chat list")
                opt = input("filter: ").strip()

                if opt == "0":
                    break

                msg_ids = []

                if opt == "1":
                    n = input("how many (default 20): ").strip() or "20"
                    try: n = int(n)
                    except ValueError: n = 20
                    msg_ids = [r[0] for r in conn.execute(
                        "SELECT message_id FROM messages WHERE chat_id = ? "
                        "ORDER BY date DESC LIMIT ?", (chat_id, n)).fetchall()]

                elif opt == "2":
                    mid = input("message_id: ").strip()
                    if mid.lstrip('-').isdigit():
                        msg_ids = [int(mid)]

                elif opt == "3":
                    who = input("sender user_id or @username: ").strip().lstrip('@')
                    if who.isdigit():
                        msg_ids = [r[0] for r in conn.execute(
                            "SELECT message_id FROM messages WHERE chat_id = ? "
                            "AND from_user_id = ? ORDER BY date DESC",
                            (chat_id, int(who))).fetchall()]
                    elif who:
                        msg_ids = [r[0] for r in conn.execute(
                            "SELECT m.message_id FROM messages m "
                            "JOIN entities e ON e.id = m.from_user_id "
                            "WHERE m.chat_id = ? AND e.username = ? "
                            "ORDER BY m.date DESC",
                            (chat_id, who)).fetchall()]

                elif opt == "4":
                    print("examples: text, photo, video, document, audio, voice,")
                    print("          video_note, sticker, animation, location,")
                    print("          contact, poll, dice, new_chat_members, ...")
                    t = input("type: ").strip()
                    if t:
                        msg_ids = [r[0] for r in conn.execute(
                            "SELECT message_id FROM messages WHERE chat_id = ? "
                            "AND content_type = ? ORDER BY date DESC",
                            (chat_id, t)).fetchall()]

                elif opt == "5":
                    kw = input("keyword: ").strip()
                    if kw:
                        like = f"%{kw}%"
                        msg_ids = [r[0] for r in conn.execute(
                            "SELECT message_id FROM messages WHERE chat_id = ? "
                            "AND (text LIKE ? OR caption LIKE ?) ORDER BY date DESC",
                            (chat_id, like, like)).fetchall()]

                elif opt == "6":
                    a = input("from (unix ts or yyyy-mm-dd, empty=-inf): ").strip()
                    b = input("to   (unix ts or yyyy-mm-dd, empty=+inf): ").strip()
                    def _parse(s):
                        if not s: return None
                        try: return int(s)
                        except ValueError:
                            try:
                                return int(datetime.strptime(s, "%Y-%m-%d")
                                           .replace(tzinfo=timezone.utc).timestamp())
                            except Exception:
                                return None
                    a_ts, b_ts = _parse(a), _parse(b)
                    q = "SELECT message_id FROM messages WHERE chat_id = ?"
                    p = [chat_id]
                    if a_ts is not None: q += " AND date >= ?"; p.append(a_ts)
                    if b_ts is not None: q += " AND date <= ?"; p.append(b_ts)
                    q += " ORDER BY date DESC"
                    msg_ids = [r[0] for r in conn.execute(q, p).fetchall()]

                elif opt == "7":
                    rows2 = conn.execute(
                        """SELECT m.from_user_id, COUNT(*) cnt,
                                  e.first_name, e.last_name, e.username, e.is_bot
                             FROM messages m
                             LEFT JOIN entities e ON e.id = m.from_user_id
                            WHERE m.chat_id = ? AND m.from_user_id IS NOT NULL
                            GROUP BY m.from_user_id
                            ORDER BY cnt DESC""", (chat_id,)).fetchall()
                    print(f"\n{B}Senders in chat {chat_id}:{N}")
                    for fid, cnt, fn, ln, un, isb in rows2:
                        nm = " ".join(p for p in [fn, ln] if p).strip() or "?"
                        uname = f"@{un}" if un else ""
                        bf = " [bot]" if isb else ""
                        print(f"  id={fid:<14} msgs={cnt:<6} {nm} {uname}{bf}")
                    continue

                elif opt == "8":
                    rows2 = conn.execute(
                        """SELECT file_type, COUNT(*), COALESCE(SUM(file_size),0)
                             FROM message_files WHERE chat_id = ?
                            GROUP BY file_type ORDER BY 2 DESC""",
                        (chat_id,)).fetchall()
                    print(f"\n{B}Files in chat {chat_id}:{N}")
                    for ft, cnt, tot in rows2:
                        print(f"  {ft:<12} count={cnt:<6} total={tot}B")
                    if input("Show all file_ids? [y/N]: ").strip().lower() == "y":
                        rows2 = conn.execute(
                            """SELECT message_id, file_type, file_id, file_unique_id,
                                      file_name, file_size
                                 FROM message_files WHERE chat_id = ?
                                ORDER BY message_id""", (chat_id,)).fetchall()
                        for mid, ft, fid, fuid, fname, fsz in rows2:
                            extra = f" name={fname}" if fname else ""
                            sz = f" size={fsz}B" if fsz is not None else ""
                            print(f"  msg={mid:<6} {ft:<12} {fid}{sz}{extra}")
                    continue

                elif opt == "9":
                    rows2 = conn.execute(
                        """SELECT message_id, date, from_user_id, content_type,
                                  text, caption
                             FROM messages WHERE chat_id = ?
                            ORDER BY date""", (chat_id,)).fetchall()
                    for mid, dt, fuid, ctype, text, cap in rows2:
                        snip = (text or cap or "").replace("\n", " ")[:70]
                        print(f"  #{mid:<6} {_fmt_ts(dt)}  u={fuid}  "
                              f"{ctype:<12}  {snip}")
                    continue

                else:
                    print(f"{R}invalid{N}")
                    continue

                if not msg_ids:
                    print(f"{Y}No messages matched.{N}")
                    continue

                print(f"\n{G}{len(msg_ids)} message(s) matched.{N}")
                show_raw = input("Show raw JSON too? [y/N]: ").strip().lower() == "y"
                for mid in msg_ids:
                    _show_msg_full(conn, chat_id, mid, show_raw=show_raw)

                if input(f"\nExport to JSON file? [y/N]: ").strip().lower() == "y":
                    fname = f"export_{abs(chat_id)}_{int(time.time())}.json"
                    out = []
                    for mid in msg_ids:
                        row = conn.execute(
                            "SELECT raw_json FROM messages WHERE chat_id = ? "
                            "AND message_id = ?", (chat_id, mid)).fetchone()
                        if row and row[0]:
                            try: out.append(json.loads(row[0]))
                            except Exception: pass
                    with open(fname, "w", encoding="utf-8") as f:
                        json.dump(out, f, indent=2, ensure_ascii=False)
                    print(f"{G}✔ Saved {len(out)} message(s) to {fname}{N}")

    finally:
        conn.close()

def create_invite_link(bot: TelegramBot):
    print(f"\n{B}--- Create Chat Invite Link ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    name = input("name (empty = skip): ").strip()
    exp = input("expire_date (unix ts, empty = skip): ").strip()
    lim = input("member_limit (empty = skip): ").strip()
    ans = input("creates_join_request? [y/N]: ").strip()
    data = {"chat_id": chat_id}
    if name:
        data["name"] = name
    if exp:
        data["expire_date"] = exp
    if lim:
        data["member_limit"] = lim
    if ans.lower() == "y":
        data["creates_join_request"] = "true"
    print(f"\n{Y}>> createChatInviteLink ...{N}")
    result = bot.post("createChatInviteLink", data=data)
    if result and result.get("ok"):
        link = result["result"].get("invite_link", "")
        print(f"{G}✔ Invite link created{N}")
        if link:
            print(f"{G}🔗 {link}{N}")
        print(f"\n{B}Full result:{N}")
        print(json.dumps(result["result"], indent=2, ensure_ascii=False))
    else:
        show_info_result(result)


def pin_message(bot: TelegramBot):
    print(f"\n{B}--- Pin Message ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    msg_id = input("message_id: ").strip()
    if not msg_id:
        print(f"{R}message_id is required{N}")
        return
    ans = input("disable_notification? [y/N]: ").strip()
    data = {"chat_id": chat_id, "message_id": msg_id}
    if ans.lower() == "y":
        data["disable_notification"] = "true"
    print(f"\n{Y}>> pinChatMessage ...{N}")
    show_send_result(bot.post("pinChatMessage", data=data))


def unpin_message(bot: TelegramBot):
    print(f"\n{B}--- Unpin Message ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    msg_id = input("message_id (empty = unpin all): ").strip()
    data = {"chat_id": chat_id}
    if msg_id:
        data["message_id"] = msg_id
    print(f"\n{Y}>> unpinChatMessage ...{N}")
    show_send_result(bot.post("unpinChatMessage", data=data))


def forward_message(bot: TelegramBot):
    print(f"\n{B}--- Forward Message ---{N}")
    from_chat = input("from_chat_id: ").strip()
    if not from_chat:
        print(f"{R}from_chat_id is required{N}")
        return
    to_chat = input("to chat_id: ").strip()
    if not to_chat:
        print(f"{R}chat_id is required{N}")
        return
    msg_id = input("message_id: ").strip()
    if not msg_id:
        print(f"{R}message_id is required{N}")
        return
    ans = input("disable_notification? [y/N]: ").strip()
    data = {"chat_id": to_chat, "from_chat_id": from_chat, "message_id": msg_id}
    if ans.lower() == "y":
        data["disable_notification"] = "true"
    print(f"\n{Y}>> forwardMessage ...{N}")
    show_send_result(bot.post("forwardMessage", data=data))


def send_chat_action_cmd(bot: TelegramBot):
    print(f"\n{B}--- Send Chat Action ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    print("Actions: typing, upload_photo, record_video, upload_video,")
    print("         record_voice, upload_voice, upload_document,")
    print("         choose_sticker, find_location, record_video_note, upload_video_note")
    action = input("action (empty = typing): ").strip() or "typing"
    print(f"\n{Y}>> sendChatAction ...{N}")
    show_send_result(bot.post("sendChatAction", data={"chat_id": chat_id, "action": action}))


def ban_user(bot: TelegramBot):
    print(f"\n{B}--- Ban User ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    user_id = input("user_id: ").strip()
    if not user_id:
        print(f"{R}user_id is required{N}")
        return
    ans = input("revoke_messages? [y/N]: ").strip()
    ud = input("until_date (unix ts, 0 = forever): ").strip()
    data = {"chat_id": chat_id, "user_id": user_id}
    if ans.lower() == "y":
        data["revoke_messages"] = "true"
    if ud:
        data["until_date"] = ud
    print(f"\n{Y}>> banChatMember ...{N}")
    show_send_result(bot.post("banChatMember", data=data))


def unban_user(bot: TelegramBot):
    print(f"\n{B}--- Unban User ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    user_id = input("user_id: ").strip()
    if not user_id:
        print(f"{R}user_id is required{N}")
        return
    ans = input("only_if_banned? [y/N]: ").strip()
    data = {"chat_id": chat_id, "user_id": user_id}
    if ans.lower() == "y":
        data["only_if_banned"] = "true"
    print(f"\n{Y}>> unbanChatMember ...{N}")
    show_send_result(bot.post("unbanChatMember", data=data))


# ================================================================
#  Bot info
# ================================================================
def show_bot_info(bot: TelegramBot):
    print(f"\n{B}--- Bot Info (getMe) ---{N}")
    if PROXY:
        print(f"{Y}using proxy:{N} {PROXY}")
    print(f"\n{Y}>> getMe ...{N}")
    resp = bot.post("getMe")
    if resp and resp.get("ok"):
        print(f"{G}✔ Bot info:{N}")
        print(json.dumps(resp["result"], indent=2, ensure_ascii=False))
    else:
        show_info_result(resp)


# ================================================================
#  Bot profile / bio
# ================================================================
def set_bot_global_name(bot: TelegramBot):
    print(f"\n{B}--- Set Bot Global Name (setMyName) ---{N}")
    name = read_text_or_file("new name")
    if not name:
        print(f"{R}name is required{N}")
        return
    lang = input("language_code (e.g. fa, en; empty = default): ").strip()
    data = {"name": name}
    if lang:
        data["language_code"] = lang
    print(f"\n{Y}>> setMyName ...{N}")
    show_send_result(bot.post("setMyName", data=data))


def set_bot_username_cmd():
    print(f"\n{B}--- Set Bot Username ---{N}")
    print(f"{Y}Note:{N} Bots cannot change their own @username via API. Use @BotFather.")


def set_bot_description(bot: TelegramBot):
    print(f"\n{B}--- Set Bot Description / Bio (setMyDescription) ---{N}")
    print("This is the description shown to users in the chat with the bot.")
    print(f"{Y}Tip:{N} leave empty to REMOVE the description.")
    desc = read_text_or_file("description")
    lang = input("language_code (e.g. fa, en; empty = default): ").strip()
    data = {"description": desc}
    if lang:
        data["language_code"] = lang
    print(f"\n{Y}>> setMyDescription ...{N}")
    show_send_result(bot.post("setMyDescription", data=data))


def set_bot_short_description(bot: TelegramBot):
    print(f"\n{B}--- Set Bot Short Description (setMyShortDescription) ---{N}")
    print("Shown on the bot's profile page and shared chats.")
    print(f"{Y}Tip:{N} leave empty to REMOVE.")
    desc = read_text_or_file("short description")
    lang = input("language_code (e.g. fa, en; empty = default): ").strip()
    data = {"short_description": desc}
    if lang:
        data["language_code"] = lang
    print(f"\n{Y}>> setMyShortDescription ...{N}")
    show_send_result(bot.post("setMyShortDescription", data=data))


def set_profile_photo(bot: TelegramBot):
    print(f"\n{B}--- Set Bot Profile Photo (setMyProfilePhoto) ---{N}")
    print(" 1) Static photo  (jpg/png, recommended 512x512)")
    print(" 2) Animated      (mp4 animated profile)")
    ptype = input("choice [1/2] (default 1): ").strip() or "1"
    photo = input("photo input (file path / URL / file_id): ").strip()
    if not photo:
        print(f"{R}photo is required{N}")
        return
    if ptype == "2":
        photo_json = json.dumps({"type": "animated", "animation": "attach://profile_photo"})
    else:
        photo_json = json.dumps({"type": "static", "photo": "attach://profile_photo"})
    files = None
    if os.path.isfile(photo):
        mime = guess_mime(photo)
        files = {"profile_photo": (os.path.basename(photo), open(photo, "rb"), mime)}
    else:
        if ptype == "2":
            photo_json = json.dumps({"type": "animated", "animation": photo})
        else:
            photo_json = json.dumps({"type": "static", "photo": photo})
    data = {"photo": photo_json}
    print(f"\n{Y}>> setMyProfilePhoto ...{N}")
    result = bot.post("setMyProfilePhoto", data=data, files=files)
    if result and result.get("ok"):
        print(f"{G}✔ Profile photo updated{N}")
    else:
        print(f"{R}✘ Failed (requires Bot API 9.2+):{N}")
        show_info_result(result)

def get_bot_profile(bot: TelegramBot):
    """Fetch the bot's current profile: name, description,
       short description, and profile photos."""
    print(f"\n{B}--- Bot Profile ---{N}")

    # 1) basic identity
    print(f"\n{Y}>> getMe ...{N}")
    me = bot.post("getMe")
    if not me or not me.get("ok"):
        show_info_result(me)
        return
    bot_user = me["result"]
    bot_id = bot_user["id"]
    print(f"{G}✔ getMe:{N}")
    print(json.dumps(bot_user, indent=2, ensure_ascii=False))

    # 2) name (Bot API 9.0+)
    print(f"\n{Y}>> getMyName ...{N}")
    r = bot.post("getMyName")
    if r and r.get("ok"):
        print(json.dumps(r["result"], indent=2, ensure_ascii=False))
    else:
        print(f"{Y}⚠ getMyName not available (needs Bot API 9.0+){N}")

    # 3) description / bio
    print(f"\n{Y}>> getMyDescription ...{N}")
    r = bot.post("getMyDescription")
    if r and r.get("ok"):
        print(json.dumps(r["result"], indent=2, ensure_ascii=False))
    else:
        print(f"{Y}⚠ getMyDescription not available{N}")

    # 4) short description
    print(f"\n{Y}>> getMyShortDescription ...{N}")
    r = bot.post("getMyShortDescription")
    if r and r.get("ok"):
        print(json.dumps(r["result"], indent=2, ensure_ascii=False))
    else:
        print(f"{Y}⚠ getMyShortDescription not available{N}")

    # 5) profile photos (uses the bot's own user_id)
    print(f"\n{Y}>> getUserProfilePhotos (self) ...{N}")
    r = bot.post("getUserProfilePhotos", data={"user_id": str(bot_id), "limit": "1"})
    if r and r.get("ok"):
        photos = r["result"].get("photos") or []
        if not photos:
            print(f"{Y}No profile photo set.{N}")
        else:
            # show only the largest size of the latest photo
            largest = max(photos[0], key=lambda p: p.get("file_size", 0))
            print(f"{G}✔ Current profile photo:{N}")
            print(json.dumps(largest, indent=2, ensure_ascii=False))
            print(f"{Y}Tip:{N} use menu 37 (Download by id) to download "
                  f"file_id = {largest.get('file_id')}")
    else:
        show_info_result(r)

def remove_profile_photo(bot: TelegramBot):
    print(f"\n{B}--- Remove Bot Profile Photo ---{N}")
    ans = input("Confirm remove profile photo? [y/N]: ").strip()
    if ans.lower() != "y":
        print(f"{Y}cancelled.{N}")
        return
    print(f"\n{Y}>> removeMyProfilePhoto ...{N}")
    result = bot.post("removeMyProfilePhoto")
    if result and result.get("ok"):
        print(f"{G}✔ Profile photo removed{N}")
    else:
        show_info_result(result)


# ================================================================
#  File upload / download
# ================================================================
def _download_by_file_id(bot: TelegramBot, file_id: Optional[str],
                         meta: dict, out_dir: str = ".") -> Optional[str]:
    """Download a file by file_id, with a live progress bar."""
    if not file_id:
        print(f"{Y}skip: no file_id{N}")
        return None

    resp = bot.post("getFile", data={"file_id": file_id}, ask_retry=False)
    if not resp or not resp.get("ok"):
        desc = (resp.get("description") if isinstance(resp, dict) else "no response")
        print(f"{R}✘ getFile failed: {desc}{N}")
        return None

    result = resp["result"]
    fpath = result.get("file_path")
    file_size = result.get("file_size")
    if not fpath:
        print(f"{R}✘ no file_path returned{N}")
        return None

    # --- safe filename ---
    title = (meta.get("title") or "audio").strip()
    performer = (meta.get("performer") or "").strip()
    safe = re.sub(r'[\\/:*?"<>|]', "_",
                  f"{performer} - {title}".strip(" -")) or "audio"
    ext = os.path.splitext(fpath)[1] or ".mp3"
    out = os.path.join(out_dir, safe + ext)

    base, e = os.path.splitext(out)
    n = 1
    while os.path.exists(out):
        out = f"{base} ({n}){e}"
        n += 1

    url = f"{bot.file_api}/{fpath}"
    print(f"{B}⬇  {os.path.basename(out)}{N}  ({_human_size(file_size or 0)})")

    start = time.time()
    tmp = out + ".part"
    try:
        r = bot.session.get(url, timeout=120, stream=True)
        r.raise_for_status()

        # prefer server Content-Length; fall back to getFile's file_size
        total = int(r.headers.get("Content-Length") or 0) or file_size
        done = 0

        with open(tmp, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
                done += len(chunk)
                draw_progress(done, total, start, prefix="⬇ ")

        os.replace(tmp, out)
        finish_progress()
        size_kb = os.path.getsize(out) / 1024
        print(f"{G}✔ saved: {out}  ({size_kb:.1f} KB){N}")
        return out

    except Exception as e:
        finish_progress()
        print(f"{R}✘ download failed: {e}{N}")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return None

def _download_to_path(bot: TelegramBot, file_id: str, out_path: str) -> bool:
    resp = bot.post("getFile", data={"file_id": file_id}, ask_retry=False)
    if not resp or not resp.get("ok"):
        desc = (resp.get("description") if isinstance(resp, dict) else "no response")
        print(f"{R}✘ getFile failed: {desc}{N}")
        return False

    result = resp["result"]
    fpath = result.get("file_path")
    file_size = result.get("file_size")
    if not fpath:
        print(f"{R}✘ no file_path{N}")
        return False

    url = f"{bot.file_api}/{fpath}"
    print(f"{B}⬇  {os.path.basename(out_path)}{N}  "
          f"({_human_size(file_size or 0)})")

    start = time.time()
    tmp = out_path + ".part"
    try:
        r = bot.session.get(url, timeout=120, stream=True)
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0) or file_size
        done = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
                done += len(chunk)
                draw_progress(done, total, start, prefix="⬇ ")
        os.replace(tmp, out_path)
        finish_progress()
        print(f"{G}✔ saved: {out_path}  "
              f"({os.path.getsize(out_path) / 1024:.1f} KB){N}")
        return True
    except Exception as e:
        finish_progress()
        print(f"{R}✘ failed: {e}{N}")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False

def download_file_by_id(bot: TelegramBot):
    print(f"\n{B}--- Download File by file_id ---{N}")
    file_id = input("file_id: ").strip()
    if not file_id:
        print(f"{R}file_id is required{N}")
        return

    out = input("save as (empty = auto name): ").strip() or None
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    # use the helper with an empty meta so it derives a name from file_path
    meta = {"title": os.path.basename(out) if out else "",
            "performer": ""}
    # temporarily force the exact name if user gave one
    if out:
        _download_to_path(bot, file_id, out)
    else:
        _download_by_file_id(bot, file_id, {"title": "", "performer": ""},
                             out_dir=".")


def upload_and_get_file_id(bot: TelegramBot):
    print(f"\n{B}--- Upload File & Get file_id ---{N}")
    chat_id = input("chat_id (number or @username): ").strip()
    if not chat_id:
        print(f"{R}chat_id is required{N}")
        return
    fpath = input("file path to upload: ").strip()
    if not os.path.isfile(fpath):
        print(f"{R}file not found: {fpath}{N}")
        return
    print("Send as:")
    print("  1) document   2) photo   3) video   4) audio")
    print("  5) voice      6) animation   7) sticker")
    ftype = input("choice [1-7] (default 1): ").strip() or "1"
    mapping = {
        "1": ("document", "sendDocument"),
        "2": ("photo", "sendPhoto"),
        "3": ("video", "sendVideo"),
        "4": ("audio", "sendAudio"),
        "5": ("voice", "sendVoice"),
        "6": ("animation", "sendAnimation"),
        "7": ("sticker", "sendSticker"),
    }
    if ftype not in mapping:
        print(f"{R}invalid{N}")
        return
    field, method = mapping[ftype]
    ans = input("disable_notification? [y/N]: ").strip()
    mime = guess_mime(fpath)
    pf = ProgressFileReader(fpath) 
    files = {field: (os.path.basename(fpath), open(fpath, "rb"), mime)}
    data = {"chat_id": chat_id}
    if ans.lower() == "y":
        data["disable_notification"] = "true"
    print(f"\n{Y}>> {method} ...{N}")
    resp = bot.post(method, data=data, files=files)
    if not resp:
        print(f"{R}✘ No response{N}")
        return
    if resp.get("ok"):
        print(f"{G}✔ Uploaded.{N}")
        result = resp.get("result", {})
        msg_id = result.get("message_id")
        if msg_id:
            print(f"{G}📨 message_id: {msg_id}{N}")
        # extract file_id from result
        for key in ("document", "video", "audio", "voice", "animation", "sticker"):
            obj = result.get(key)
            if obj and "file_id" in obj:
                print(f"{G}🆔 file_id: {obj['file_id']}{N}")
                break
        else:
            photos = result.get("photo")
            if photos:
                print(f"{G}🆔 file_id: {photos[-1].get('file_id', 'N/A')}{N}")
    else:
        show_info_result(resp)


# ================================================================
#  Monitor Mode (new feature)
# ================================================================
def _check_mentioned(descr: dict, bot_id: int, bot_username: str) -> bool:
    """Return True if the bot was mentioned in the message."""
    text = descr.get("text") or descr.get("caption") or ""
    mentions = descr.get("mentions") or []
    for ent in mentions:
        etype = ent.get("type")
        if etype == "text_mention":
            user = ent.get("user") or {}
            if user.get("id") == bot_id:
                return True
        elif etype == "mention":
            frag = text[ent.get("offset", 0):ent.get("offset", 0) + ent.get("length", 0)]
            if frag.lower().lstrip("@") == (bot_username or "").lower().lstrip("@"):
                return True
    if bot_username and ("@" + bot_username.lower()) in text.lower():
        return True
    return False


def _display_files(files: list) -> None:
    if not files:
        return
    for fi in files:
        bits = [f"type={fi['file_type']}"]
        if fi.get('file_id'):
            bits.append(f"file_id={fi['file_id']}")
        if fi.get('file_name'):
            bits.append(f"name={fi['file_name']}")
        if fi.get('file_size') is not None:
            bits.append(f"size={fi['file_size']}B")
        if fi.get('width') and fi.get('height'):
            bits.append(f"{fi['width']}x{fi['height']}")
        if fi.get('duration'):
            bits.append(f"dur={fi['duration']}s")
        print(f"  {M}▸ {N}{' | '.join(bits)}")




def _extract_emojis(reaction_list) -> str:
    out = []
    for r in reaction_list or []:
        t = r.get("type")
        if t == "emoji":
            out.append(r.get("emoji", "?"))
        elif t == "custom_emoji":
            out.append(f"[custom:{str(r.get('custom_emoji_id','?'))[:8]}]")
    return " ".join(out) if out else "(none)"


def _handle_reaction_update(conn, mr: dict) -> dict:
    chat = mr.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return {}
    if chat.get("type") or chat.get("title") or chat.get("username"):
        db_upsert_entity(
            conn, chat_id, kind=chat.get("type", "unknown"),
            first_name=chat.get("first_name"), last_name=chat.get("last_name"),
            username=chat.get("username"), title=chat.get("title"),
            force_kind=True)
    user = mr.get("user") or {}
    actor_chat = mr.get("actor_chat") or {}
    user_id = user.get("id")
    actor_chat_id = actor_chat.get("id")
    if user:
        db_register_user(conn, user)
    if actor_chat:
        db_upsert_entity(
            conn, actor_chat_id, kind="channel",
            title=actor_chat.get("title"),
            username=actor_chat.get("username"), force_kind=False)
    msg_id = mr.get("message_id")
    old = mr.get("old_reaction") or []
    new = mr.get("new_reaction") or []
    changed = mr.get("date", 0)
    now = db_utcnow()
    conn.execute(
        "INSERT INTO message_reactions "
        "(chat_id, message_id, user_id, actor_chat_id, "
        " old_reactions, new_reactions, is_anonymous, changed_at, first_seen_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
        (chat_id, msg_id, user_id, actor_chat_id,
         json.dumps(old, ensure_ascii=False),
         json.dumps(new, ensure_ascii=False),
         changed, now))
    conn.commit()
    _apply_reaction_delta(conn, chat_id, msg_id, old, new)
    return {
        "chat_id": chat_id,
        "chat_title": chat.get("title") or chat.get("first_name") or str(chat_id),
        "message_id": msg_id,
        "user_id": user_id,
        "actor_chat_id": actor_chat_id,
        "user_name": " ".join(p for p in [
            user.get("first_name"), user.get("last_name")] if p).strip() or "?",
        "user_username": user.get("username", ""),
        "old": _extract_emojis(old),
        "new": _extract_emojis(new),
        "changed_at": changed,
    }


def _handle_reaction_count_update(conn, mrc: dict) -> dict:
    chat = mrc.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return {}
    msg_id = mrc.get("message_id")
    reactions = mrc.get("reactions") or []
    changed = mrc.get("date", 0)
    now = db_utcnow()
    summary = []
    for r in reactions:
        rt = r.get("type") or {}
        count = r.get("total_count", 0)
        emoji = rt.get("emoji") if rt.get("type") == "emoji" else ""
        custom = rt.get("custom_emoji_id", "") if rt.get("type") == "custom_emoji" else ""
        summary.append(f"{emoji or '[custom]'}x{count}")
        conn.execute(
            "INSERT INTO message_reactions "
            "(chat_id, message_id, user_id, actor_chat_id, "
            " old_reactions, new_reactions, is_anonymous, changed_at, first_seen_at) "
            "VALUES (?, ?, NULL, NULL, NULL, ?, 1, ?, ?)",
            (chat_id, msg_id,
             json.dumps([{"type": rt.get("type", "emoji"),
                          "emoji": emoji, "custom_emoji_id": custom,
                          "total_count": count}], ensure_ascii=False),
             changed, now))
    conn.commit()
    return {
        "chat_id": chat_id,
        "chat_title": chat.get("title") or chat.get("first_name") or str(chat_id),
        "message_id": msg_id,
        "summary": "  ".join(summary),
        "changed_at": changed,
    }


def monitor_mode(bot: TelegramBot):
    print(f"\n{G}{'=' * 60}{N}")
    print(f"{G}  MONITOR MODE – live getUpdates + SQLite + actions{N}")
    print(f"{G}{'=' * 60}{N}")

    # --- bot identity ---
    bot_id = bot.bot_id
    bot_username = ""
    me = bot.post("getMe")
    if me and me.get("ok"):
        bot_id = bot_id or me["result"].get("id")
        bot_username = me["result"].get("username", "") or ""

    # --- DB ---
    conn = sqlite3.connect(DB_FILE)
    db_init(conn)
    offset = int(db_state_get(conn, 'offset', '0') or '0')

    # --- pick chat ---
    target_chat_id = _pick_chat_for_monitor(conn)
    if target_chat_id is None:
        print(f"{G}Live filter: ALL chats{N}")
    else:
        print(f"{G}Live filter: chat_id = {target_chat_id}{N}")

    print(f"\n{Y}Hotkeys:{N}  ⏎=next  h=help  q=quit")
    print(f"{Y}Actions:{N}  r=reply  l=react  f=forward  d=delete  p=pin")
    print(f"{Y}Info   :{N}  i=full info  j=save JSON  c=change chat")
    print(f"{Y}Auto   :{N}  a=auto-reply  u=auto-react  s=set reply  e=set emoji")
    print(f"{Y}Stored :{N}  {DB_FILE}  (offset={offset})")
    print(f"{Y}Tip    :{N} actions don't advance — do reply + react, then ⏎\n")

    auto_reply = False
    auto_reply_text = ""
    auto_react = False
    auto_react_emoji = "👍"

    try:
        while True:
            resp = bot.get(
                "getUpdates",
                params={"offset": offset, "limit": 100, "timeout": 30,
                             "allowed_updates": ["message", "edited_message", "channel_post",
                                                 "edited_channel_post", "message_reaction",
                                                 "message_reaction_count", "managed_bot"]},
                ask_retry=False,
            )
            if not resp or not resp.get("ok"):
                time.sleep(5)
                continue

            updates = resp.get("result", [])
            if not updates:
                continue

            for upd in updates:
                uid = upd.get("update_id", 0)
                offset = uid + 1

                if "message_reaction" in upd:
                    d = _handle_reaction_update(conn, upd["message_reaction"])
                    db_store_update(conn, uid, "message_reaction", upd)
                    db_state_set(conn, "offset", offset)
                    if d and (target_chat_id is None or d["chat_id"] == target_chat_id):
                        print(f"\n{M}{'-' * 58}{N}")
                        print(f"{M}[REACTION]{N}  {_fmt_ts(d['changed_at'])}  (uid={uid})")
                        print(f"  Chat    : {d['chat_title']}")
                        print(f"  Chat ID : {d['chat_id']}")
                        print(f"  Message : #{d['message_id']}")
                        un = f" (@{d['user_username']})" if d['user_username'] else ""
                        print(f"  User    : {d['user_name']}{un} ({d['user_id']})")
                        print(f"  Old     : {d['old']}")
                        print(f"  New     : {d['new']}")
                        print(f"{M}{'-' * 58}{N}")
                    continue

                if "message_reaction_count" in upd:
                    d = _handle_reaction_count_update(conn, upd["message_reaction_count"])
                    db_store_update(conn, uid, "message_reaction_count", upd)
                    db_state_set(conn, "offset", offset)
                    if d and (target_chat_id is None or d["chat_id"] == target_chat_id):
                        print(f"\n{M}{'-' * 58}{N}")
                        print(f"{M}[REACTION COUNT]{N}  {_fmt_ts(d['changed_at'])}  (uid={uid})")
                        print(f"  Chat    : {d['chat_title']}")
                        print(f"  Chat ID : {d['chat_id']}")
                        print(f"  Message : #{d['message_id']}")
                        print(f"  Total   : {d['summary']}")
                        print(f"{M}{'-' * 58}{N}")
                    continue

                kind = None
                obj = None
                for k in ("message", "edited_message",
                          "channel_post", "edited_channel_post",
                          "managed_bot"):
                    if k in upd:
                        kind, obj = k, upd[k]
                        break

                if obj is None:
                    db_store_update(conn, uid, 'non-message', upd)
                    db_state_set(conn, 'offset', offset)
                    continue

                if kind == "managed_bot":
                    mb = obj
                    db_store_update(conn, uid, "managed_bot", upd)
                    db_state_set(conn, 'offset', offset)
                    print(f"\n{G}📢 New managed bot created!{N}")
                    print(f"  Bot ID   : {mb.get('bot_id')}")
                    print(f"  Username : @{mb.get('username')}")
                    print(f"  Name     : {mb.get('name')}")
                    print(f"  Owner ID : {mb.get('user_id')}")
                    tok_resp = bot.get_managed_bot_token(mb.get('user_id'))
                    if tok_resp and tok_resp.get("ok"):
                        new_token = tok_resp.get("result")
                        print(f"{G}✔ Token received: {new_token}{N}")
                        try:
                            conn.execute(
                                "INSERT OR REPLACE INTO managed_bots "
                                "(bot_id, username, first_name, token, added_at, "
                                " last_seen_at, updated_at) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (mb.get('bot_id'), mb.get('username'), mb.get('name'),
                                 new_token, db_utcnow(), db_utcnow(), db_utcnow()))
                            conn.commit()
                        except Exception as e:
                            print(f"{Y}⚠ Could not save to managed_bots: {e}{N}")
                    else:
                        print(f"{R}✘ Could not fetch token{N}")
                    continue

                db_store_update(conn, uid, kind, upd)
                descr = db_process_message(conn, uid, kind, obj)
                _record_mention_if_needed(conn, descr, bot)
                db_state_set(conn, 'offset', offset)
                if descr is None:
                    continue

                if get_guest_chat_mode():
                    is_guest = bool(obj.get("business_connection_id") or
                                    obj.get("sender_business_bot") or
                                    obj.get("via_bot") or
                                    obj.get("sender_boost_count"))
                    if not is_guest:
                        continue

                # --- filter ---
                if target_chat_id is not None and descr['chat_id'] != target_chat_id:
                    continue

                # --- display ---
                chat_id = descr['chat_id']
                chat_title = descr['chat_title'] or str(chat_id)
                from_name = (descr['from_first'] + " " +
                             descr['from_last']).strip() or "?"
                from_disp = from_name
                if descr['from_username']:
                    from_disp += f" (@{descr['from_username']})"
                if descr['is_bot']:
                    from_disp += f" {Y}[bot]{N}"
                text = descr['text'] or descr['caption'] or ""
                mentioned = _check_mentioned(descr, bot_id or 0, bot_username)

                print(f"\n{M}{'─' * 58}{N}")
                print(f"{M}📨 #{descr['content_type']}{N}  "
                      f"{_fmt_ts(descr['date'])}  (update_id={uid})")
                print(f"  Chat    : {chat_title}")
                print(f"  Chat ID : {chat_id}")
                print(f"  From    : {from_disp} ({descr['from_id']})")
                print(f"  Msg ID  : {descr['message_id']}")

                # ---- reply context ----
                replied_to_bot = False
                if descr['reply_to_message_id']:
                    replied_to_bot = _show_reply_context(
                        conn, chat_id, descr['message_id'], bot_id)

                if text:
                    print(f"  Text    : {text[:400]}")
                if descr['is_edit']:
                    print(f"  {Y}⚠ edited{N}")

                # ---- mention flags ----
                if mentioned:
                    print(f"  {G}📢 YOU WERE MENTIONED (entity / @username){N}")
                if replied_to_bot:
                    print(f"  {G}🔔 REPLY TO YOUR MESSAGE{N}")
                if not mentioned and not replied_to_bot and not descr['reply_to_message_id']:
                    print(f"  Mention : no")

                _display_files(descr['files'])
                print(f"{M}{'─' * 58}{N}")

                # --- auto actions ---
                if auto_reply and auto_reply_text and text:
                    _r = bot.post("sendMessage", data={
                        "chat_id": str(chat_id),
                        "text": auto_reply_text,
                        "reply_to_message_id": str(descr['message_id']),
                    })
                    _persist_from_resp(_r)
                    print(f"{G}  [auto-reply] sent{N}")
                if auto_react and text:
                    reaction_json = json.dumps(
                        [{"type": "emoji", "emoji": auto_react_emoji}])
                    bot.post("setMessageReaction", data={
                        "chat_id": str(chat_id),
                        "message_id": str(descr['message_id']),
                        "reaction": reaction_json,
                    })
                    print(f"{G}  [auto-react] {auto_react_emoji}{N}")

                if auto_reply or auto_react:
                    continue

                # --- interactive prompt (multi-action loop) ---
                acted = False
                while True:
                    hint = "(⏎=next" if not acted else "(⏎=next, actions done"
                    prompt = (f"{B}{hint}, h=help, q=quit, "
                              f"r l f d p | i j c | a u s e): {N}")
                    cmd = input(prompt).strip().lower()

                    if cmd in ("", "n"):
                        break  # advance to next message

                    if cmd == "q":
                        print(f"{Y}Returning to main menu...{N}")
                        return

                    if cmd == "h":
                        print(f"""
{Y}Commands:{N}
  ⏎ / n   skip to next message
  r       reply (you can also react after)
  l       react (you can also reply after)
  f       forward this message
  d       delete this message
  p       pin this message
  i       full info (sender + files + raw JSON)
  j       save raw JSON to a file
  c       change watched chat (back to chat list)
  a       toggle auto-reply
  u       toggle auto-react
  s       set auto-reply text
  e       set auto-react emoji
  q       quit to main menu
""")
                        continue

                    if cmd == "r":
                        qa = input("Quote a part of this message? [y/N]: ").strip().lower()
                        quote = None
                        if qa == "y":
                            quote = input("quote text (exact substring): ")
                            if not quote or not quote.strip():
                                quote = None
                                print(f"{Y}empty quote — sending without quote{N}")
                        rt = input("Reply text: ").strip()
                        if rt:
                            data = {"chat_id": str(chat_id), "text": rt}
                            if quote:
                                data["reply_parameters"] = json.dumps({
                                    "message_id": int(descr['message_id']),
                                    "quote": quote,
                                })
                            else:
                                data["reply_to_message_id"] = str(descr['message_id'])
                            r = bot.post("sendMessage", data=data)
                            ok = r and r.get("ok")
                            if ok:
                                _persist_from_resp(r)
                                mid = (r.get("result") or {}).get("message_id", "?")
                                print(f"{G}✔ Reply sent (msg_id={mid}){N}")
                                acted = True
                            else:
                                desc = (r.get("description") if isinstance(r, dict) else "?")
                                print(f"{R}✘ Reply failed: {desc}{N}")
                        continue

                    if cmd == "l":
                        emoji = pick_reaction()
                        if emoji:
                            reaction_json = json.dumps(
                                [{"type": "emoji", "emoji": emoji}])
                            r = bot.post("setMessageReaction", data={
                                "chat_id": str(chat_id),
                                "message_id": str(descr['message_id']),
                                "reaction": reaction_json,
                            })
                            if r and r.get("ok"):
                                print(f"{G}✔ Reaction {emoji} sent{N}")
                                acted = True
                                # ── persist to DB ──
                                try:
                                    _pc = sqlite3.connect(DB_FILE); db_init(_pc)
                                    _prev_row = _pc.execute(
                                        "SELECT new_reactions FROM message_reactions "
                                        " WHERE chat_id = ? AND message_id = ? "
                                        "   AND user_id = ? "
                                        " ORDER BY changed_at DESC LIMIT 1",
                                        (chat_id, descr['message_id'], bot.bot_id)).fetchone()
                                    _prev_rx = (json.loads(_prev_row[0])
                                                if _prev_row and _prev_row[0] else [])
                                    _new_rx = [{"type": "emoji", "emoji": emoji}]
                                    _pc.execute(
                                        "INSERT INTO message_reactions "
                                        "(chat_id, message_id, user_id, actor_chat_id, "
                                        " old_reactions, new_reactions, is_anonymous, "
                                        " changed_at, first_seen_at) "
                                        "VALUES (?, ?, ?, NULL, ?, ?, 0, ?, ?)",
                                        (chat_id, descr['message_id'], bot.bot_id,
                                        json.dumps(_prev_rx, ensure_ascii=False),
                                        json.dumps(_new_rx, ensure_ascii=False),
                                        int(time.time()), db_utcnow()))
                                    _apply_reaction_delta(
                                        _pc, chat_id, descr['message_id'],
                                        _prev_rx, _new_rx)
                                    _pc.commit()
                                    _pc.close()
                                except Exception as e:
                                    print(f"{Y}⚠ react persist: {e}{N}")
                            else:
                                print(f"{R}✘ Reaction failed{N}")
                        continue

                    if cmd == "f":
                        to_chat = input("Forward to chat_id: ").strip()
                        if to_chat:
                            r = bot.post("forwardMessage", data={
                                "chat_id": to_chat,
                                "from_chat_id": str(chat_id),
                                "message_id": str(descr['message_id']),
                            })
                            if r and r.get("ok"):
                                print(f"{G}✔ Forwarded{N}")
                                acted = True
                                _persist_from_resp(r)
                            else:
                                print(f"{R}✘ Forward failed{N}")
                        continue

                    if cmd == "d":
                        if input(f"Delete {descr['message_id']}? [y/N]: "
                                 ).strip().lower() == "y":
                            r = bot.post("deleteMessage", data={
                                "chat_id": str(chat_id),
                                "message_id": str(descr['message_id']),
                            })
                            print(f"{G}✔ Deleted{N}" if r and r.get("ok")
                                  else f"{R}✘ Failed{N}")
                            acted = True
                        continue

                    if cmd == "p":
                        r = bot.post("pinChatMessage", data={
                            "chat_id": str(chat_id),
                            "message_id": str(descr['message_id']),
                        })
                        print(f"{G}✔ Pinned{N}" if r and r.get("ok")
                              else f"{R}✘ Failed{N}")
                        acted = True
                        continue

                    if cmd == "i":
                        _show_msg_full(conn, chat_id, descr['message_id'],
                                       show_raw=True)
                        continue

                    if cmd == "j":
                        row = conn.execute(
                            "SELECT raw_json FROM messages "
                            "WHERE chat_id = ? AND message_id = ?",
                            (chat_id, descr['message_id'])).fetchone()
                        if row and row[0]:
                            fn = f"msg_{abs(chat_id)}_{descr['message_id']}.json"
                            with open(fn, "w", encoding="utf-8") as f:
                                f.write(row[0])
                            print(f"{G}✔ Saved {fn}{N}")
                        else:
                            print(f"{R}no raw JSON found{N}")
                        continue

                    if cmd == "c":
                        target_chat_id = _pick_chat_for_monitor(conn)
                        if target_chat_id is None:
                            print(f"{G}Live filter: ALL chats{N}")
                        else:
                            print(f"{G}Live filter: chat_id = {target_chat_id}{N}")
                        break

                    if cmd == "a":
                        auto_reply = not auto_reply
                        print(f"  Auto-reply: {'ON' if auto_reply else 'OFF'}")
                        continue

                    if cmd == "u":
                        auto_react = not auto_react
                        print(f"  Auto-react: {'ON' if auto_react else 'OFF'}")
                        continue

                    if cmd == "s":
                        auto_reply_text = input("Auto-reply text: ").strip()
                        if auto_reply_text:
                            auto_reply = True
                            print(f"{G}Auto-reply set and enabled{N}")
                        continue

                    if cmd == "e":
                        emoji = pick_reaction()
                        if emoji:
                            auto_react_emoji = emoji
                            auto_react = True
                            print(f"{G}Auto-react emoji = {emoji} (enabled){N}")
                        continue

                    print(f"{R}unknown command, press h for help{N}")

    except KeyboardInterrupt:
        print(f"\n{Y}Monitor stopped.{N}")
    finally:
        conn.close()


# ================================================================
#  Menu
# ================================================================


def chat_history_viewer(bot: TelegramBot):
    """View stored history of a chat: messages + reactions."""
    conn = sqlite3.connect(DB_FILE)
    db_init(conn)
    try:
        target_chat_id = _pick_chat_for_monitor(conn)
        if target_chat_id is None:
            print(f"{Y}Pick a specific chat.{N}")
            return
        while True:
            print(f"\n{B}--- History of chat {target_chat_id} ---{N}")
            print("  1) Last N messages (with reactions)")
            print("  2) Full reactions history")
            print("  3) Full info of a message + its reactions")
            print("  4) Search keyword")
            print("  5) Top-reacted messages")
            print("  0) Back")
            opt = input("choice: ").strip()
            if opt == "0":
                return

            if opt == "1":
                try: n = int(input("how many (default 30): ") or "30")
                except ValueError: n = 30
                rows = conn.execute(
                    "SELECT message_id, date, from_user_id, content_type, "
                    "       text, caption, reply_to_message_id "
                    "  FROM messages WHERE chat_id = ? "
                    " ORDER BY date DESC LIMIT ?",
                    (target_chat_id, n)).fetchall()
                if not rows:
                    print(f"{Y}No messages stored.{N}")
                    continue
                for mid, dt, uid, ct, text, cap, rep in rows:
                    rx = conn.execute(
                        "SELECT new_reactions FROM message_reactions "
                        " WHERE chat_id = ? AND message_id = ? "
                        " ORDER BY changed_at DESC LIMIT 1",
                        (target_chat_id, mid)).fetchone()
                    emojis = ""
                    if rx and rx[0]:
                        try: emojis = _extract_emojis(json.loads(rx[0]))
                        except Exception: pass
                    snippet = (text or cap or "").replace("\n", " ")[:70]
                    print(f"\n#{mid}  {_fmt_ts(dt)}  u={uid}  {ct}")
                    if rep: print(f"  reply_to={rep}")
                    if snippet: print(f"  {snippet}")
                    if emojis: print(f"  {G}reactions: {emojis}{N}")

            elif opt == "2":
                try: n = int(input("how many (default 50): ") or "50")
                except ValueError: n = 50
                rows = conn.execute(
                    "SELECT message_id, user_id, old_reactions, new_reactions, "
                    "       is_anonymous, changed_at "
                    "  FROM message_reactions WHERE chat_id = ? "
                    " ORDER BY changed_at DESC LIMIT ?",
                    (target_chat_id, n)).fetchall()
                if not rows:
                    print(f"{Y}No reactions recorded.{N}")
                    continue
                for mid, uid, oj, nj, anon, ts in rows:
                    oe = _extract_emojis(json.loads(oj)) if oj else "-"
                    ne = _extract_emojis(json.loads(nj)) if nj else "-"
                    who = "anonymous" if anon else f"user={uid}"
                    print(f"  [{_fmt_ts(ts)}] #{mid}  {who}  {oe} -> {ne}")

            elif opt == "3":
                m = input("message_id: ").strip()
                if not m.isdigit():
                    continue
                _show_msg_full(conn, target_chat_id, int(m), show_raw=False)
                rows = conn.execute(
                    "SELECT user_id, old_reactions, new_reactions, is_anonymous, changed_at "
                    "  FROM message_reactions WHERE chat_id = ? AND message_id = ? "
                    " ORDER BY changed_at",
                    (target_chat_id, int(m))).fetchall()
                if rows:
                    print(f"  {M}Reactions history:{N}")
                    for uid, oj, nj, anon, ts in rows:
                        oe = _extract_emojis(json.loads(oj)) if oj else "-"
                        ne = _extract_emojis(json.loads(nj)) if nj else "-"
                        who = "anonymous" if anon else f"user={uid}"
                        print(f"    [{_fmt_ts(ts)}] {who}  {oe} -> {ne}")

            elif opt == "4":
                kw = input("keyword: ").strip()
                if not kw:
                    continue
                like = f"%{kw}%"
                rows = conn.execute(
                    "SELECT message_id, date, from_user_id, content_type, text, caption "
                    "  FROM messages WHERE chat_id = ? "
                    "   AND (text LIKE ? OR caption LIKE ?) "
                    " ORDER BY date DESC LIMIT 100",
                    (target_chat_id, like, like)).fetchall()
                print(f"{G}{len(rows)} match(es){N}")
                for mid, dt, uid, ct, text, cap in rows:
                    sn = (text or cap or "").replace("\n", " ")[:80]
                    print(f"  #{mid}  {_fmt_ts(dt)}  u={uid}  {ct}  {sn}")

            elif opt == "5":
                rows = conn.execute(
                    "SELECT message_id, COUNT(*) AS n FROM message_reactions "
                    " WHERE chat_id = ? GROUP BY message_id "
                    " ORDER BY n DESC LIMIT 20",
                    (target_chat_id,)).fetchall()
                if not rows:
                    print(f"{Y}No reactions recorded.{N}")
                    continue
                for mid, cnt in rows:
                    r = conn.execute(
                        "SELECT date, from_user_id, content_type, text, caption "
                        "  FROM messages WHERE chat_id = ? AND message_id = ?",
                        (target_chat_id, mid)).fetchone()
                    if r:
                        dt, uid, ct, text, cap = r
                        sn = (text or cap or "").replace("\n", " ")[:60]
                        print(f"  #{mid}  {cnt} events  {_fmt_ts(dt)}  u={uid}  {ct}  {sn}")
                    else:
                        print(f"  #{mid}  {cnt} events  (message not stored)")
            else:
                print(f"{R}invalid{N}")
    finally:
        conn.close()

def toggle_guest_chat_mode():
    cur = get_guest_chat_mode()
    set_guest_chat_mode(not cur)
    print(f"{G}✔ Guest chat mode → {'ON' if not cur else 'OFF'}{N}")

def chat_id_lock_menu():
    while True:
        cur = get_locked_chat_id()
        print(f"\n{B}--- Lock / Unlock chat_id ---{N}")
        print(f"  Current: {cur or '(none)'}")
        print("  1) Enter manually")
        print("  2) Pick from DB")
        print("  3) Clear lock")
        print("  0) Back")
        c = input("choice: ").strip()
        if c == "1":
            v = input("chat_id: ").strip()
            if v:
                set_locked_chat_id(v)
                print(f"{G}✔ Locked to {v}{N}")
        elif c == "2":
            conn = sqlite3.connect(DB_FILE); db_init(conn)
            cid = _pick_chat_for_monitor(conn)
            conn.close()
            if cid is not None:
                set_locked_chat_id(str(cid))
                print(f"{G}✔ Locked to {cid}{N}")
        elif c == "3":
            set_locked_chat_id("")
            print(f"{G}✔ Lock cleared{N}")
        elif c == "0":
            return

def db_purge_menu(bot: TelegramBot):
    conn = sqlite3.connect(DB_FILE); db_init(conn)
    try:
        while True:
            print(f"\n{B}--- Purge DB data ---{N}")
            print("  1) Purge a specific chat (pick from list)")
            print("  2) Purge by chat type (private/group/supergroup/channel)")
            print("  3) Purge by date range (unix ts)")
            print("  4) Purge by message_id range in a chat (pick from list)")
            print("  5) Cleanup orphans (chat_users/entities with no messages)")
            print("  0) Back")
            c = input("choice: ").strip()
            if c == "0":
                return
            where, params, label = None, [], ""
            if c == "1":
                cid = _pick_chat_required(conn)
                if cid is None:
                    continue
                where, params, label = "chat_id = ?", [cid], f"chat {cid}"
            elif c == "2":
                k = input("kind (private/group/supergroup/channel): ").strip()
                if not k:
                    continue
                ids = [r[0] for r in conn.execute(
                    "SELECT id FROM entities WHERE kind = ?", (k,)).fetchall()]
                if not ids:
                    print(f"{Y}no chats of that kind{N}")
                    continue
                where = f"chat_id IN ({','.join('?' * len(ids))})"
                params, label = ids, f"kind={k}"
            elif c == "3":
                a = input("from unix ts: ").strip()
                b = input("to unix ts: ").strip()
                try:
                    where = "date >= ? AND date <= ?"
                    params = [int(a), int(b)]
                    label = f"date {a}..{b}"
                except ValueError:
                    continue
            elif c == "4":
                cid = _pick_chat_required(conn)
                if cid is None:
                    continue
                a = input("from message_id: ").strip()
                b = input("to message_id: ").strip()
                try:
                    where = "chat_id = ? AND message_id BETWEEN ? AND ?"
                    params = [cid, int(a), int(b)]
                    label = f"chat={cid} msg {a}..{b}"
                except ValueError:
                    continue
            elif c == "5":
                # orphan = chat with 0 messages (chat_users may still have stale rows)
                orphans = conn.execute(
                    """SELECT e.id, e.kind, e.title, e.first_name, e.last_name,
                              (SELECT COUNT(*) FROM chat_users cu
                                WHERE cu.chat_id = e.id) AS stale_members
                         FROM entities e
                        WHERE e.kind IN ('group','supergroup','channel','private')
                          AND NOT EXISTS (
                              SELECT 1 FROM messages m WHERE m.chat_id = e.id
                          )"""
                ).fetchall()
                if not orphans:
                    print(f"{G}✔ No orphans found{N}")
                    continue
                print(f"\n{B}Orphan entities ({len(orphans)}) "
                      f"— no messages, may have stale chat_users:{N}")
                for eid, kind, title, fn, ln, stale in orphans:
                    lbl = title or (fn and f"{fn} {ln or ''}".strip()) or "?"
                    tag = f"  stale_members={stale}" if stale else ""
                    print(f"  id={eid:<16} [{kind:<10}] {lbl}{tag}")
                if input("Delete all orphans (entities + chat_users)? [y/N]: "
                         ).strip().lower() != "y":
                    continue
                for eid, *_rest in orphans:
                    conn.execute("DELETE FROM chat_users WHERE chat_id = ?", [eid])
                    conn.execute("DELETE FROM entities WHERE id = ?", [eid])
                conn.commit()
                print(f"{G}✔ Removed {len(orphans)} orphan(s){N}")
                continue
            else:
                continue
            if not where:
                continue
            cnt = conn.execute(f"SELECT COUNT(*) FROM messages WHERE {where}",
                               params).fetchone()[0]
            if not cnt:
                print(f"{Y}no rows matched{N}")
                continue
            if input(f"Delete {cnt} message(s) [{label}] + related rows? [y/N]: "
                     ).strip().lower() != "y":
                continue
            conn.execute(f"DELETE FROM message_files WHERE {where}", params)
            conn.execute(f"DELETE FROM message_edits WHERE {where}", params)
            conn.execute(f"DELETE FROM message_reactions WHERE {where}", params)
            conn.execute(f"DELETE FROM messages WHERE {where}", params)

            # also drop ghost chat_users / entity rows for those chats
            cids = [r[0] for r in conn.execute(
                f"SELECT DISTINCT chat_id FROM messages WHERE {where}", params
            ).fetchall()]
            # above will be empty since we just deleted, so use params directly
            if c == "1" or c == "4":
                target_cid = params[0]
                conn.execute("DELETE FROM chat_users WHERE chat_id = ?", [target_cid])
                conn.execute(
                    "DELETE FROM entities WHERE id = ? "
                    "AND kind IN ('group','supergroup','channel','private')",
                    [target_cid])
            elif c == "2":
                for cid in params:
                    conn.execute("DELETE FROM chat_users WHERE chat_id = ?", [cid])
                    conn.execute(
                        "DELETE FROM entities WHERE id = ? "
                        "AND kind IN ('group','supergroup','channel','private')",
                        [cid])

            conn.commit()
            print(f"{G}✔ Purged {cnt} message(s) + related metadata{N}")
    finally:
        conn.close()

def bot_management_mode(bot: TelegramBot):
    conn = sqlite3.connect(DB_FILE)
    db_init(conn)
    try:
        # Register the current bot in the registry
        me = bot.post("getMe", ask_retry=False)
        if me and me.get("ok"):
            info = me["result"]
            now = db_utcnow()
            conn.execute(
                "INSERT OR REPLACE INTO managed_bots "
                "(bot_id, username, first_name, token, added_at, last_seen_at, updated_at) "
                "VALUES (?, ?, ?, ?, "
                " COALESCE((SELECT added_at FROM managed_bots WHERE bot_id=?), ?), ?, ?)",
                (info['id'], info.get('username'), info.get('first_name'), bot.token,
                 info['id'], now, now, now))
            conn.commit()

        while True:
            rows = conn.execute(
                "SELECT bot_id, username, first_name, added_at, last_seen_at "
                "FROM managed_bots ORDER BY last_seen_at DESC").fetchall()

            print(f"\n{B}--- Bot Management ({len(rows)}) ---{N}")
            if not rows:
                print(f"{Y}No bots managed yet.{N}")
            for i, (bid, un, fn, added, seen) in enumerate(rows, 1):
                print(f"  {i:>3}) {fn or '?'} (@{un or '?'})  id={bid}  seen={seen}")
            print("  0) Back")
            print("  a) Add new bot (via link)")
            c = input("choice: ").strip()

            if c == "0":
                return

            if c.lower() == "a":
                # --- Generate invite link for creating a new managed bot ---
                print(f"\n{B}--- Create Managed Bot Link ---{N}")
                suggested = input("Suggested username for new bot (e.g. MyCoolBot): ").strip()
                if not suggested:
                    print(f"{R}Username is required.{N}")
                    continue
                suggested_name = input("Suggested display name (optional): ").strip() or suggested
                manager_username = bot.bot_info.get('username') if bot.bot_info else ''
                if not manager_username:
                    me = bot.post("getMe", ask_retry=False)
                    if me and me.get("ok"):
                        manager_username = me['result'].get('username', '')
                        bot.bot_info = me['result']
                if not manager_username:
                    print(f"{R}Could not determine manager bot username.{N}")
                    continue
                link = f"https://t.me/newbot/{manager_username}/{suggested}?name={urllib.parse.quote(suggested_name)}"
                print(f"\n{G}✔ Link generated:{N}")
                print(f"  {link}")
                print(f"\n{Y}Share this link with users so they can create a bot managed by you.{N}")
                continue

            if not c.isdigit():
                print(f"{R}invalid — type a number, 'a', or 0{N}")
                continue

            idx = int(c) - 1
            if idx < 0 or idx >= len(rows):
                print(f"{R}invalid number{N}")
                continue

            bid, un, fn, added, seen = rows[idx]

            # ===== Submenu for the selected bot =====
            while True:
                print(f"\n{B}--- Bot: {fn or '?'} (@{un or '?'}) id={bid} ---{N}")
                print(f"  added: {added}   last_seen: {seen}")
                print("  1) View stored token")
                print("  2) View permissions for a chat")
                print("  3) Delete this bot from DB")
                print("  4) Get/Refresh managed bot token (getManagedBotToken)")
                print("  5) Replace managed bot token (replaceManagedBotToken)")
                print("  6) View/Edit access settings")
                print("  7) Export token via MTProto (bots.exportBotToken)")
                print("  0) Back")
                sub = input("choice: ").strip()

                if sub == "0":
                    break
                elif sub == "1":
                    tok = conn.execute(
                        "SELECT token FROM managed_bots WHERE bot_id=?", (bid,)
                    ).fetchone()
                    val = tok[0] if tok and tok[0] else "(none)"
                    print(f"  token: {val}")
                elif sub == "2":
                    perms = conn.execute(
                        "SELECT chat_id, permissions_json FROM bot_permissions WHERE bot_id=?",
                        (bid,)).fetchall()
                    if not perms:
                        print(f"{Y}no permissions stored{N}")
                    for cid, pj in perms:
                        print(f"  chat {cid}: {pj}")
                elif sub == "3":
                    if input(f"Delete bot {bid} + permissions? [y/N]: "
                             ).strip().lower() == "y":
                        conn.execute("DELETE FROM bot_permissions WHERE bot_id=?", (bid,))
                        conn.execute("DELETE FROM managed_bots WHERE bot_id=?", (bid,))
                        conn.commit()
                        print(f"{G}✔ Deleted{N}")
                        break
                elif sub == "4":
                    print(f"\n{Y}>> getManagedBotToken ...{N}")
                    resp = bot.get_managed_bot_token(bid)
                    show_info_result(resp)
                    if resp and resp.get("ok"):
                        new_token = resp["result"]
                        conn.execute(
                            "UPDATE managed_bots SET token = ?, updated_at = ? WHERE bot_id = ?",
                            (new_token, db_utcnow(), bid))
                        conn.commit()
                        print(f"{G}✔ Token updated in local DB{N}")
                elif sub == "5":
                    ans = input(f"Replace token for bot {bid}? Old token will be invalidated. [y/N]: ").strip().lower()
                    if ans == "y":
                        print(f"\n{Y}>> replaceManagedBotToken ...{N}")
                        resp = bot.replace_managed_bot_token(bid)
                        show_info_result(resp)
                        if resp and resp.get("ok"):
                            new_token = resp["result"]
                            conn.execute(
                                "UPDATE managed_bots SET token = ?, updated_at = ? WHERE bot_id = ?",
                                (new_token, db_utcnow(), bid))
                            conn.commit()
                            print(f"{G}✔ Token replaced and saved{N}")
                elif sub == "6":
                    print(f"\n{Y}>> bots.getAccessSettings ...{N}")
                    resp = bot.get_managed_bot_access_settings(bid)
                    show_info_result(resp)
                    if resp and resp.get("ok"):
                        print(f"\n{B}Edit settings? (leave blank to skip){N}")
                        settings = {}
                        for key in ("can_send_messages", "can_send_media", "can_add_web_page_previews",
                                    "can_send_polls", "can_change_info", "can_invite_users",
                                    "can_pin_messages", "can_manage_topics"):
                            val = input(f"  {key} [y/N/blank]: ").strip().lower()
                            if val == "y":
                                settings[key] = True
                            elif val == "n":
                                settings[key] = False
                        if settings:
                            edit_resp = bot.edit_managed_bot_access_settings(bid, **settings)
                            show_info_result(edit_resp)
                elif sub == "7":
                    print(f"\n{Y}>> bots.exportBotToken ...{N}")
                    resp = bot.export_managed_bot_token(bid)
                    show_info_result(resp)
                else:
                    print(f"{R}invalid{N}")
    finally:
        conn.close()

def manage_bot_token_menu(bot: TelegramBot):
    """Submenu for viewing, updating, and testing the bot token."""
    while True:
        token = get_config_token()
        masked = (token[:9] + "..." + token[-4:]) if len(token) > 13 else (token or "(not configured)")
        bot_user = f"@{bot.bot_info.get('username')}" if getattr(bot, "bot_info", None) and bot.bot_info.get("username") else "Not connected / Unknown"

        print(f"\n{B}--- Manage Bot Token ---{N}")
        print(f"  Current Token : {masked}")
        print(f"  Connected Bot : {bot_user}")
        cur_base = get_config_base_url() or "https://api.telegram.org"
        print(f"  Base URL      : {cur_base}")
        print("  1) Show full token")
        print("  2) Change / update token (validates with Telegram API)")
        print("  3) Test token connectivity (getMe)")
        print("  4) Set custom Base URL")
        print("  0) Back")

        c = input("choice: ").strip()
        if c == "1":
            print(f"\n{Y}Bot Token:{N} {token if token else '(none)'}")
        elif c == "2":
            new_tok = input("\nEnter new bot token (empty to cancel): ").strip()
            if not new_tok:
                print(f"{Y}Cancelled.{N}")
                continue
            print(f"{Y}Validating token with Telegram API...{N}")
            test_bot = TelegramBot(new_tok, PROXY)
            resp = test_bot.post("getMe", ask_retry=False)
            if resp and resp.get("ok"):
                info = resp["result"]
                bot.token = new_tok
                bot.base_url = f"https://api.telegram.org/bot{new_tok}"
                bot.file_api = f"https://api.telegram.org/file/bot{new_tok}"
                bot.bot_id = info.get("id")
                bot.bot_info = info
                set_config_token(new_tok)
                print(f"{G}✔ Token valid and updated! Connected as @{info.get('username', '?')} ({info.get('first_name', '?')}){N}")
            else:
                desc = resp.get("description", "Unknown error") if resp else "Connection error"
                err_code = resp.get("error_code", "NetError") if resp else "NetError"
                print(f"{R}✘ Telegram API rejected token ({err_code}): {desc}{N}")
                ans = input("Do you still want to save this token to config? [y/N]: ").strip()
                if ans.lower() == "y":
                    bot.token = new_tok
                    bot.base_url = f"https://api.telegram.org/bot{new_tok}"
                    bot.file_api = f"https://api.telegram.org/file/bot{new_tok}"
                    set_config_token(new_tok)
                    print(f"{Y}Token saved to {CONFIG_FILE}.{N}")
        elif c == "3":
            resp = bot.post("getMe")
            show_info_result(resp)
            if resp and resp.get("ok"):
                bot.bot_info = resp["result"]
        elif c == "4":
            new_base = input(f"Base URL (empty = default api.telegram.org): ").strip()
            set_config_base_url(new_base)
            _root = (new_base or "https://api.telegram.org").rstrip("/")
            bot.base_url = f"{_root}/bot{bot.token}"
            bot.file_api = f"{_root}/file/bot{bot.token}"
            print(f"{G}✔ Base URL set to {_root}{N}")
        elif c == "0":
            break
        else:
            print(f"{R}invalid choice{N}")


def manage_reactions_menu():
    """Submenu for viewing, adding, removing, and resetting reactions."""
    while True:
        reactions = load_reactions()
        print(f"\n{B}--- Manage Reactions ---{N}")
        print(f"  Configured reactions: {len(reactions)}")
        print("  1) List all configured reactions")
        print("  2) Add / update reaction")
        print("  3) Remove a reaction")
        print("  4) Reset to Telegram default set (61 reactions)")
        print("  0) Back")

        c = input("choice: ").strip()
        if c == "1":
            print(f"\n{B}--- Configured Reactions ({len(reactions)}) ---{N}")
            cols = 3
            per_col = (len(reactions) + cols - 1) // cols
            for row in range(per_col):
                line = "  "
                for col_idx in range(cols):
                    i = row + col_idx * per_col
                    if i < len(reactions):
                        emoji, name = reactions[i]
                        cell = f"{i + 1:>2}) {emoji}  {name[:20]}"
                        line += cell.ljust(32)
                print(line)
        elif c == "2":
            emoji = input("\nEnter emoji (e.g. 🔥): ").strip()
            if not emoji:
                print(f"{R}Emoji is required.{N}")
                continue
            name = input("Enter description / label (e.g. Fire): ").strip()
            updated = False
            new_reactions = []
            for em, nm in reactions:
                if em == emoji:
                    new_reactions.append((em, name if name else nm))
                    updated = True
                else:
                    new_reactions.append((em, nm))
            if not updated:
                new_reactions.append((emoji, name))
            save_reactions(new_reactions)
            print(f"{G}✔ Reaction '{emoji}' ({name}) saved to {CONFIG_FILE}!{N}")
        elif c == "3":
            if not reactions:
                print(f"{Y}No reactions configured.{N}")
                continue
            val = input("\nEnter reaction number or emoji to remove: ").strip()
            if not val:
                continue
            idx_to_remove = None
            if val.isdigit():
                idx = int(val) - 1
                if 0 <= idx < len(reactions):
                    idx_to_remove = idx
            if idx_to_remove is None:
                for i, (em, _) in enumerate(reactions):
                    if em == val:
                        idx_to_remove = i
                        break
            if idx_to_remove is not None:
                removed_em, removed_name = reactions[idx_to_remove]
                new_reactions = [r for i, r in enumerate(reactions) if i != idx_to_remove]
                save_reactions(new_reactions)
                print(f"{G}✔ Removed reaction: {removed_em} ({removed_name}){N}")
            else:
                print(f"{R}Reaction not found.{N}")
        elif c == "4":
            ans = input(f"Reset reactions to default Telegram set ({len(TELEGRAM_REACTIONS)} reactions)? [y/N]: ").strip()
            if ans.lower() == "y":
                save_reactions(list(TELEGRAM_REACTIONS))
                print(f"{G}✔ Reactions reset to default Telegram set!{N}")
        elif c == "0":
            break
        else:
            print(f"{R}invalid choice{N}")


# ============ Menu animation ============
MENU_SPEED = "fast"   # "off" | "fast" | "normal" | "slow"

_SPEED_MAP = {
    "off":    (0.0,   0.0),
    "fast":   (0.006, 0.008),
    "normal": (0.012, 0.015),
    "slow":   (0.025, 0.03),
}

def _tw_print(text: str, delay: float) -> None:
    """Typewriter effect — only if stdout is a real terminal."""
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    if not is_tty or delay <= 0:
        print(text)
        return
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()


def render_menu(header_lines: List[str],
                groups: List[Tuple[Optional[str], List[Tuple[int, str]]]],
                footer_lines: Optional[List[str]] = None) -> None:
    char_delay, line_delay = _SPEED_MAP.get(MENU_SPEED, _SPEED_MAP["fast"])

    term_w, _ = _term_size()
    min_cell_width = 32
    columns = max(1, min(term_w // min_cell_width, 5))
    cell_width = max(min_cell_width, term_w // columns)

    # --- phase 1: header (typewriter on the title line only) ---
    for i, line in enumerate(header_lines):
        if i == 0 and line.strip():
            # only the title line gets the typewriter; rest are instant
            _tw_print(line, char_delay)
        else:
            print(line)

    # --- phase 2: groups ---
    for title, items in groups:
        if not items:
            continue
        if title:
            dashes = max(0, term_w - len(title) - 8)
            header_line = f"  {B}--- {title} " + "-" * dashes + f"{N}"
            print(header_line)
            if line_delay > 0 and hasattr(sys.stdout, "isatty") \
                    and sys.stdout.isatty():
                time.sleep(line_delay * 2)
        for i in range(0, len(items), columns):
            row = items[i:i + columns]
            line = "  "
            for num, label in row:
                cell = f"{num:>2}) {label}"
                line += cell[:cell_width].ljust(cell_width)
            print(line)
            if line_delay > 0 and hasattr(sys.stdout, "isatty") \
                    and sys.stdout.isatty():
                time.sleep(line_delay)

    # --- phase 3: footer ---
    if footer_lines:
        for line in footer_lines:
            print(line)
            if line_delay > 0 and hasattr(sys.stdout, "isatty") \
                    and sys.stdout.isatty():
                time.sleep(line_delay)


# kept for backward compat
def render_animated_menu(lines: List[str], delay: float = 0.005) -> None:
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    for line in lines:
        print(line)
        if is_tty and delay > 0:
            time.sleep(delay)

def format_menu_row(n1, t1, n2=None, t2=None):
    if n2 is not None and t2 is not None:
        return f"  {n1:2d}) {t1:<22s}   {n2:2d}) {t2:<22s}"
    return f"  {n1:2d}) {t1}"


def print_menu_row(n1, t1, n2, t2):
    print(format_menu_row(n1, t1, n2, t2))

import threading
import http.server
import urllib.parse

def _try_persist_payload(payload: bytes) -> None:
    """If payload is a Message object, persist to DB. Silent on failure."""
    try:
        js = json.loads(payload)
        if js.get("ok") and isinstance(js.get("result"), dict):
            if "message_id" in js["result"]:
                _persist_from_resp(js)
    except Exception:
        pass

_api_server_instance = {"httpd": None, "thread": None}

def _start_api_server(bot: TelegramBot) -> bool:
    cfg = load_config()
    host = cfg.get("api_server_host", "127.0.0.1")
    port = int(cfg.get("api_server_port", 8080))
    api_token = (cfg.get("api_server_token") or bot.token).strip()

    _proxy = PROXY or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")

    class Handler(http.server.BaseHTTPRequestHandler):
        def _respond(self, code, body: bytes):
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._handle()

        def do_POST(self):
            self._handle()

        def _handle(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            # ---------- file download: /file/bot<token>/<path> ----------
            if path.startswith(f"/file/bot{api_token}/"):
                file_path = path[len(f"/file/bot{api_token}/"):]
                url = f"{bot.file_api}/{file_path}"
                sess = requests.Session()
                if _proxy:
                    sess.proxies = {"http": _proxy, "https": _proxy}
                try:
                    r = sess.get(url, timeout=120, stream=True)
                    self.send_response(r.status_code)
                    for h in ("Content-Type", "Content-Length", "Content-Disposition"):
                        if h in r.headers:
                            self.send_header(h, r.headers[h])
                    self.end_headers()
                    for chunk in r.iter_content(65536):
                        self.wfile.write(chunk)
                except Exception as e:
                    self._respond(502, json.dumps(
                        {"ok": False, "description": str(e)}).encode())
                return

            # ---------- bot methods: /bot<token>/<method> ----------
            if not path.startswith(f"/bot{api_token}/"):
                self._respond(404, b'{"ok":false,"description":"unknown token"}')
                return

            method = path.rsplit("/", 1)[-1]
            qs = urllib.parse.parse_qs(parsed.query)
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            content_type = self.headers.get("Content-Type", "")

            # ---------- multipart: forward raw body untouched ----------
            if content_type.startswith("multipart/form-data"):
                sess = requests.Session()
                if _proxy:
                    sess.proxies = {"http": _proxy, "https": _proxy}
                try:
                    resp = sess.post(
                        f"{bot.base_url}/{method}",
                        data=raw,
                        headers={"Content-Type": content_type},
                        timeout=300,
                    )
                    payload = resp.content
                except Exception as e:
                    self._respond(502, json.dumps(
                        {"ok": False, "description": str(e)}).encode())
                    return
                # try to persist any Message in the response
                _try_persist_payload(payload)
                self._respond(resp.status_code, payload)
                return

            # ---------- form / JSON body ----------
            if content_type.startswith("application/json"):
                try:
                    body_data = json.loads(raw) if raw else {}
                except Exception:
                    body_data = {}
            else:
                body_data = {k: v[0] for k, v in
                            urllib.parse.parse_qs(raw.decode("utf-8", "ignore")).items()}
            params = {k: v[0] for k, v in qs.items()}
            params.update(body_data)

            # ---------- getUpdates: exclusive lock ----------
            if method == "getUpdates":
                if not acquire_getupdates_lock("api-server"):
                    holder = getupdates_lock_holder() or {}
                    err = json.dumps({
                        "ok": False,
                        "error_code": 503,
                        "description": f"getUpdates unavailable: lock held by "
                                    f"{holder.get('owner', '?')} "
                                    f"(pid {holder.get('pid', '?')}, "
                                    f"age {_fmt_age(holder.get('started', 0))})",
                    }).encode()
                    self._respond(503, err)
                    return
                try:
                    sess = requests.Session()
                    if _proxy:
                        sess.proxies = {"http": _proxy, "https": _proxy}
                    resp = sess.post(f"{bot.base_url}/{method}",
                                    data=params, timeout=90)
                    payload = resp.content
                    try:
                        js = resp.json()
                        if js.get("ok"):
                            _conn = sqlite3.connect(DB_FILE); db_init(_conn)
                            _latest_uid = None
                            for upd in js.get("result", []):
                                uid = upd.get("update_id", 0)
                                _latest_uid = uid
                                kind, obj = None, None
                                for k in ("message", "edited_message",
                                        "channel_post", "edited_channel_post",
                                        "managed_bot"):
                                    if k in upd:
                                        kind, obj = k, upd[k]; break
                                if obj is None:
                                    db_store_update(_conn, uid, "non-message", upd)
                                    continue
                                if kind == "managed_bot":
                                    db_store_update(_conn, uid, "managed_bot", upd)
                                    continue
                                db_store_update(_conn, uid, kind, upd)
                                _d = db_process_message(_conn, uid, kind, obj)
                                _record_mention_if_needed(_conn, _d, bot)
                            if _latest_uid is not None:
                                db_state_set(_conn, "offset", _latest_uid + 1)
                            _conn.commit()
                            _conn.close()
                    except Exception as e:
                        print(f"{Y}api-server persist warn: {e}{N}")
                    self._respond(resp.status_code, payload)
                finally:
                    release_getupdates_lock()
                return

            # ---------- all other methods ----------
            sess = requests.Session()
            if _proxy:
                sess.proxies = {"http": _proxy, "https": _proxy}
            try:
                resp = sess.post(f"{bot.base_url}/{method}",
                                data=params, timeout=120)
                payload = resp.content
                _try_persist_payload(payload)   # ← save bot's own messages
                self._respond(resp.status_code, payload)
            except Exception as e:
                self._respond(502, json.dumps(
                    {"ok": False, "description": str(e)}).encode())

        def log_message(self, *a, **k):
            pass

    try:
        httpd = http.server.ThreadingHTTPServer((host, port), Handler)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        _api_server_instance["httpd"] = httpd
        _api_server_instance["thread"] = t
        print(f"{G}✔ API server listening on http://{host}:{port}/bot<token>/<method>{N}")
        return True
    except Exception as e:
        print(f"{R}✘ Could not start API server: {e}{N}")
        return False


def _stop_api_server():
    httpd = _api_server_instance.get("httpd")
    if httpd:
        httpd.shutdown()
        _api_server_instance["httpd"] = None
        _api_server_instance["thread"] = None
        print(f"{G}✔ API server stopped{N}")
    else:
        print(f"{Y}Server not running{N}")


def start_api_server_menu(bot: TelegramBot):
    while True:
        cfg = load_config()
        running = _api_server_instance.get("httpd") is not None
        print(f"\n{B}--- API Server ---{N}")
        print(f"  Status : {'RUNNING' if running else 'stopped'}")
        print(f"  Host   : {cfg.get('api_server_host')}")
        print(f"  Port   : {cfg.get('api_server_port')}")
        print(f"  Token  : {'(bot token)' if not cfg.get('api_server_token') else cfg.get('api_server_token')[:12] + '...'}")
        print("  1) Start   2) Stop   3) Set host   4) Set port   5) Set token   0) Back")
        c = input("choice: ").strip()
        if c == "1":
            if _start_api_server(bot):
                cfg2 = load_config(); cfg2["api_server_enabled"] = True; save_config(cfg2)
        elif c == "2":
            _stop_api_server()
            cfg2 = load_config(); cfg2["api_server_enabled"] = False; save_config(cfg2)
        elif c == "3":
            cfg2 = load_config(); cfg2["api_server_host"] = input("host: ").strip(); save_config(cfg2)
        elif c == "4":
            cfg2 = load_config()
            try: cfg2["api_server_port"] = int(input("port: ").strip())
            except ValueError: pass
            save_config(cfg2)
        elif c == "5":
            cfg2 = load_config(); cfg2["api_server_token"] = input("token (empty=bot token): ").strip(); save_config(cfg2)
        elif c == "0":
            return

# ================================================================
#  Chat members (from DB) / Mentions / User info
# ================================================================
def _fetch_members(conn, chat_id: int) -> List[dict]:
    rows = conn.execute(
        """SELECT cu.user_id, cu.message_count, cu.last_seen_at,
                  e.first_name, e.last_name, e.username, e.is_bot
             FROM chat_users cu
             LEFT JOIN entities e ON e.id = cu.user_id
            WHERE cu.chat_id = ?
              AND (e.is_bot IS NULL OR e.is_bot = 0)
            ORDER BY cu.last_seen_at DESC""",
        (chat_id,)).fetchall()
    out = []
    for uid, cnt, seen, fn, ln, un, isb in rows:
        name = " ".join(p for p in [fn, ln] if p).strip() or "?"
        out.append({
            'user_id': uid, 'message_count': cnt, 'last_seen': seen,
            'first_name': fn, 'last_name': ln, 'username': un,
            'is_bot': bool(isb), 'name': name,
        })
    return out

def _pick_group_for_members(conn) -> Optional[int]:
    """Like _pick_chat_for_monitor but only lists groups/supergroups."""
    rows = conn.execute(
        """SELECT e.id, e.kind, e.title, e.first_name, e.last_name, e.username,
                  COUNT(DISTINCT cu.user_id) AS member_cnt,
                  MAX(cu.last_seen_at) AS last_seen,
                  (SELECT COUNT(*) FROM messages m WHERE m.chat_id = e.id) AS msg_cnt
             FROM entities e
             LEFT JOIN chat_users cu ON cu.chat_id = e.id
            WHERE e.kind IN ('group', 'supergroup')
            GROUP BY e.id
            ORDER BY last_seen DESC""").fetchall()

    print(f"\n{B}--- Groups / Supergroups in DB ---{N}")
    if not rows:
        print(f"{Y}No groups stored. Run Monitor / Silent fetch in a group first.{N}")
        return None

    for i, r in enumerate(rows, 1):
        cid, kind, title, fn, ln, un, mem_cnt, _ls, msg_cnt = r
        label = title or (fn and f"{fn} {ln or ''}".strip()) or str(cid)
        uname = f" @{un}" if un else ""
        ghost = f" {Y}⚠ ghost (use 54→5 to clean){N}" if msg_cnt == 0 else ""
        print(f"  {i:>3}) {label:<28} [{kind:<10}] "
              f"id={cid}  members={mem_cnt}  msgs={msg_cnt}{uname}{ghost}")

    print("    0) Back")
    sel = input("\nSelect group: ").strip()
    if not sel or sel == "0":
        return None
    if sel.isdigit() and 1 <= int(sel) <= len(rows):
        return rows[int(sel) - 1][0]
    print(f"{R}invalid selection{N}")
    return None

def chat_members_menu(bot: TelegramBot):
    conn = sqlite3.connect(DB_FILE); db_init(conn)
    try:
        target = _pick_group_for_members(conn)
        if target is None:
            return
        while True:
            members = _fetch_members(conn, target)
            print(f"\n{B}--- Members of chat {target} ({len(members)}) ---{N}")
            if not members:
                print(f"{Y}No members recorded for this group yet.{N}")
                print(f"{Y}Members are collected only from incoming messages — run{N}")
                print(f"{Y}Monitor / Silent fetch while members are talking, then retry.{N}")
            for i, m in enumerate(members, 1):
                uname = f"@{m['username']}" if m['username'] else "-"
                flag = " [bot]" if m['is_bot'] else ""
                print(f"  {i:>3}) id={m['user_id']:<14} {m['name']:<25} "
                      f"{uname:<20} msgs={m['message_count']:<5} "
                      f"last={m['last_seen']}{flag}")
            print("  d) Delete one   r) Reset all   e) Export JSON   0) Back")
            c = input("choice: ").strip().lower()
            if c == "0":
                return
            if c == "d":
                idx = input("row # to delete: ").strip()
                if idx.isdigit() and 1 <= int(idx) <= len(members):
                    uid = members[int(idx) - 1]['user_id']
                    if input(f"Remove user {uid} from chat {target}'s member list? "
                             f"[y/N]: ").strip().lower() == "y":
                        conn.execute("DELETE FROM chat_users WHERE chat_id=? AND user_id=?",
                                     (target, uid))
                        conn.commit()
                        print(f"{G}✔ Removed{N}")
            elif c == "r":
                if input(f"Reset ALL member records for chat {target}? [y/N]: "
                         ).strip().lower() == "y":
                    n = conn.execute("SELECT COUNT(*) FROM chat_users WHERE chat_id=?",
                                     (target,)).fetchone()[0]
                    conn.execute("DELETE FROM chat_users WHERE chat_id=?", (target,))
                    conn.commit()
                    print(f"{G}✔ Removed {n} record(s){N}")
            elif c == "e":
                fname = f"members_{abs(target)}_{int(time.time())}.json"
                out = [{"user_id": m['user_id'],
                        "first_name": m['first_name'], "last_name": m['last_name'],
                        "username": m['username'], "is_bot": m['is_bot'],
                        "message_count": m['message_count'],
                        "last_seen": m['last_seen']} for m in members]
                with open(fname, "w", encoding="utf-8") as f:
                    json.dump(out, f, indent=2, ensure_ascii=False)
                print(f"{G}✔ Saved {len(out)} member(s) to {fname}{N}")
    finally:
        conn.close()


def mention_members_menu(bot: TelegramBot):
    conn = sqlite3.connect(DB_FILE); db_init(conn)
    try:
        target = _pick_group_for_members(conn)
        if target is None:
            return
        members = _fetch_members(conn, target)
        if not members:
            print(f"{R}No members recorded. Run Monitor / Silent fetch first.{N}")
            return

        print(f"\n{B}--- Mention members of {target} ({len(members)} known) ---{N}")
        print("  1) All members")
        print("  2) From a list (ids/usernames, comma-separated, mixed OK)")
        print("  0) Back")
        c = input("choice: ").strip()
        if c == "0":
            return

        if c == "1":
            targets = members
        elif c == "2":
            raw = input("ids or @usernames (comma-separated): ").strip()
            wanted_ids, wanted_unames = set(), set()
            for tok in raw.split(","):
                tok = tok.strip().lstrip("@")
                if not tok:
                    continue
                if tok.lstrip('-').isdigit():
                    wanted_ids.add(int(tok))
                else:
                    wanted_unames.add(tok.lower())
            targets = [m for m in members
                       if m['user_id'] in wanted_ids
                       or (m['username'] and m['username'].lower() in wanted_unames)]
            print(f"{G}Matched {len(targets)} of {len(members)} known member(s){N}")
            if not targets:
                return
        else:
            return

        header = input("Header text (optional, empty = none): ").strip()
        reply_to = input("Reply to message_id (empty = no reply): ").strip()
        reply_chat = input("Reply-to chat_id (empty = same chat; for cross-chat): ").strip()
        bs = input("Max mentions per message (default 30): ").strip()
        try:
            batch_size = int(bs) if bs else 30
        except ValueError:
            batch_size = 30

        MAX_TEXT = 3800
        batches: List[List[str]] = []
        cur, cur_len = [], len(header) + 2 if header else 0
        for m in targets:
            uid = m['user_id']
            label = f"@{m['username']}" if m['username'] else (m['name'] or str(uid))
            frag = f'<a href="tg://user?id={uid}">{html.escape(label)}</a>'
            if cur and (len(cur) >= batch_size or cur_len + len(frag) + 2 > MAX_TEXT):
                batches.append(cur)
                cur, cur_len = [], 0
            cur.append(frag)
            cur_len += len(frag) + 2
        if cur:
            batches.append(cur)

        print(f"\n{G}Will send {len(targets)} mention(s) in {len(batches)} message(s).{N}")
        if input("Confirm? [y/N]: ").strip().lower() != "y":
            return

        ok = fail = 0
        for i, batch in enumerate(batches, 1):
            text = " ".join(batch)
            if header:
                text = f"{html.escape(header)}\n\n{text}"
            data = {"chat_id": str(target), "text": text, "parse_mode": "HTML"}
            if reply_to:
                if reply_chat:
                    src_val = (int(reply_chat)
                               if str(reply_chat).lstrip('-').isdigit()
                               else reply_chat)
                    try: msg_val = int(reply_to)
                    except ValueError: msg_val = reply_to
                    data["reply_parameters"] = json.dumps(
                        {"message_id": msg_val, "chat_id": src_val})
                else:
                    data["reply_to_message_id"] = reply_to
            r = bot.post("sendMessage", data=data, ask_retry=False)
            if r and r.get("ok"):
                _persist_from_resp(r)
                ok += 1
                mid = (r.get("result") or {}).get("message_id", "?")
                print(f"  {G}✔{N} batch {i}/{len(batches)} sent (msg_id={mid})")
                time.sleep(1)
            else:
                fail += 1
                desc = (r.get("description") if isinstance(r, dict) else "no response")
                print(f"  {R}✘{N} batch {i} failed: {desc}")

        print(f"\n{G}{'=' * 46}{N}")
        print(f"{G}  MENTION SUMMARY{N}")
        print(f"{G}{'=' * 46}{N}")
        print(f"  Members mentioned : {len(targets)}")
        print(f"  Messages sent     : {ok}")
        print(f"  Failed            : {fail}")
        print(f"{G}{'=' * 46}{N}")
    finally:
        conn.close()


def user_account_info(bot: TelegramBot):
    print(f"\n{B}--- User Account Info ---{N}")
    user_id = input("user_id (numeric): ").strip()
    if not user_id.lstrip('-').isdigit():
        print(f"{R}user_id must be numeric{N}")
        return

    # 1) profile photos
    print(f"\n{Y}>> getUserProfilePhotos ...{N}")
    r = bot.post("getUserProfilePhotos", data={"user_id": user_id, "limit": "1"})
    if r and r.get("ok"):
        photos = (r.get("result") or {}).get("photos") or []
        if photos:
            largest = max(photos[0], key=lambda p: p.get("file_size", 0))
            print(f"{G}✔ Latest profile photo:{N}")
            print(json.dumps(largest, indent=2, ensure_ascii=False))
        else:
            print(f"{Y}No profile photo set.{N}")
    else:
        desc = (r.get("description") if isinstance(r, dict) else "no response")
        print(f"{Y}⚠ getUserProfilePhotos failed: {desc}{N}")

    # 2) profile audios ("songs")
    print(f"\n{Y}>> getUserProfileAudios ...{N}")
    r = bot.post("getUserProfileAudios", data={"user_id": user_id, "limit": "10"})
    if r and r.get("ok"):
        audios = (r.get("result") or {}).get("audios") or []
        if audios:
            print(f"{G}✔ {len(audios)} profile audio(s):{N}")
            for a in audios:
                print(f"  🎵 {a.get('title', '?')} — {a.get('performer', '?')}")
                print(f"     file_id : {a.get('file_id')}")
                print(f"     duration: {a.get('duration', '?')}s")
        else:
            print(f"{Y}No profile audios.{N}")
    else:
        desc = (r.get("description") if isinstance(r, dict) else "no response")
        print(f"{Y}⚠ getUserProfileAudios not available (needs Bot API 7.0+): {desc}{N}")

    # 3) chat/account info (works if bot has ever chatted with them)
    print(f"\n{Y}>> getChat ...{N}")
    r = bot.post("getChat", data={"chat_id": user_id})
    if r and r.get("ok"):
        print(json.dumps(r["result"], indent=2, ensure_ascii=False))
    else:
        desc = (r.get("description") if isinstance(r, dict) else "no response")
        print(f"{Y}⚠ getChat failed: {desc}{N}")
        print(f"{Y}(bot must have an existing private chat with this user){N}")


def create_managed_bot_link(bot: TelegramBot):
    """Generate a shareable link that lets users create a managed bot."""
    print(f"\n{B}--- Create Managed Bot Invite Link ---{N}")
    suggested = input("Suggested username for new bot (e.g. MyCoolBot): ").strip().lstrip("@")
    if not suggested:
        print(f"{R}Username is required.{N}")
        return
    suggested_name = input("Suggested display name (optional): ").strip() or suggested
    manager_username = (bot.bot_info or {}).get("username", "")
    if not manager_username:
        me = bot.post("getMe", ask_retry=False)
        if me and me.get("ok"):
            manager_username = me["result"].get("username", "")
            bot.bot_info = me["result"]
    if not manager_username:
        print(f"{R}Could not determine manager bot username.{N}")
        return
    link = (
        f"https://t.me/newbot/{manager_username}/{suggested}"
        f"?name={urllib.parse.quote(suggested_name)}"
    )
    print(f"\n{G}✔ Link generated:{N}")
    print(f"  {link}")
    print(f"\n{Y}Share this link with users so they can create a bot managed by you.{N}")

def _set_base_url_menu(bot: TelegramBot):
    print(f"\n{B}--- Set Base URL ---{N}")
    cur = get_config_base_url() or "(default: https://api.telegram.org)"
    print(f"  Current: {cur}")
    new_base = input("New base URL (empty = default, 'c' = cancel): ").strip()
    if new_base.lower() == "c":
        return
    set_config_base_url(new_base)
    _root = (new_base or "https://api.telegram.org").rstrip("/")
    bot.base_url = f"{_root}/bot{bot.token}"
    bot.file_api = f"{_root}/file/bot{bot.token}"
    print(f"{G}✔ Base URL set to {_root}{N}")


def settings_menu(bot: TelegramBot):
    while True:
        clear_screen()
        header = [
            f"\n{G}=============== Settings & Config ==============={N}",
            "",
        ]
        groups = [
            ("Network", [
                (1, "Configure proxy / retry"),
                (2, "Set Base URL"),
            ]),
            ("Bot", [
                (3, "Manage bot token"),
                (4, "Manage reactions"),
            ]),
            ("Chat Behavior", [
                (5, "Lock / Unlock chat_id"),
                (6, "Toggle guest chat mode"),
            ]),
            ("Server", [
                (7, "API server"),
            ]),
        ]
        footer = ["", "  0) Back to main menu", ""]
        render_menu(header, groups, footer)

        choice = input("choice: ").strip()
        if not choice:
            continue
        if choice == "0":
            return

        actions = {
            "1": lambda: configure_proxy_menu(bot),
            "2": lambda: _set_base_url_menu(bot),
            "3": lambda: manage_bot_token_menu(bot),
            "4": lambda: manage_reactions_menu(),
            "5": lambda: chat_id_lock_menu(),
            "6": lambda: toggle_guest_chat_mode(),
            "7": lambda: start_api_server_menu(bot),
        }
        action = actions.get(choice)
        if not action:
            continue

        try:
            clear_screen()
            action()
        except KeyboardInterrupt:
            print(f"\n{Y}Cancelled.{N}")
        except Exception as e:
            print(f"{R}Error: {e}{N}")
        input(f"\n{Y}Press Enter to return...{N}")

def monitor_mode_locked(bot: TelegramBot):
    """Wrapper: acquire lock, run monitor_mode, release lock."""
    if not acquire_getupdates_lock("monitor"):
        print(f"\n{R}✘ Cannot start Monitor Mode{N}")
        print_lock_holder(prefix="  ")
        print(f"{Y}  Stop the other component first.{N}")
        return
    try:
        monitor_mode(bot)
    finally:
        release_getupdates_lock()


def silent_fetch_locked(bot: TelegramBot):
    """Wrapper: acquire lock, run silent_fetch, release lock."""
    if not acquire_getupdates_lock("silent-fetch"):
        print(f"\n{R}✘ Cannot start Silent Fetch{N}")
        print_lock_holder(prefix="  ")
        print(f"{Y}  Stop the other component first.{N}")
        return
    try:
        silent_fetch(bot)
    finally:
        release_getupdates_lock()

def main_menu(bot: TelegramBot):
    # Main menu structure — contiguous numbering, settings collapsed into #54.
    groups_def = [
        ("Send Messages", [
            (1, "Text message"), (2, "Photo"),
            (3, "Animation (GIF)"), (4, "Video"),
            (5, "Document / File"), (6, "Audio"),
            (7, "Voice"), (8, "Video note"),
            (9, "Sticker"), (10, "Location"),
            (11, "Contact"), (12, "Poll"),
            (13, "Dice"), (14, "Reaction"),
            (15, "Edit message"), (16, "Delete message"),
        ]),
        ("Chat Management", [
            (17, "Leave chat"), (18, "Get chat info"),
            (19, "Member count"), (20, "Pin message"),
            (21, "Unpin message"), (22, "Forward message"),
            (23, "Chat action"), (24, "Ban user"),
            (25, "Unban user"), (26, "Set chat title"),
            (27, "Set chat desc"), (28, "Set admin title"),
            (29, "Set bot name"), (30, "Create invite link"),
        ]),
        ("Bot Profile", [
            (31, "Bot info (getMe)"), (32, "Set bio (desc)"),
            (33, "Set short bio"), (34, "Set profile photo"),
            (35, "Remove photo"), (36, "Get current profile"),
        ]),
        ("Files", [
            (37, "Download by id"), (38, "Upload & get id"),
        ]),
        ("Monitor & Data", [
            (39, "Monitor mode"), (40, "Silent fetch"),
            (41, "Chat explorer"), (42, "History viewer"),
        ]),
        ("Admin & Members", [
            (43, "Member info"), (44, "Promote admin"),
            (45, "Demote admin"), (46, "Set user title"),
            (47, "Set member tag"), (48, "Chat members (DB)"),
            (49, "Mention members"), (50, "User account info"),
            (60, "User profile audios"),
        ]),
        ("Bot Management", [
            (51, "Bot management"), (52, "Managed bot link"),
            (53, "Purge DB data"),
        ]),
        ("Settings", [
            (54, "Settings & Config"),
        ]),
    ]

    actions = {
        "1":  lambda: send_message(bot),
        "2":  lambda: send_photo(bot),
        "3":  lambda: send_animation(bot),
        "4":  lambda: send_video(bot),
        "5":  lambda: send_document(bot),
        "6":  lambda: send_audio(bot),
        "7":  lambda: send_voice(bot),
        "8":  lambda: send_video_note(bot),
        "9":  lambda: send_sticker(bot),
        "10": lambda: send_location(bot),
        "11": lambda: send_contact(bot),
        "12": lambda: send_poll(bot),
        "13": lambda: send_dice(bot),
        "14": lambda: send_reaction(bot),
        "15": lambda: edit_message(bot),
        "16": lambda: delete_message(bot),
        "17": lambda: leave_chat(bot),
        "18": lambda: get_chat_info(bot),
        "19": lambda: get_chat_member_count(bot),
        "20": lambda: pin_message(bot),
        "21": lambda: unpin_message(bot),
        "22": lambda: forward_message(bot),
        "23": lambda: send_chat_action_cmd(bot),
        "24": lambda: ban_user(bot),
        "25": lambda: unban_user(bot),
        "26": lambda: set_chat_title(bot),
        "27": lambda: set_chat_description(bot),
        "28": lambda: set_admin_custom_title(bot),
        "29": lambda: set_bot_global_name(bot),
        "30": lambda: create_invite_link(bot),
        "31": lambda: show_bot_info(bot),
        "32": lambda: set_bot_description(bot),
        "33": lambda: set_bot_short_description(bot),
        "34": lambda: set_profile_photo(bot),
        "35": lambda: remove_profile_photo(bot),
        "36": lambda: get_bot_profile(bot),
        "37": lambda: download_file_by_id(bot),
        "38": lambda: upload_and_get_file_id(bot),
        "39": lambda: monitor_mode_locked(bot),
        "40": lambda: silent_fetch_locked(bot),
        "41": lambda: chat_explorer(bot),
        "42": lambda: chat_history_viewer(bot),
        "43": lambda: get_chat_member_info(bot),
        "44": lambda: promote_member(bot),
        "45": lambda: demote_member(bot),
        "46": lambda: set_user_custom_title(bot),
        "47": lambda: set_chat_member_tag(bot),
        "48": lambda: chat_members_menu(bot),
        "49": lambda: mention_members_menu(bot),
        "50": lambda: user_account_info(bot),
        "51": lambda: bot_management_mode(bot),
        "52": lambda: create_managed_bot_link(bot),
        "53": lambda: db_purge_menu(bot),
        "54": lambda: settings_menu(bot),
        "60": lambda: user_profile_audios_menu(bot),
    }

    while True:
        clear_screen()
        _lock = get_locked_chat_id() or "(none)"
        _guest = "ON" if get_guest_chat_mode() else "OFF"
        _api = "ON" if load_config().get("api_server_enabled") else "OFF"
        header = [
            f"\n{G}=============== Telegram Bot Sender ==============={N}",
            f"  {Y}Locked chat_id:{N} {_lock}   {Y}Guest:{N} {_guest}   {Y}API:{N} {_api}",
            "",
        ]
        footer = ["", "  0) Exit", ""]
        render_menu(header, groups_def, footer)

        choice = input("choice: ").strip()

        # 1) empty Enter → reload the menu (was: repeat last choice)
        if not choice:
            continue

        if choice == "0":
            print("Bye.")
            break

        action = actions.get(choice)
        # 2) invalid number → also reload
        if not action:
            continue

        # 3) clear before running the action
        try:
            clear_screen()
            action()
        except KeyboardInterrupt:
            print(f"\n{Y}Cancelled.{N}")
        except Exception as e:
            print(f"{R}Error: {e}{N}")

        # 4) pause before returning to main menu
        input(f"\n{Y}Press Enter to return to main menu...{N}")


# ================================================================
#  CLI mode (non-interactive)
# ================================================================
def _read_caption_arg(inline_caption: Optional[str],
                      caption_file: Optional[str]) -> str:
    """Return caption text either from --caption or from --caption-file."""
    if caption_file:
        if not os.path.isfile(caption_file):
            print(f"{R}caption file not found: {caption_file}{N}", file=sys.stderr)
            sys.exit(2)
        with open(caption_file, encoding="utf-8") as f:
            return f.read()
    return inline_caption or ""


def _cli_send_file(bot: TelegramBot, method: str, field: str,
                   chat_id: str, path: str, caption: str,
                   reply_to: Optional[int] = None,
                   parse_mode: Optional[str] = None,
                   reply_to_chat: Optional[str] = None) -> int:
    data = {"chat_id": chat_id}
    files = None
    if path and os.path.isfile(path):
        pf = ProgressFileReader(path)
        files = {field: (os.path.basename(path), open(path, "rb"), guess_mime(path))}
    elif path:
        data[field] = path  # file_id or URL
    if caption:
        data["caption"] = caption
    if reply_to is not None and reply_to_chat:
        src_val = int(reply_to_chat) if str(reply_to_chat).lstrip('-').isdigit() else reply_to_chat
        data["reply_parameters"] = json.dumps({
            "message_id": int(reply_to),
            "chat_id": src_val,
        })
    elif reply_to is not None:
        data["reply_to_message_id"] = str(reply_to)
    if parse_mode:
        data["parse_mode"] = parse_mode
    resp = bot.post(method, data=data, files=files, ask_retry=False)
    show_send_result(resp)
    return 0 if (resp and resp.get("ok")) else 1


def _read_text_arg(inline: Optional[str],
                   file_path: Optional[str]) -> Optional[str]:
    """Return text from inline arg or file. None if neither given."""
    if file_path:
        if not os.path.isfile(file_path):
            print(f"{R}text file not found: {file_path}{N}", file=sys.stderr)
            return None
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    return inline

def _send_ok(resp) -> int:
    show_send_result(resp)
    return 0 if (resp and resp.get("ok")) else 1

# ================================================================
#  Web UI (browser client) — CLI-only
# ================================================================
def _make_web_handler(bot: TelegramBot, password: str,
                      session_ttl: int, cache_max_mb: int,
                      web_dir: str):
    """Build a BaseHTTPRequestHandler subclass with closures over config+db."""

    login_attempts: Dict[str, List[float]] = {}
    rate_lock = threading.Lock()

    download_locks: Dict[str, threading.Lock] = {}
    download_lock = threading.Lock()

    db_lock = threading.Lock()

    recent_sends: Dict[str, float] = {}
    recent_lock = threading.Lock()
    RECENT_TTL = 2.0

    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "cache", "files")
    os.makedirs(cache_dir, exist_ok=True)

    # ---------------- helpers ----------------
    def _check_rate(ip: str) -> bool:
        now = time.time()
        with rate_lock:
            attempts = [t for t in login_attempts.get(ip, []) if now - t < 60]
            login_attempts[ip] = attempts
            if len(attempts) >= 5:
                return False
            attempts.append(now)
            return True

    def _make_session(ip: str, ua: str) -> Tuple[str, str]:
        session = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        now = db_utcnow()
        exp_str = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() + session_ttl,
            tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        with db_lock:
            conn = sqlite3.connect(DB_FILE)
            conn.execute(
                "INSERT INTO web_sessions "
                "(token, csrf_token, created_at, expires_at, ip, user_agent) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (session, csrf, now, exp_str, ip, ua[:200]))
            conn.commit()
            conn.close()
        return session, csrf

    def _get_session(cookie_header: str) -> Optional[dict]:
        if not cookie_header:
            return None
        cookies = {}
        for part in cookie_header.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                cookies[k.strip()] = v.strip()
        token = cookies.get("session")
        if not token:
            return None
        with db_lock:
            conn = sqlite3.connect(DB_FILE)
            row = conn.execute(
                "SELECT csrf_token, expires_at FROM web_sessions WHERE token = ?",
                (token,)).fetchone()
            conn.close()
        if not row:
            return None
        if row[1] < db_utcnow():
            return None
        return {"token": token, "csrf": row[0]}

    def _delete_session(token: str):
        with db_lock:
            conn = sqlite3.connect(DB_FILE)
            conn.execute("DELETE FROM web_sessions WHERE token = ?", (token,))
            conn.commit()
            conn.close()

    def _list_chats() -> List[dict]:
        with db_lock:
            conn = sqlite3.connect(DB_FILE)
            rows = conn.execute(
                "SELECT m.chat_id, COUNT(*) cnt, MAX(m.date) last_date, "
                "       e.title, e.first_name, e.last_name, e.username, e.kind "
                "  FROM messages m "
                "  LEFT JOIN entities e ON e.id = m.chat_id "
                " GROUP BY m.chat_id "
                " ORDER BY last_date DESC").fetchall()
            conn.close()
        out = []
        for cid, cnt, last, title, fn, ln, un, kind in rows:
            label = title or (fn and f"{fn} {ln or ''}".strip()) or str(cid)
            out.append({
                "chat_id": cid, "title": label, "kind": kind,
                "message_count": cnt, "last_date": last,
                "username": un,
            })
        return out

    def _get_messages(chat_id: int, limit: int = 50,
                      before: Optional[int] = None) -> List[dict]:
        with db_lock:
            conn = sqlite3.connect(DB_FILE)
            if before is not None:
                rows = conn.execute(
                    "SELECT m.message_id, m.date, m.from_user_id, m.content_type, "
                    "       m.text, m.caption, m.reply_to_message_id, "
                    "       e.first_name, e.last_name, e.username, e.is_bot, "
                    "       m.raw_json "
                    "  FROM messages m "
                    "  LEFT JOIN entities e ON e.id = m.from_user_id "
                    " WHERE m.chat_id = ? AND m.message_id < ? "
                    " ORDER BY m.date DESC LIMIT ?",
                    (chat_id, before, limit)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT m.message_id, m.date, m.from_user_id, m.content_type, "
                    "       m.text, m.caption, m.reply_to_message_id, "
                    "       e.first_name, e.last_name, e.username, e.is_bot, "
                    "       m.raw_json "
                    "  FROM messages m "
                    "  LEFT JOIN entities e ON e.id = m.from_user_id "
                    " WHERE m.chat_id = ? "
                    " ORDER BY m.date DESC LIMIT ?",
                    (chat_id, limit)).fetchall()

                        # batch-lookup replied messages for preview
            reply_ids = {r[6] for r in rows if r[6]}
            reply_lookup = {}
            if reply_ids:
                placeholders = ",".join("?" * len(reply_ids))
                reply_rows = conn.execute(
                    f"SELECT m.message_id, m.from_user_id, m.text, m.caption, "
                    f"       m.content_type, e.first_name, e.last_name, "
                    f"       e.username, e.is_bot "
                    f"  FROM messages m "
                    f"  LEFT JOIN entities e ON e.id = m.from_user_id "
                    f" WHERE m.chat_id = ? AND m.message_id IN ({placeholders})",
                    [chat_id] + list(reply_ids)).fetchall()
                for rmid, ruid, rtext, rcap, rctype, rfn, rln, run, risb in reply_rows:
                    rname = " ".join(p for p in [rfn, rln] if p).strip() or "?"
                    reply_lookup[rmid] = {
                        "message_id": rmid,
                        "from_id": ruid,
                        "from_name": rname,
                        "from_username": run,
                        "is_bot": bool(risb),
                        "content_type": rctype,
                        "text": (rtext or rcap or "")[:200],
                    }

            msgs = []
            # Read the latest reactions from the message_reactions table
            _reactions_map = {}
            if rows:
                _msg_ids = [r[0] for r in rows]
                _placeholders = ",".join("?" * len(_msg_ids))
                _rx_rows = conn.execute(
                    f"SELECT message_id, new_reactions "
                    f"  FROM message_reactions "
                    f" WHERE chat_id = ? AND message_id IN ({_placeholders}) "
                    f" ORDER BY changed_at DESC",
                    [chat_id] + _msg_ids
                ).fetchall()
                for _rmid, _new_rx_json in _rx_rows:
                    if _rmid not in _reactions_map and _new_rx_json:
                        try:
                            _rx_list = json.loads(_new_rx_json)
                            _reactions_map[_rmid] = [
                                {"emoji": _r.get("emoji", ""),
                                 "count": _r.get("total_count", 1)}
                                for _r in _rx_list if _r.get("type") == "emoji"
                            ]
                        except Exception:
                            pass
            for mid, dt, uid, ctype, text, cap, reply, fn, ln, un, isb, raw_json_val in rows:
                files = conn.execute(
                    "SELECT file_type, file_unique_id, file_id, file_name, "
                    "       mime_type, file_size "
                    "  FROM message_files WHERE chat_id = ? AND message_id = ?",
                    (chat_id, mid)).fetchall()
                name = " ".join(p for p in [fn, ln] if p).strip() or "?"
                _reactions_out = []
                if raw_json_val:
                    try:
                        _payload = json.loads(raw_json_val)
                        _msg_obj = _payload.get("message") or {}
                        for _r in (_msg_obj.get("reactions") or []):
                            _rt = _r.get("type") or {}
                            _em = _rt.get("emoji") if _rt.get("type") == "emoji" else ""
                            _cnt = _r.get("total_count", 0)
                            if _em and _cnt > 0:
                                _reactions_out.append(
                                    {"emoji": _em, "count": _cnt})
                    except Exception:
                        pass
                if not _reactions_out and mid in _reactions_map:
                    _reactions_out = _reactions_map[mid]

                _msg_entities = []
                _forward_info = None
                if raw_json_val:
                    try:
                        _pl = json.loads(raw_json_val)
                        _mo = _pl.get("message") or {}
                        _msg_entities = (
                            _mo.get("entities")
                            or _mo.get("caption_entities")
                            or [])
                        _fo = _mo.get("forward_origin")
                        if _fo:
                            _ft = _fo.get("type")
                            if _ft == "user":
                                _su = _fo.get("sender_user") or {}
                                _forward_info = {
                                    "type": "user",
                                    "name": " ".join(
                                        p for p in [
                                            _su.get("first_name"),
                                            _su.get("last_name")]
                                        if p).strip() or "?",
                                    "username": _su.get("username"),
                                    "id": _su.get("id"),
                                }
                            elif _ft == "hidden_user":
                                _forward_info = {
                                    "type": "hidden_user",
                                    "name": _fo.get("sender_user_name") or "Unknown",
                                }
                            elif _ft == "chat":
                                _sc = _fo.get("sender_chat") or {}
                                _forward_info = {
                                    "type": "chat",
                                    "name": _sc.get("title") or "?",
                                    "username": _sc.get("username"),
                                    "id": _sc.get("id"),
                                }
                            elif _ft == "channel":
                                _ch = _fo.get("chat") or {}
                                _forward_info = {
                                    "type": "channel",
                                    "name": _ch.get("title") or "?",
                                    "username": _ch.get("username"),
                                    "id": _ch.get("id"),
                                }
                        else:
                            # legacy pre-Bot-API-7.0 fields
                            _ff = _mo.get("forward_from")
                            _ffc = _mo.get("forward_from_chat")
                            _ffsn = _mo.get("forward_sender_name")
                            if _ff:
                                _forward_info = {
                                    "type": "user",
                                    "name": " ".join(
                                        p for p in [
                                            _ff.get("first_name"),
                                            _ff.get("last_name")]
                                        if p).strip() or "?",
                                    "username": _ff.get("username"),
                                    "id": _ff.get("id"),
                                }
                            elif _ffc:
                                _forward_info = {
                                    "type": "channel",
                                    "name": _ffc.get("title") or "?",
                                    "username": _ffc.get("username"),
                                    "id": _ffc.get("id"),
                                }
                            elif _ffsn:
                                _forward_info = {
                                    "type": "hidden_user",
                                    "name": _ffsn,
                                }
                    except Exception:
                        _msg_entities = []

                _sender_status = None
                if uid is not None:
                    try:
                        _ar = conn.execute(
                            "SELECT status, custom_title, is_anonymous "
                            "  FROM chat_admins "
                            " WHERE chat_id = ? AND user_id = ?",
                            (chat_id, uid)).fetchone()
                        if _ar:
                            _sender_status = {
                                "status": _ar[0] or "member",
                                "custom_title": _ar[1],
                                "is_anonymous": bool(_ar[2]),
                            }
                    except Exception:
                        pass

                msgs.append({
                    "message_id": mid, "date": dt, "from_id": uid,
                    "from_name": name, "from_username": un,
                    "is_bot": bool(isb),
                    "content_type": ctype, "text": text, "caption": cap,
                    "reply_to_message_id": reply,
                    "reply_preview": reply_lookup.get(reply),
                    "reactions": _reactions_out,
                    "entities": _msg_entities,
                    "sender_status": _sender_status,
                    "forward_from": _forward_info,
                    "files": [
                        {"type": ft, "unique_id": fuid, "file_id": fid,
                         "name": fname, "mime": mime, "size": sz}
                        for ft, fuid, fid, fname, mime, sz in files
                    ],
                })
            conn.close()
        return list(reversed(msgs))

    def _serve_file_cached(file_unique_id: str) -> Optional[bytes]:
        cache_path = os.path.join(cache_dir, file_unique_id)

        # 1) disk cache hit
        if os.path.isfile(cache_path):
            with db_lock:
                conn = sqlite3.connect(DB_FILE)
                conn.execute(
                    "UPDATE file_cache SET last_accessed_at = ?, "
                    "access_count = access_count + 1 "
                    "WHERE file_unique_id = ?",
                    (db_utcnow(), file_unique_id))
                conn.commit()
                conn.close()
            with open(cache_path, "rb") as f:
                return f.read()

        # 2) one lock per file to prevent duplicate downloads
        with download_lock:
            if file_unique_id not in download_locks:
                download_locks[file_unique_id] = threading.Lock()
            lock = download_locks[file_unique_id]

        with lock:
            if os.path.isfile(cache_path):
                with open(cache_path, "rb") as f:
                    return f.read()

            with db_lock:
                conn = sqlite3.connect(DB_FILE)
                row = conn.execute(
                    "SELECT file_id, file_size FROM message_files "
                    "WHERE file_unique_id = ? LIMIT 1",
                    (file_unique_id,)).fetchone()
                conn.close()
            if not row:
                return None
            file_id, expected_size = row

            if expected_size and expected_size > cache_max_mb * 1024 * 1024:
                return None

            resp = bot.post("getFile", data={"file_id": file_id},
                            ask_retry=False)
            if not resp or not resp.get("ok"):
                return None
            file_path = resp["result"]["file_path"]
            url = f"{bot.file_api}/{file_path}"

            tmp = cache_path + ".part"
            try:
                r = bot.session.get(url, timeout=120, stream=True)
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(65536):
                        f.write(chunk)
                os.replace(tmp, cache_path)
            except Exception:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
                return None

            with db_lock:
                conn = sqlite3.connect(DB_FILE)
                conn.execute(
                    "INSERT OR REPLACE INTO file_cache "
                    "(file_unique_id, file_id, file_path, file_size, "
                    " downloaded_at, last_accessed_at, access_count) "
                    "VALUES (?, ?, ?, ?, ?, ?, 1)",
                    (file_unique_id, file_id, cache_path,
                     os.path.getsize(cache_path),
                     db_utcnow(), db_utcnow()))
                conn.commit()
                conn.close()

            with open(cache_path, "rb") as f:
                return f.read()

    # ---------------- handler ----------------
    class Handler(http.server.BaseHTTPRequestHandler):

        def _safe_write(self, body: bytes) -> bool:
            """Write to client; return False if the connection was closed."""
            try:
                self.wfile.write(body)
                return True
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return False

        def _json(self, code: int, obj: dict):
            body = json.dumps(obj, ensure_ascii=False).encode()
            try:
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return
            self._safe_write(body)

        def _error(self, code: int, msg: str):
            self._json(code, {"ok": False, "error": msg})

        def _session(self) -> Optional[dict]:
            return _get_session(self.headers.get("Cookie", ""))

        def _require_session(self) -> Optional[dict]:
            s = self._session()
            if not s:
                self._error(401, "unauthorized")
                return None
            return s

        def _require_csrf(self, session: dict) -> bool:
            tok = self.headers.get("X-CSRF-Token", "")
            if not hmac.compare_digest(tok.encode(), session["csrf"].encode()):
                self._error(403, "csrf")
                return False
            return True

        def _read_json(self) -> Optional[dict]:
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if n == 0:
                    return {}
                return json.loads(self.rfile.read(n))
            except Exception:
                return None

        # ---------- routing ----------
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)

            if path == "/api/health":
                self._json(200, {"ok": True})
                return

            if path.startswith("/static/"):
                self._serve_static(path[len("/static/"):])
                return

            if path in ("/", "/index.html"):
                self._serve_index()
                return

            if path == "/api/me":
                session = self._require_session()
                if not session:
                    return
                me = bot.bot_info or {}
                self._json(200, {
                    "ok": True,
                    "id": me.get("id"),
                    "username": me.get("username"),
                    "first_name": me.get("first_name"),
                    "csrf_token": session["csrf"],
                })
                return

            if path == "/api/poller/status":
                if not self._require_session():
                    return
                self._json(200, {"ok": True,
                                 "running": _is_web_poller_running()})
                return



            m = re.match(r"^/api/chats/(-?\d+)/info$", path)
            if m:
                if not self._require_session():
                    return
                _cid = int(m.group(1))
                _chat_resp = bot.post("getChat", data={"chat_id": str(_cid)},
                                      ask_retry=False)
                if not _chat_resp or not _chat_resp.get("ok"):
                    _d = ((_chat_resp.get("description")
                           if isinstance(_chat_resp, dict) else None)
                          or "no response")
                    self._error(502, _d)
                    return
                _info = _chat_resp.get("result") or {}
                _mc = None
                try:
                    _c_mc = bot.post("getChatMemberCount",
                                     data={"chat_id": str(_cid)},
                                     ask_retry=False)
                    if _c_mc and _c_mc.get("ok"):
                        _mc = _c_mc.get("result")
                except Exception:
                    pass
                _cached_members = 0
                try:
                    _c_info = sqlite3.connect(DB_FILE)
                    _cached_members = _c_info.execute(
                        "SELECT COUNT(*) FROM chat_users WHERE chat_id = ?",
                        (_cid,)).fetchone()[0]
                    _c_info.close()
                except Exception:
                    pass
                _photo_uid = None
                _ph = _info.get("photo") or {}
                if _ph:
                    _photo_uid = _ph.get("big_file_unique_id") or \
                                 _ph.get("small_file_unique_id")
                self._json(200, {
                    "ok": True,
                    "info": _info,
                    "member_count": _mc,
                    "members_cached": _cached_members,
                    "photo_unique_id": _photo_uid,
                })
                return

            m = re.match(r"^/api/chats/(-?\d+)/members$", path)
            if m:
                if not self._require_session():
                    return
                _cid = int(m.group(1))
                _mm = []
                try:
                    _c_m = sqlite3.connect(DB_FILE)
                    _rows = _c_m.execute(
                        "SELECT cu.user_id, cu.message_count, cu.last_seen_at, "
                        "       e.first_name, e.last_name, e.username, e.is_bot "
                        "  FROM chat_users cu "
                        "  LEFT JOIN entities e ON e.id = cu.user_id "
                        " WHERE cu.chat_id = ? "
                        "   AND (e.is_bot IS NULL OR e.is_bot = 0) "
                        " ORDER BY cu.last_seen_at DESC",
                        (_cid,)).fetchall()
                    _c_m.close()
                    for _uid, _cnt, _seen, _fn, _ln, _un, _isb in _rows:
                        _name = " ".join(p for p in [_fn, _ln] if p).strip() or "?"
                        _mm.append({
                            "user_id": _uid,
                            "first_name": _fn,
                            "last_name": _ln,
                            "username": _un,
                            "name": _name,
                            "message_count": _cnt,
                            "last_seen_at": _seen,
                            "is_bot": bool(_isb),
                        })
                except Exception as e:
                    self._error(500, str(e))
                    return
                self._json(200, {"ok": True, "members": _mm})
                return


            m = re.match(r"^/api/users/(-?\d+)/profile$", path)
            if m:
                if not self._require_session():
                    return
                _puid = int(m.group(1))
                _pchat = qs.get("chat_id", [None])[0]
                _prof = {
                    "ok": True, "user_id": _puid,
                    "first_name": None, "last_name": None,
                    "username": None, "is_bot": False,
                    "language_code": None,
                    "has_photo": False,
                    "message_count": None,
                    "first_seen_at": None, "last_seen_at": None,
                }
                try:
                    _cp = sqlite3.connect(DB_FILE)
                    _er = _cp.execute(
                        "SELECT first_name, last_name, username, is_bot, "
                        "       language_code "
                        "  FROM entities WHERE id = ?",
                        (_puid,)).fetchone()
                    if _er:
                        (_prof["first_name"], _prof["last_name"],
                         _prof["username"], _prof["is_bot"],
                         _prof["language_code"]) = _er
                        _prof["is_bot"] = bool(_prof["is_bot"])
                    _ph = _cp.execute(
                        "SELECT file_path FROM user_photos "
                        " WHERE user_id = ?", (_puid,)).fetchone()
                    if _ph and _ph[0] and os.path.isfile(_ph[0]):
                        _prof["has_photo"] = True
                    if _pchat is not None:
                        try:
                            _pcid = int(_pchat)
                            _cr = _cp.execute(
                                "SELECT message_count, first_seen_at, "
                                "       last_seen_at "
                                "  FROM chat_users "
                                " WHERE chat_id = ? AND user_id = ?",
                                (_pcid, _puid)).fetchone()
                            if _cr:
                                (_prof["message_count"],
                                 _prof["first_seen_at"],
                                 _prof["last_seen_at"]) = _cr
                        except (ValueError, TypeError):
                            pass
                    _cp.close()
                except Exception as _e:
                    self._error(500, str(_e))
                    return
                self._json(200, _prof)
                return

            m = re.match(r"^/api/chats/(-?\d+)/admins$", path)
            if m:
                if not self._require_session():
                    return
                _acid = int(m.group(1))
                _refresh = qs.get("refresh", ["0"])[0] == "1"
                _use_cache = not _refresh
                _cached = []
                if _use_cache:
                    try:
                        _ca = sqlite3.connect(DB_FILE)
                        _cutoff = db_utcnow()[:13]  # coarse hourly check
                        _rows = _ca.execute(
                            "SELECT user_id, status, custom_title, "
                            "       is_anonymous, updated_at "
                            "  FROM chat_admins WHERE chat_id = ?",
                            (_acid,)).fetchall()
                        _ca.close()
                        for _uid, _st, _ct, _ia, _up in _rows:
                            _cached.append({
                                "user_id": _uid,
                                "status": _st,
                                "custom_title": _ct,
                                "is_anonymous": bool(_ia),
                                "updated_at": _up,
                            })
                        if _cached:
                            _latest = max(x["updated_at"] for x in _cached)
                            if _latest[:13] == _cutoff:
                                self._json(200, {"ok": True,
                                                 "admins": _cached,
                                                 "cached": True})
                                return
                    except Exception:
                        pass

                _resp = bot.post("getChatAdministrators",
                                 data={"chat_id": str(_acid)},
                                 ask_retry=False)
                if not _resp or not _resp.get("ok"):
                    if _cached:
                        self._json(200, {"ok": True, "admins": _cached,
                                         "cached": True,
                                         "stale": True})
                    else:
                        _d = ((_resp.get("description")
                               if isinstance(_resp, dict) else None)
                              or "no response")
                        self._error(502, _d)
                    return
                _admins = []
                try:
                    _ca = sqlite3.connect(DB_FILE)
                    _ca.execute("DELETE FROM chat_admins WHERE chat_id = ?",
                                (_acid,))
                    for _a in (_resp.get("result") or []):
                        _u = _a.get("user") or {}
                        _uid = _u.get("id")
                        if _uid is None:
                            continue
                        _entry = {
                            "user_id": _uid,
                            "status": _a.get("status"),
                            "custom_title": _a.get("custom_title"),
                            "is_anonymous": bool(_a.get("is_anonymous", False)),
                        }
                        _admins.append(_entry)
                        _ca.execute(
                            "INSERT OR REPLACE INTO chat_admins "
                            "(chat_id, user_id, status, custom_title, "
                            " is_anonymous, updated_at) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (_acid, _uid, _entry["status"],
                             _entry["custom_title"],
                             1 if _entry["is_anonymous"] else 0,
                             db_utcnow()))
                    _ca.commit()
                    _ca.close()
                except Exception:
                    pass
                self._json(200, {"ok": True, "admins": _admins,
                                 "cached": False})
                return

            if path == "/api/reactions":
                if not self._require_session():
                    return
                try:
                    _usage = {}
                    _c = sqlite3.connect(DB_FILE)
                    for _u_emoji, _u_count, _u_last in _c.execute(
                            "SELECT emoji, count, last_used_at "
                            "  FROM reaction_usage").fetchall():
                        _usage[_u_emoji] = (_u_count, _u_last)
                    _c.close()
                except Exception:
                    _usage = {}

                try:
                    _rs = []
                    for _e, _l in load_reactions():
                        _cnt, _last = _usage.get(_e, (0, ""))
                        _rs.append({
                            "emoji": _e, "label": _l,
                            "count": _cnt, "last_used_at": _last,
                        })
                except Exception:
                    _rs = []

                # most-used first; among ties, most-recently-used first;
                # never-used keep original order (stable sort)
                _rs.sort(key=lambda r: r["last_used_at"] or "",
                         reverse=True)
                _rs.sort(key=lambda r: -r["count"])

                self._json(200, {"ok": True, "reactions": _rs})
                return

            if path == "/api/chats/all":
                if not self._require_session():
                    return
                _all_c = []
                try:
                    _ca = sqlite3.connect(DB_FILE)
                    _rows = _ca.execute(
                        "SELECT e.id, e.kind, e.title, e.first_name, "
                        "       e.last_name, e.username, "
                        "       (SELECT COUNT(*) FROM messages m "
                        "         WHERE m.chat_id = e.id) AS cnt "
                        "  FROM entities e "
                        " WHERE e.kind IN "
                        "       ('private','group','supergroup','channel') "
                        " ORDER BY e.last_seen_at DESC").fetchall()
                    _ca.close()
                    for _eid, _kind, _title, _fn, _ln, _un, _cnt in _rows:
                        _lbl = (_title
                                or " ".join(p for p in [_fn, _ln]
                                            if p).strip()
                                or str(_eid))
                        _all_c.append({
                            "chat_id": _eid,
                            "kind": _kind,
                            "title": _lbl,
                            "username": _un,
                            "message_count": _cnt,
                        })
                except Exception as _e:
                    self._error(500, str(_e))
                    return
                self._json(200, {"ok": True, "chats": _all_c})
                return

            m = re.match(r"^/api/chats/(-?\d+)/photo$", path)
            if m:
                if not self._require_session():
                    return
                _cid = int(m.group(1))
                _cav_dir = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "cache", "chat_avatars")
                _path, _mime = _fetch_chat_photo(bot, _cid, _cav_dir)
                if not _path:
                    self._error(404, "no photo")
                    return
                try:
                    with open(_path, "rb") as _f:
                        _data = _f.read()
                except Exception:
                    self._error(500, "read failed")
                    return
                self.send_response(200)
                self.send_header("Content-Type", _mime or "image/jpeg")
                self.send_header("Content-Length", str(len(_data)))
                self.send_header(
                    "Cache-Control", "private, max-age=86400, immutable")
                self.end_headers()
                self._safe_write(_data)
                return

            # --- saved media: list ---
            if path == "/api/media/saved":
                if not self._require_session():
                    return
                _mt = qs.get("type", ["all"])[0]
                _fav = qs.get("fav", ["0"])[0] == "1"
                _rows = []
                try:
                    _cm = sqlite3.connect(DB_FILE)
                    _where = []
                    _params = []
                    if _mt in ("sticker", "animation"):
                        _where.append("media_type = ?")
                        _params.append(_mt)
                    if _fav:
                        _where.append("is_favorite = 1")
                    _sql = "SELECT id, media_type, file_id, file_unique_id, " \
                           "       emoji, set_name, file_name, saved_at, " \
                           "       is_favorite, use_count " \
                           "  FROM saved_media"
                    if _where:
                        _sql += " WHERE " + " AND ".join(_where)
                    _sql += " ORDER BY is_favorite DESC, use_count DESC, " \
                            "          saved_at DESC"
                    for _r in _cm.execute(_sql, _params).fetchall():
                        _rows.append({
                            "id": _r[0], "media_type": _r[1],
                            "file_id": _r[2], "file_unique_id": _r[3],
                            "emoji": _r[4], "set_name": _r[5],
                            "file_name": _r[6], "saved_at": _r[7],
                            "is_favorite": bool(_r[8]),
                            "use_count": _r[9] or 0,
                        })
                    _cm.close()
                except Exception as _e:
                    self._error(500, str(_e))
                    return
                self._json(200, {"ok": True, "items": _rows})
                return

            # --- saved media: preview ---
            m = re.match(r"^/api/media/saved/(\d+)/preview$", path)
            if m:
                if not self._require_session():
                    return
                _sid = int(m.group(1))
                try:
                    _cm = sqlite3.connect(DB_FILE)
                    _r = _cm.execute(
                        "SELECT file_id, file_unique_id, "
                        "       thumbnail_file_id, media_type "
                        "  FROM saved_media WHERE id = ?",
                        (_sid,)).fetchone()
                    _cm.close()
                except Exception:
                    _r = None
                if not _r:
                    self._error(404, "not found")
                    return
                _row = {
                    "file_id": _r[0], "file_unique_id": _r[1],
                    "thumbnail_file_id": _r[2],
                    "media_type": _r[3],
                }
                _sav_dir = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "cache", "saved_media")
                _data = _serve_saved_media_preview(bot, _row, _sav_dir)
                if _data is None:
                    self._error(404, "preview unavailable")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/webp")
                self.send_header("Content-Length", str(len(_data)))
                self.send_header(
                    "Cache-Control", "private, max-age=86400, immutable")
                self.end_headers()
                self._safe_write(_data)
                return

            if path == "/api/mentions/unseen":
                if not self._require_session():
                    return
                _mc = sqlite3.connect(DB_FILE)
                try:
                    _rows = _mc.execute(
                        "SELECT chat_id, COUNT(*) as cnt, "
                        "       MAX(message_id) as latest "
                        "  FROM mention_flags WHERE seen = 0 "
                        " GROUP BY chat_id "
                        " ORDER BY latest DESC").fetchall()
                except Exception as _e:
                    _mc.close()
                    self._error(500, str(_e))
                    return
                _mc.close()
                _chats = []
                for _cid, _cnt, _latest in _rows:
                    _chats.append({
                        "chat_id": _cid, "count": _cnt,
                        "latest_message_id": _latest,
                    })
                self._json(200, {"ok": True, "chats": _chats})
                return

            m = re.match(r"^/api/chats/(-?\d+)/mentions$", path)
            if m:
                if not self._require_session():
                    return
                _mcid = int(m.group(1))
                _mc = sqlite3.connect(DB_FILE)
                try:
                    _rows = _mc.execute(
                        "SELECT id, message_id, kind, from_user_id, "
                        "       created_at, seen "
                        "  FROM mention_flags WHERE chat_id = ? "
                        " ORDER BY message_id ASC").fetchall()
                except Exception as _e:
                    _mc.close()
                    self._error(500, str(_e))
                    return
                _mc.close()
                _items = [{
                    "id": r[0], "message_id": r[1], "kind": r[2],
                    "from_user_id": r[3], "created_at": r[4],
                    "seen": bool(r[5]),
                } for r in _rows]
                self._json(200, {"ok": True, "mentions": _items})
                return

            if path == "/api/chats":
                if not self._require_session():
                    return
                self._json(200, {"ok": True, "chats": _list_chats()})
                return


            m = re.match(r"^/api/users/(-?\d+)/photo$", path)
            if m:
                if not self._require_session():
                    return
                _uid = int(m.group(1))
                _avatar_dir = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "cache", "avatars")
                _path, _mime = _fetch_user_photo(bot, _uid, _avatar_dir)
                if not _path:
                    self._error(404, "no photo")
                    return
                try:
                    with open(_path, "rb") as _f:
                        _data = _f.read()
                except Exception:
                    self._error(500, "read failed")
                    return
                self.send_response(200)
                self.send_header("Content-Type", _mime or "image/jpeg")
                self.send_header("Content-Length", str(len(_data)))
                self.send_header(
                    "Cache-Control", "private, max-age=86400, immutable")
                self.end_headers()
                self._safe_write(_data)
                return

            m = re.match(r"^/api/chats/(-?\d+)/messages$", path)
            if m:
                if not self._require_session():
                    return
                cid = int(m.group(1))
                try:
                    limit = int(qs.get("limit", ["50"])[0])
                except ValueError:
                    limit = 50
                limit = max(1, min(limit, 200))
                before = None
                if "before" in qs:
                    try:
                        before = int(qs["before"][0])
                    except ValueError:
                        pass
                self._json(200, {"ok": True,
                                 "messages": _get_messages(cid, limit, before)})
                return

            m = re.match(r"^/api/files/([A-Za-z0-9_\-]+)$", path)
            if m:
                if not self._require_session():
                    return
                fuid = m.group(1)
                data = _serve_file_cached(fuid)
                if data is None:
                    self._error(404, "file not found or too large")
                    return
                with db_lock:
                    conn = sqlite3.connect(DB_FILE)
                    meta = conn.execute(
                        "SELECT mime_type, file_name, file_type "
                        "  FROM message_files "
                        " WHERE file_unique_id = ? LIMIT 1",
                        (fuid,)).fetchone()
                    conn.close()
                mime = (meta[0] if meta and meta[0]
                        else "application/octet-stream")
                fname = _derive_filename(
                    fuid,
                    meta[1] if meta else None,
                    meta[0] if meta else None,
                    meta[2] if meta else None)
                is_download = "download" in qs
                disp = "attachment" if is_download else "inline"
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Disposition",
                                 f'{disp}; filename="{fname}"')
                # file_unique_id is a stable content hash → cache forever
                self.send_header(
                    "Cache-Control", "private, max-age=31536000, immutable")
                self.send_header("ETag", f'"{fuid}"')
                self.end_headers()
                self.wfile.write(data)
                return

            self._error(404, "not found")

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            # ---------- login (no auth required) ----------
            if path == "/api/login":
                ip = self.client_address[0]
                if not _check_rate(ip):
                    self._error(429, "too many attempts")
                    return
                body = self._read_json()
                if body is None or "password" not in body:
                    self._error(400, "password required")
                    return
                if not hmac.compare_digest(
                        str(body["password"]).encode(), password.encode()):
                    self._error(401, "invalid password")
                    return
                ua = self.headers.get("User-Agent", "")
                session, csrf = _make_session(ip, ua)
                body_out = json.dumps(
                    {"ok": True, "csrf_token": csrf}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header(
                    "Set-Cookie",
                    f"session={session}; HttpOnly; SameSite=Strict; "
                    f"Path=/; Max-Age={session_ttl}")
                self.send_header("Content-Length", str(len(body_out)))
                self.end_headers()
                self.wfile.write(body_out)
                return

            # ---------- everything below requires auth ----------
            session = self._require_session()
            if not session:
                return

            if path == "/api/logout":
                if not self._require_csrf(session):
                    return
                _delete_session(session["token"])
                body = b'{"ok":true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Set-Cookie",
                                 "session=; HttpOnly; Max-Age=0; Path=/")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self._safe_write(body)
                return

            if path == "/api/poller/start":
                if not self._require_csrf(session):
                    return
                _start_web_poller(bot, 2, 30)
                self._json(200, {"ok": True, "running": True})
                return

            if path == "/api/poller/stop":
                if not self._require_csrf(session):
                    return
                _stop_web_poller()
                self._json(200, {"ok": True, "running": False})
                return

            # --- saved media: add ---
            if path == "/api/media/saved":
                if not self._require_csrf(session):
                    return
                _b = self._read_json()
                if not _b:
                    self._error(400, "invalid json")
                    return

                _file_id = _b.get("file_id")
                _fuid = _b.get("file_unique_id")
                _mt = _b.get("media_type")
                _thumb = _b.get("thumbnail_file_id")
                _emoji = _b.get("emoji")
                _set = _b.get("set_name")
                _fname = _b.get("file_name")

                if not _file_id and _b.get("chat_id") is not None \
                        and _b.get("message_id") is not None:
                    try:
                        _cm = sqlite3.connect(DB_FILE)
                        _row = _cm.execute(
                            "SELECT file_type, file_id, file_unique_id, "
                            "       thumbnail_file_id, emoji, set_name, "
                            "       file_name "
                            "  FROM message_files "
                            " WHERE chat_id = ? AND message_id = ? "
                            "   AND file_type IN ('sticker', 'animation') "
                            " LIMIT 1",
                            (int(_b["chat_id"]), int(_b["message_id"]))
                        ).fetchone()
                        _cm.close()
                        if not _row:
                            self._error(404, "no sticker/animation in message")
                            return
                        _mt, _file_id, _fuid, _thumb, _emoji, _set, _fname = _row
                    except Exception as _e:
                        self._error(500, str(_e))
                        return

                if not _file_id or not _fuid or _mt not in (
                        "sticker", "animation"):
                    self._error(400, "file_id, file_unique_id, "
                                     "media_type required "
                                     "(media_type: sticker|animation)")
                    return

                try:
                    _cm = sqlite3.connect(DB_FILE)
                    _cm.execute(
                        "INSERT OR REPLACE INTO saved_media "
                        "(media_type, file_id, file_unique_id, "
                        " thumbnail_file_id, emoji, set_name, file_name, "
                        " saved_at, is_favorite, use_count) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, "
                        "        COALESCE((SELECT is_favorite FROM saved_media "
                        "                   WHERE file_unique_id = ?), 0), "
                        "        COALESCE((SELECT use_count FROM saved_media "
                        "                   WHERE file_unique_id = ?), 0))",
                        (_mt, _file_id, _fuid, _thumb, _emoji, _set,
                         _fname, db_utcnow(), _fuid, _fuid))
                    _cm.commit()
                    _new_id = _cm.execute(
                        "SELECT id FROM saved_media WHERE file_unique_id = ?",
                        (_fuid,)).fetchone()
                    _cm.close()
                    self._json(200, {"ok": True,
                                     "id": _new_id[0] if _new_id else None})
                except Exception as _e:
                    self._error(500, str(_e))
                return

            # --- saved media: send ---
            m = re.match(r"^/api/media/saved/(\d+)/send$", path)
            if m:
                if not self._require_csrf(session):
                    return
                _sid = int(m.group(1))
                _b = self._read_json()
                if not _b or "chat_id" not in _b:
                    self._error(400, "chat_id required")
                    return
                try:
                    _cm = sqlite3.connect(DB_FILE)
                    _r = _cm.execute(
                        "SELECT media_type, file_id FROM saved_media "
                        " WHERE id = ?", (_sid,)).fetchone()
                    if not _r:
                        _cm.close()
                        self._error(404, "media not found")
                        return
                    _mt, _fid = _r
                    _cm.execute(
                        "UPDATE saved_media SET use_count = use_count + 1 "
                        " WHERE id = ?", (_sid,))
                    _cm.commit()
                    _cm.close()
                except Exception as _e:
                    self._error(500, str(_e))
                    return
                _method = ("sendSticker" if _mt == "sticker"
                           else "sendAnimation")
                _field = _mt
                _data = {"chat_id": str(_b["chat_id"]), _field: _fid}
                if _b.get("reply_to"):
                    _data["reply_to_message_id"] = str(_b["reply_to"])
                _resp = bot.post(_method, data=_data, ask_retry=False)
                if _resp and _resp.get("ok"):
                    try:
                        _persist_from_resp(_resp)
                    except Exception:
                        pass
                    _mid = (_resp.get("result") or {}).get("message_id")
                    self._json(200, {"ok": True, "message_id": _mid})
                else:
                    _d = ((_resp.get("description")
                           if isinstance(_resp, dict) else None)
                          or "no response")
                    self._error(502, _d)
                return

            # --- saved media: favorite toggle ---
            m = re.match(r"^/api/media/saved/(\d+)/favorite$", path)
            if m:
                if not self._require_csrf(session):
                    return
                _sid = int(m.group(1))
                try:
                    _cm = sqlite3.connect(DB_FILE)
                    _cm.execute(
                        "UPDATE saved_media SET is_favorite = "
                        "  CASE is_favorite WHEN 1 THEN 0 ELSE 1 END "
                        " WHERE id = ?", (_sid,))
                    _cm.commit()
                    _r = _cm.execute(
                        "SELECT is_favorite FROM saved_media WHERE id = ?",
                        (_sid,)).fetchone()
                    _cm.close()
                    if not _r:
                        self._error(404, "not found")
                        return
                    self._json(200, {"ok": True,
                                     "is_favorite": bool(_r[0])})
                except Exception as _e:
                    self._error(500, str(_e))
                return

            m = re.match(r"^/api/mentions/(\d+)/seen$", path)
            if m:
                if not self._require_csrf(session):
                    return
                _mid = int(m.group(1))
                _mc = sqlite3.connect(DB_FILE)
                try:
                    _mc.execute(
                        "UPDATE mention_flags SET seen = 1 WHERE id = ?",
                        (_mid,))
                    _mc.commit()
                finally:
                    _mc.close()
                self._json(200, {"ok": True})
                return

            m = re.match(r"^/api/chats/(-?\d+)/mentions/seen$", path)
            if m:
                if not self._require_csrf(session):
                    return
                _mcid = int(m.group(1))
                _mc = sqlite3.connect(DB_FILE)
                try:
                    _cur = _mc.execute(
                        "UPDATE mention_flags SET seen = 1 "
                        " WHERE chat_id = ? AND seen = 0",
                        (_mcid,))
                    _n = _cur.rowcount
                    _mc.commit()
                finally:
                    _mc.close()
                self._json(200, {"ok": True, "marked": _n})
                return

            m = re.match(r"^/api/chats/(-?\d+)/send$", path)
            if m:
                if not self._require_csrf(session):
                    return
                cid = m.group(1)
                body = self._read_json()
                if body is None or "text" not in body:
                    self._error(400, "text required")
                    return
                # dedupe: same chat + same body within 2 seconds = ignore
                import hashlib
                _sig = hashlib.sha256(
                    json.dumps(body, sort_keys=True).encode()
                ).hexdigest()
                _key = f"{cid}:{_sig}"
                _now = time.time()
                with recent_lock:
                    last = recent_sends.get(_key, 0)
                    recent_sends[_key] = _now
                    # prune
                    for k in [k for k, v in recent_sends.items()
                              if _now - v > RECENT_TTL * 4]:
                        recent_sends.pop(k, None)
                if _now - last < RECENT_TTL:
                    self._json(200, {"ok": True, "duplicate": True,
                                     "message_id": None})
                    return
                data = {"chat_id": cid, "text": str(body["text"])}
                if "reply_parameters" in body and isinstance(
                        body["reply_parameters"], dict):
                    data["reply_parameters"] = json.dumps(
                        body["reply_parameters"], ensure_ascii=False)
                elif "reply_to" in body:
                    data["reply_to_message_id"] = str(body["reply_to"])
                r = bot.post("sendMessage", data=data, ask_retry=False)
                if r and r.get("ok"):
                    _persist_from_resp(r)
                    mid = (r.get("result") or {}).get("message_id")
                    self._json(200, {"ok": True, "message_id": mid})
                else:
                    desc = ((r.get("description")
                             if isinstance(r, dict) else None)
                            or "no response")
                    self._error(502, desc)
                return


            m = re.match(r"^/api/chats/(-?\d+)/mention$", path)
            if m:
                if not self._require_csrf(session):
                    return
                _cid = int(m.group(1))
                _b = self._read_json()
                if _b is None:
                    self._error(400, "invalid json")
                    return
                _text = str(_b.get("text") or "").strip()
                _all = bool(_b.get("all"))
                _ids = _b.get("user_ids") or []
                _bs = int(_b.get("batch_size") or 30)
                _rmid = _b.get("reply_to")

                _targets = []
                try:
                    _cm = sqlite3.connect(DB_FILE)
                    if _all:
                        _rows = _cm.execute(
                            "SELECT cu.user_id, e.first_name, e.last_name, e.username "
                            "  FROM chat_users cu "
                            "  LEFT JOIN entities e ON e.id = cu.user_id "
                            " WHERE cu.chat_id = ? "
                            "   AND (e.is_bot IS NULL OR e.is_bot = 0)",
                            (_cid,)).fetchall()
                        for _uid, _fn, _ln, _un in _rows:
                            _nm = " ".join(p for p in [_fn, _ln] if p).strip() or "?"
                            _targets.append({
                                "user_id": _uid,
                                "name": _nm,
                                "username": _un,
                            })
                    elif _ids:
                        _ph = ",".join("?" * len(_ids))
                        _rows = _cm.execute(
                            f"SELECT cu.user_id, e.first_name, e.last_name, e.username "
                            f"  FROM chat_users cu "
                            f"  LEFT JOIN entities e ON e.id = cu.user_id "
                            f" WHERE cu.chat_id = ? AND cu.user_id IN ({_ph})",
                            [_cid] + list(_ids)).fetchall()
                        for _uid, _fn, _ln, _un in _rows:
                            _nm = " ".join(p for p in [_fn, _ln] if p).strip() or "?"
                            _targets.append({
                                "user_id": _uid,
                                "name": _nm,
                                "username": _un,
                            })
                    _cm.close()
                except Exception as e:
                    self._error(500, str(e))
                    return

                if not _targets:
                    self._json(200, {"ok": True, "mentioned": 0,
                                     "messages_sent": 0, "failed": 0})
                    return

                _ok, _fail = _batch_mention(
                    bot, _cid, _targets, _text,
                    reply_msg_id=(int(_rmid) if _rmid else None),
                    batch_size=_bs)
                self._json(200, {
                    "ok": True,
                    "mentioned": len(_targets),
                    "messages_sent": _ok,
                    "failed": _fail,
                })
                return

            m = re.match(r"^/api/chats/(-?\d+)/upload$", path)
            if m:
                if not self._require_csrf(session):
                    return
                _cid = int(m.group(1))
                _ct = self.headers.get("Content-Type", "")
                if not _ct.startswith("multipart/form-data"):
                    self._error(400, "expected multipart/form-data")
                    return
                _bm = re.search(r"boundary=([^;]+)", _ct)
                if not _bm:
                    self._error(400, "missing boundary")
                    return
                _bnd = _bm.group(1).strip('"').encode()
                try:
                    _n = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    _n = 0
                if _n <= 0:
                    self._error(400, "empty body")
                    return
                if _n > 50 * 1024 * 1024:
                    self._error(413, "file too large (max 50 MB)")
                    return
                try:
                    _body = self.rfile.read(_n)
                    _parts = _parse_multipart(_body, _bnd)
                except Exception as e:
                    self._error(400, f"parse failed: {e}")
                    return

                _kind = (_parts.get("kind") or "document").strip()
                _caption = _parts.get("caption") or ""
                _file = _parts.get("file")
                if not _file or not isinstance(_file, tuple):
                    self._error(400, "no file")
                    return
                _fname, _fdata, _fmime = _file

                _methods = {
                    "photo": ("sendPhoto", "photo"),
                    "video": ("sendVideo", "video"),
                    "document": ("sendDocument", "document"),
                    "audio": ("sendAudio", "audio"),
                    "voice": ("sendVoice", "voice"),
                    "animation": ("sendAnimation", "animation"),
                    "sticker": ("sendSticker", "sticker"),
                    "video_note": ("sendVideoNote", "video_note"),
                }
                if _kind not in _methods:
                    self._error(400, f"unknown kind: {_kind}")
                    return
                _method, _field = _methods[_kind]

                _data = {"chat_id": str(_cid)}
                if _caption:
                    _data["caption"] = _caption
                _files = {_field: (_fname, _fdata, _fmime or
                                   "application/octet-stream")}
                _r = bot.post(_method, data=_data, files=_files,
                              ask_retry=False)
                if _r and _r.get("ok"):
                    try:
                        _persist_from_resp(_r)
                    except Exception:
                        pass
                    _mid = (_r.get("result") or {}).get("message_id")
                    self._json(200, {"ok": True, "message_id": _mid})
                else:
                    _d = ((_r.get("description")
                           if isinstance(_r, dict) else None)
                          or "no response")
                    self._error(502, _d)
                return

            m = re.match(
                r"^/api/chats/(-?\d+)/messages/(-?\d+)/react$", path)
            if m:
                if not self._require_csrf(session):
                    return
                _rcid, _rmid = m.group(1), m.group(2)
                _rbody = self._read_json()
                if _rbody is None:
                    self._error(400, "invalid json")
                    return
                _emoji = _rbody.get("emoji")
                if _emoji is None or _emoji == "" or _emoji is False:
                    _rx_list = []
                    _rx_emoji = None
                else:
                    _emoji_s = str(_emoji).strip()
                    if not _emoji_s:
                        _rx_list = []
                        _rx_emoji = None
                    else:
                        _rx_list = [{"type": "emoji", "emoji": _emoji_s}]
                        _rx_emoji = _emoji_s
                _rdata = {
                    "chat_id": str(_rcid),
                    "message_id": str(_rmid),
                    "reaction": json.dumps(_rx_list, ensure_ascii=False),
                }
                _rr = bot.post("setMessageReaction", data=_rdata,
                               ask_retry=False)
                if _rr and _rr.get("ok"):
                    if _rx_emoji:
                        try:
                            _cu = sqlite3.connect(DB_FILE)
                            _cu.execute(
                                "INSERT INTO reaction_usage "
                                "(emoji, count, last_used_at) "
                                "VALUES (?, 1, ?) "
                                "ON CONFLICT(emoji) DO UPDATE SET "
                                "count = count + 1, "
                                "last_used_at = excluded.last_used_at",
                                (_rx_emoji, db_utcnow()))
                            _cu.commit()
                            _cu.close()
                        except Exception:
                            pass
                    try:
                        _pc = sqlite3.connect(DB_FILE)
                        _prev_row = _pc.execute(
                            "SELECT new_reactions FROM message_reactions "
                            " WHERE chat_id = ? AND message_id = ? "
                            "   AND user_id = ? "
                            " ORDER BY changed_at DESC LIMIT 1",
                            (int(_rcid), int(_rmid),
                             bot.bot_id)).fetchone()
                        _prev_rx = []
                        if _prev_row and _prev_row[0]:
                            try:
                                _prev_rx = json.loads(_prev_row[0])
                            except Exception:
                                _prev_rx = []
                        _new_rx = ([{"type": "emoji", "emoji": _rx_emoji}]
                                   if _rx_emoji else [])
                        _pc.execute(
                            "INSERT INTO message_reactions "
                            "(chat_id, message_id, user_id, actor_chat_id, "
                            " old_reactions, new_reactions, is_anonymous, "
                            " changed_at, first_seen_at) "
                            "VALUES (?, ?, ?, NULL, ?, ?, 0, ?, ?)",
                            (int(_rcid), int(_rmid), bot.bot_id,
                             json.dumps(_prev_rx, ensure_ascii=False),
                             json.dumps(_new_rx, ensure_ascii=False),
                             int(time.time()), db_utcnow()))
                        _apply_reaction_delta(
                            _pc, int(_rcid), int(_rmid),
                            _prev_rx, _new_rx)
                        _pc.commit()
                        _pc.close()
                    except Exception as _e:
                        try:
                            print(f"warn: reaction persist: {_e}")
                        except Exception:
                            pass
                    self._json(200, {"ok": True, "reaction": _rx_emoji})
                else:
                    _rd = ((_rr.get("description")
                            if isinstance(_rr, dict) else None)
                           or "no response")
                    self._error(502, _rd)
                return

            m = re.match(r"^/api/chats/(-?\d+)/forward$", path)
            if m:
                if not self._require_csrf(session):
                    return
                src = m.group(1)
                body = self._read_json()
                if not body or "to_chat_id" not in body or \
                        "message_id" not in body:
                    self._error(400, "to_chat_id and message_id required")
                    return
                r = bot.post("forwardMessage", data={
                    "chat_id": str(body["to_chat_id"]),
                    "from_chat_id": src,
                    "message_id": str(body["message_id"]),
                }, ask_retry=False)
                if r and r.get("ok"):
                    _persist_from_resp(r)
                    self._json(200, {"ok": True})
                else:
                    desc = ((r.get("description")
                             if isinstance(r, dict) else None)
                            or "no response")
                    self._error(502, desc)
                return

            self._error(404, "not found")

        # ---------- static files ----------
        def _serve_index(self):
            idx = os.path.join(web_dir, "index.html")
            if not os.path.isfile(idx):
                self._error(500, "index.html missing")
                return
            with open(idx, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_static(self, rel: str):
            safe = os.path.normpath(
                os.path.join(web_dir, rel.lstrip("/")))
            if not safe.startswith(web_dir + os.sep):
                self._error(403, "forbidden")
                return
            if not os.path.isfile(safe):
                self._error(404, "not found")
                return
            ext = os.path.splitext(safe)[1].lower()
            mime = {
                ".css": "text/css", ".js": "application/javascript",
                ".html": "text/html", ".svg": "image/svg+xml",
                ".png": "image/png", ".ico": "image/x-icon",
                ".json": "application/json",
            }.get(ext, "application/octet-stream")
            with open(safe, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type",
                             mime + ("; charset=utf-8"
                                     if mime.startswith("text") else ""))
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass  # silence per-request noise

        def handle_one_request(self):
            try:
                super().handle_one_request()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    return Handler

def _derive_filename(file_unique_id: str, file_name: Optional[str],
                     mime_type: Optional[str],
                     file_type: Optional[str]) -> str:
    """Best-effort filename with proper extension for downloads."""
    # 1. file_name already has extension → use as-is
    if file_name and os.path.splitext(file_name)[1]:
        return file_name

    ext_by_type = {
        "photo": ".jpg", "sticker": ".webp", "animation": ".mp4",
        "video": ".mp4", "video_note": ".mp4", "voice": ".ogg",
        "audio": ".mp3", "document": ".bin",
    }
    ext_by_mime = {
        "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
        "image/webp": ".webp", "video/mp4": ".mp4", "video/webm": ".webm",
        "audio/mpeg": ".mp3", "audio/mp4": ".m4a", "audio/ogg": ".ogg",
        "audio/x-wav": ".wav", "application/pdf": ".pdf",
        "application/zip": ".zip",
    }

    ext = ""
    if mime_type:
        ext = ext_by_mime.get(mime_type, "")
    if not ext:
        ext = ext_by_type.get(file_type or "", ".bin")

    base = file_name or f"{file_type or 'file'}_{file_unique_id}"
    return os.path.splitext(base)[0] + ext

_web_poller_state = {"thread": None, "stop_event": None}

def _web_poller_thread(bot: TelegramBot, interval: int, timeout: int,
                       stop_event: threading.Event):
    try:
        try:
            conn = sqlite3.connect(DB_FILE)
            db_init(conn)
            offset = int(db_state_get(conn, "offset", "0") or "0")
            conn.close()
        except Exception as e:
            print(f"{Y}web poller: could not read offset: {e}{N}")
            return

        while not stop_event.is_set():
            try:
                resp = bot.get("getUpdates", params={
                    "offset": offset, "limit": 100, "timeout": timeout,
                    "allowed_updates": [
                        "message", "edited_message",
                        "channel_post", "edited_channel_post",
                        "message_reaction", "message_reaction_count",
                        "managed_bot",
                    ],
                }, ask_retry=False)
                if not resp or not resp.get("ok"):
                    stop_event.wait(interval)
                    continue

                updates = resp.get("result", [])
                if not updates:
                    continue

                conn = sqlite3.connect(DB_FILE)
                db_init(conn)
                for upd in updates:
                    uid = upd.get("update_id", 0)
                    offset = uid + 1
                    if "message_reaction" in upd:
                        _handle_reaction_update(conn, upd["message_reaction"])
                        db_store_update(conn, uid, "message_reaction", upd)
                        continue
                    if "message_reaction_count" in upd:
                        _handle_reaction_count_update(
                            conn, upd["message_reaction_count"])
                        db_store_update(conn, uid, "message_reaction_count", upd)
                        continue
                    kind, obj = None, None
                    for k in ("message", "edited_message",
                              "channel_post", "edited_channel_post",
                              "managed_bot"):
                        if k in upd:
                            kind, obj = k, upd[k]
                            break
                    if obj is None:
                        db_store_update(conn, uid, "non-message", upd)
                        continue
                    if kind == "managed_bot":
                        db_store_update(conn, uid, "managed_bot", upd)
                        continue
                    db_store_update(conn, uid, kind, upd)
                    _descr = db_process_message(conn, uid, kind, obj)
                    _record_mention_if_needed(conn, _descr, bot)
                db_state_set(conn, "offset", offset)
                conn.commit()
                conn.close()
            except Exception as e:
                if stop_event.is_set():
                    break
                print(f"{Y}web poller error: {e}{N}")
                stop_event.wait(interval * 2)
    finally:
        # lock is released when the thread exits
        if _lock_owner == "web-poller":
            release_getupdates_lock()


def _start_web_poller(bot: TelegramBot, interval: int = 2,
                      timeout: int = 30) -> bool:
    if _web_poller_state["thread"] and _web_poller_state["thread"].is_alive():
        return True
    if not acquire_getupdates_lock("web-poller"):
        print(f"{Y}⚠ Web poller: lock held by "
              f"{(getupdates_lock_holder() or {}).get('owner', '?')}{N}")
        return False
    stop_event = threading.Event()
    t = threading.Thread(
        target=_web_poller_thread,
        args=(bot, interval, timeout, stop_event),
        daemon=True,
        name="web-poller")
    t.start()
    _web_poller_state.update({"thread": t, "stop_event": stop_event})
    return True


def _stop_web_poller() -> bool:
    if _web_poller_state["stop_event"]:
        _web_poller_state["stop_event"].set()
    # don't release here — the thread does it in its finally block
    _web_poller_state.update({"thread": None, "stop_event": None})
    return True

def _is_web_poller_running() -> bool:
    t = _web_poller_state["thread"]
    return bool(t and t.is_alive())

# ================================================================
#  User avatars (profile photos) — cached on disk
# ================================================================
_avatar_locks = {}
_avatar_locks_guard = threading.Lock()


def _get_avatar_lock(user_id):
    with _avatar_locks_guard:
        if user_id not in _avatar_locks:
            _avatar_locks[user_id] = threading.Lock()
        return _avatar_locks[user_id]

def user_profile_audios_menu(bot: TelegramBot):
    """Browse + download a user's profile songs.
       After listing, type the number of a song to download it directly."""
    print(f"\n{B}--- User Profile Audios ---{N}")
    user_id = input("user_id (numeric): ").strip()
    if not user_id.lstrip('-').isdigit():
        print(f"{R}user_id must be numeric{N}")
        return

    print(f"{Y}>> getUserProfileAudios ...{N}")
    r = bot.post("getUserProfileAudios",
                 data={"user_id": user_id, "limit": "100"})
    if not r or not r.get("ok"):
        desc = (r.get("description") if isinstance(r, dict) else "no response")
        print(f"{R}✘ Failed: {desc}{N}")
        return

    audios = (r.get("result") or {}).get("audios") or []
    if not audios:
        print(f"{Y}No profile audios.{N}")
        return

    # choose output dir once
    out_dir = input(f"output dir [default: .]: ").strip() or "."
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception as e:
        print(f"{R}✘ Cannot create {out_dir}: {e}{N}")
        return

    while True:
        print(f"\n{B}--- {len(audios)} profile audio(s) ---{N}")
        for i, a in enumerate(audios, 1):
            print(f"  {i:>3}) 🎵 {a.get('title', '?')} "
                  f"— {a.get('performer', '?')}")
            print(f"       duration={a.get('duration', '?')}s  "
                  f"size={a.get('file_size', '?')}B")
        print(f"\n  {Y}type a number to download that song{N}")
        print("  a) Download all   j) Export JSON   0) Back")

        c = input("choice: ").strip().lower()

        if c == "0":
            return

        # ---- number → download directly ----
        if c.isdigit():
            idx = int(c)
            if 1 <= idx <= len(audios):
                a = audios[idx - 1]
                _download_by_file_id(bot, a.get("file_id"), a, out_dir)
            else:
                print(f"{R}invalid number (1..{len(audios)}){N}")
            continue

        if c == "j":
            fname = f"audios_{user_id}_{int(time.time())}.json"
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(audios, f, indent=2, ensure_ascii=False)
            print(f"{G}✔ Saved {len(audios)} audio metadata to {fname}{N}")
            continue

        if c == "a":
            print(f"{Y}Downloading {len(audios)} file(s) to {out_dir} ...{N}")
            ok = fail = 0
            for i, a in enumerate(audios, 1):
                print(f"  [{i}/{len(audios)}] {a.get('title', '?')}")
                if _download_by_file_id(bot, a.get("file_id"), a, out_dir):
                    ok += 1
                else:
                    fail += 1
            print(f"\n{G}✔ Done: {ok} saved, {fail} failed → {out_dir}{N}")
            continue

        print(f"{R}unknown choice (type a number, a, j, or 0){N}")

def _fetch_user_photo(bot, user_id, cache_dir):
    """Return (local_path, mime) for the user's current profile photo.
       Fetches via getUserProfilePhotos -> getFile -> download (cached on disk).
       Returns (None, None) if the user has no photo or the fetch fails."""
    with _get_avatar_lock(user_id):
        conn = sqlite3.connect(DB_FILE)
        try:
            row = conn.execute(
                "SELECT file_path FROM user_photos WHERE user_id = ?",
                (user_id,)).fetchone()
            if row and row[0] and os.path.isfile(row[0]):
                return row[0], "image/jpeg"
        finally:
            conn.close()

        resp = bot.post("getUserProfilePhotos",
                        data={"user_id": str(user_id), "limit": "1"},
                        ask_retry=False)
        if not resp or not resp.get("ok"):
            return None, None

        photos = (resp.get("result") or {}).get("photos") or []
        if not photos:
            return None, None

        largest = max(photos[0], key=lambda p: p.get("file_size", 0))
        file_id = largest.get("file_id")
        fuid = largest.get("file_unique_id") or "p"
        if not file_id:
            return None, None

        f = bot.post("getFile", data={"file_id": file_id}, ask_retry=False)
        if not f or not f.get("ok"):
            return None, None
        file_path = f["result"].get("file_path")
        if not file_path:
            return None, None

        url = f"{bot.file_api}/{file_path}"
        os.makedirs(cache_dir, exist_ok=True)
        local = os.path.join(cache_dir, f"{user_id}_{fuid}.jpg")
        tmp = local + ".part"
        try:
            r = bot.session.get(url, timeout=60, stream=True)
            r.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(65536):
                    fh.write(chunk)
            os.replace(tmp, local)
        except Exception:
            try:
                os.remove(tmp)
            except Exception:
                pass
            return None, None

        conn = sqlite3.connect(DB_FILE)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO user_photos "
                "(user_id, file_unique_id, file_id, file_path, file_size, "
                " fetched_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, fuid, file_id, local,
                 os.path.getsize(local),
                 db_utcnow(), db_utcnow()))
            conn.commit()
        finally:
            conn.close()
        return local, "image/jpeg"




# ================================================================
#  Web helpers: multipart parsing + batched mentions
# ================================================================
def _parse_multipart(body: bytes, boundary: bytes):
    """Very small multipart/form-data parser (text fields + file parts)."""
    parts = {}
    delimiter = b"--" + boundary
    segments = body.split(delimiter)
    for seg in segments:
        if seg.startswith(b"\r\n"):
            seg = seg[2:]
        if seg.endswith(b"\r\n"):
            seg = seg[:-2]
        if not seg or seg in (b"--", b""):
            continue
        if b"\r\n\r\n" not in seg:
            continue
        hb, data = seg.split(b"\r\n\r\n", 1)
        headers = {}
        for line in hb.split(b"\r\n"):
            if b":" in line:
                k, v = line.split(b":", 1)
                headers[k.strip().lower().decode()] = v.strip().decode()
        disp = headers.get("content-disposition", "")
        nm = re.search(r'name="([^"]+)"', disp)
        fm = re.search(r'filename="([^"]+)"', disp)
        if not nm:
            continue
        name = nm.group(1)
        if fm:
            parts[name] = (fm.group(1), data,
                           headers.get("content-type",
                                       "application/octet-stream"))
        else:
            parts[name] = data.decode("utf-8", "replace")
    return parts


def _batch_mention(bot, chat_id, targets, header_text,
                   reply_msg_id=None, batch_size=30):
    """Send HTML <a tg://user> mentions in batches. Returns (ok, fail)."""
    import html as _html
    MAX_TEXT = 3800
    batches, cur, cur_len = [], [], len(header_text) + 2 if header_text else 0
    for m in targets:
        uid = m["user_id"]
        label = (f"@{m['username']}" if m.get("username")
                 else (m.get("name") or str(uid)))
        frag = f'<a href="tg://user?id={uid}">{_html.escape(label)}</a>'
        if cur and (len(cur) >= batch_size
                    or cur_len + len(frag) + 2 > MAX_TEXT):
            batches.append(cur)
            cur, cur_len = [], 0
        cur.append(frag)
        cur_len += len(frag) + 2
    if cur:
        batches.append(cur)

    ok = fail = 0
    for batch in batches:
        body = " ".join(batch)
        if header_text:
            body = f"{_html.escape(header_text)}\n\n{body}"
        data = {"chat_id": str(chat_id), "text": body,
                "parse_mode": "HTML"}
        if reply_msg_id:
            data["reply_to_message_id"] = str(reply_msg_id)
        r = bot.post("sendMessage", data=data, ask_retry=False)
        if r and r.get("ok"):
            ok += 1
            try:
                from termgram import _persist_from_resp  # noqa
            except Exception:
                pass
            try:
                _persist_from_resp(r)
            except Exception:
                pass
        else:
            fail += 1
    return ok, fail




def _apply_reaction_delta(conn, chat_id, message_id, old_rx, new_rx):
    """Update a message's raw_json reactions array to reflect a delta.
       old_rx: list of {type,emoji} being removed (may be empty)
       new_rx: list of {type,emoji} being added  (may be empty)
       This keeps raw_json as the single source of truth for reactions."""
    try:
        row = conn.execute(
            "SELECT raw_json FROM messages "
            " WHERE chat_id = ? AND message_id = ?",
            (chat_id, message_id)).fetchone()
        if not row or not row[0]:
            return
        payload = json.loads(row[0])
        msg_obj = payload.get("message") or {}
        rx_arr = msg_obj.get("reactions") or []

        for old in (old_rx or []):
            if isinstance(old, dict) and old.get("type") == "emoji":
                emoji = old.get("emoji")
                for r in rx_arr:
                    rt = r.get("type") or {}
                    if rt.get("type") == "emoji" and rt.get("emoji") == emoji:
                        r["total_count"] = r.get("total_count", 1) - 1
                        break

        for new in (new_rx or []):
            if isinstance(new, dict) and new.get("type") == "emoji":
                emoji = new.get("emoji")
                found = False
                for r in rx_arr:
                    rt = r.get("type") or {}
                    if rt.get("type") == "emoji" and rt.get("emoji") == emoji:
                        r["total_count"] = r.get("total_count", 0) + 1
                        found = True
                        break
                if not found:
                    rx_arr.append({
                        "type": {"type": "emoji", "emoji": emoji},
                        "total_count": 1
                    })

        rx_arr = [r for r in rx_arr if r.get("total_count", 0) > 0]
        if rx_arr:
            msg_obj["reactions"] = rx_arr
        else:
            msg_obj.pop("reactions", None)
        payload["message"] = msg_obj

        conn.execute(
            "UPDATE messages SET raw_json = ?, updated_at = ? "
            " WHERE chat_id = ? AND message_id = ?",
            (json.dumps(payload, ensure_ascii=False), db_utcnow(),
             chat_id, message_id))
        conn.commit()
    except Exception as e:
        try:
            print(f"warn: _apply_reaction_delta: {e}")
        except Exception:
            pass



def _fetch_chat_photo(bot, chat_id, cache_dir):
    """Return (local_path, mime) for a chat/group/channel photo (cached on disk)."""
    with _get_avatar_lock(("chat", chat_id)):
        conn = sqlite3.connect(DB_FILE)
        try:
            row = conn.execute(
                "SELECT file_path FROM chat_photos WHERE chat_id = ?",
                (chat_id,)).fetchone()
            if row and row[0] and os.path.isfile(row[0]):
                return row[0], "image/jpeg"
        finally:
            conn.close()

        resp = bot.post("getChat", data={"chat_id": str(chat_id)},
                        ask_retry=False)
        if not resp or not resp.get("ok"):
            # Private chat without conversation history? try user photo
            if str(chat_id).lstrip("-").isdigit() and not str(chat_id).startswith("-"):
                try:
                    return _fetch_user_photo(bot, int(chat_id), cache_dir)
                except Exception:
                    pass
            return None, None

        chat = resp.get("result") or {}
        photo = chat.get("photo") or {}
        if not photo:
            # Private chat: getChat returns no photo sometimes; try user
            if chat.get("type") == "private":
                try:
                    return _fetch_user_photo(bot, int(chat_id), cache_dir)
                except Exception:
                    pass
            return None, None

        file_id = photo.get("big_file_id") or photo.get("small_file_id")
        fuid = (photo.get("big_file_unique_id")
                or photo.get("small_file_unique_id") or "p")
        if not file_id:
            return None, None

        f = bot.post("getFile", data={"file_id": file_id}, ask_retry=False)
        if not f or not f.get("ok"):
            return None, None
        file_path = f["result"].get("file_path")
        if not file_path:
            return None, None

        url = f"{bot.file_api}/{file_path}"
        os.makedirs(cache_dir, exist_ok=True)
        local = os.path.join(cache_dir, f"chat_{chat_id}_{fuid}.jpg")
        tmp = local + ".part"
        try:
            r = bot.session.get(url, timeout=60, stream=True)
            r.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(65536):
                    fh.write(chunk)
            os.replace(tmp, local)
        except Exception:
            try:
                os.remove(tmp)
            except Exception:
                pass
            return None, None

        conn = sqlite3.connect(DB_FILE)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO chat_photos "
                "(chat_id, file_unique_id, file_id, file_path, file_size, "
                " fetched_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (chat_id, fuid, file_id, local,
                 os.path.getsize(local),
                 db_utcnow(), db_utcnow()))
            conn.commit()
        finally:
            conn.close()
        return local, "image/jpeg"




def _serve_saved_media_preview(bot, row, cache_dir):
    """Return bytes for a saved_media row's preview. Uses thumbnail if available."""
    file_id = row.get("thumbnail_file_id") or row.get("file_id")
    fuid = row.get("file_unique_id") or "x"
    is_thumb = bool(row.get("thumbnail_file_id"))
    cache_key = (f"thumb_{fuid}" if is_thumb else fuid)
    cache_path = os.path.join(cache_dir, cache_key)

    # 1. disk cache
    if os.path.isfile(cache_path):
        try:
            with open(cache_path, "rb") as fh:
                return fh.read()
        except Exception:
            pass

    # 2. try message_files / file_cache via unique id (may already be cached)
    try:
        _c = sqlite3.connect(DB_FILE)
        _r = _c.execute(
            "SELECT file_path FROM file_cache WHERE file_unique_id = ?",
            (fuid,)).fetchone()
        _c.close()
        if _r and _r[0] and os.path.isfile(_r[0]):
            try:
                with open(_r[0], "rb") as fh:
                    return fh.read()
            except Exception:
                pass
    except Exception:
        pass

    # 3. download
    resp = bot.post("getFile", data={"file_id": file_id}, ask_retry=False)
    if not resp or not resp.get("ok"):
        return None
    fpath = resp["result"].get("file_path")
    if not fpath:
        return None
    url = f"{bot.file_api}/{fpath}"
    os.makedirs(cache_dir, exist_ok=True)
    tmp = cache_path + ".part"
    try:
        r = bot.session.get(url, timeout=60, stream=True)
        r.raise_for_status()
        with open(tmp, "wb") as fh:
            for ch in r.iter_content(65536):
                fh.write(ch)
        os.replace(tmp, cache_path)
        with open(cache_path, "rb") as fh:
            return fh.read()
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        return None




def _record_mention_if_needed(conn, descr, bot):
    """After db_process_message, store a mention/reply flag if applicable."""
    if not descr:
        return
    bot_id = getattr(bot, "bot_id", None)
    if not bot_id:
        return
    if descr.get("from_id") == bot_id:
        return  # never flag bot's own messages
    bot_username = ((getattr(bot, "bot_info", None) or {})
                    .get("username", "") or "")
    kind = None
    try:
        if _check_mentioned(descr, bot_id, bot_username):
            kind = "mention"
    except Exception:
        pass
    if kind is None and descr.get("reply_to_message_id"):
        try:
            if _check_reply_to_bot(conn, descr["chat_id"],
                                    descr["message_id"], bot_id):
                kind = "reply"
        except Exception:
            pass
    if not kind:
        return
    try:
        conn.execute(
            "INSERT OR IGNORE INTO mention_flags "
            "(chat_id, message_id, kind, from_user_id, created_at, seen) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            (descr["chat_id"], descr["message_id"], kind,
             descr.get("from_id"), db_utcnow()))
        conn.commit()
    except Exception:
        pass


def _run_web_server(bot: TelegramBot,
                    host: str = "127.0.0.1", port: int = 8081,
                    password: Optional[str] = None,
                    session_ttl: int = 86400,
                    cache_max_mb: int = 512,
                    cert: Optional[str] = None,
                    key: Optional[str] = None,
                    disable_poller: bool = False):
    """Start the web UI (browser client). CLI-only; Ctrl+C to stop."""

    # Load bot identity — required by /api/me → state.botId (own-message detection)
    if not bot.bot_info:
        _me = bot.post("getMe", ask_retry=False)
        if _me and _me.get("ok"):
            bot.bot_info = _me["result"]
            bot.bot_id = bot.bot_info.get("id")
            print(f"{G}✔ Bot identity loaded: @{bot.bot_info.get('username')} "
                  f"(id={bot.bot_info.get('id')}){N}")
        else:
            print(f"{R}✘ getMe failed — state.botId will be null, so you "
                  f"won't see your own messages on the right side.{N}")

    if not password:
        password = bot.token
        print(f"{Y}⚠ No --password given; using the bot token as web password.{N}")
        print(f"{Y}  For safety, pass --password <separate-secret> instead.{N}")

    if host == "0.0.0.0" and not cert:
        print(f"{R}⚠ Binding to 0.0.0.0 without HTTPS — "
              f"credentials would travel in plaintext.{N}")
        if input("Continue anyway? [y/N]: ").strip().lower() != "y":
            return

    web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "web-ui")
    if not os.path.isdir(web_dir):
        print(f"{R}✘ web-ui/ directory not found next to termgram.py{N}")
        return
    if not os.path.isfile(os.path.join(web_dir, "index.html")):
        print(f"{R}✘ web-ui/index.html not found{N}")
        return

    conn = sqlite3.connect(DB_FILE); db_init(conn); conn.close()

    Handler = _make_web_handler(bot, password, session_ttl,
                                cache_max_mb, web_dir)
    try:
        httpd = http.server.ThreadingHTTPServer((host, port), Handler)
    except OSError as e:
        print(f"{R}✘ Could not bind {host}:{port}: {e}{N}")
        return

    if cert and key:
        import ssl
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

    proto = "https" if cert else "http"
    print(f"{G}✔ Web UI listening on {proto}://{host}:{port}{N}")
    print(f"  Login password: {'(bot token)' if password == bot.token else '(custom)'}")
    print(f"  Session TTL   : {session_ttl}s")
    print(f"  Cache max     : {cache_max_mb} MB")
    print(f"  Press Ctrl+C to stop.\n")

        # Poller is opt-in via the UI checkbox (/api/poller/start).
    # It is NOT started here so users control when getUpdates runs.
    stop_event = threading.Event()  # kept for compatibility, unused
    if disable_poller:
        print(f"{Y}ℹ Poller disabled by --no-poller.{N}\n")
    else:
        print(f"{Y}ℹ Poller idle — enable 'Sync & auto-refresh' "
              f"in the web UI to start getUpdates.{N}\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{Y}Stopping web server...{N}")
    finally:
        _stop_web_poller()
        try:
            httpd.server_close()
        except Exception:
            pass



def run_cli(bot: TelegramBot, argv: List[str]) -> int:
    """Parse argv and execute a one-shot command. Return exit code."""

    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description=f"{APP_TAGLINE} — CLI mode.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
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
""",
    )
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="<command>")

    # ============ SEND ============
    p = sub.add_parser("text", help="send a text message")
    p.add_argument("chat_id")
    p.add_argument("text", nargs="?", default=None,
                   help="message text (or use --text-file)")
    p.add_argument("--text-file", default=None, help="read text from file")
    p.add_argument("--reply-to", type=int, default=None)
    p.add_argument("--reply-to-chat", default=None,
                   help="source chat_id if replying cross-chat (e.g. -100... or @ch)")
    p.add_argument("--quote", default=None,
                   help="quote an exact substring of the replied-to message")
    p.add_argument("--parse-mode", default=None)

    for name in ("photo", "document", "video", "audio",
                 "voice", "animation", "video_note", "sticker"):
        sp = sub.add_parser(name, help=f"send a {name}")
        sp.add_argument("chat_id")
        sp.add_argument("path", help="local file path, URL, or file_id")
        sp.add_argument("--caption", default=None)
        sp.add_argument("--caption-file", default=None)
        sp.add_argument("--reply-to", type=int, default=None)
        sp.add_argument("--parse-mode", default=None)

    sp = sub.add_parser("location", help="send a location")
    sp.add_argument("chat_id")
    sp.add_argument("latitude", type=float)
    sp.add_argument("longitude", type=float)

    sp = sub.add_parser("contact", help="send a contact")
    sp.add_argument("chat_id")
    sp.add_argument("phone_number")
    sp.add_argument("first_name")
    sp.add_argument("--last-name", default=None)

    sp = sub.add_parser("dice", help="send a dice")
    sp.add_argument("chat_id")
    sp.add_argument("emoji", nargs="?", default="🎲")

    # ============ MESSAGE MANAGEMENT ============
    sp = sub.add_parser("react", help="set a reaction on a message")
    sp.add_argument("chat_id")
    sp.add_argument("message_id", type=int)
    sp.add_argument("emoji")

    sp = sub.add_parser("edit", help="edit a message's text")
    sp.add_argument("chat_id")
    sp.add_argument("message_id", type=int)
    sp.add_argument("text", nargs="?", default=None)
    sp.add_argument("--text-file", default=None)
    sp.add_argument("--parse-mode", default=None)

    sp = sub.add_parser("delete", help="delete a message")
    sp.add_argument("chat_id")
    sp.add_argument("message_id", type=int)

    sp = sub.add_parser("pin", help="pin a message")
    sp.add_argument("chat_id")
    sp.add_argument("message_id", type=int)
    sp.add_argument("--silent", action="store_true")

    sp = sub.add_parser("unpin", help="unpin a message (no id = unpin all)")
    sp.add_argument("chat_id")
    sp.add_argument("message_id", type=int, nargs="?", default=None)

    sp = sub.add_parser("forward", help="forward a message")
    sp.add_argument("from_chat_id")
    sp.add_argument("to_chat_id")
    sp.add_argument("message_id", type=int)
    sp.add_argument("--silent", action="store_true")

    sp = sub.add_parser("reply", help="reply to a message (works across chats)")
    sp.add_argument("src_chat_id")
    sp.add_argument("src_message_id", type=int)
    sp.add_argument("dst_chat_id")
    sp.add_argument("text", nargs="?", default=None)
    sp.add_argument("--text-file", default=None)
    sp.add_argument("--quote", default=None,
                    help="quote an exact substring of the source message")
    sp.add_argument("--parse-mode", default=None)

    sp = sub.add_parser("chat-action", help="send a chat action")
    sp.add_argument("chat_id")
    sp.add_argument("action", nargs="?", default="typing")

    # ============ CHAT / MEMBERS ============
    sp = sub.add_parser("leave", help="leave a chat/channel")
    sp.add_argument("chat_id")

    sp = sub.add_parser("chat-info", help="get chat info")
    sp.add_argument("chat_id")

    sp = sub.add_parser("member-count", help="get member count")
    sp.add_argument("chat_id")

    sp = sub.add_parser("member-info", help="get a chat member")
    sp.add_argument("chat_id")
    sp.add_argument("user_id")

    sp = sub.add_parser("ban", help="ban a user")
    sp.add_argument("chat_id")
    sp.add_argument("user_id")
    sp.add_argument("--revoke", action="store_true", help="revoke messages")
    sp.add_argument("--until", type=int, default=None, help="unix ts (0=forever)")

    sp = sub.add_parser("unban", help="unban a user")
    sp.add_argument("chat_id")
    sp.add_argument("user_id")
    sp.add_argument("--only-if-banned", action="store_true")

    sp = sub.add_parser("promote", help="promote a user to admin (all perms)")
    sp.add_argument("chat_id")
    sp.add_argument("user_id")

    sp = sub.add_parser("demote", help="remove admin rights")
    sp.add_argument("chat_id")
    sp.add_argument("user_id")

    sp = sub.add_parser("set-title", help="set chat title")
    sp.add_argument("chat_id")
    sp.add_argument("title")

    sp = sub.add_parser("set-description", help="set chat description")
    sp.add_argument("chat_id")
    sp.add_argument("description", nargs="?", default="")

    sp = sub.add_parser("invite-link", help="create a chat invite link")
    sp.add_argument("chat_id")
    sp.add_argument("--name", default=None)
    sp.add_argument("--limit", type=int, default=None)
    sp.add_argument("--expire", type=int, default=None)

    # ============ BOT PROFILE ============
    sub.add_parser("me", help="show bot info (getMe)")
    sub.add_parser("profile", help="show full bot profile")

    sp = sub.add_parser("set-name", help="set bot global name")
    sp.add_argument("name")
    sp.add_argument("--lang", default=None)

    sp = sub.add_parser("set-bio", help="set bot description / bio")
    sp.add_argument("description", nargs="?", default=None)
    sp.add_argument("--bio-file", default=None)
    sp.add_argument("--lang", default=None)

    sp = sub.add_parser("set-short-bio", help="set bot short description")
    sp.add_argument("description", nargs="?", default=None)
    sp.add_argument("--bio-file", default=None)
    sp.add_argument("--lang", default=None)

    sub.add_parser("remove-photo", help="remove bot profile photo")

    # ============ WEB UI ============
    sp = sub.add_parser("web", help="start the web UI (browser client)")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8081)
    sp.add_argument("--password", default=None,
                    help="web login password (default: bot token)")
    sp.add_argument("--session-ttl", type=int, default=86400,
                    help="session TTL in seconds (default 86400)")
    sp.add_argument("--cache-max-mb", type=int, default=512,
                    help="max disk cache for files (default 512 MB)")
    sp.add_argument("--https-cert", default=None,
                    help="optional path to .pem certificate (enables HTTPS)")
    sp.add_argument("--https-key", default=None,
                    help="optional path to .pem private key")
    sp.add_argument("--no-poller", action="store_true",
                    help="don't poll getUpdates (if you run monitor "
                         "or silent-fetch elsewhere)")

    # ============ FILES ============
    sp = sub.add_parser("download", help="download a file by file_id")
    sp.add_argument("file_id")
    sp.add_argument("--out", default=None, help="output path")

    sp = sub.add_parser("upload", help="upload a file and print its file_id")
    sp.add_argument("chat_id")
    sp.add_argument("path")
    sp.add_argument("--as", dest="as_type", default="document",
                    choices=["document", "photo", "video", "audio",
                             "voice", "animation", "sticker"])

    args = parser.parse_args(argv)

    # ================================================================
    #  DISPATCH
    # ================================================================

    # ---------- web UI ----------
    if args.cmd == "web":
        _run_web_server(
            bot,
            host=args.host,
            port=args.port,
            password=args.password,
            session_ttl=args.session_ttl,
            cache_max_mb=args.cache_max_mb,
            cert=args.https_cert,
            key=args.https_key,
            disable_poller=getattr(args, "no_poller", False),
        )
        return 0

    # ---------- text ----------
    if args.cmd == "text":
        text = _read_text_arg(args.text, args.text_file)
        if not text:
            print(f"{R}text is required (positional or --text-file){N}",
                  file=sys.stderr)
            return 2
        data = {"chat_id": args.chat_id, "text": text}
        if args.reply_to is not None and (args.reply_to_chat or args.quote):
            rp: Dict[str, Any] = {"message_id": int(args.reply_to)}
            if args.reply_to_chat:
                src = args.reply_to_chat
                rp["chat_id"] = int(src) if str(src).lstrip('-').isdigit() else src
            if args.quote:
                rp["quote"] = args.quote
            data["reply_parameters"] = json.dumps(rp, ensure_ascii=False)
        elif args.reply_to is not None:
            data["reply_to_message_id"] = str(args.reply_to)
        if args.parse_mode:
            data["parse_mode"] = args.parse_mode
        return _send_ok(bot.post("sendMessage", data=data, ask_retry=False))

    # ---------- file senders ----------
    file_cmds = {
        "photo":     ("sendPhoto",     "photo"),
        "document":  ("sendDocument",  "document"),
        "video":     ("sendVideo",     "video"),
        "audio":     ("sendAudio",     "audio"),
        "voice":     ("sendVoice",     "voice"),
        "animation": ("sendAnimation", "animation"),
        "video_note":("sendVideoNote", "video_note"),
        "sticker":   ("sendSticker",   "sticker"),
    }
    if args.cmd in file_cmds:
        method, field = file_cmds[args.cmd]
        caption = ""
        if getattr(args, "caption_file", None) or getattr(args, "caption", None):
            caption = _read_caption_arg(args.caption, args.caption_file)
        return _cli_send_file(
            bot, method, field, args.chat_id, args.path, caption,
            getattr(args, "reply_to", None),
            getattr(args, "parse_mode", None),
        )

    # ---------- location / contact / dice ----------
    if args.cmd == "location":
        return _send_ok(bot.post("sendLocation", data={
            "chat_id": args.chat_id,
            "latitude": str(args.latitude),
            "longitude": str(args.longitude),
        }, ask_retry=False))

    if args.cmd == "contact":
        data = {"chat_id": args.chat_id,
                "phone_number": args.phone_number,
                "first_name": args.first_name}
        if args.last_name:
            data["last_name"] = args.last_name
        return _send_ok(bot.post("sendContact", data=data, ask_retry=False))

    if args.cmd == "dice":
        return _send_ok(bot.post("sendDice", data={
            "chat_id": args.chat_id, "emoji": args.emoji,
        }, ask_retry=False))

    # ---------- react ----------
    if args.cmd == "react":
        reaction = json.dumps([{"type": "emoji", "emoji": args.emoji}])
        return _send_ok(bot.post("setMessageReaction", data={
            "chat_id": args.chat_id,
            "message_id": str(args.message_id),
            "reaction": reaction,
        }, ask_retry=False))

    # ---------- edit ----------
    if args.cmd == "edit":
        text = _read_text_arg(args.text, args.text_file)
        if not text:
            print(f"{R}text is required{N}", file=sys.stderr)
            return 2
        data = {"chat_id": args.chat_id,
                "message_id": str(args.message_id),
                "text": text}
        if args.parse_mode:
            data["parse_mode"] = args.parse_mode
        return _send_ok(bot.post("editMessageText", data=data, ask_retry=False))

    # ---------- delete ----------
    if args.cmd == "delete":
        return _send_ok(bot.post("deleteMessage", data={
            "chat_id": args.chat_id,
            "message_id": str(args.message_id),
        }, ask_retry=False))

    # ---------- pin / unpin ----------
    if args.cmd == "pin":
        data = {"chat_id": args.chat_id,
                "message_id": str(args.message_id)}
        if args.silent:
            data["disable_notification"] = "true"
        return _send_ok(bot.post("pinChatMessage", data=data, ask_retry=False))

    if args.cmd == "unpin":
        data = {"chat_id": args.chat_id}
        if args.message_id is not None:
            data["message_id"] = str(args.message_id)
        return _send_ok(bot.post("unpinChatMessage", data=data, ask_retry=False))

    # ---------- forward ----------
    if args.cmd == "forward":
        data = {"chat_id": args.to_chat_id,
                "from_chat_id": args.from_chat_id,
                "message_id": str(args.message_id)}
        if args.silent:
            data["disable_notification"] = "true"
        return _send_ok(bot.post("forwardMessage", data=data, ask_retry=False))

    # ---------- reply (cross-chat) ----------
    if args.cmd == "reply":
        text = _read_text_arg(args.text, args.text_file)
        if not text:
            print(f"{R}text is required{N}", file=sys.stderr)
            return 2
        data = {"chat_id": args.dst_chat_id, "text": text}
        if str(args.src_chat_id) == str(args.dst_chat_id) and not args.quote:
            data["reply_to_message_id"] = str(args.src_message_id)
        else:
            rp: Dict[str, Any] = {"message_id": int(args.src_message_id)}
            if str(args.src_chat_id) != str(args.dst_chat_id):
                rp["chat_id"] = (int(args.src_chat_id)
                                 if str(args.src_chat_id).lstrip('-').isdigit()
                                 else args.src_chat_id)
            if args.quote:
                rp["quote"] = args.quote
            data["reply_parameters"] = json.dumps(rp, ensure_ascii=False)
        if args.parse_mode:
            data["parse_mode"] = args.parse_mode
        return _send_ok(bot.post("sendMessage", data=data, ask_retry=False))

    # ---------- chat action ----------
    if args.cmd == "chat-action":
        return _send_ok(bot.post("sendChatAction", data={
            "chat_id": args.chat_id, "action": args.action,
        }, ask_retry=False))

    # ---------- leave / chat-info / member-count ----------
    if args.cmd == "leave":
        return _send_ok(bot.post("leaveChat", data={"chat_id": args.chat_id},
                                 ask_retry=False))

    if args.cmd == "chat-info":
        show_info_result(bot.post("getChat", data={"chat_id": args.chat_id},
                                  ask_retry=False))
        return 0

    if args.cmd == "member-count":
        show_info_result(bot.post("getChatMemberCount",
                                  data={"chat_id": args.chat_id},
                                  ask_retry=False))
        return 0

    if args.cmd == "member-info":
        show_info_result(bot.post("getChatMember", data={
            "chat_id": args.chat_id, "user_id": args.user_id,
        }, ask_retry=False))
        return 0

    # ---------- ban / unban ----------
    if args.cmd == "ban":
        data = {"chat_id": args.chat_id, "user_id": args.user_id}
        if args.revoke:
            data["revoke_messages"] = "true"
        if args.until is not None:
            data["until_date"] = str(args.until)
        return _send_ok(bot.post("banChatMember", data=data, ask_retry=False))

    if args.cmd == "unban":
        data = {"chat_id": args.chat_id, "user_id": args.user_id}
        if args.only_if_banned:
            data["only_if_banned"] = "true"
        return _send_ok(bot.post("unbanChatMember", data=data, ask_retry=False))

    # ---------- promote / demote ----------
    if args.cmd == "promote":
        data = {
            "chat_id": args.chat_id, "user_id": args.user_id,
            "can_change_info": True, "can_post_messages": True,
            "can_edit_messages": True, "can_delete_messages": True,
            "can_invite_users": True, "can_restrict_members": True,
            "can_pin_messages": True, "can_promote_members": True,
            "can_manage_video_chats": True, "can_manage_chat": True,
            "can_manage_topics": True,
        }
        return _send_ok(bot.post("promoteChatMember", data=data, ask_retry=False))

    if args.cmd == "demote":
        data = {
            "chat_id": args.chat_id, "user_id": args.user_id,
            "can_change_info": False, "can_post_messages": False,
            "can_edit_messages": False, "can_delete_messages": False,
            "can_invite_users": False, "can_restrict_members": False,
            "can_pin_messages": False, "can_promote_members": False,
            "can_manage_video_chats": False, "can_manage_chat": False,
            "can_manage_topics": False,
        }
        return _send_ok(bot.post("promoteChatMember", data=data, ask_retry=False))

    # ---------- set title / description ----------
    if args.cmd == "set-title":
        return _send_ok(bot.post("setChatTitle", data={
            "chat_id": args.chat_id, "title": args.title,
        }, ask_retry=False))

    if args.cmd == "set-description":
        data = {"chat_id": args.chat_id}
        if args.description:
            data["description"] = args.description
        return _send_ok(bot.post("setChatDescription", data=data, ask_retry=False))

    # ---------- invite link ----------
    if args.cmd == "invite-link":
        data = {"chat_id": args.chat_id}
        if args.name:
            data["name"] = args.name
        if args.limit is not None:
            data["member_limit"] = str(args.limit)
        if args.expire is not None:
            data["expire_date"] = str(args.expire)
        resp = bot.post("createChatInviteLink", data=data, ask_retry=False)
        if resp and resp.get("ok"):
            link = resp["result"].get("invite_link", "")
            if link:
                print(link)
            return 0
        show_info_result(resp)
        return 1

    # ---------- bot identity / profile ----------
    if args.cmd == "me":
        show_bot_info(bot)
        return 0

    if args.cmd == "profile":
        get_bot_profile(bot)
        return 0

    if args.cmd == "set-name":
        data = {"name": args.name}
        if args.lang:
            data["language_code"] = args.lang
        return _send_ok(bot.post("setMyName", data=data, ask_retry=False))

    if args.cmd == "set-bio":
        desc = _read_text_arg(args.description, args.bio_file) or ""
        data = {"description": desc}
        if args.lang:
            data["language_code"] = args.lang
        return _send_ok(bot.post("setMyDescription", data=data, ask_retry=False))

    if args.cmd == "set-short-bio":
        desc = _read_text_arg(args.description, args.bio_file) or ""
        data = {"short_description": desc}
        if args.lang:
            data["language_code"] = args.lang
        return _send_ok(bot.post("setMyShortDescription", data=data,
                                 ask_retry=False))

    if args.cmd == "remove-photo":
        return _send_ok(bot.post("removeMyProfilePhoto", ask_retry=False))

    # ---------- download by file_id ----------
    if args.cmd == "download":
        resp = bot.post("getFile", data={"file_id": args.file_id},
                        ask_retry=False)
        if not resp or not resp.get("ok"):
            show_info_result(resp)
            return 1
        file_path = resp["result"].get("file_path")
        if not file_path:
            print(f"{R}could not resolve file_path{N}", file=sys.stderr)
            return 1
        out = args.out or os.path.basename(file_path)
        url = f"{bot.file_api}/{file_path}"
        try:
            r = bot.session.get(url, timeout=60)
            with open(out, "wb") as f:
                f.write(r.content)
            print(f"{G}✔ Saved: {out} "
                  f"({os.path.getsize(out) / 1024:.1f} KB){N}")
            return 0
        except Exception as e:
            print(f"{R}download failed: {e}{N}", file=sys.stderr)
            return 1

    # ---------- upload & get file_id ----------
    if args.cmd == "upload":
        if not os.path.isfile(args.path):
            print(f"{R}file not found: {args.path}{N}", file=sys.stderr)
            return 2
        method_field = {
            "document":  ("sendDocument",  "document"),
            "photo":     ("sendPhoto",     "photo"),
            "video":     ("sendVideo",     "video"),
            "audio":     ("sendAudio",     "audio"),
            "voice":     ("sendVoice",     "voice"),
            "animation": ("sendAnimation", "animation"),
            "sticker":   ("sendSticker",   "sticker"),
        }[args.as_type]
        method, field = method_field
        pf = ProgressFileReader(args.path)
        files = {field: (os.path.basename(args.path),
                         open(args.path, "rb"),
                         guess_mime(args.path))}
        resp = bot.post(method, data={"chat_id": args.chat_id},
                        files=files, ask_retry=False)
        finish_progress()
        if not resp or not resp.get("ok"):
            show_info_result(resp)
            return 1
        result = resp["result"]
        for key in ("document", "video", "audio", "voice",
                    "animation", "sticker"):
            obj = result.get(key)
            if obj and "file_id" in obj:
                print(obj["file_id"])
                return 0
        photos = result.get("photo")
        if photos:
            print(photos[-1].get("file_id", ""))
            return 0
        print(f"{Y}file_id not found in response{N}", file=sys.stderr)
        return 1

    return 1

# ================================================================
#  Entry point
# ================================================================
def print_banner() -> None:
    line = "═" * 52
    print(f"{G}╔{line}╗{N}")
    print(f"{G}║{N}  {B}📡 {APP_NAME}{N}  {Y}v{APP_VERSION}{N}"
          f"{' ' * (52 - len(APP_NAME) - len(APP_VERSION) - 8)}{G}║{N}")
    print(f"{G}║{N}  {M}{APP_TAGLINE}{N}"
          f"{' ' * (52 - len(APP_TAGLINE) - 2)}{G}║{N}")
    print(f"{G}╚{line}╝{N}")
def main():
    global PROXY

    cli_mode = len(sys.argv) > 1

    # --- banner ---
    if cli_mode:
        print(f"{B}{APP_NAME}{N} {Y}v{APP_VERSION}{N}")
    else:
        print_banner()

    # --- bootstrap config & database ---
    config = load_config()
    ensure_db()
    if not cli_mode and config.get("api_server_enabled"):
        try:
            _start_api_server(TelegramBot(config.get("token", ""),
                                          config.get("proxy", ""),
                                          config.get("base_url") or None))
        except Exception as e:
            print(f"{Y}⚠ Could not auto-start API server: {e}{N}")

    token = str(config.get("token", "")).strip()
    proxy_url = str(config.get("proxy", "")).strip()
    PROXY = proxy_url

    # --- CLI mode: run one-shot command ---
    if cli_mode:
        if "-h" in sys.argv[1:] or "--help" in sys.argv[1:]:
            sys.exit(run_cli(None, sys.argv[1:]))
        if not token:
            print(f"{R}ERROR: bot token is not configured in {CONFIG_FILE}. Run termgram interactively or edit {CONFIG_FILE}.{N}", file=sys.stderr)
            sys.exit(1)
        bot = TelegramBot(token, proxy_url, get_config_base_url() or None)
        sys.exit(run_cli(bot, sys.argv[1:]))

    # --- Interactive mode: ensure valid bot token ---
    base_url = get_config_base_url() or None
    bot = TelegramBot(token, proxy_url, base_url)
    while True:
        if not token:
            print(f"\n{Y}⚠ No bot token found in {CONFIG_FILE}.{N}")
            new_tok = input("Enter bot token (or 'q' to exit): ").strip()
            if not new_tok or new_tok.lower() == 'q':
                print(f"{Y}Exiting.{N}")
                sys.exit(0)
            token = new_tok
            bot = TelegramBot(token, proxy_url, get_config_base_url() or None)

        print(f"\n{Y}Connecting to Telegram API...{N}")
        if proxy_url:
            print(f"{Y}Using proxy: {proxy_url}{N}")

        resp = bot.post("getMe", ask_retry=False)
        if resp and resp.get("ok"):
            bot_info = resp["result"]
            bot.bot_id = bot_info.get("id")
            bot.bot_info = bot_info
            if get_config_token() != token:
                set_config_token(token)
            print(f"{G}✔ Bot connected: @{bot_info.get('username', '?')} ({bot_info.get('first_name', '?')}){N}")
            break

        # Check if Telegram server explicitly confirmed the token is invalid
        if resp and resp.get("error_code") in (401, 404):
            desc = resp.get("description", "Unauthorized")
            err_code = resp.get("error_code")
            print(f"\n{R}✘ Invalid bot token! Telegram server rejected the token ({err_code}: {desc}){N}")
            print(f"{Y}Please enter a valid bot token to continue, or 'q' to exit.{N}")
            new_tok = input("Enter valid bot token (or 'q' to exit): ").strip()
            if not new_tok or new_tok.lower() == 'q':
                print(f"{Y}Exiting.{N}")
                sys.exit(1)
            token = new_tok
            bot = TelegramBot(token, proxy_url)
            continue
        else:
            # Network failure, proxy timeout, or other issue
            print(f"\n{R}✘ Could not connect to Telegram API{N}")
            if resp:
                print(json.dumps(resp, indent=2, ensure_ascii=False))
            else:
                print(f"{Y}Connection failed. Please check your internet connection or proxy settings.{N}")

            print(f"\n  1) Retry connection")
            print(f"  2) Enter a new bot token")
            print(f"  3) Configure proxy")
            print(f"  4) Enter custom Base URL   ← (e.g. your own API proxy)")
            print(f"  5) Continue anyway (offline)")
            print(f"  0) Exit")
            ans = input("choice [1/2/3/4/5/0]: ").strip()
            if ans == "1":
                continue
            elif ans == "2":
                new_tok = input("Enter bot token: ").strip()
                if new_tok:
                    token = new_tok
                    bot = TelegramBot(token, proxy_url, get_config_base_url() or None)
                continue
            elif ans == "3":
                configure_proxy_menu(bot)
                proxy_url = PROXY
                continue
            elif ans == "4":
                new_base = input("Base URL (empty = api.telegram.org): ").strip()
                set_config_base_url(new_base)
                bot = TelegramBot(token, proxy_url, new_base or None)
                continue
            elif ans == "5":
                break
            else:
                print(f"{Y}Exiting.{N}")
                sys.exit(0)

    main_menu(bot)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Y}Bye.{N}")