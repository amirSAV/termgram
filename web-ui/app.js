"use strict";

const state = {
  csrf: null,
  botId: null,
  chats: [],
  activeChat: null,
  replyTo: null,
  autoFetch: false,
  messages: [],
  reactions: [],
  admins: {},
  unseenMentions: {},
  chatMentions: [],
};
let _autoFetchTimer = null;

/* ---------- api helper ---------- */
async function api(path, opts = {}) {
  const headers = Object.assign({}, opts.headers || {});
  headers["Content-Type"] = "application/json";
  if (opts.method && opts.method !== "GET") {
    headers["X-CSRF-Token"] = state.csrf || "";
  }

  const send = () => fetch(path, Object.assign({}, opts, {
    headers, credentials: "same-origin",
  }));

  let r = await send();

  // If CSRF was rejected, refresh it from /api/me and retry ONCE
  if (r.status === 403) {
    let errBody = {};
    try { errBody = await r.clone().json(); } catch (_) {}
    if (errBody.error === "csrf") {
      try {
        const meRes = await fetch("/api/me", { credentials: "same-origin" });
        if (meRes.ok) {
          const meData = await meRes.json();
          if (meData.csrf_token) {
            state.csrf = meData.csrf_token;
            headers["X-CSRF-Token"] = state.csrf;
            r = await send();  // retry exactly once
          }
        } else if (meRes.status === 401) {
          showLogin();
          throw new Error("session expired");
        }
      } catch (e) {
        if (e && e.message === "session expired") throw e;
        // otherwise fall through with original 403
      }
    }
  }

  if (r.status === 401) {
    showLogin();
    throw new Error("unauthorized");
  }
  return r.json();
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

/* ---------- views ---------- */
function showLogin() {
  document.getElementById("login-view").hidden = false;
  document.getElementById("app-view").hidden = true;
}

async function showApp() {
  document.getElementById("login-view").hidden = true;
  document.getElementById("app-view").hidden = false;
  const me = await api("/api/me");
  state.csrf = me.csrf_token || null;
  state.botId = me.id || null;
  document.getElementById("bot-name").textContent = "@" + (me.username || "bot");
  await loadChats();
}

/* ---------- auth ---------- */
async function login(ev) {
  ev.preventDefault();
  const pw = document.getElementById("password").value;
  const errEl = document.getElementById("login-error");
  errEl.textContent = "";
  try {
    const res = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({ password: pw }),
    });
    if (!res.ok) {
      errEl.textContent = res.error || "login failed";
      return;
    }
    state.csrf = res.csrf_token;
    showApp();
  } catch (e) {
    errEl.textContent = "connection error";
  }
}

async function logout() {
  try {
    await api("/api/logout", { method: "POST", body: "{}" });
  } catch (_) {}
  state.csrf = null;
  state.activeChat = null;
  showLogin();
}

/* ---------- chat list ---------- */
async function loadChats() {
  // refresh unseen mentions first so the badges render correctly
  await refreshUnseenMentions();
  const { chats } = await api("/api/chats");
  state.chats = chats;
  const ul = document.getElementById("chat-list");
  ul.innerHTML = "";
  for (const c of chats) {
    const li = document.createElement("li");
    li.dataset.chatId = c.chat_id;
    const _init = (c.title || "?").trim().charAt(0).toUpperCase() || "?";
    const _unseen = (state.unseenMentions && state.unseenMentions[c.chat_id]) || 0;
    const _badgeHtml = _unseen > 0
      ? `<span class="mention-badge" title="${_unseen} unread mention${_unseen>1?"s":""}">@</span>`
      : "";
    li.innerHTML =
      `<div class="chat-list-avatar">` +
        `<span>${escapeHtml(_init)}</span>` +
        `<img src="/api/chats/${c.chat_id}/photo" alt="" loading="lazy" ` +
          `onerror="this.remove()">` +
      `</div>` +
      `<div class="chat-list-info">` +
        `<strong>${escapeHtml(c.title)}</strong>` +
        `<span class="meta">${c.message_count} msgs · ${c.kind || "?"}</span>` +
      `</div>` +
      _badgeHtml;
    li.onclick = () => {
      document.querySelectorAll("#chat-list li").forEach(el => el.classList.remove("active"));
      li.classList.add("active");
      selectChat(c);
    };
    ul.appendChild(li);
  }
}

/* ---------- messages ---------- */


function _renderChatHeader(c) {
  const header = document.getElementById("chat-header");
  if (!header || !c) return;
  const initial = (c.title || "?").trim().charAt(0).toUpperCase() || "?";
  const kindBase = (c.kind || "").replace(/_/g, " ");
  header.innerHTML =
    `<div class="chat-header-avatar">` +
      `<span>${escapeHtml(initial)}</span>` +
      `<img src="/api/chats/${c.chat_id}/photo" alt="" ` +
        `onerror="this.remove()">` +
    `</div>` +
    `<div class="chat-header-info">` +
      `<div class="chat-header-title">${escapeHtml(c.title || ("chat " + c.chat_id))}</div>` +
      `<div class="chat-header-kind">${escapeHtml(kindBase || "?")}</div>` +
    `</div>`;
  // async: enrich kind text with member counts
  _updateChatHeaderMemberCount(c.chat_id, kindBase);
}

async function _updateChatHeaderMemberCount(chatId, baseKindText) {
  try {
    const r = await api(`/api/chats/${chatId}/info`);
    if (!r || !r.ok) return;
    if (!state.activeChat
        || String(state.activeChat.chat_id) !== String(chatId)) return;
    const el = document.querySelector(".chat-header-kind");
    if (!el) return;
    const type = (r.info && r.info.type) || baseKindText;
    const total = r.member_count;
    const cached = r.members_cached;
    let text = String(type || "?").replace(/_/g, " ");
    if (total != null && total > 0) {
      text += ` · ${total} members`;
      if (cached != null && cached > 0) {
        text += ` (${cached} cached)`;
      }
    }
    el.textContent = text;
  } catch (e) {
    // silent
  }
}


async function selectChat(c) {
  state.activeChat = c;
  state.replyTo = null;
  _renderChatHeader(c);
  document.body.classList.add("chat-open");
  document.body.classList.toggle(
    "in-private-chat", !!(c && c.kind === "private"));
  document.getElementById("composer").hidden = false;
  if (typeof refreshChatMentions === "function") {
    refreshChatMentions(c.chat_id).catch(() => {});
  }
  renderReplyBanner();
  await loadAdmins(c.chat_id);
  await reloadMessages();
}

let _reloadInFlight = false;

async function reloadMessages(opts = {}) {
  if (_reloadInFlight) return;
  if (!state.activeChat) return;
  _reloadInFlight = true;
  try {
    await _doReloadMessages(opts);
  } finally {
    _reloadInFlight = false;
  }
}

async function _doReloadMessages(opts = {}) {
  if (!state.activeChat) return;
  const box = document.getElementById("message-list");
  const wasAtBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 100;
  const oldScrollTop = box.scrollTop;
  const chatIdAtStart = state.activeChat.chat_id;

  // fetch first — never clear the DOM before we know we have data
  let data;
  try {
    data = await api(
      `/api/chats/${chatIdAtStart}/messages?limit=100`);
  } catch (e) {
    console.warn("reloadMessages: fetch failed:", e);
    return;  // leave the current view untouched
  }

  // guard: user might have switched chats while we were fetching
  if (!state.activeChat || state.activeChat.chat_id !== chatIdAtStart) {
    return;
  }

  // guard: bad response shape
  if (!data || !Array.isArray(data.messages)) {
    console.warn("reloadMessages: bad response:", data);
    return;
  }

  // Deduplicate by message_id (defensive)
  const _seenIds = new Set();
  const messages = [];
  for (const _m of (data.messages || [])) {
    if (!_seenIds.has(_m.message_id)) {
      _seenIds.add(_m.message_id);
      messages.push(_m);
    }
  }

  // ---- incremental append (auto-fetch path) ----
  if (opts.incremental && state.messages.length > 0) {
    const lastKnownId = state.messages[state.messages.length - 1].message_id;
    const fresh = messages.filter(m => m.message_id > lastKnownId);
    if (fresh.length === 0) return;

    const overflow = state.messages.length + fresh.length - 100;
    if (overflow > 0) {
      for (let i = 0; i < overflow; i++) {
        state.messages.shift();
        if (box.firstChild) box.removeChild(box.firstChild);
      }
    }

    let _lastRow = box.lastElementChild;
    let _lastFid = (_lastRow && _lastRow.dataset.fromId) || null;
    const _existingIds = new Set(state.messages.map(x => x.message_id));
    for (const m of fresh) {
      if (_existingIds.has(m.message_id)) continue;
      _existingIds.add(m.message_id);
      const _isOwn = isOwnMessage(m);
      const _fromStr = (!_isOwn && m.from_id != null) ? String(m.from_id) : null;
      const _showAv = !_isOwn && _fromStr !== null && _fromStr !== _lastFid;
      state.messages.push(m);
      const _bubble = renderMessage(m);
      box.appendChild(wrapWithAvatar(_bubble, m, _showAv));
      _lastFid = _isOwn ? null : _fromStr;
    }
    if (wasAtBottom) box.scrollTop = box.scrollHeight;
    return;
  }

  // ---- full reload ----
  state.messages = messages;

  // render into a fragment so we never leave the box half-built
  const frag = document.createDocumentFragment();
  let _lastFromId = null;
  for (const m of messages) {
    try {
      const _isOwn = isOwnMessage(m);
      const _fromStr = (!_isOwn && m.from_id != null) ? String(m.from_id) : null;
      const _showAv = !_isOwn && _fromStr !== null && _fromStr !== _lastFromId;
      const _bubble = renderMessage(m);
      frag.appendChild(wrapWithAvatar(_bubble, m, _showAv));
      _lastFromId = _isOwn ? null : _fromStr;
    } catch (e) {
      console.warn("renderMessage failed for", m.message_id, e);
    }
  }
  box.innerHTML = "";
  box.appendChild(frag);
  box.scrollTop = wasAtBottom ? box.scrollHeight : oldScrollTop;
}

function replyPreviewContent(p) {
  if (!p) return null;
  const text = (p.text || "").trim();
  if (text) return text.slice(0, 120);
  const map = {
    photo: "📷 Photo",
    video: "🎬 Video",
    animation: "🎞 GIF",
    document: "📄 Document",
    audio: "🎵 Audio",
    voice: "🎤 Voice message",
    video_note: "📹 Video note",
    sticker: "🎨 Sticker",
    location: "📍 Location",
    contact: "👤 Contact",
    poll: "📊 Poll",
    dice: "🎲 Dice",
  };
  return map[p.content_type] || `[${p.content_type}]`;
}

function choosePreviewable(files) {
  const previews = [];
  const others = [];
  const bestByType = {};
  for (const f of files) {
    if (f.type === "photo" || f.type === "sticker" || f.type === "animation") {
      const cur = bestByType[f.type];
      if (!cur || (f.size || 0) > (cur.size || 0)) bestByType[f.type] = f;
    } else {
      others.push(f);
    }
  }
  for (const t of ["photo", "sticker", "animation"]) {
    if (bestByType[t]) previews.push(bestByType[t]);
  }
  return { previews, others };
}

function renderMediaHtml(files) {
  const { previews, others } = choosePreviewable(files || []);
  let html = "";

  for (const f of previews) {
    const fid = encodeURIComponent(f.unique_id);
    const src = `/api/files/${fid}`;
    if (f.type === "animation") {
      html += `<video class="img-preview" src="${src}" ` +
              `data-lightbox="video" data-src="${src}" ` +
              `autoplay loop muted playsinline></video>`;
    } else {
      html += `<img class="img-preview" src="${src}" ` +
              `loading="lazy" data-lightbox="image" ` +
              `data-src="${src}" alt="${escapeHtml(f.type)}">`;
    }
  }

  for (const f of others) {
    const fid = encodeURIComponent(f.unique_id);
    const sz = f.size ? ` · ${Math.round(f.size / 1024)} KB` : "";
    html +=
      `<span class="file-wrap">` +
      `<a class="file" href="/api/files/${fid}" target="_blank" rel="noopener">` +
      `📎 ${escapeHtml(f.type)}${sz}</a>` +
      `<a class="file-dl" href="/api/files/${fid}?download=1" ` +
      `download title="Download">⬇</a>` +
      `</span>`;
  }

  return html;
}

function isOwnMessage(m) {
  if (state.botId == null || m.from_id == null) return false;
  return String(state.botId) === String(m.from_id);
}

