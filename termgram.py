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
from datetime import datetime, timezone
import argparse
from typing import Optional, Dict, Any, List, Tuple

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

# ============ App info ============
APP_NAME    = "termgram"
APP_VERSION = "1.2.0"
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
        "reply_parameters": reply_params,   # ← جدید
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
    """Ask user for file path / URL / file_id. Returns (key, files_dict_or_value)."""
    value = input(f"input {field_name} (file path / URL / file_id): ").strip()
    if not value:
        print(f"{R}value is empty{N}")
        return None, None
    if os.path.isfile(value):
        mime = guess_mime(value)
        files = {field_name: (os.path.basename(value), open(value, "rb"), mime)}
        return None, files
    return value, None


def show_send_result(result: Optional[dict]):
    if not result:
        print(f"{R}✘ No response from server{N}")
        return
    if result.get("ok"):
        res = result.get("result")
        if isinstance(res, dict):
            msg_id = res.get("message_id")
            if msg_id:
                print(f"{G}✔ Success{N}")
                print(f"{G}📨 message_id: {msg_id}{N}")
                return
        print(f"{G}✔ Success{N}")
    else:
        print(f"{R}✘ Failed:{N}")
        print(json.dumps(result, indent=2, ensure_ascii=False))


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
                                                 "message_reaction_count"]},
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
                          "channel_post", "edited_channel_post"):
                    if k in upd:
                        kind, obj = k, upd[k]
                        break

                if obj is None:
                    db_store_update(conn, uid, 'non-message', upd)
                    db_state_set(conn, 'offset', offset)
                    continue

                db_store_update(conn, uid, kind, upd)
                descr = db_process_message(conn, uid, kind, obj)
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
def download_file_by_id(bot: TelegramBot):
    print(f"\n{B}--- Download File by file_id ---{N}")
    file_id = input("file_id: ").strip()
    if not file_id:
        print(f"{R}file_id is required{N}")
        return
    print(f"{Y}>> getFile ...{N}")
    resp = bot.post("getFile", data={"file_id": file_id})
    if not resp or not resp.get("ok"):
        show_info_result(resp)
        return
    file_path = resp["result"].get("file_path")
    fsize = resp["result"].get("file_size")
    if fsize:
        print(f"{B}file_size:{N} {fsize} bytes")
    if not file_path:
        print(f"{R}✘ could not resolve file_path{N}")
        return
    fname = os.path.basename(file_path)
    out = input(f"save as [default: {fname}]: ").strip() or fname
    url = f"{bot.file_api}/{file_path}"
    print(f"{Y}>> downloading to {out} ...{N}")
    try:
        resp_dl = bot.session.get(url, timeout=60)
        with open(out, "wb") as f:
            f.write(resp_dl.content)
        size_kb = os.path.getsize(out) / 1024
        print(f"{G}✔ Saved: {out} ({size_kb:.1f} KB){N}")
    except Exception as e:
        print(f"{R}✘ download failed: {e}{N}")


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
                                                 "message_reaction_count"]},
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
                          "channel_post", "edited_channel_post"):
                    if k in upd:
                        kind, obj = k, upd[k]
                        break

                if obj is None:
                    db_store_update(conn, uid, 'non-message', upd)
                    db_state_set(conn, 'offset', offset)
                    continue

                db_store_update(conn, uid, kind, upd)
                descr = db_process_message(conn, uid, kind, obj)
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
                    bot.post("sendMessage", data={
                        "chat_id": str(chat_id),
                        "text": auto_reply_text,
                        "reply_to_message_id": str(descr['message_id']),
                    })
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
                            else:
                                print(f"{R}✘ Reaction failed: "
                                      f"{(r or {}).get('description', '?')}{N}")
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
    conn = sqlite3.connect(DB_FILE); db_init(conn)
    try:
        # ثبت بات فعلی
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
            c = input("choice (number to select, 0=back): ").strip()

            if c == "0":
                return
            if not c.isdigit():
                print(f"{R}invalid — type a number or 0{N}")
                continue

            idx = int(c) - 1
            if idx < 0 or idx >= len(rows):
                print(f"{R}invalid number{N}")
                continue

            # ===== زیرمنوی بات انتخاب‌شده =====
            bid, un, fn, added, seen = rows[idx]
            while True:
                print(f"\n{B}--- Bot: {fn or '?'} (@{un or '?'}) id={bid} ---{N}")
                print(f"  added: {added}   last_seen: {seen}")
                print("  1) View stored token")
                print("  2) View permissions for a chat")
                print("  3) Delete this bot from DB")
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