function wrapWithAvatar(bubble, m, showAvatar) {
  const row = document.createElement("div");
  const isOwn = isOwnMessage(m);
  const isPrivate = !!(state.activeChat && state.activeChat.kind === "private");

  let senderId = null;
  if (m.from_id != null) senderId = m.from_id;
  else if (m.sender_chat_id != null) senderId = "chat:" + m.sender_chat_id;

  const hasAvatarSlot = !isOwn && !isPrivate && senderId != null;

  row.className = isOwn ? "msg-row outgoing" : "msg-row incoming";
  row.dataset.fromId = isOwn ? "" : (senderId != null ? String(senderId) : "");

  if (hasAvatarSlot) {
    const av = document.createElement("div");
    av.className = "avatar";
    av.style.visibility = "hidden";
    const initial = (m.from_name || "?").trim().charAt(0).toUpperCase() || "?";
    let avatarUrl = null;
    if (m.from_id != null) {
      avatarUrl = `/api/users/${m.from_id}/photo`;
    } else if (m.sender_chat_id != null) {
      avatarUrl = `/api/chats/${m.sender_chat_id}/photo`;
    }
    if (avatarUrl) {
      const img = document.createElement("img");
      img.src = avatarUrl;
      img.alt = "";
      img.loading = "lazy";
      img.addEventListener("error", () => {
        img.remove();
        av.textContent = initial;
      });
      av.appendChild(img);
    } else {
      av.textContent = initial;
    }
    row.appendChild(av);
  } else if (!isOwn && !isPrivate) {
    row.style.paddingLeft = "38px";
    row.dataset.noAvatar = "1";
  }

  row.appendChild(bubble);

  // attach swipe NOW that bubble has a real parent
  if (typeof window._attachRowSwipe === "function") {
    try { window._attachRowSwipe(row, bubble, m); } catch (e) {}
  }

  return row;
}



/* ==============================================================
   Entities → HTML (mentions, links, bold, italic, code, etc.)
   ============================================================== */

function _escHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function _escAttr(s) {
  return _escHtml(s).replace(/`/g, "&#96;");
}

function renderEntities(text, entities) {
  if (!text) return "";
  if (!entities || entities.length === 0) {
    return _escHtml(text);
  }
  // sort by offset; drop overlapping (keep longest at each start)
  const sorted = entities
    .filter(e => typeof e.offset === "number" && typeof e.length === "number")
    .sort((a, b) => a.offset - b.offset || b.length - a.length);

  let out = "";
  let pos = 0;
  for (const e of sorted) {
    if (e.offset < pos) continue;  // overlap
    const start = e.offset;
    const end = e.offset + e.length;
    if (end > text.length) continue;

    out += _escHtml(text.slice(pos, start));
    const inner = _escHtml(text.slice(start, end));

    switch (e.type) {
      case "bold":
        out += `<b>${inner}</b>`; break;
      case "italic":
        out += `<i>${inner}</i>`; break;
      case "underline":
        out += `<u>${inner}</u>`; break;
      case "strikethrough":
        out += `<s>${inner}</s>`; break;
      case "spoiler":
        out += `<span class="spoiler" onclick="this.classList.add('revealed')">${inner}</span>`;
        break;
      case "code":
        out += `<code class="inline-code">${inner}</code>`; break;
      case "pre":
        out += `<pre class="code-block">${inner}</pre>`; break;
      case "blockquote":
        out += `<blockquote>${inner}</blockquote>`; break;
      case "mention": {
        const un = text.slice(start, end).replace(/^@/, "");
        out += `<a class="mention-link" href="javascript:void(0)" ` +
               `data-mention="${_escAttr(un)}">${inner}</a>`;
        break;
      }
      case "text_mention": {
        const uid = e.user && e.user.id;
        if (uid) {
          out += `<a class="mention-link" href="javascript:void(0)" ` +
                 `data-user-id="${uid}">${inner}</a>`;
        } else {
          out += `<span class="mention-text">${inner}</span>`;
        }
        break;
      }
      case "hashtag":
        out += `<a class="hashtag-link" href="javascript:void(0)" ` +
               `data-hashtag="${_escAttr(text.slice(start, end))}">${inner}</a>`;
        break;
      case "bot_command":
        out += `<code class="bot-cmd">${inner}</code>`; break;
      case "url":
      case "text_link": {
        const url = e.type === "url" ? text.slice(start, end) : (e.url || "");
        out += `<a class="text-link" href="${_escAttr(url)}" ` +
               `target="_blank" rel="noopener noreferrer">${inner}</a>`;
        break;
      }
      case "email":
      case "phone_number":
        out += `<a class="text-link" href="mailto:${_escAttr(text.slice(start, end))}">${inner}</a>`;
        break;
      default:
        out += inner;
    }
    pos = end;
  }
  out += _escHtml(text.slice(pos));
  return out;
}

/* wire mention clicks after render */
function wireMentions(root) {
  if (!root) return;
  root.querySelectorAll(".mention-link[data-user-id]").forEach(el => {
    el.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const uid = parseInt(el.dataset.userId, 10);
      if (Number.isFinite(uid)) openUserProfile(uid);
    });
  });
  root.querySelectorAll(".mention-link[data-mention]").forEach(el => {
    el.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const un = el.dataset.mention || "";
      // try to resolve username → user_id from cached entities in messages
      const target = (state.messages || []).find(m =>
        m.from_username && m.from_username.toLowerCase() === un.toLowerCase());
      if (target && target.from_id != null) {
        openUserProfile(target.from_id);
      } else {
        window.open(`https://t.me/${encodeURIComponent(un)}`, "_blank",
                    "noopener,noreferrer");
      }
    });
  });
}

/* ==============================================================
   Admin badge — fetch + cache per chat
   ============================================================== */

async function loadAdmins(chatId) {
  try {
    const r = await api(`/api/chats/${chatId}/admins`);
    if (r && r.ok) {
      state.admins = {};
      for (const a of (r.admins || [])) {
        state.admins[a.user_id] = a;
      }
      return;
    }
  } catch (e) {
    console.warn("loadAdmins:", e);
  }
  state.admins = {};
}

function adminBadgeFor(userId) {
  if (!state.admins || userId == null) return "";
  const a = state.admins[userId];
  if (!a) return "";
  if (a.status === "creator" || a.status === "owner") {
    const ownerLabel = a.custom_title
      ? _escHtml(a.custom_title)
      : "👑 owner";
    return `<span class="admin-badge owner">${ownerLabel}</span>`;
  }
  if (a.status === "administrator") {
    const label = a.custom_title
      ? _escHtml(a.custom_title)
      : "admin";
    return `<span class="admin-badge admin">${label}</span>`;
  }
  return "";
}

/* ==============================================================
   Lightbox — click media to open, scroll to zoom, drag to pan
   ============================================================== */

let _lbState = { scale: 1, tx: 0, ty: 0, dragging: false,
                 sx: 0, sy: 0 };

function openLightbox(src, kind, downloadName) {
  const lb = document.getElementById("lightbox");
  const inner = document.getElementById("lightbox-inner");
  if (!lb || !inner) return;

  inner.innerHTML = "";
  _lbState = { scale: 1, tx: 0, ty: 0, dragging: false,
               sx: 0, sy: 0 };

  let el;
  if (kind === "video") {
    el = document.createElement("video");
    el.src = src;
    el.controls = true;
    el.autoplay = true;
    el.loop = true;
    el.muted = true;
    el.playsInline = true;
  } else {
    el = document.createElement("img");
    el.src = src;
    el.alt = "";
  }
  el.style.transform = "translate(0px, 0px) scale(1)";
  el.style.transformOrigin = "center center";
  el.draggable = false;
  inner.appendChild(el);

  lb.hidden = false;
  document.body.style.overflow = "hidden";

  const applyTransform = () => {
    el.style.transform =
      `translate(${_lbState.tx}px, ${_lbState.ty}px) ` +
      `scale(${_lbState.scale})`;
  };

  lb.onwheel = (ev) => {
    ev.preventDefault();
    const delta = ev.deltaY < 0 ? 1.2 : 1 / 1.2;
    _lbState.scale = Math.max(0.5, Math.min(8, _lbState.scale * delta));
    applyTransform();
  };

  inner.onmousedown = (ev) => {
    if (ev.target !== el) return;
    _lbState.dragging = true;
    _lbState.sx = ev.clientX - _lbState.tx;
    _lbState.sy = ev.clientY - _lbState.ty;
    el.style.cursor = "grabbing";
  };
  inner.onmousemove = (ev) => {
    if (!_lbState.dragging) return;
    _lbState.tx = ev.clientX - _lbState.sx;
    _lbState.ty = ev.clientY - _lbState.sy;
    applyTransform();
  };
  inner.onmouseup = () => {
    _lbState.dragging = false;
    el.style.cursor = "grab";
  };
  inner.onmouseleave = () => {
    _lbState.dragging = false;
  };

  el.style.cursor = "grab";

  const close = () => {
    lb.hidden = true;
    document.body.style.overflow = "";
    inner.innerHTML = "";
    lb.onwheel = null;
    inner.onmousedown = null;
    inner.onmousemove = null;
    inner.onmouseup = null;
    inner.onmouseleave = null;
  };

  lb.querySelector(".lightbox-close").onclick = close;
  lb.onclick = (ev) => {
    if (ev.target === lb) close();
  };
  const keyHandler = (ev) => {
    if (ev.key === "Escape") {
      close();
      document.removeEventListener("keydown", keyHandler);
    }
  };
  document.addEventListener("keydown", keyHandler);
}

function renderMessage(m) {
  const div = document.createElement("div");
    const isOwn = isOwnMessage(m);
  div.className = isOwn ? "msg outgoing" : "msg incoming";
  div.dataset.messageId = m.message_id;

  const when = m.date
    ? new Date(m.date * 1000).toLocaleString([], {
        hour: "2-digit", minute: "2-digit",
      })
    : "";

  const _adminBadge = isOwn ? "" : adminBadgeFor(m.from_id);
  const who = isOwn
    ? ""
    : escapeHtml(m.from_name || "?") +
      (m.is_bot ? " 🤖" : "") +
      (_adminBadge ? ` ${_adminBadge}` : "");
  const whoHtml = who ? `<span class="who">${who}</span>` : "";

  let forwardHtml = "";
  if (m.forward_from) {
    const ff = m.forward_from;
    const icon = ff.type === "channel" ? "📢"
               : ff.type === "hidden_user" ? "👻" : "👤";
    const name = escapeHtml(ff.name || "?");
    if (ff.id != null && ff.type !== "hidden_user") {
      forwardHtml =
        `<div class="msg-forward" data-fwd-id="${ff.id}" ` +
        `data-fwd-type="${escapeHtml(ff.type)}" ` +
        `data-fwd-username="${escapeHtml(ff.username || "")}">` +
        `${icon} Forwarded from <b>${name}</b></div>`;
    } else {
      forwardHtml =
        `<div class="msg-forward">${icon} Forwarded from <b>${name}</b></div>`;
    }
  }

  let replyHtml = "";
  if (m.reply_to_message_id) {
    const p = m.reply_preview;
    let previewInner;
    if (p) {
      const pName = (state.botId != null && p.from_id === state.botId)
        ? "You" : escapeHtml(p.from_name || "?");
      previewInner =
        `<span class="reply-name">${pName}</span>` +
        `<span class="reply-text">${escapeHtml(replyPreviewContent(p))}</span>`;
    } else {
      previewInner =
        `<span class="reply-name">message #${m.reply_to_message_id}</span>` +
        `<span class="reply-text">(not loaded)</span>`;
    }
    replyHtml =
      `<div class="reply" data-target-id="${m.reply_to_message_id}">` +
      previewInner + `</div>`;
  }

  let textHtml = "";
  const body = m.text || m.caption || "";
  if (body) {
    const _ents = m.entities || [];
    textHtml = `<div class="bubble-text">${renderEntities(body, _ents)}</div>`;
  }

  const mediaHtml = renderMediaHtml(m.files);

  let reactionsHtml = "";
  if (m.reactions && m.reactions.length > 0) {
    reactionsHtml = '<div class="msg-reactions">';
    for (const r of m.reactions) {
      reactionsHtml += `<span class="reaction-chip">${escapeHtml(r.emoji)} <b>${r.count}</b></span>`;
    }
    reactionsHtml += '</div>';
  }

  div.innerHTML =
    whoHtml +
    forwardHtml + replyHtml + textHtml + mediaHtml + reactionsHtml +
    `<div class="msg-footer">` +
    `<span class="msg-id">#${m.message_id}</span>` +
    `<span class="date">${when}</span>` +
    `</div>`;

  div.addEventListener("click", (e) => {
    if (Date.now() - (window._lastSwipeTs || 0) < 300) return;
    if (e.target.closest("a")) return;
    if (e.target.closest(".media-del, .media-fav")) return;
    if (e.target.closest(".msg .reply")) {
      const replyEl = e.target.closest(".reply");
      jumpToReply(parseInt(replyEl.dataset.targetId, 10));
      return;
    }
    if (e.target.closest("[data-lightbox]")) return;
    e.stopPropagation();
    openContextMenu(m, e.clientX, e.clientY);
  });

  /* swipe is attached in wrapWithAvatar (see _attachRowSwipe) */

  div.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    e.stopPropagation();
    openContextMenu(m, e.clientX, e.clientY);
  });

  // forward badge → open profile (user) or telegram link (channel)
  div.querySelectorAll(".msg-forward[data-fwd-id]").forEach(el => {
    el.style.cursor = "pointer";
    el.title = "Click to view source";
    el.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const fwdType = el.dataset.fwdType;
      const fwdId = parseInt(el.dataset.fwdId, 10);
      const fwdUsername = el.dataset.fwdUsername || "";
      if (fwdType === "user" || fwdType === "chat") {
        if (Number.isFinite(fwdId)) openUserProfile(fwdId);
      } else if (fwdType === "channel") {
        if (fwdUsername) {
          window.open(`https://t.me/${encodeURIComponent(fwdUsername)}`,
                      "_blank", "noopener,noreferrer");
        } else if (Number.isFinite(fwdId)) {
          openChatInfoById(fwdId);
        }
      }
    });
  });

  // wire media lightbox + mentions
  div.querySelectorAll("[data-lightbox]").forEach(el => {
    el.style.cursor = "zoom-in";
    el.addEventListener("click", (ev) => {
      ev.stopPropagation();
      openLightbox(el.dataset.src, el.dataset.lightbox);
    });
  });
  wireMentions(div);

  const moreBtn = div.querySelector(".msg-more");
  if (moreBtn) {
    moreBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const r2 = moreBtn.getBoundingClientRect();
      openContextMenu(m, r2.left, r2.bottom + 4);
    });
  }

  return div;
}

function jumpToReply(targetId) {
  if (!Number.isFinite(targetId)) return;
  const target = document.querySelector(`[data-message-id="${targetId}"]`);
  if (!target) {
    alert(`Message #${targetId} is not in the loaded window.`);
    return;
  }
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  target.classList.remove("highlight");
  void target.offsetWidth;
  target.classList.add("highlight");
  setTimeout(() => target.classList.remove("highlight"), 1400);
}

function setReplyTo(m) {
  state.replyTo = { message_id: m.message_id, chat_id: state.activeChat.chat_id };
  renderReplyBanner();
  document.getElementById("message-input").focus();
}

function renderReplyBanner() {
  const banner = document.getElementById("reply-banner");
  const text = document.getElementById("reply-banner-text");
  if (!state.replyTo) {
    banner.hidden = true;
    return;
  }
  banner.hidden = false;
  text.textContent = `↩ Replying to #${state.replyTo.message_id}`;
}

/* ---------- send ---------- */
let _sendPending = false;

async function send(ev) {
  if (ev && typeof ev.preventDefault === "function") ev.preventDefault();
  if (!state.activeChat || _sendPending) return;
  const chatIdAtStart = state.activeChat.chat_id;
  const input = document.getElementById("message-input");
  const btn = document.getElementById("send-btn");
  const text = input.value.trim();
  if (!text) return;

  _sendPending = true;
  input.disabled = true;
  if (btn) btn.disabled = true;

  const payload = { text };
  if (state.replyTo) payload.reply_parameters = state.replyTo;
  input.value = "";
  state.replyTo = null;
  renderReplyBanner();

  try {
    const r = await api(`/api/chats/${state.activeChat.chat_id}/send`, {
      method: "POST", body: JSON.stringify(payload),
    });
    if (!r.ok) {
      alert("Send failed: " + (r.error || "unknown"));
      input.value = text;
    } else {
      // try incremental first, then verify the message landed
      await reloadMessages({ incremental: true });
      const last = state.messages[state.messages.length - 1];
      if (!last || last.message_id !== r.message_id) {
        await reloadMessages();
      }
      // sanity: user must still be on the same chat
      if (!state.activeChat || state.activeChat.chat_id !== chatIdAtStart) {
        console.warn("activeChat changed during send — restoring");
        state.activeChat = state.chats.find(c => c.chat_id === chatIdAtStart) || null;
        if (state.activeChat) {
          _renderChatHeader(state.activeChat);
          document.getElementById("composer").hidden = false;
        }
      }
    }
  } catch (e) {
    alert("Network error");
    input.value = text;
  } finally {
    _sendPending = false;
    input.disabled = false;
    if (btn) btn.disabled = false;
    input.focus();
  }
}

/* ---------- bootstrap ---------- */
/* ---------- auto-fetch ---------- */
async function setAutoFetch(enabled) {
  state.autoFetch = enabled;
  if (_autoFetchTimer) {
    clearInterval(_autoFetchTimer);
    _autoFetchTimer = null;
  }
  try {
    await api(`/api/poller/${enabled ? "start" : "stop"}`, {
      method: "POST", body: "{}",
    });
  } catch (e) {
    console.warn("poller toggle failed:", e);
  }
  if (enabled) {
    _autoFetchTimer = setInterval(async () => {
      if (!state.activeChat) return;
      try {
        await reloadMessages({ incremental: true });
      } catch (e) {
        console.warn("auto-fetch:", e);
      }
    }, 8000);
  }
}

/* ---------- context menu ---------- */
function openContextMenu(msg, x, y) {
  const menu = document.getElementById("ctx-menu");
  menu.innerHTML = "";

  const btnReply = document.createElement("button");
  btnReply.textContent = "↩ Reply";
  btnReply.onclick = () => { setReplyTo(msg); hideContextMenu(); };
  menu.appendChild(btnReply);

  const btnReact = document.createElement("button");
  btnReact.textContent = "😀 React";
  btnReact.onclick = () => {
    hideContextMenu();
    openReactionPicker(msg, x, y);
  };
  menu.appendChild(btnReact);

  const { previews, others } = choosePreviewable(msg.files || []);
  const allFiles = [...previews, ...others];
  if (allFiles.length > 0) {
    const sep = document.createElement("div");
    sep.className = "ctx-sep";
    menu.appendChild(sep);
    for (const f of allFiles) {
      const btn = document.createElement("button");
      const sz = f.size ? ` (${Math.round(f.size / 1024)} KB)` : "";
      btn.textContent = `⬇ Save ${f.type}${sz}`;
      btn.onclick = () => { triggerDownload(f.unique_id); hideContextMenu(); };
      menu.appendChild(btn);
    }
  }

  menu.hidden = false;
  // keep menu inside viewport
  const rect = menu.getBoundingClientRect();
  const maxX = window.innerWidth - rect.width - 8;
  const maxY = window.innerHeight - rect.height - 8;
  menu.style.left = Math.min(x, maxX) + "px";
  menu.style.top = Math.min(y, maxY) + "px";
}

function hideContextMenu() {
  const menu = document.getElementById("ctx-menu");
  if (menu) menu.hidden = true;
}

function triggerDownload(fuid) {
  const a = document.createElement("a");
  a.href = `/api/files/${encodeURIComponent(fuid)}?download=1`;
  a.download = "";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

/* ---------- bootstrap ---------- */
document.getElementById("login-form").addEventListener("submit", login);
document.getElementById("send-btn").addEventListener("click", send);
document.getElementById("logout-btn").addEventListener("click", logout);
document.getElementById("toggle-sidebar").addEventListener("click", () => {
  document.getElementById("sidebar").classList.toggle("open");
});
document.getElementById("cancel-reply").addEventListener("click", () => {
  state.replyTo = null;
  renderReplyBanner();
});
document.getElementById("auto-fetch").addEventListener("change", async (e) => {
  localStorage.setItem("termgram.autoFetch", e.target.checked ? "1" : "0");
  await setAutoFetch(e.target.checked);
});
document.getElementById("message-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    e.stopPropagation();
    send(e);
  }
});

document.addEventListener("click", hideContextMenu);
document.addEventListener("scroll", hideContextMenu, true);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") hideContextMenu();
});

(async function boot() {
  try {
    const r = await fetch("/api/me", { credentials: "same-origin" });
    if (!r.ok) {
      showLogin();
      return;
    }
    await showApp();
    await loadReactions();
    // restore auto-fetch preference & sync checkbox with server
    const saved = localStorage.getItem("termgram.autoFetch") === "1";
    const st = await api("/api/poller/status").catch(() => null);
    const running = !!(st && st.running);
    const cb = document.getElementById("auto-fetch");
    if (saved && !running) {
      cb.checked = true;
      await setAutoFetch(true);
    } else if (!saved && running) {
      await setAutoFetch(false);
      cb.checked = false;
    } else {
      cb.checked = running;
      if (running) setAutoFetch(true);
    }
  } catch (e) {
    console.warn("boot error:", e);
    showLogin();
  }
})();

/* ==============================================================
   Reaction support
   ============================================================== */
async function loadReactions() {
  try {
    const r = await api("/api/reactions");
    state.reactions = (r && r.reactions) || [];
  } catch (e) {
    console.warn("loadReactions:", e);
    state.reactions = [];
  }
}

function _defaultReactions() {
  return [
    { emoji: "👍", label: "Thumbs Up" },
    { emoji: "❤️", label: "Red Heart" },
    { emoji: "🔥", label: "Fire" },
    { emoji: "😂", label: "Laughing" },
    { emoji: "😮", label: "Surprised" },
    { emoji: "😢", label: "Crying" },
    { emoji: "🙏", label: "Pray" },
    { emoji: "👏", label: "Clap" },
    { emoji: "🎉", label: "Party" },
    { emoji: "💯", label: "Hundred" },
    { emoji: "🤔", label: "Thinking" },
    { emoji: "👌", label: "OK" },
  ];
}

function openReactionPicker(msg, x, y) {
  const picker = document.getElementById("react-picker");
  if (!picker) return;
  picker.innerHTML = "";

  const list = (state.reactions && state.reactions.length > 0)
    ? state.reactions
    : _defaultReactions();

  for (const r of list) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = r.emoji;
    btn.title = r.label || r.emoji;
    btn.onclick = (e) => {
      e.stopPropagation();
      picker.hidden = true;
      sendReaction(msg, r.emoji);
    };
    picker.appendChild(btn);
  }

  const sep = document.createElement("div");
  sep.className = "react-sep";
  picker.appendChild(sep);

  const clearBtn = document.createElement("button");
  clearBtn.type = "button";
  clearBtn.className = "react-clear";
  clearBtn.textContent = "✕ Clear my reaction";
  clearBtn.onclick = (e) => {
    e.stopPropagation();
    picker.hidden = true;
    sendReaction(msg, "");
  };
  picker.appendChild(clearBtn);

  picker.hidden = false;
  const rect = picker.getBoundingClientRect();
  picker.style.left = Math.min(x, window.innerWidth - rect.width - 8) + "px";
  picker.style.top = Math.min(y, window.innerHeight - rect.height - 8) + "px";
}

async function sendReaction(msg, emoji) {
  if (!state.activeChat) return;
  const cid = state.activeChat.chat_id;
  try {
    const r = await api(
      `/api/chats/${cid}/messages/${msg.message_id}/react`,
      { method: "POST", body: JSON.stringify({ emoji: emoji || "" }) }
    );
    if (!r.ok) {
      alert("Reaction failed: " + (r.error || "unknown"));
      return;
    }
    const localMsg = state.messages.find(
      m => m.message_id === msg.message_id);
    if (localMsg) {
      if (emoji) {
        localMsg.reactions = localMsg.reactions || [];
        const ex = localMsg.reactions.find(x => x.emoji === emoji);
        if (ex) ex.count += 1;
        else localMsg.reactions.push({ emoji: emoji, count: 1 });
      } else {
        localMsg.reactions = [];
      }
      _rerenderMessageRow(localMsg);
    }
    // keep picker sorted by usage on next open
    if (emoji) {
      const rx = state.reactions.find(x => x.emoji === emoji);
      if (rx) {
        rx.count = (rx.count || 0) + 1;
        rx.last_used_at = new Date().toISOString();
      } else {
        state.reactions.push({
          emoji: emoji, label: emoji, count: 1,
          last_used_at: new Date().toISOString(),
        });
      }
      state.reactions.sort((a, b) => {
        const ca = a.count || 0, cb = b.count || 0;
        if (ca !== cb) return cb - ca;
        const la = a.last_used_at || "", lb = b.last_used_at || "";
        if (la !== lb) return lb.localeCompare(la);
        return 0;
      });
    }
  } catch (e) {
    console.warn("sendReaction error:", e);
  }
}