def render_animated_menu(lines: List[str], delay: float = 0.005) -> None:
    """Print menu lines with a fast cascading animation for a smooth, non-jarring appearance."""
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    for line in lines:
        print(line)
        if is_tty and delay > 0:
            time.sleep(delay)


def format_menu_row(n1: int, t1: str, n2: Optional[int] = None, t2: Optional[str] = None) -> str:
    if n2 is not None and t2 is not None:
        return f"  {n1:2d}) {t1:<22s}   {n2:2d}) {t2:<22s}"
    return f"  {n1:2d}) {t1}"


def print_menu_row(n1, t1, n2, t2):
    print(format_menu_row(n1, t1, n2, t2))

import threading
import http.server
import urllib.parse

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
            if not path.startswith(f"/bot{api_token}/"):
                self._respond(404, b'{"ok":false,"description":"unknown token"}')
                return
            method = path.rsplit("/", 1)[-1]
            qs = urllib.parse.parse_qs(parsed.query)
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            if self.headers.get("Content-Type", "").startswith("application/json"):
                try:
                    body_data = json.loads(raw) if raw else {}
                except Exception:
                    body_data = {}
            else:
                body_data = {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode("utf-8", "ignore")).items()}
            params = {k: v[0] for k, v in qs.items()}
            params.update(body_data)

            sess = requests.Session()
            if _proxy:
                sess.proxies = {"http": _proxy, "https": _proxy}
            try:
                resp = sess.post(
                    f"{bot.base_url}/{method}",
                    data=params, timeout=60)
                payload = resp.content
                if method == "getUpdates":
                    try:
                        js = resp.json()
                        if js.get("ok"):
                            _conn = sqlite3.connect(DB_FILE); db_init(_conn)
                            for upd in js.get("result", []):
                                uid = upd.get("update_id", 0)
                                kind, obj = None, None
                                for k in ("message", "edited_message", "channel_post", "edited_channel_post"):
                                    if k in upd:
                                        kind, obj = k, upd[k]; break
                                if obj is None:
                                    db_store_update(_conn, uid, "non-message", upd); continue
                                db_store_update(_conn, uid, kind, upd)
                                db_process_message(_conn, uid, kind, obj)
                            _conn.close()
                    except Exception:
                        pass
                self._respond(resp.status_code, payload)
            except Exception as e:
                self._respond(502, json.dumps({"ok": False, "description": str(e)}).encode())

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