function _rerenderMessageRow(localMsg) {
  const bubbles = document.querySelectorAll(
    `.msg[data-message-id="${localMsg.message_id}"]`);
  if (bubbles.length === 0) return;
  const bubble = bubbles[0];
  const row = bubble.closest(".msg-row");
  if (!row) return;
  // remove any duplicate rows for this message_id
  for (let _i = 1; _i < bubbles.length; _i++) {
    const _extra = bubbles[_i].closest(".msg-row");
    if (_extra && _extra.parentElement) _extra.remove();
  }
  const hadAvatar = !!row.querySelector(".avatar");
  const isOwn = isOwnMessage(localMsg);
  const isPrivate = !!(state.activeChat
                       && state.activeChat.kind === "private");
  const showAvatar = hadAvatar && !isOwn && !isPrivate;
  const newBubble = renderMessage(localMsg);
  const newRow = wrapWithAvatar(newBubble, localMsg, showAvatar);
  row.parentElement.replaceChild(newRow, row);
}

/* ==============================================================
   Group features: info modal, members, mention, forward, upload
   ============================================================== */

function showModal(html) {
  const modal = document.getElementById("modal");
  const body = document.getElementById("modal-body");
  body.innerHTML = html;
  modal.hidden = false;
}

function hideModal() {
  const modal = document.getElementById("modal");
  if (modal) modal.hidden = true;
}

function fmtBytes(n) {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n < 10 ? 1 : 0)} ${u[i]}`;
}

/* ---------- chat info ---------- */
async function openChatInfo() {
  if (!state.activeChat) return;
  const cid = state.activeChat.chat_id;
  showModal(`<h3>Loading…</h3>`);
  try {
    const data = await api(`/api/chats/${cid}/info`);
    if (!data.ok) {
      showModal(`<h3>Error</h3><p>${escapeHtml(data.error || "?")}</p>
        <button class="modal-close">Close</button>`);
      return;
    }
    const info = data.info || {};
    const mc = data.member_count != null ? data.member_count : "?";
    const cached = data.members_cached || 0;
    const photo = data.photo_unique_id
      ? `<img class="chat-photo" src="/api/files/${encodeURIComponent(data.photo_unique_id)}" alt="">`
      : `<div class="chat-photo chat-photo-fallback">${escapeHtml((info.title || "?").charAt(0))}</div>`;
    const username = info.username ? `@${escapeHtml(info.username)}` : "—";
    const desc = info.description
      ? `<div class="info-desc">${escapeHtml(info.description)}</div>`
      : "";
    const link = info.invite_link
      ? `<div class="info-row"><b>Invite link:</b> <a href="${escapeHtml(info.invite_link)}" target="_blank" rel="noopener">${escapeHtml(info.invite_link)}</a></div>`
      : "";
    const pinned = info.pinned_message
      ? `<div class="info-row"><b>Pinned:</b> ${escapeHtml((info.pinned_message.text || info.pinned_message.caption || "(media)").slice(0, 100))}</div>`
      : "";

    showModal(`
      <div class="chat-info-header">
        ${photo}
        <div class="chat-info-title">
          <h3>${escapeHtml(info.title || info.first_name || "?")}</h3>
          <div class="info-kind">${escapeHtml(info.type || "?")}</div>
        </div>
      </div>
      <div class="info-row"><b>ID:</b> <code>${cid}</code></div>
      <div class="info-row"><b>Username:</b> ${username}</div>
      <div class="info-row"><b>Members:</b> ${mc} total · ${cached} cached</div>
      ${link}
      ${pinned}
      ${desc}
      <div class="modal-actions">
        <button class="btn-primary" id="btn-show-members">Members (${cached})</button>
        <button class="btn-secondary modal-close">Close</button>
      </div>
    `);
    document.getElementById("btn-show-members").onclick = openMembersModal;
  } catch (e) {
    showModal(`<h3>Error</h3><p>${escapeHtml(String(e))}</p>
      <button class="modal-close">Close</button>`);
  }
}

/* ---------- members list + mention ---------- */
async function openMembersModal() {
  if (!state.activeChat) return;
  const cid = state.activeChat.chat_id;
  showModal(`<h3>Loading members…</h3>`);
  try {
    const data = await api(`/api/chats/${cid}/members`);
    if (!data.ok) {
      showModal(`<h3>Error</h3><p>${escapeHtml(data.error || "?")}</p>
        <button class="modal-close">Close</button>`);
      return;
    }
    const members = data.members || [];
    if (members.length === 0) {
      showModal(`<h3>No members cached</h3>
        <p>Run a fetch in this group first to collect senders.</p>
        <button class="modal-close">Close</button>`);
      return;
    }
    let rows = "";
    for (const m of members) {
      const un = m.username ? `@${escapeHtml(m.username)}` : "";
      const init = (m.name || "?").trim().charAt(0).toUpperCase() || "?";
      rows += `
        <div class="member-row" data-uid="${m.user_id}">
          <input type="checkbox" class="member-cb" value="${m.user_id}">
          <div class="member-avatar member-avatar-clickable" data-uid="${m.user_id}">
            <span>${escapeHtml(init)}</span>
            <img src="/api/users/${m.user_id}/photo" alt="" loading="lazy"
                 onerror="this.remove()">
          </div>
          <div class="member-info member-info-clickable" data-uid="${m.user_id}">
            <span class="member-name">${escapeHtml(m.name)}</span>
            <span class="member-un">${un}</span>
          </div>
          <span class="member-count">${m.message_count || 0}</span>
        </div>`;
    }
    showModal(`
      <h3>Members (${members.length})</h3>
      <div class="mention-form">
        <input type="text" id="mention-text" placeholder="Optional header text…">
        <div class="member-actions">
          <button type="button" class="btn-secondary" id="btn-select-all">Select all</button>
          <button type="button" class="btn-secondary" id="btn-select-none">Clear</button>
          <span id="mention-count" class="mention-count">0 selected</span>
        </div>
        <div class="member-list" id="member-list">${rows}</div>
        <div class="modal-actions">
          <button type="button" class="btn-primary" id="btn-do-mention">Mention selected</button>
          <button type="button" class="btn-secondary modal-close">Cancel</button>
        </div>
      </div>
    `);

    const updateCount = () => {
      const n = document.querySelectorAll(".member-cb:checked").length;
      document.getElementById("mention-count").textContent =
        `${n} selected`;
    };
    document.querySelectorAll(".member-cb").forEach(cb =>
      cb.addEventListener("change", updateCount));
    document.getElementById("btn-select-all").onclick = () => {
      document.querySelectorAll(".member-cb").forEach(cb => cb.checked = true);
      updateCount();
    };
    document.getElementById("btn-select-none").onclick = () => {
      document.querySelectorAll(".member-cb").forEach(cb => cb.checked = false);
      updateCount();
    };
    document.getElementById("btn-do-mention").onclick = async () => {
      const ids = [...document.querySelectorAll(".member-cb:checked")]
        .map(cb => parseInt(cb.value, 10));
      if (ids.length === 0) { alert("Select at least one member."); return; }
      const text = document.getElementById("mention-text").value.trim();
      const btn = document.getElementById("btn-do-mention");
      btn.disabled = true; btn.textContent = "Sending…";
      try {
        const r = await api(`/api/chats/${cid}/mention`, {
          method: "POST",
          body: JSON.stringify({
            user_ids: ids, text: text, all: false, batch_size: 30,
          }),
        });
        if (r.ok) {
          alert(`Mentioned ${r.mentioned} member(s) in ${r.messages_sent} message(s).`);
          hideModal();
          await reloadMessages({ incremental: true });
        } else {
          alert("Mention failed: " + (r.error || "unknown"));
        }
      } catch (e) {
        alert("Mention error: " + e);
      } finally {
        btn.disabled = false; btn.textContent = "Mention selected";
      }
    };

    // Profile open on avatar or name click
    document.querySelectorAll(
        ".member-avatar-clickable, .member-info-clickable"
    ).forEach(el => {
      el.addEventListener("click", async (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        const uid = parseInt(el.dataset.uid, 10);
        if (!Number.isFinite(uid)) return;
        await openUserProfile(uid);
        const body = document.getElementById("modal-body");
        const actions = body.querySelector(".modal-actions");
        if (!actions) return;
        if (!actions.querySelector(".btn-back-to-members")) {
          const backBtn = document.createElement("button");
          backBtn.className = "btn-secondary btn-back-to-members";
          backBtn.textContent = "← Back to members";
          backBtn.onclick = () => openMembersModal();
          actions.insertBefore(backBtn, actions.firstChild);
        }
      });
    });
  } catch (e) {
    showModal(`<h3>Error</h3><p>${escapeHtml(String(e))}</p>
      <button class="modal-close">Close</button>`);
  }
}

/* ---------- forward modal ---------- */
function openForwardModal(msg) {
  const chats = state.chats || [];
  if (chats.length === 0) {
    alert("No chats loaded.");
    return;
  }
  let rows = "";
  for (const c of chats) {
    if (c.chat_id === state.activeChat.chat_id) continue;
    rows += `
      <button type="button" class="forward-row" data-cid="${c.chat_id}">
        <span>${escapeHtml(c.title || ("chat " + c.chat_id))}</span>
        <span class="forward-kind">${c.kind || "?"}</span>
      </button>`;
  }
  showModal(`
    <h3>Forward to…</h3>
    <div class="forward-list">${rows}</div>
    <div class="modal-actions">
      <button type="button" class="btn-secondary modal-close">Cancel</button>
    </div>
  `);
  document.querySelectorAll(".forward-row").forEach(btn => {
    btn.onclick = async () => {
      const toCid = btn.dataset.cid;
      btn.disabled = true;
      try {
        const r = await api(
          `/api/chats/${state.activeChat.chat_id}/forward`, {
            method: "POST",
            body: JSON.stringify({
              to_chat_id: toCid,
              message_id: msg.message_id,
            }),
          });
        if (r.ok) {
          alert("Forwarded.");
          hideModal();
        } else {
          alert("Forward failed: " + (r.error || "unknown"));
          btn.disabled = false;
        }
      } catch (e) {
        alert("Forward error: " + e);
        btn.disabled = false;
      }
    };
  });
}

/* ---------- upload ---------- */
function detectKind(file) {
  const mime = (file.type || "").toLowerCase();
  if (mime === "image/gif") return "animation";
  if (mime.startsWith("image/")) return "photo";
  if (mime.startsWith("video/")) return "video";
  if (mime.startsWith("audio/")) return "audio";
  return "document";
}

async function uploadFile(file, caption) {
  if (!state.activeChat) return;
  const cid = state.activeChat.chat_id;
  const _ks = document.getElementById("upload-kind");
  const _k = _ks ? (_ks.value || "auto") : "auto";
  const kind = (_k === "auto") ? detectKind(file) : _k;
  const fd = new FormData();
  fd.append("kind", kind);
  if (caption) fd.append("caption", caption);
  fd.append("file", file, file.name);

  const composer = document.getElementById("composer");
  const status = document.createElement("div");
  status.className = "upload-status";
  status.textContent = `Uploading ${file.name} (${fmtBytes(file.size)})…`;
  composer.parentElement.insertBefore(status, composer);

  try {
    const r = await fetch(`/api/chats/${cid}/upload`, {
      method: "POST",
      headers: { "X-CSRF-Token": state.csrf || "" },
      credentials: "same-origin",
      body: fd,
    });
    const data = await r.json().catch(() => ({}));
    status.remove();
    if (data.ok) {
      await reloadMessages({ incremental: true });
    } else {
      alert("Upload failed: " + (data.error || r.status));
    }
  } catch (e) {
    status.remove();
    alert("Upload error: " + e);
  }
}

async function _onFilesSelected(files, caption) {
  if (!files || files.length === 0) return;
  for (const f of files) {
    if (f.size > 50 * 1024 * 1024) {
      alert(`"${f.name}" exceeds 50 MB limit.`);
      continue;
    }
    await uploadFile(f, caption);
  }
}

/* ---------- wire up buttons + drag & drop ---------- */
function setupGroupFeatures() {
  // chat header → open info
  const hdr = document.getElementById("chat-header");
  if (hdr && !hdr.dataset.wired) {
    hdr.dataset.wired = "1";
    hdr.style.cursor = "pointer";
    hdr.title = "Click to view group info";
    hdr.addEventListener("click", (e) => {
      if (e.target.closest(".chat-back-btn")) return;
      openChatInfo();
    });
  }

  // upload button
  const ub = document.getElementById("upload-btn");
  const fi = document.getElementById("file-input");
  if (ub && fi && !ub.dataset.wired) {
    ub.dataset.wired = "1";
    ub.addEventListener("click", () => fi.click());
    fi.addEventListener("change", async () => {
      const files = [...fi.files];
      fi.value = "";
      const caption = document.getElementById("message-input").value.trim();
      document.getElementById("message-input").value = "";
      await _onFilesSelected(files, caption);
    });
  }

  // drag & drop
  const main = document.getElementById("main");
  if (main && !main.dataset.dndWired) {
    main.dataset.dndWired = "1";
    let counter = 0;
    main.addEventListener("dragenter", (e) => {
      e.preventDefault();
      counter++;
      main.classList.add("drag-over");
    });
    main.addEventListener("dragleave", (e) => {
      e.preventDefault();
      counter--;
      if (counter <= 0) { counter = 0; main.classList.remove("drag-over"); }
    });
    main.addEventListener("dragover", (e) => e.preventDefault());
    main.addEventListener("drop", async (e) => {
      e.preventDefault();
      counter = 0;
      main.classList.remove("drag-over");
      if (!state.activeChat) return;
      await _onFilesSelected([...e.dataTransfer.files], "");
    });
  }

  // modal close
  const modal = document.getElementById("modal");
  if (modal && !modal.dataset.wired) {
    modal.dataset.wired = "1";
    modal.addEventListener("click", (e) => {
      if (e.target.classList.contains("modal-close") ||
          e.target.id === "modal-backdrop") {
        hideModal();
      }
    });
  }
}

/* add Forward to context menu — hook into existing openContextMenu */
const _origOpenContextMenu = window.openContextMenu || openContextMenu;
openContextMenu = function(msg, x, y) {
  _origOpenContextMenu.call(this, msg, x, y);
  const menu = document.getElementById("ctx-menu");
  if (!menu || menu.hidden) return;
  if (!menu.querySelector(".ctx-forward-btn")) {
    const sep = document.createElement("div");
    sep.className = "ctx-sep";
    menu.appendChild(sep);
    const fwd = document.createElement("button");
    fwd.className = "ctx-forward-btn";
    fwd.textContent = "➡ Forward…";
    fwd.onclick = () => { hideModal(); openForwardModal(msg); };
    menu.appendChild(fwd);
  }
};

/* run setup after boot */
setTimeout(setupGroupFeatures, 300);



/* ==============================================================
   User profile modal
   ============================================================== */
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(String(text));
    return true;
  } catch (_) {
    const ta = document.createElement("textarea");
    ta.value = String(text);
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (_) {}
    ta.remove();
    return ok;
  }
}

async function openUserProfile(userId) {
  if (userId == null) return;
  showModal(`<h3>Loading…</h3>`);
  const chatId = state.activeChat ? state.activeChat.chat_id : "";
  try {
    const p = await api(`/api/users/${userId}/profile?chat_id=${chatId}`);
    if (!p.ok) {
      showModal(`<h3>Error</h3><p>${escapeHtml(p.error || "?")}</p>
        <button class="modal-close">Close</button>`);
      return;
    }
    const fullName = [p.first_name, p.last_name].filter(Boolean).join(" ") || "(no name)";
    const uname = p.username ? `@${escapeHtml(p.username)}` : "—";
    const avatarUrl = `/api/users/${userId}/photo`;
    const avatarHtml = p.has_photo
      ? `<img class="profile-avatar" src="${avatarUrl}" alt=""
              onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'profile-avatar profile-avatar-fallback',textContent:'${escapeHtml(fullName.charAt(0).toUpperCase())}'}))">`
      : `<div class="profile-avatar profile-avatar-fallback">${escapeHtml(fullName.charAt(0).toUpperCase())}</div>`;
    const botBadge = p.is_bot ? ' <span class="badge">BOT</span>' : "";
    const msgCountHtml = p.message_count != null
      ? `<div class="info-row"><b>Messages in this chat:</b> ${p.message_count}</div>` : "";
    const seenHtml = (p.first_seen_at || p.last_seen_at)
      ? `<div class="info-row"><b>First seen:</b> ${escapeHtml(p.first_seen_at || "?")}</div>
         <div class="info-row"><b>Last seen:</b> ${escapeHtml(p.last_seen_at || "?")}</div>` : "";
    const openLink = p.username
      ? `<a class="btn-secondary" href="https://t.me/${encodeURIComponent(p.username)}"
             target="_blank" rel="noopener" style="text-decoration:none;display:inline-block">Open in Telegram</a>`
      : "";

    showModal(`
      <div class="profile-header">
        ${avatarHtml}
        <div class="profile-info">
          <h3>${escapeHtml(fullName)}${botBadge}</h3>
          <div class="profile-username">${uname}</div>
        </div>
      </div>
      <div class="info-row profile-copy-row">
        <span><b>User ID:</b> <code>${userId}</code></span>
        <button class="btn-secondary btn-copy" data-copy="${userId}">Copy</button>
      </div>
      ${p.username ? `
      <div class="info-row profile-copy-row">
        <span><b>Username:</b> <code>@${escapeHtml(p.username)}</code></span>
        <button class="btn-secondary btn-copy" data-copy="@${escapeHtml(p.username)}">Copy</button>
      </div>` : ""}
      ${p.language_code ? `<div class="info-row"><b>Language:</b> ${escapeHtml(p.language_code)}</div>` : ""}
      ${msgCountHtml}
      ${seenHtml}
      <div class="modal-actions">
        ${openLink}
        <button class="btn-secondary modal-close">Close</button>
      </div>
    `);

    document.querySelectorAll(".btn-copy").forEach(btn => {
      btn.onclick = async () => {
        const ok = await copyToClipboard(btn.dataset.copy);
        const orig = btn.textContent;
        btn.textContent = ok ? "Copied ✓" : "Failed";
        setTimeout(() => { btn.textContent = orig; }, 1200);
      };
    });
  } catch (e) {
    showModal(`<h3>Error</h3><p>${escapeHtml(String(e))}</p>
      <button class="modal-close">Close</button>`);
  }
}

/* wrap avatar click handler after wrapWithAvatar is defined */
const _origWrapWithAvatar = wrapWithAvatar;
wrapWithAvatar = function(bubble, m, showAvatar) {
  const row = _origWrapWithAvatar(bubble, m, showAvatar);
  const av = row.querySelector(".avatar");
  if (av && m.from_id != null) {
    av.style.cursor = "pointer";
    av.title = "View profile";
    av.addEventListener("click", (e) => {
      e.stopPropagation();
      openUserProfile(m.from_id);
    });
  }
  return row;
};

/* add "View profile" to context menu */
const _origOpenCtxMenu2 = openContextMenu;
openContextMenu = function(msg, x, y) {
  _origOpenCtxMenu2.call(this, msg, x, y);
  const menu = document.getElementById("ctx-menu");
  if (!menu || menu.hidden) return;
  if (!menu.querySelector(".ctx-view-profile")) {
    const sep = document.createElement("div");
    sep.className = "ctx-sep";
    menu.insertBefore(sep, menu.firstChild);
    const btn = document.createElement("button");
    btn.className = "ctx-view-profile";
    btn.textContent = "👤 View profile";
    btn.onclick = () => {
      hideContextMenu();
      openUserProfile(msg.from_id);
    };
    menu.insertBefore(btn, sep);
  }
};



/* ==============================================================
   Forward modal v2 — full chat list + search + manual entry
   ============================================================== */

let _allChatsCache = null;
let _allChatsCacheTs = 0;
const _ALL_CHATS_TTL_MS = 30000;

async function _loadAllChats(forceRefresh) {
  const now = Date.now();
  if (!forceRefresh && _allChatsCache
      && (now - _allChatsCacheTs) < _ALL_CHATS_TTL_MS) {
    return _allChatsCache;
  }
  try {
    const r = await api("/api/chats/all");
    if (r && r.ok) {
      _allChatsCache = r.chats || [];
      _allChatsCacheTs = now;
      return _allChatsCache;
    }
  } catch (e) {
    console.warn("_loadAllChats:", e);
  }
  return state.chats || [];
}

const _origForwardModal = openForwardModal;
openForwardModal = async function(msg) {
  showModal(`<h3>Loading chats…</h3>`);
  let chats;
  try {
    chats = await _loadAllChats(true);
  } catch (_) {
    chats = state.chats || [];
  }

  const selfCid = state.activeChat ? state.activeChat.chat_id : null;
  // show all chats including the current one (tagged in the UI)
  let allForList = (chats || []);

  const renderRows = (filter) => {
    const q = (filter || "").trim().toLowerCase();
    let rows = "";
    let shown = 0;
    for (const c of allForList) {
      const label = c.title || ("chat " + c.chat_id);
      const hay = (label + " " + String(c.chat_id)
                   + " " + (c.username || "")).toLowerCase();
      if (q && !hay.includes(q)) continue;
      shown++;
      const un = c.username ? ` · @${escapeHtml(c.username)}` : "";
      const mc = (c.message_count != null)
        ? ` · ${c.message_count} msgs` : "";
      const isCurrent = (c.chat_id === selfCid);
      const currentTag = isCurrent
        ? ` <span class="forward-current">(current)</span>` : "";
      rows += `<button type="button" class="forward-row"
                       data-cid="${c.chat_id}">
        <div class="forward-info">
          <span class="forward-name">${escapeHtml(label)}${currentTag}</span>
          <span class="forward-meta">${escapeHtml(c.kind || "?")}${un}${mc} · id=${c.chat_id}</span>
        </div>
        <span class="forward-kind">${escapeHtml(c.kind || "?")}</span>
      </button>`;
    }
    if (shown === 0) {
      return `<div class="forward-empty">No chats match. Try a different search, or enter manually below.</div>`;
    }
    return rows;
  };

  showModal(`
    <h3>Forward to…</h3>
    <div class="forward-toolbar">
      <input type="text" id="forward-search" class="forward-search"
             placeholder="Search by name, id, or @username">
      <button type="button" class="btn-secondary" id="forward-refresh"
              title="Reload chat list">↻</button>
    </div>
    <div class="forward-list" id="forward-list">${renderRows("")}</div>
    <details class="forward-manual">
      <summary>Enter chat_id or @username manually</summary>
      <div class="forward-manual-form">
        <input type="text" id="forward-manual-cid"
               placeholder="-100... or @channel">
        <button type="button" class="btn-primary" id="forward-manual-go">Forward</button>
      </div>
    </details>
    <div class="modal-actions">
      <button type="button" class="btn-secondary modal-close">Cancel</button>
    </div>
  `);

  const doForward = async (toCid, btn) => {
    if (!toCid) return;
    if (btn) btn.disabled = true;
    try {
      const r = await api(
        `/api/chats/${state.activeChat.chat_id}/forward`, {
          method: "POST",
          body: JSON.stringify({
            to_chat_id: toCid,
            message_id: msg.message_id,
          }),
        });
      if (r.ok) {
        hideModal();
      } else {
        alert("Forward failed: " + (r.error || "unknown"));
        if (btn) btn.disabled = false;
      }
    } catch (e) {
      alert("Forward error: " + e);
      if (btn) btn.disabled = false;
    }
  };

  const wireRows = () => {
    document.querySelectorAll(".forward-row").forEach(btn => {
      btn.onclick = () => doForward(btn.dataset.cid, btn);
    });
  };
  wireRows();

  const searchEl = document.getElementById("forward-search");
  searchEl.addEventListener("input", (e) => {
    document.getElementById("forward-list").innerHTML =
      renderRows(e.target.value);
    wireRows();
  });
  setTimeout(() => searchEl.focus(), 30);

  document.getElementById("forward-refresh").onclick = async () => {
    const btn = document.getElementById("forward-refresh");
    btn.disabled = true; btn.textContent = "…";
    try {
      const fresh = await _loadAllChats(true);
      allForList = (fresh || []).filter(c => c.chat_id !== selfCid);
      document.getElementById("forward-list").innerHTML =
        renderRows(document.getElementById("forward-search").value);
      wireRows();
    } finally {
      btn.disabled = false; btn.textContent = "↻";
    }
  };

  document.getElementById("forward-manual-go").onclick = () => {
    const cid = document.getElementById("forward-manual-cid").value.trim();
    if (!cid) return;
    doForward(cid, document.getElementById("forward-manual-go"));
  };
};



/* ==============================================================
   Saved media (stickers + GIFs) — server-synced
   ============================================================== */

let _mediaState = { tab: "sticker", items: [], open: false };

async function loadSavedMedia(tab) {
  if (tab === "favorites") tab = "all";
  _mediaState.tab = tab;
  try {
    const params = new URLSearchParams();
    if (tab !== "all" && tab !== "favorites") {
      params.set("type", tab);
    }
    const r = await api(`/api/media/saved?${params.toString()}`);
    if (r && r.ok) {
      _mediaState.items = r.items || [];
    } else {
      _mediaState.items = [];
    }
  } catch (e) {
    console.warn("loadSavedMedia:", e);
    _mediaState.items = [];
  }
  renderMediaPanel();
}