def main_menu(bot: TelegramBot):
    while True:
        _lock = get_locked_chat_id() or "(none)"
        _guest = "ON" if get_guest_chat_mode() else "OFF"
        _api = "ON" if load_config().get("api_server_enabled") else "OFF"
        menu_lines = [
            f"\n{G}=============== Telegram Bot Sender ==============={N}",
            f"  {Y}Locked chat_id:{N} {_lock}   {Y}Guest:{N} {_guest}   {Y}API:{N} {_api}",
            format_menu_row(1, "Text message", 2, "Photo"),
            format_menu_row(3, "Animation (GIF)", 4, "Video"),
            format_menu_row(5, "Document / File", 6, "Audio"),
            format_menu_row(7, "Voice", 8, "Video note"),
            format_menu_row(9, "Sticker", 10, "Location"),
            format_menu_row(11, "Contact", 12, "Poll"),
            format_menu_row(13, "Dice", 14, "Reaction"),
            format_menu_row(15, "Edit message", 16, "Delete message"),
            f"{B}--- Settings & Config -----------------------------{N}",
            format_menu_row(50, "Manage bot token", 51, "Manage reactions"),
            format_menu_row(17, "Configure proxy", 18, "Bot info (getMe)"),
            f"{B}--- Chat Management -------------------------------{N}",
            format_menu_row(19, "Leave chat", 20, "Get chat info"),
            format_menu_row(21, "Member count", 22, "Pin message"),
            format_menu_row(23, "Unpin message", 24, "Forward message"),
            format_menu_row(25, "Chat action", 26, "Ban user"),
            format_menu_row(27, "Unban user", 28, "Set chat title"),
            format_menu_row(29, "Set chat desc", 30, "Set admin title"),
            format_menu_row(31, "Set bot name", 32, "Create invite link"),
            f"{B}--- Bot Profile -----------------------------------{N}",
            format_menu_row(33, "Set bio (desc)", 34, "Set short bio"),
            format_menu_row(35, "Set profile photo", 36, "Remove photo"),
            "  49) Get current profile",
            f"{B}--- Files -----------------------------------------{N}",
            format_menu_row(37, "Download by id", 38, "Upload & get id"),
            f"{B}--- Monitor ---------------------------------------{N}",
            "  39) Monitor mode",
            f"{B}--- Admin / Members -------------------------------{N}",
            format_menu_row(41, "Member info", 42, "Promote admin"),
            format_menu_row(43, "Demote admin", 44, "Set user title"),
            "  45) Set member tag",
            f"{B}--- Data / DB -------------------------------------{N}",
            format_menu_row(46, "Silent fetch", 47, "Chat explorer"),
            "  48) History viewer",
            f"{B}--- Advanced -------------------------------------{N}",
            format_menu_row(52, "API Server", 53, "Bot management"),
            format_menu_row(54, "Purge DB data", 55, "Lock/Unlock chat_id"),
            "  56) Toggle guest chat mode",
            format_menu_row(57, "Chat members (DB)", 58, "Mention members"),
            "  59) User account info",
            "",
            "   0) Exit",
            ""
        ]
        render_animated_menu(menu_lines, delay=0.005)

        choice = input("choice: ").strip()
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
            "17": lambda: configure_proxy_menu(bot),
            "18": lambda: show_bot_info(bot),
            "19": lambda: leave_chat(bot),
            "20": lambda: get_chat_info(bot),
            "21": lambda: get_chat_member_count(bot),
            "22": lambda: pin_message(bot),
            "23": lambda: unpin_message(bot),
            "24": lambda: forward_message(bot),
            "25": lambda: send_chat_action_cmd(bot),
            "26": lambda: ban_user(bot),
            "27": lambda: unban_user(bot),
            "28": lambda: set_chat_title(bot),
            "29": lambda: set_chat_description(bot),
            "30": lambda: set_admin_custom_title(bot),
            "31": lambda: set_bot_global_name(bot),
            "32": lambda: create_invite_link(bot),
            "33": lambda: set_bot_description(bot),
            "34": lambda: set_bot_short_description(bot),
            "35": lambda: set_profile_photo(bot),
            "36": lambda: remove_profile_photo(bot),
            "37": lambda: download_file_by_id(bot),
            "38": lambda: upload_and_get_file_id(bot),
            "39": lambda: monitor_mode(bot),
            "41": lambda: get_chat_member_info(bot),
            "42": lambda: promote_member(bot),
            "43": lambda: demote_member(bot),
            "44": lambda: set_user_custom_title(bot),
            "45": lambda: set_chat_member_tag(bot),
            "46": lambda: silent_fetch(bot),
            "47": lambda: chat_explorer(bot),
            "48": lambda: chat_history_viewer(bot),
            "49": lambda: get_bot_profile(bot),
            "50": lambda: manage_bot_token_menu(bot),
            "51": lambda: manage_reactions_menu(),
            "52": lambda: start_api_server_menu(bot),
            "53": lambda: bot_management_mode(bot),
            "54": lambda: db_purge_menu(bot),
            "55": lambda: chat_id_lock_menu(),
            "56": lambda: toggle_guest_chat_mode(),
            "57": lambda: chat_members_menu(bot),
            "58": lambda: mention_members_menu(bot),
            "59": lambda: user_account_info(bot),
            "0":  lambda: None,
        }

        if choice == "0":
            print("Bye.")
            break

        action = actions.get(choice)
        if action:
            try:
                action()
            except KeyboardInterrupt:
                print(f"\n{Y}Cancelled.{N}")
            except Exception as e:
                print(f"{R}Error: {e}{N}")
        else:
            print(f"{R}invalid choice{N}")


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
    """Generic file sender used by several CLI subcommands."""
    data = {"chat_id": chat_id}
    files = None
    if path and os.path.isfile(path):
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
        files = {field: (os.path.basename(args.path),
                         open(args.path, "rb"),
                         guess_mime(args.path))}
        resp = bot.post(method, data={"chat_id": args.chat_id},
                        files=files, ask_retry=False)
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