function renderMediaPanel() {
  const grid = document.getElementById("media-grid");
  const empty = document.getElementById("media-empty");
  if (!grid) return;
  if (_mediaState.items.length === 0) {
    grid.innerHTML = "";
    empty.hidden = false;
    return;
  }
  empty.hidden = true;
  grid.innerHTML = "";
  for (const it of _mediaState.items) {
    const item = document.createElement("div");
    item.className = "media-item";
    item.title = it.emoji
      ? `${it.media_type} ${it.emoji} (used ${it.use_count}×)`
      : `${it.media_type} (used ${it.use_count}×)`;
    item.innerHTML =
      `<img class="media-thumb" src="/api/media/saved/${it.id}/preview" ` +
        `alt="" loading="lazy">` +
      `<button class="media-fav ${it.is_favorite ? "active" : ""}" ` +
        `title="${it.is_favorite ? "Unfavorite" : "Favorite"}">⭐</button>` +
      `<button class="media-del" title="Remove">✕</button>`;
    item.addEventListener("click", async (ev) => {
      if (ev.target.closest(".media-fav, .media-del")) return;
      await sendSavedMedia(it);
    });
    item.querySelector(".media-fav").addEventListener("click",
      async (ev) => {
        ev.stopPropagation();
        await toggleMediaFavorite(it);
      });
    item.querySelector(".media-del").addEventListener("click",
      async (ev) => {
        ev.stopPropagation();
        if (!confirm("Remove this from saved media?")) return;
        await deleteSavedMedia(it);
      });
    grid.appendChild(item);
  }
}

async function sendSavedMedia(it) {
  if (!state.activeChat) {
    alert("Pick a chat first.");
    return;
  }
  const payload = { chat_id: state.activeChat.chat_id };
  if (state.replyTo) payload.reply_to = state.replyTo.message_id;
  try {
    const r = await api(`/api/media/saved/${it.id}/send`, {
      method: "POST", body: JSON.stringify(payload),
    });
    if (!r.ok) {
      alert("Send failed: " + (r.error || "unknown"));
      return;
    }
    state.replyTo = null;
    renderReplyBanner();
    closeMediaPanel();
    await reloadMessages({ incremental: true });
  } catch (e) {
    alert("Send error: " + e);
  }
}

async function toggleMediaFavorite(it) {
  try {
    const r = await api(`/api/media/saved/${it.id}/favorite`, {
      method: "POST", body: "{}",
    });
    if (r.ok) {
      it.is_favorite = r.is_favorite;
      renderMediaPanel();
    }
  } catch (e) {
    console.warn(e);
  }
}

async function deleteSavedMedia(it) {
  try {
    const r = await api(`/api/media/saved/${it.id}`, { method: "DELETE" });
    if (r.ok) {
      _mediaState.items = _mediaState.items.filter(x => x.id !== it.id);
      renderMediaPanel();
    }
  } catch (e) {
    console.warn(e);
  }
}

async function saveMediaFromMessage(msg) {
  const f = (msg.files || []).find(
    x => x.type === "sticker" || x.type === "animation");
  if (!f) {
    alert("This message has no sticker or GIF.");
    return;
  }
  try {
    const r = await api("/api/media/saved", {
      method: "POST",
      body: JSON.stringify({
        chat_id: state.activeChat.chat_id,
        message_id: msg.message_id,
      }),
    });
    if (!r.ok) {
      alert("Save failed: " + (r.error || "unknown"));
      return;
    }
    if (_mediaState.open) await loadSavedMedia(_mediaState.tab);
  } catch (e) {
    alert("Save error: " + e);
  }
}

function openMediaPanel() {
  const panel = document.getElementById("media-panel");
  if (!panel) return;
  panel.hidden = false;
  _mediaState.open = true;
  loadSavedMedia(_mediaState.tab || "sticker");
}

function closeMediaPanel() {
  const panel = document.getElementById("media-panel");
  if (!panel) return;
  panel.hidden = true;
  _mediaState.open = false;
}

/* wire buttons + tabs */
function _setupMediaUI() {
  const mb = document.getElementById("media-btn");
  if (mb && !mb.dataset.wired) {
    mb.dataset.wired = "1";
    mb.addEventListener("click", (e) => {
      e.stopPropagation();
      if (_mediaState.open) closeMediaPanel();
      else openMediaPanel();
    });
  }
  const panel = document.getElementById("media-panel");
  if (panel && !panel.dataset.wired) {
    panel.dataset.wired = "1";
    panel.addEventListener("click", (e) => e.stopPropagation());
  }
  document.querySelectorAll(".media-tabs [data-mtab]").forEach(btn => {
    if (btn.dataset.wired) return;
    btn.dataset.wired = "1";
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      document.querySelectorAll(".media-tabs [data-mtab]")
        .forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const tab = btn.dataset.mtab;
      if (tab === "favorites") {
        // favorites = favorite-only across all types
        api("/api/media/saved?fav=1").then(r => {
          _mediaState.items = (r && r.items) || [];
          renderMediaPanel();
        });
      } else {
        loadSavedMedia(tab);
      }
    });
  });
  const closeBtn = document.getElementById("media-close");
  if (closeBtn && !closeBtn.dataset.wired) {
    closeBtn.dataset.wired = "1";
    closeBtn.addEventListener("click", closeMediaPanel);
  }
  if (!document.body.dataset.mediaOutsideWired) {
    document.body.dataset.mediaOutsideWired = "1";
    document.addEventListener("click", (e) => {
      if (!_mediaState.open) return;
      const panel = document.getElementById("media-panel");
      const mb = document.getElementById("media-btn");
      if (panel && panel.contains(e.target)) return;
      if (mb && mb.contains(e.target)) return;
      closeMediaPanel();
    });
  }
}

setTimeout(_setupMediaUI, 400);

/* hook into context menu: add "Save to media" */
const _origOpenCtxMenuSaved = openContextMenu;
openContextMenu = function(msg, x, y) {
  _origOpenCtxMenuSaved.call(this, msg, x, y);
  const menu = document.getElementById("ctx-menu");
  if (!menu || menu.hidden) return;
  const hasMedia = (msg.files || []).some(
    f => f.type === "sticker" || f.type === "animation");
  if (!hasMedia) return;
  if (menu.querySelector(".ctx-save-media")) return;
  const sep = document.createElement("div");
  sep.className = "ctx-sep";
  menu.appendChild(sep);
  const btn = document.createElement("button");
  btn.className = "ctx-save-media";
  btn.textContent = "⭐ Save to media";
  btn.onclick = async () => {
    hideContextMenu();
    await saveMediaFromMessage(msg);
  };
  menu.appendChild(btn);
};



/* ==============================================================
   Mobile UI: global back-button handler + body-class sync
   ============================================================== */
(function _setupMobileBack() {
  if (document.body.dataset.mobileBackWired) return;
  document.body.dataset.mobileBackWired = "1";

  document.addEventListener("click", (e) => {
    const backBtn = e.target.closest(".chat-back-btn");
    if (!backBtn) return;
    e.preventDefault();
    e.stopPropagation();
    state.activeChat = null;
    state.messages = [];
    state.replyTo = null;
    document.body.classList.remove("chat-open");
    document.body.classList.remove("in-private-chat");
    const ml = document.getElementById("message-list");
    if (ml) ml.innerHTML = "";
    const ch = document.getElementById("chat-header");
    if (ch) ch.textContent = "Select a chat";
    const comp = document.getElementById("composer");
    if (comp) comp.hidden = true;
    renderReplyBanner();
  });

  // If the page ever loads with an active chat but no class, sync it.
  const _origEnterApp = typeof enterApp === "function" ? enterApp : null;
  if (_origEnterApp) {
    // sync after app is ready (safe because selectChat handles the rest)
    setTimeout(() => {
      if (state.activeChat) {
        document.body.classList.add("chat-open");
      } else {
        document.body.classList.remove("chat-open");
      }
    }, 500);
  }
})();



/* Kind selector: update title + aria-label on change */
(function _setupKindTitle() {
  const sel = document.getElementById("upload-kind");
  if (!sel || sel.dataset.titleWired) return;
  sel.dataset.titleWired = "1";
  const labels = {
    auto: "auto (detect by MIME)",
    photo: "photo",
    video: "video",
    document: "document / file",
    audio: "audio",
    voice: "voice message",
    animation: "animation / GIF",
    sticker: "sticker",
    video_note: "video note (round)",
  };
  const update = () => {
    const label = labels[sel.value] || sel.value;
    sel.title = "Send as: " + label;
    sel.setAttribute("aria-label", "Send as: " + label);
  };
  sel.addEventListener("change", update);
  update();
})();



/* ==============================================================
   Avatar padding walker — fixes already-rendered rows
   Runs on load and after each reload; also on mutation.
   ============================================================== */
(function _setupAvatarWalker() {
  if (window._avatarWalkerWired) return;
  window._avatarWalkerWired = true;

  function fixRow(row) {
    if (!row.classList.contains("msg-row")) return;
    if (row.classList.contains("outgoing")) return;
    const hasAvatar = !!row.querySelector(":scope > .avatar");
    if (hasAvatar) {
      row.style.paddingLeft = "";
      delete row.dataset.noAvatar;
    } else {
      row.style.paddingLeft = "38px";
      row.dataset.noAvatar = "1";
    }
  }

  function walkAll() {
    document.querySelectorAll(".msg-row.incoming").forEach(fixRow);
  }

  // on load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", walkAll);
  } else {
    walkAll();
  }

  // observe new rows
  const target = document.getElementById("message-list");
  if (target && window.MutationObserver) {
    const mo = new MutationObserver((mutations) => {
      for (const mut of mutations) {
        for (const node of mut.addedNodes) {
          if (node.nodeType !== 1) continue;
          if (node.classList && node.classList.contains("msg-row")) {
            fixRow(node);
          } else if (node.querySelectorAll) {
            node.querySelectorAll(".msg-row").forEach(fixRow);
          }
        }
      }
    });
    mo.observe(target, { childList: true, subtree: true });
  }

  // expose for manual calls
  window._fixAvatarPadding = walkAll;
})();



/* ==============================================================
   _normalizeAvatars — Telegram-style: avatar on LAST of each run
   ============================================================== */
function _normalizeAvatars() {
  const rows = Array.from(
    document.querySelectorAll("#message-list .msg-row.incoming"));
  for (let i = 0; i < rows.length; i++) {
    const cur = rows[i].dataset.fromId || "";
    const next = (i + 1 < rows.length)
      ? (rows[i + 1].dataset.fromId || "")
      : "\u0000END\u0000";
    const av = rows[i].querySelector(":scope > .avatar");

    if (!av) {
      // Private chat: no avatar concept → bubble stays flush left
      if (state.activeChat && state.activeChat.kind === "private") {
        rows[i].style.paddingLeft = "";
        delete rows[i].dataset.noAvatar;
        continue;
      }
      // Group/channel with unknown sender — pad left to align
      if (!rows[i].dataset.noAvatar) {
        rows[i].style.paddingLeft = "38px";
        rows[i].dataset.noAvatar = "1";
      }
      continue;
    }

    // Avatar slot exists — bubble aligns via flex (30px + 8px gap)
    rows[i].style.paddingLeft = "";
    delete rows[i].dataset.noAvatar;

    // Visible only if this row ends its group
    av.style.visibility = (cur !== next) ? "visible" : "hidden";
  }
}

/* Keep avatars normalized on any DOM change */
(function _setupAvatarNormalizer() {
  if (window._avatarNormalizerWired) return;
  window._avatarNormalizerWired = true;

  let _pending = null;
  function schedule() {
    if (_pending) return;
    _pending = setTimeout(() => {
      _pending = null;
      try { _normalizeAvatars(); } catch (e) {}
    }, 16);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", schedule);
  } else {
    schedule();
  }

  const target = document.getElementById("message-list");
  if (target && window.MutationObserver) {
    const mo = new MutationObserver(schedule);
    mo.observe(target, { childList: true, subtree: true });
  }

  window._normalizeAvatars = _normalizeAvatars;
})();



/* ==============================================================
   _normalizeNames — Telegram-style:
   - incoming: name only on FIRST message of a consecutive group
   - outgoing: no name ever
   - private chats: no name at all
   ============================================================== */
function _normalizeNames() {
  const isPrivate = !!(state.activeChat && state.activeChat.kind === "private");
  if (isPrivate) {
    document.querySelectorAll("#message-list .msg .who").forEach(el => {
      el.style.display = "none";
    });
    return;
  }
  const rows = Array.from(
    document.querySelectorAll("#message-list .msg-row"));
  let prevFromId = null;
  let prevIsOwn = null;
  for (const row of rows) {
    const isOwn = row.classList.contains("outgoing");
    const fromId = row.dataset.fromId || "";
    const whoEl = row.querySelector(".msg .who");

    if (!whoEl) {
      // outgoing (no .who) — break the group
      prevFromId = null;
      prevIsOwn = true;
      continue;
    }

    if (isOwn) {
      whoEl.style.display = "none";
      prevFromId = null;
      prevIsOwn = true;
      continue;
    }

    // incoming: show only when starting a new group
    if (prevIsOwn !== false || prevFromId !== fromId) {
      whoEl.style.display = "";
    } else {
      whoEl.style.display = "none";
    }
    prevFromId = fromId;
    prevIsOwn = false;
  }
}

(function _setupNamesNormalizer() {
  if (window._namesNormalizerWired) return;
  window._namesNormalizerWired = true;

  let _pending = null;
  function schedule() {
    if (_pending) return;
    _pending = setTimeout(() => {
      _pending = null;
      try { _normalizeNames(); } catch (e) {}
    }, 16);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", schedule);
  } else {
    schedule();
  }

  const target = document.getElementById("message-list");
  if (target && window.MutationObserver) {
    const mo = new MutationObserver(schedule);
    mo.observe(target, { childList: true, subtree: true });
  }

  window._normalizeNames = _normalizeNames;
})();



/* ==============================================================
   Composer textarea auto-grow (max 3 lines)
   - Measures scrollHeight, sets height to min(scrollHeight, 3 lines)
   - Resets to 1 line when emptied (e.g. after send)
   - Works on Android/iOS/desktop
   ============================================================== */
(function _setupTextareaAutogrow() {
  function initAutogrow() {
    const ta = document.getElementById("message-input");
    if (!ta || ta.dataset.autogrowWired) return;
    ta.dataset.autogrowWired = "1";

    // Cache line-height + 3-line cap once (recomputed on resize)
    let LINE_HEIGHT = 22;
    let MAX_HEIGHT = 66;
    let VERT_PAD = 16;

    function recomputeSizes() {
      const cs = getComputedStyle(ta);
      const lh = parseFloat(cs.lineHeight);
      const pt = parseFloat(cs.paddingTop) || 0;
      const pb = parseFloat(cs.paddingBottom) || 0;
      const bt = parseFloat(cs.borderTopWidth) || 0;
      const bb = parseFloat(cs.borderBottomWidth) || 0;
      VERT_PAD = pt + pb + bt + bb;
      LINE_HEIGHT = isNaN(lh) ? 22 : lh;
      MAX_HEIGHT = Math.ceil(LINE_HEIGHT * 3 + VERT_PAD);
    }

    function resize() {
      // reset to auto so scrollHeight reflects real content
      ta.style.height = "auto";
      ta.style.overflowY = "hidden";
      const desired = ta.scrollHeight;
      const applied = Math.min(desired, MAX_HEIGHT);
      ta.style.height = applied + "px";
      ta.style.overflowY = (desired > MAX_HEIGHT) ? "auto" : "hidden";
    }

    function reset() {
      ta.style.height = "";
      ta.style.overflowY = "hidden";
      // force one reflow so the empty state collapses cleanly
      void ta.offsetHeight;
      resize();
    }

    recomputeSizes();
    resize();

    ta.addEventListener("input", resize);
    ta.addEventListener("change", resize);
    ta.addEventListener("paste", () => setTimeout(resize, 0));
    ta.addEventListener("cut", () => setTimeout(resize, 0));
    window.addEventListener("resize", () => {
      recomputeSizes();
      resize();
    });

    // expose so send() can reset after sending
    window._textareaAutogrowReset = reset;
    window._textareaAutogrowResize = resize;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAutogrow);
  } else {
    initAutogrow();
  }
})();



/* ==============================================================
   Mobile back button + composer force-show
   ============================================================== */
(function _setupMobileBackFix() {
  if (window._mobileBackFixWired) return;
  window._mobileBackFixWired = true;

  function backToChatList() {
    state.activeChat = null;
    state.messages = [];
    state.replyTo = null;
    document.body.classList.remove("chat-open");
    document.body.classList.remove("in-private-chat");
    const ml = document.getElementById("message-list");
    if (ml) ml.innerHTML = "";
    const ch = document.getElementById("chat-header");
    if (ch) ch.textContent = "Select a chat";
    const comp = document.getElementById("composer");
    if (comp) comp.hidden = true;
    if (typeof renderReplyBanner === "function") renderReplyBanner();
    const sb = document.getElementById("sidebar");
    if (sb) sb.classList.remove("open");
  }

  document.addEventListener("click", (e) => {
    // Floating back button
    if (e.target.closest("#mobile-back-btn")) {
      e.preventDefault();
      e.stopPropagation();
      backToChatList();
      return;
    }
    // Existing header back button (in case _renderChatHeader added it)
    if (e.target.closest(".chat-back-btn")) {
      e.preventDefault();
      e.stopPropagation();
      backToChatList();
    }
  }, true);

  // Force composer visible after any selectChat call
  window._forceComposerVisible = function () {
    const comp = document.getElementById("composer");
    if (!comp) return;
    if (!state.activeChat) return;
    comp.hidden = false;
    comp.removeAttribute("hidden");
    comp.style.display = "flex";
  };

  // Observe body class changes → if chat-open but composer hidden, force
  const bodyObs = new MutationObserver(() => {
    if (document.body.classList.contains("chat-open")
        && state.activeChat) {
      const comp = document.getElementById("composer");
      if (comp && comp.hidden) {
        comp.hidden = false;
        comp.removeAttribute("hidden");
        comp.style.display = "flex";
      }
    }
  });
  bodyObs.observe(document.body, {
    attributes: true, attributeFilter: ["class"],
  });

  // Patch selectChat to force composer after awaits
  const _origSelectChat = window.selectChat;
  if (typeof _origSelectChat === "function") {
    window.selectChat = async function(c) {
      const r = await _origSelectChat.call(this, c);
      // After all awaits, ensure composer is visible
      if (window._forceComposerVisible) window._forceComposerVisible();
      return r;
    };
  }

  // Also patch showApp or boot to ensure initial state
  window.addEventListener("load", () => {
    if (state.activeChat && window._forceComposerVisible) {
      window._forceComposerVisible();
    }
  });

  setTimeout(() => {
    if (state.activeChat && window._forceComposerVisible) {
      window._forceComposerVisible();
    }
  }, 500);
})();



/* ==============================================================
   Global row-swipe helper (attached by wrapWithAvatar)
   LEFT  → reply
   RIGHT → forward
   ============================================================== */
window._attachRowSwipe = function(row, bubble, msg) {
  if (!row || row.dataset.swipeWired === "1") return;
  row.dataset.swipeWired = "1";
  let sx = 0, sy = 0, dx = 0, active = false;
  row.addEventListener("touchstart", (ev) => {
    if (ev.touches.length !== 1) return;
    sx = ev.touches[0].clientX;
    sy = ev.touches[0].clientY;
    dx = 0;
    active = false;
  }, { passive: true });
  row.addEventListener("touchmove", (ev) => {
    if (ev.touches.length !== 1) return;
    const ddx = ev.touches[0].clientX - sx;
    const ddy = ev.touches[0].clientY - sy;
    if (!active && Math.abs(ddx) > 12
        && Math.abs(ddx) > Math.abs(ddy) * 1.5) {
      active = true;
      bubble.classList.add("swiping");
    }
    if (active) {
      if (ev.cancelable) ev.preventDefault();
      dx = Math.max(-120, Math.min(120, ddx));
      bubble.style.transform = "translateX(" + dx + "px)";
      bubble.classList.toggle("swipe-left-hint", dx < -30);
      bubble.classList.toggle("swipe-right-hint", dx > 30);
    }
  }, { passive: false });
  row.addEventListener("touchend", () => {
    if (!active) return;
    const d = dx;
    active = false;
    dx = 0;
    bubble.classList.remove("swiping", "swipe-left-hint", "swipe-right-hint");
    bubble.style.transform = "";
    window._lastSwipeTs = Date.now();
    if (d < -60) {
      setReplyTo(msg);  // LEFT → reply
    } else if (d > 60) {
      if (typeof openForwardModal === "function") openForwardModal(msg);
    }
  });
  row.addEventListener("touchcancel", () => {
    active = false;
    dx = 0;
    bubble.classList.remove("swiping", "swipe-left-hint", "swipe-right-hint");
    bubble.style.transform = "";
  });
};


/* ==============================================================
   Keyboard-aware viewport height (visualViewport → --app-vh)
   Fixes composer being hidden behind mobile keyboard.
   ============================================================== */
(function _setupKeyboardViewport() {
  if (window._kbViewportWired) return;
  window._kbViewportWired = true;

  const vv = window.visualViewport;
  let lastH = 0;
  let rafId = null;

  function applyHeight() {
    rafId = null;
    let h;
    if (vv) {
      h = vv.height;
    } else {
      h = window.innerHeight;
    }
    // Guard against 0/NaN during transitions
    if (!h || h < 100) return;
    if (Math.abs(h - lastH) < 1) return;
    lastH = h;
    document.documentElement.style.setProperty("--app-vh", h + "px");

    // If the message list is visible and we're in a chat,
    // keep the bottom-most message in view after the resize.
    const box = document.getElementById("message-list");
    if (box && state && state.activeChat) {
      const wasNearBottom =
        (box.scrollHeight - box.scrollTop - box.clientHeight) < 120;
      if (wasNearBottom) {
        box.scrollTop = box.scrollHeight;
      }
    }
  }

  function schedule() {
    if (rafId) return;
    rafId = requestAnimationFrame(applyHeight);
  }

  if (vv) {
    vv.addEventListener("resize", schedule);
    vv.addEventListener("scroll", schedule);
  }
  window.addEventListener("resize", schedule);
  window.addEventListener("orientationchange", () => {
    setTimeout(schedule, 120);
  });

  // On focusin of the composer, run a couple of follow-up passes
  // because some browsers delay the keyboard resize event.
  document.addEventListener("focusin", (e) => {
    if (e.target && e.target.id === "message-input") {
      schedule();
      setTimeout(schedule, 100);
      setTimeout(schedule, 320);
      setTimeout(schedule, 600);
    }
  });
  document.addEventListener("focusout", (e) => {
    if (e.target && e.target.id === "message-input") {
      schedule();
      setTimeout(schedule, 120);
    }
  });

  // Initial run (twice, in case fonts load late and shift layout)
  schedule();
  setTimeout(schedule, 200);
})();


/* ==============================================================
   loadOlderMessages — robust, debuggable, with timeout + fallback
   ============================================================== */
let _loadingOlder = false;
let _allOldLoaded = false;

function _olderLog(...args) {
  try { console.log("[older]", ...args); } catch (_) {}
}

async function loadOlderMessages(force) {
  if (_loadingOlder) { _olderLog("skip: already loading"); return; }
  if (_allOldLoaded && !force) { _olderLog("skip: no more"); return; }
  if (!state.activeChat) { _olderLog("skip: no chat"); return; }
  if (!Array.isArray(state.messages) || state.messages.length === 0) {
    _olderLog("skip: empty state");
    return;
  }
  _loadingOlder = true;
  _olderLog("begin, oldestId=", state.messages[0].message_id,
            "total=", state.messages.length);

  const box = document.getElementById("message-list");
  if (!box) { _loadingOlder = false; return; }

  // remove any old indicator / error
  const prev = document.getElementById("older-loading");
  if (prev) prev.remove();
  const prevErr = document.getElementById("older-error");
  if (prevErr) prevErr.remove();

  const indicator = document.createElement("div");
  indicator.id = "older-loading";
  indicator.className = "older-loading";
  indicator.textContent = "Loading older messages…";
  box.insertBefore(indicator, box.firstChild);

  const oldestId = state.messages[0].message_id;
  const chatId = state.activeChat.chat_id;

  // 20s timeout
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 20000);

  let data = null, err = null;
  try {
    const res = await fetch(
      `/api/chats/${chatId}/messages?limit=50&before=${oldestId}`,
      { credentials: "same-origin", signal: ctl.signal }
    );
    _olderLog("http", res.status);
    if (!res.ok) throw new Error("HTTP " + res.status);
    data = await res.json();
  } catch (e) {
    err = e;
    _olderLog("fetch error:", e.name, e.message);
  } finally {
    clearTimeout(timer);
  }

  if (err) {
    indicator.remove();
    const errEl = document.createElement("div");
    errEl.id = "older-error";
    errEl.className = "older-error";
    errEl.textContent =
      "Could not load older messages (" + err.message + "). Tap to retry.";
    errEl.style.cursor = "pointer";
    errEl.addEventListener("click", () => {
      errEl.remove();
      loadOlderMessages(true);
    });
    box.insertBefore(errEl, box.firstChild);
    _loadingOlder = false;
    return;
  }

  if (!data || !data.ok || !Array.isArray(data.messages)) {
    indicator.remove();
    _allOldLoaded = true;
    _olderLog("bad response:", data);
    _loadingOlder = false;
    return;
  }

  _olderLog("got", data.messages.length, "messages");

  const existing = new Set(state.messages.map(m => m.message_id));
  const older = data.messages.filter(m => !existing.has(m.message_id));
  _olderLog("new after dedupe:", older.length);

  if (older.length === 0) {
    indicator.remove();
    _allOldLoaded = true;
    _olderLog("no new — end of history");
    _loadingOlder = false;
    return;
  }

  // prepend to state
  state.messages = [...older, ...state.messages];

  // render into fragment
  const frag = document.createDocumentFragment();
  let _lastFromId = null;
  for (const m of older) {
    try {
      const _isOwn = isOwnMessage(m);
      const _senderId = (typeof effectiveSenderId === "function")
        ? effectiveSenderId(m)
        : (m.from_id != null ? m.from_id : null);
      const _fromStr = (!_isOwn && _senderId != null) ? String(_senderId) : null;
      const _showAv = !_isOwn && _fromStr !== null && _fromStr !== _lastFromId;
      const _bubble = renderMessage(m);
      frag.appendChild(wrapWithAvatar(_bubble, m, _showAv));
      _lastFromId = _isOwn ? null : _fromStr;
    } catch (e) {
      _olderLog("render failed:", m.message_id, e);
    }
  }

  const oldScrollHeight = box.scrollHeight;
  const oldScrollTop = box.scrollTop;
  box.insertBefore(frag, indicator.nextSibling);
  indicator.remove();
  // maintain visual position
  const newScrollHeight = box.scrollHeight;
  box.scrollTop = oldScrollTop + (newScrollHeight - oldScrollHeight);
  _olderLog("inserted, scrollTop=", box.scrollTop);

  if (typeof window._normalizeAvatars === "function") {
    try { window._normalizeAvatars(); } catch (_) {}
  }
  if (typeof window._normalizeNames === "function") {
    try { window._normalizeNames(); } catch (_) {}
  }

  _loadingOlder = false;
  _olderLog("done");
}

window.loadOlderMessages = loadOlderMessages;
window._debugOlderLoad = function() {
  const box = document.getElementById("message-list");
  console.log("=== older-load debug ===");
  console.log("activeChat:", state.activeChat && state.activeChat.chat_id);
  console.log("messages.length:", (state.messages || []).length);
  console.log("oldest id:", state.messages && state.messages[0] && state.messages[0].message_id);
  console.log("box:", box);
  console.log("scrollTop:", box && box.scrollTop);
  console.log("scrollHeight:", box && box.scrollHeight);
  console.log("clientHeight:", box && box.clientHeight);
  console.log("can scroll:", box && box.scrollHeight > box.clientHeight);
  console.log("_loadingOlder:", _loadingOlder);
  console.log("_allOldLoaded:", _allOldLoaded);
  console.log("loadOlderMessages type:", typeof loadOlderMessages);
};

/* ==============================================================
   Trigger setup: IntersectionObserver + scroll + button
   ============================================================== */
(function _setupOlderTriggers() {
  if (window._olderTriggersWired) return;
  window._olderTriggersWired = true;

  let observer = null;

  function attachObserver(box) {
    if (observer) { try { observer.disconnect(); } catch (_) {} }
    if (!box || !window.IntersectionObserver) return;
    const firstChild = box.firstElementChild;
    if (!firstChild) return;
    observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          _olderLog("observer: first row visible");
          loadOlderMessages();
          break;
        }
      }
    }, { root: box, rootMargin: "200px 0px 0px 0px", threshold: 0 });
    observer.observe(firstChild);
  }

  function attachScroll(box) {
    if (!box || box.dataset.olderScrollWired === "1") return;
    box.dataset.olderScrollWired = "1";
    box.addEventListener("scroll", () => {
      if (box.scrollTop < 150) {
        loadOlderMessages();
      }
    }, { passive: true });
  }

  function attachButton(box) {
    let btn = document.getElementById("older-btn");
    if (!btn) {
      btn = document.createElement("button");
      btn.id = "older-btn";
      btn.type = "button";
      btn.className = "older-btn";
      btn.textContent = "↑ Load older messages";
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        loadOlderMessages(true);
      });
    }
    if (btn.parentNode !== box) {
      box.insertBefore(btn, box.firstChild);
    }
  }

  function refresh() {
    const box = document.getElementById("message-list");
    if (!box) return;
    attachScroll(box);
    attachButton(box);
    attachObserver(box);
    // hide the button if we already know we're at end
    const btn = document.getElementById("older-btn");
    if (btn) btn.style.display = _allOldLoaded ? "none" : "";
  }

  // initial
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refresh);
  } else {
    refresh();
  }

  // refresh when message list children change (chat switch, new content)
  const box = document.getElementById("message-list");
  if (box && window.MutationObserver) {
    const mo = new MutationObserver(() => {
      // debounced refresh
      clearTimeout(refresh._t);
      refresh._t = setTimeout(refresh, 250);
    });
    mo.observe(box, { childList: true });
  }

  // reset flags on chat switch
  const _origReload = window._doReloadMessages;
  if (typeof _origReload === "function") {
    window._doReloadMessages = async function(opts) {
      if (!opts || !opts.incremental) {
        _allOldLoaded = false;
      }
      return _origReload.call(this, opts);
    };
  }
})();


/* ==============================================================
   Mentions & jump-to-latest
   ============================================================== */

async function refreshUnseenMentions() {
  try {
    const r = await api("/api/mentions/unseen");
    if (!r || !r.ok) { state.unseenMentions = {}; return; }
    const map = {};
    for (const c of (r.chats || [])) {
      map[c.chat_id] = c.count;
    }
    state.unseenMentions = map;
  } catch (e) {
    console.warn("refreshUnseenMentions:", e);
    state.unseenMentions = {};
  }
}

async function refreshChatMentions(chatId) {
  if (!chatId) return;
  try {
    const r = await api(`/api/chats/${chatId}/mentions`);
    if (!r || !r.ok) { state.chatMentions = []; return; }
    state.chatMentions = r.mentions || [];
    _updateMentionButton();
  } catch (e) {
    console.warn("refreshChatMentions:", e);
    state.chatMentions = [];
    _updateMentionButton();
  }
}

function _unseenInCurrentChat() {
  if (!state.activeChat) return [];
  return (state.chatMentions || []).filter(m => !m.seen);
}

function _updateMentionButton() {
  const btn = document.getElementById("mention-jump-btn");
  if (!btn) return;
  if (!state.activeChat) { btn.style.display = "none"; return; }
  const unseen = _unseenInCurrentChat();
  if (unseen.length === 0) {
    btn.style.display = "none";
    return;
  }
  btn.style.display = "flex";
  btn.title = `${unseen.length} unread mention${unseen.length>1?"s":""}`;
  const badge = btn.querySelector(".mention-count");
  if (badge) badge.textContent = unseen.length;
}

async function jumpToMention(mentionId) {
  const mention = (state.chatMentions || []).find(m => m.id === mentionId);
  if (!mention) return;
  const targetMsgId = mention.message_id;

  let el = document.querySelector(`[data-message-id="${targetMsgId}"]`);
  let tries = 0;
  while (!el && tries < 8) {
    if (typeof loadOlderMessages !== "function") break;
    if (window._allOldLoaded) break;
    try {
      await window.loadOlderMessages(true);
    } catch (e) {
      console.warn("loadOlderMessages failed:", e);
      break;
    }
    tries++;
    el = document.querySelector(`[data-message-id="${targetMsgId}"]`);
  }

  if (!el) {
    alert("Message #" + targetMsgId + " not in loaded history.");
    return;
  }

  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.remove("highlight");
  void el.offsetWidth;
  el.classList.add("highlight");
  setTimeout(() => el.classList.remove("highlight"), 1500);

  try {
    await api(`/api/mentions/${mentionId}/seen`, {
      method: "POST", body: "{}",
    });
    mention.seen = true;
    _updateMentionButton();
    refreshUnseenMentions().then(() => loadChats()).catch(() => {});
  } catch (e) {
    console.warn("mark seen:", e);
  }
}

async function markAllMentionsSeen() {
  if (!state.activeChat) return;
  try {
    await api(`/api/chats/${state.activeChat.chat_id}/mentions/seen`, {
      method: "POST", body: "{}",
    });
    for (const m of state.chatMentions) m.seen = true;
    _updateMentionButton();
    refreshUnseenMentions().then(() => loadChats()).catch(() => {});
  } catch (e) {
    console.warn("markAllMentionsSeen:", e);
  }
}

/* ==============================================================
   Jump-to-latest button
   ============================================================== */
function _updateJumpLatestButton() {
  const btn = document.getElementById("jump-latest-btn");
  const box = document.getElementById("message-list");
  if (!btn || !box) return;
  if (!state.activeChat) { btn.style.display = "none"; return; }
  const atBottom =
    (box.scrollHeight - box.scrollTop - box.clientHeight) < 200;
  const hasScroll = box.scrollHeight > box.clientHeight + 100;
  btn.style.display = (!atBottom && hasScroll) ? "flex" : "none";
}

/* ==============================================================
   Setup: floating buttons + scroll watcher + periodic refresh
   ============================================================== */
(function _setupMentions() {
  if (window._mentionsWired) return;
  window._mentionsWired = true;

  function ensureButtons() {
    const main = document.getElementById("main");
    if (!main) return;

    if (!document.getElementById("mention-jump-btn")) {
      const b = document.createElement("button");
      b.id = "mention-jump-btn";
      b.className = "mention-jump-btn";
      b.type = "button";
      b.title = "Jump to mention";
      b.innerHTML =
        `<span>@</span><span class="mention-count">0</span>`;
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        const unseen = _unseenInCurrentChat();
        if (unseen.length === 0) return;
        jumpToMention(unseen[0].id);
      });
      main.appendChild(b);
    }

    if (!document.getElementById("jump-latest-btn")) {
      const b = document.createElement("button");
      b.id = "jump-latest-btn";
      b.className = "jump-latest-btn";
      b.type = "button";
      b.title = "Jump to latest";
      b.innerHTML = "↓";
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        const box = document.getElementById("message-list");
        if (box) box.scrollTo({ top: box.scrollHeight, behavior: "smooth" });
      });
      main.appendChild(b);
    }
  }

  ensureButtons();

  // watch scroll
  function attachScrollWatcher() {
    const box = document.getElementById("message-list");
    if (!box || box.dataset.jumpLatestWired === "1") return;
    box.dataset.jumpLatestWired = "1";
    box.addEventListener("scroll", () => {
      _updateJumpLatestButton();
    }, { passive: true });
  }

  // call button updates after any message-list mutation
  function attachMutation() {
    const box = document.getElementById("message-list");
    if (!box || box.dataset.jumpLatestMutWired === "1") return;
    box.dataset.jumpLatestMutWired = "1";
    const mo = new MutationObserver(() => {
      _updateJumpLatestButton();
    });
    mo.observe(box, { childList: true, subtree: true });
  }

  function refreshAll() {
    ensureButtons();
    attachScrollWatcher();
    attachMutation();
    _updateJumpLatestButton();
    _updateMentionButton();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refreshAll);
  } else {
    refreshAll();
  }
  setTimeout(refreshAll, 300);
  setTimeout(refreshAll, 1200);

  // periodic refresh of unseen mentions (every 15s)
  setInterval(async () => {
    if (!state.chats || state.chats.length === 0) return;
    await refreshUnseenMentions();
    // update badges in chat list without full reload
    document.querySelectorAll("#chat-list li").forEach(li => {
      const cid = li.dataset.chatId;
      if (!cid) return;
      const count = state.unseenMentions[cid] || state.unseenMentions[parseInt(cid, 10)] || 0;
      let badge = li.querySelector(".mention-badge");
      if (count > 0) {
        if (!badge) {
          badge = document.createElement("span");
          badge.className = "mention-badge";
          badge.textContent = "@";
          li.appendChild(badge);
        }
        badge.title = `${count} unread mention${count>1?"s":""}`;
        badge.style.display = "";
      } else if (badge) {
        badge.remove();
      }
    });
    if (state.activeChat) {
      await refreshChatMentions(state.activeChat.chat_id);
    }
  }, 15000);

  window.refreshUnseenMentions = refreshUnseenMentions;
  window.refreshChatMentions = refreshChatMentions;
  window.jumpToMention = jumpToMention;
  window.markAllMentionsSeen = markAllMentionsSeen;
})();

