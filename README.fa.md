# termgram

> یک کلاینت ترمینالی (TUI + CLI) و کلاینت مرورگری برای **ربات‌های تلگرام** — ارسال، مدیریت، مانیتور، بریج، و حتی ساخت ربات‌های مدیریت‌شده، مستقیم از ترمینال یا مرورگر شما.

`termgram` یک TUI تک‌فایلی و منو-محور است که با پایتون خالص نوشته شده. با **Bot API** تلگرام از طریق HTTPS (با `requests`) صحبت می‌کند و پشتیبانی از **پروکسی SOCKS5 / HTTP** را به‌صورت پیش‌فرض دارد (با `PySocks`). همه‌ی پیام‌های دریافتی در SQLite محلی ذخیره می‌شوند برای مرور بعدی. از v1.1.0 حالت **CLI غیرتعاملی** برای اسکریپت‌نویسی، از v1.2.0 **API Server** داخلی که می‌تواند نقش پروکسی/بریج کامل جلوی Telegram Bot API را بازی کند، و از **v1.3.0** یک **Web UI** کامل (کلاینت مرورگری) و پشتیبانی **Managed Bots** (ساخت و مدیریت ربات‌های دیگر از طریق یک deeplink قابل اشتراک) همراه این ابزار است.

> 🌐 **English version:** [README.md](README.md)

---

## ✨ امکانات

### 📨 ارسال همه‌ی نوع‌های پیام

متن · عکس · انیمیشن (GIF) · ویدیو · سند · صدا · ویس · ویدیو نوت · استیکر · موقعیت · مخاطب · نظرسنجی · تاس · واکنش

### 🖥 چهار روش برای استفاده

- **TUI تعاملی** — منوی شماره‌دار و پرامپت‌محور؛ ایده‌آل برای کشف دستی API.
- **حالت CLI** — ساب‌کامندهای یک‌باره برای اسکریپت‌نویسی، cron، یا ارسال سریع از شل. `python3 termgram.py --help` را ببینید.
- **API Server** — یک بریج HTTP داخلی (منوی **52**) که روی `host:port` با توکن مستقل گوش می‌دهد و درخواست‌های `/bot<token>/<method>` را به Telegram Bot API واقعی پروکسی می‌کند. پاسخ‌های `getUpdates` **قبل از** بازگشت به فراخواننده در `tg.db` ذخیره می‌شوند.
- **Web UI** — کلاینت مرورگری با دیوار ورود، لیست چت، نمایش پیام، واکنش‌ها، مدیای ذخیره‌شده (استیکر/انیمیشن)، جست‌وجوی اعضا، ارسال گروهی منشن، آپلود فایل، و پولر پس‌زمینه‌ی اختیاری که `tg.db` را تازه نگه می‌دارد. اجرا با `python3 termgram.py web` (پایین‌تر توضیح داده شده).

### 🔗 دکمه‌های URL درون‌خطی

زیر هر پیامی که می‌فرستید می‌توانید **دکمه‌های کیبورد درون‌خطی** بگذارید. دکمه‌ها سطر به سطر چیده می‌شوند؛ هر سطر می‌تواند یک یا چند دکمه‌ی URL داشته باشد. بعد از انتخاب محتوا در هر جریان `send_*`، `termgram` می‌پرسد که آیا می‌خواهید دکمه اضافه کنید — برای هر دکمه یک برچسب و یک URL وارد کنید.

```
Row 1 — number of buttons: 2
  button 1 — text: 🌐 Website   url: https://example.com
  button 2 — text: 📢 Channel   url: https://t.me/mychannel
Row 2 — number of buttons: 1
  button 1 — text: 💬 Support   url: https://t.me/support
Row 3 — number of buttons:            ← empty = finish
```

> ⚠️ `sendVideoNote` از دکمه پشتیبانی **نمی‌کند** (محدودیت Telegram API)، پس آن جریان پرامپت دکمه را رد می‌کند.

### 💬 Quote-reply (reply_parameters)

به یک **بخش مشخص** از یک پیام موجود پاسخ دهید با استفاده از `reply_parameters.quote`. هر جریان ارسال از طریق پرامپت مشترک حالا می‌پرسد:

```
reply_to_message_id (empty = no reply): 12913
  ↳ cross-chat reply (source msg in another chat)? [y/N]: n
  ↳ quote a specific part of the message? [y/N]: y
  ↳ quote text (must be an exact substring of the original): hello world
```

همین رفتار در TUI، حالت مانیتور (دستور `r`)، Web UI و CLI (`--quote "..."`) یکسان است. نقل‌قول **باید دقیقاً یک زیررشته‌ی** متن/کپشن پیام منبع باشد، وگرنه تلگرام `QUOTE_TEXT_INVALID` برمی‌گرداند.

### 🔀 پاسخ بین‌چتی — بومی، بدون copy

پاسخ به پیامی که در **چت دیگری** قرار دارد کاملاً بومی شده. `termgram` از `reply_parameters` تلگرام با `chat_id` جاسازی‌شده استفاده می‌کند:

```json
{
  "reply_parameters": {
    "message_id": 42,
    "chat_id": -1001234567890,
    "quote": "optional fragment"
  }
}
```

دیگر خبری از رفت‌وبرگشت `copyMessage` نیست. پاسخ **مستقیماً زیر پیام اصلی** نمایش داده می‌شود، حتی بین چت‌ها. اگر چت مبدأ و مقصد یکی باشد، برای سادگی از `reply_to_message_id` استفاده می‌شود.

- **TUI:** هر جریان ارسال (متن، عکس، تاس، …) — پرامپت `reply_to_message_id` حالا شاخه‌ی بین‌چتی هم دارد.
- **CLI:** `--reply-to <id> --reply-to-chat <chat> [--quote "..."]`، یا ساب‌کامند اختصاصی `reply`.

> ⚠️ تلگرام پاسخ بین‌چتی را فقط وقتی می‌پذیرد که ربات به پیام مبدأ دسترسی داشته باشد (عضو چت مبدأ باشد، یا پیام مبدأ توسط خود ربات یا ربات دیگری با دسترسی مشترک نوشته شده باشد). در غیر این صورت `MESSAGE_TO_BE_REPLIED_NOT_FOUND` می‌گیرید.

### 💬 واکنش‌های سفارشی

`termgram` مجموعه‌ی **۶۱ واکنش استاندارد تلگرام** (👍 ❤️ 🔥 …) را در `config.json` همراه دارد. واکنش‌ها را می‌توانید به‌صورت تعاملی از طریق **منوی 51) Manage reactions** (لیست، افزودن، حذف، یا بازنشانی به واکنش‌های استاندارد تلگرام) مدیریت کنید، یا مستقیماً `config.json` را ویرایش کنید.

واکنش‌ها به‌صورت JSON تمیز ساختار یافته‌اند:

```json
{
  "emoji": "👍",
  "label": "Thumbs Up"
}
```

- فیلد `emoji` به تلگرام ارسال می‌شود.
- فیلد `label` توضیح نمایشی در انتخاب‌گر است.
- تغییرات ذخیره‌شده در `config.json` بدون ری‌استارت دوباره بارگذاری می‌شوند.

در **Web UI**، استفاده‌ی واکنش‌ها در جدول `reaction_usage` ذخیره می‌شود، بنابراین پرکاربردترین ایموجی‌ها اول نمایش داده می‌شوند.

### 🔑 مدیریت توکن ربات و اعتبارسنجی سرور

هر زمان خواستید توکن ربات را از طریق **منوی 50) Manage bot token** مدیریت کنید:
- نمایش توکن ماسک‌شده یا کامل.
- به‌روزرسانی توکن با اعتبارسنجی فوری Telegram API (`getMe`).
- تست اتصال و هویت بدون خروج از کلاینت.
- تنظیم **Base URL سفارشی** (برای استفاده پشت یک پروکسی API خود-میزبان).

هنگام راه‌اندازی، `termgram` توکن شما را مستقیماً با سرورهای تلگرام اعتبارسنجی می‌کند. اگر توکن نامعتبر یا خالی باشد، فوراً هشدار می‌دهد (پاسخ `401 Unauthorized` تلگرام را تأیید می‌کند) و از شما توکن معتبر، Base URL سفارشی، یا خروج تمیز می‌خواهد.

### 🌐 Base URL سفارشی

اگر `api.telegram.org` مسدود است (یا می‌خواهید ترافیک را از بریج خودتان بفرستید)، آدرس ریشه‌ی سفارشی را از **منوی 50 → 4**، از پرامپت خطای راه‌اندازی، یا مستقیماً در `config.json` تنظیم کنید:

```json
{ "base_url": "https://tg-bridge.example.com" }
```

سپس `termgram` فراخوانی‌ها را به `https://tg-bridge.example.com/bot<token>/<method>` می‌فرستد. خالی گذاشتن `base_url` به endpoint پیش‌فرض تلگرام بازمی‌گردد.

### 🛡 راه‌اندازی بدون کرش

حتی اگر `termgram.py` را به‌تنهایی در یک پوشه‌ی خالی اجرا کنید، به‌طور خودکار `config.json` را می‌سازد و اسکیمای SQLite `tg.db` را بدون کرش یا خطای فایل‌گم‌شده مقداردهی می‌کند.

### 🤖 پروفایل ربات

هویت و پروفایل فعلی ربات را یک‌جا بخوانید:

- **`getMe`** — شناسه، نام، یوزرنیم، قابلیت‌ها
- **`getMyName`** — نام نمایشی سراسری (Bot API 9.0+)
- **`getMyDescription`** — بیوگرافی صفحه‌ی پروفایل
- **`getMyShortDescription`** — متن کوتاه نمایش در چت‌های اشتراکی
- **`getUserProfilePhotos`** — مجموعه‌ی عکس پروفایل فعلی

و طبیعتاً می‌توانید همه را **تغییر** دهید:

تنظیم نام · تنظیم بیو (description) · تنظیم بیوی کوتاه · تنظیم / حذف عکس پروفایل

- **TUI:** منوی **49) Get current profile**
- **CLI:** `python3 termgram.py profile`

جریان **تنظیم عکس پروفایل** (منوی 35) از عکس **استاتیک** (JPG/PNG، پیشنهاد 512×512) و **انیمیشن** (MP4) از طریق `setMyProfilePhoto` پشتیبانی می‌کند.

### 👤 اطلاعات حساب کاربر

هر پروفایل عمومی کاربر را با **منوی 59** ببینید:

- **`getUserProfilePhotos`** — آخرین عکس پروفایل + `file_id` بزرگ‌ترین سایز
- **`getUserProfileAudios`** — آهنگ‌های پروفایل کاربر (Bot API 7.0+)
- **`getChat`** — اطلاعات عمومی حساب (فقط اگر ربات چت خصوصی با کاربر داشته باشد)

حداقلی و هدفمند — فقط ضروری‌ها، بدون شلوغی.

### 🛠 مدیریت پیام

ویرایش · حذف (تکی **یا** بازه‌ای) · سنجاق · برداشتن سنجاق · فوروارد · اکشن‌های چت (تایپ / آپلود)

**حذف بازه‌ای** — یک `chat_id` از DB (یا دستی) انتخاب کنید و بازه‌ی `from → to` از `message_id` را بدهید. `termgram` برای هر شناسه یک `deleteMessage` می‌فرستد، flood-control (`429 retry_after`) را رعایت می‌کند و خلاصه‌ی کامل می‌دهد:

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

### 💾 مدیریت پایگاه داده‌ی محلی

همه‌ی پیام‌های دریافتی در `tg.db` ذخیره می‌شوند. برای سبک نگه داشتن آن، **منوی 54** این گزینه‌ها را دارد:

1. پاک‌سازی **چت خاص** (از DB)
2. پاک‌سازی **بر اساس نوع چت** (private / group / supergroup / channel)
3. پاک‌سازی **بر اساس بازه‌ی تاریخ** (unix ts)
4. پاک‌سازی **بر اساس بازه‌ی message_id** داخل یک چت (از DB)
5. **پاک‌سازی یتیم‌ها** — ردیف‌های `entities` / `chat_users` بدون پیام

### 👥 اعضای چت (از DB)

**منوی 57** همه‌ی اعضای شناخته‌شده‌ی یک گروه/سوپرگروه را که از پیام‌های دریافتی تجمیع شده‌اند (`chat_users`) نشان می‌دهد:

```
--- Members of chat -1001234567890 (12) ---
  1) id=8195921211    Sarina            @Sarina_girl_bot   msgs=42   last=2026-...
  2) id=123456789     Ali Rezaei        @ali_reza          msgs=120  last=2026-...
  d) Delete one   r) Reset all   e) Export JSON   0) Back
```

- `d` — حذف یک کاربر از لیست DB (او را از گروه واقعی **بیرون نمی‌کند**)
- `r` — بازنشانی کل لیست اعضا برای آن چت
- `e` — خروجی به `members_<chat>_<ts>.json`

### 📣 منشن گروهی اعضا

**منوی 58** به شما اجازه می‌دهد اعضا را از DB @-منشن کنید:

- **همه‌ی اعضا** یا **لیست سفارشی** (`123, @ali, 456` — شناسه و یوزرنیم ترکیبی)
- تقسیم خودکار به چند پیام بر اساس **اندازه‌ی دسته** (پیش‌فرض ۳۰) و **محدودیت کاراکتر** (۳۸۰۰)
- از HTML `<a href="tg://user?id=...">` استفاده می‌کند تا برای کاربران بدون یوزرنیم هم کار کند
- متن سرصفحه‌ی اختیاری، پاسخ اختیاری (با پشتیبانی پاسخ بین‌چتی)
- خلاصه در پایان: تعداد اعضای منشن‌شده / پیام‌های ارسالی / خطاها

**Web UI** همین گروه‌بندی را از طریق `POST /api/chats/<id>/mention` با `{text, all, user_ids, batch_size, reply_to}` ارائه می‌دهد.

### 🧭 قفل chat_id

**منوی 55** یک `chat_id` را سراسری پین می‌کند. پس از قفل شدن:
- هر پرامپتی که `chat_id` می‌خواهد (ارسال، ویرایش، حذف، فوروارد، سنجاق، …) بی‌صدا از مقدار قفل استفاده می‌کند.
- قفل فعلی در بالای منوی اصلی نمایش داده می‌شود: `Locked chat_id: -1001   Guest: OFF   API: OFF`
- دستی قفل کنید، از DB انتخاب کنید، یا پاک کنید.

### 👻 حالت Guest در مانیتور

**منوی 56** مانیتور را به فیلتر **فقط guest-chat** تغییر می‌دهد. فقط پیام‌هایی که از طریق business connection / guest bot می‌آیند (تشخیص با `business_connection_id`، `sender_business_bot`، `via_bot`، `sender_boost_count`) نمایش داده می‌شوند؛ بقیه بی‌صدا ذخیره اما پنهان می‌شوند. وضعیت در هدر منو به‌صورت `Guest: ON` / `Guest: OFF` دیده می‌شود.

### 📡 تشخیص منشن/پاسخ در Silent Fetch

وقتی یک اجرای `Silent fetch` تمام می‌شود، `termgram` همه‌ی پیام‌های ذخیره‌شده را برای این‌ها اسکن می‌کند:
- **@-منشن‌های ربات** (از طریق entityهای تلگرام یا متن `@username`)
- **پاسخ‌ها به پیام‌های خود ربات**

در پایان گزارش می‌دهد:

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

انتخاب `y` هر پیام را باز می‌کند و اجازه‌ی پاسخ درجا می‌دهد — بدون نیاز به برگشت به مانیتور.

**Web UI** این‌ها را در `mention_flags` ذخیره می‌کند و یک بج «Unseen mentions» در نوار کنار نشان می‌دهد.

### 🤖 حالت مدیریت ربات (رجیستری محلی)

**منوی 53** یک رجیستری محلی از همه‌ی ربات‌هایی که مدیریت می‌کنید نگه می‌دارد:

- لیست هر ربات مدیریت‌شده با id، username، `added_at`، `last_seen_at`
- مشاهده‌ی توکن ذخیره‌شده
- مشاهده / بررسی مجوزهای ذخیره‌شده در هر چت
- حذف ردیف یک ربات (و ردیف‌های مجوزش) از DB
- **افزودن ربات جدید** — یک deeplink قابل اشتراک تولید می‌کند (ببینید Managed Bots در پایین)

### 🆕 Managed Bots (Bot API 9.6+)

از v1.3.0، `termgram` از قابلیت **Managed Bots** تلگرام پشتیبانی می‌کند. رباتی با فلگ `can_manage_bots` (فعال‌شده از طریق **Bot Management Mode** در `@BotFather`) می‌تواند از طرف کاربران ربات‌های دیگر بسازد و مدیریت کند — **بدون نیاز به باز کردن `@BotFather`**.

**چطور کار می‌کند**

1. **منوی 60) Managed bot link** — یا **منوی 53 → a** — یک لینک قابل اشتراک تولید می‌کند:
   ```
   https://t.me/newbot/<manager_bot_username>/<suggested_username>?name=<suggested_display_name>
   ```
   لینک **به‌صورت محلی** ساخته می‌شود (بدون تماس API) با `urllib.parse.quote`.

2. این لینک را برای کاربری بفرستید. او در اپ تلگرام باز می‌کند، تأیید می‌کند، و ربات جدیدی تحت ربات مدیر شما ساخته می‌شود.

3. تلگرام یک **`updateManagedBot`** برای ربات مدیر شما می‌فرستد. `termgram` آن را در **هر چهار حلقه‌ی دریافت** (Silent fetch، Monitor، Web UI poller، API Server) پردازش می‌کند و به‌صورت خودکار:
   - id، username، name، و owner ربات جدید را چاپ می‌کند
   - `getManagedBotToken` را فراخوانی می‌کند تا توکن را بگیرد
   - ربات جدید را در `managed_bots` ذخیره می‌کند

4. از **منوی 53 → انتخاب ربات** مدیریتش کنید:
   - **`getManagedBotToken`** — دریافت/به‌روزرسانی توکن
   - **`replaceManagedBotToken`** — چرخش توکن (توکن قبلی باطل می‌شود)
   - **`bots.getAccessSettings`** / **`bots.editAccessSettings`** — مشاهده یا تغییر مجموعه‌ی مجوزهای ربات
   - **`bots.exportBotToken`** — خروجی توکن در سطح MTProto

**متدهای API پشتیبانی‌شده**

| متد | کاربرد |
|---|---|
| `bots.checkUsername` | اعتبارسنجی یوزرنیم پیشنهادی |
| `bots.createBot` | (فقط از طریق deeplink — پایین را ببینید) |
| `getManagedBotToken` | دریافت توکن |
| `replaceManagedBotToken` | چرخش توکن |
| `bots.getAccessSettings` | خواندن مجموعه‌ی دسترسی |
| `bots.editAccessSettings` | به‌روزرسانی مجموعه‌ی دسترسی |
| `bots.exportBotToken` | خروجی توکن MTProto |
| `updateManagedBot` | نوع آپدیت دریافتی در ساخت / تغییر |

> 💡 **توجه:** `bots.createBot` یک متد MTProto است و **هرگز** مستقیماً توسط `termgram` فراخوانی نمی‌شود. ساخت ربات همیشه **سمت کلاینت** اتفاق می‌افتد وقتی کاربر deeplink را در اپ تلگرام باز می‌کند. `termgram` فقط لینک را تولید می‌کند و به `updateManagedBot` حاصل واکنش می‌دهد — دقیقاً همان‌طور که تلگرام در نظر گرفته.

> ⚠️ **پیش‌نیاز:** **Bot Management Mode** را در `@BotFather` برای ربات مدیر خود فعال کنید. در غیر این صورت `getMe` مقدار `can_manage_bots: false` برمی‌گرداند و همه‌ی فراخوانی‌های Managed Bot شکست می‌خورند.

### 🛰 API Server (بریج / پروکسی)

**منوی 52** یک HTTP server خودکفا راه می‌اندازد که مثل `api.telegram.org` رفتار می‌کند:

- روی `api_server_host:api_server_port` گوش می‌دهد (پیش‌فرض `127.0.0.1:8080`)
- فراخوانی‌ها را در `/bot<token>/<method>` می‌پذیرد
- از `api_server_token` در `config.json` استفاده می‌کند، یا به توکن ربات فعال برمی‌گردد
- هر درخواست را به Bot API بالادست فوروارد می‌کند (از طریق `PROXY` / `HTTPS_PROXY` اگر تنظیم شده باشد)
- **هر پاسخ `getUpdates` را** در `tg.db` (پیام‌ها، ویرایش‌ها، فایل‌ها، واکنش‌ها، entityها) **قبل از** بازگشت به فراخواننده ذخیره می‌کند
- بی‌خطر برای اجرا در پس‌زمینه؛ اگر `api_server_enabled` در `config.json` برابر `true` باشد، هنگام راه‌اندازی خودکار فعال می‌شود

### 🌐 Web UI (کلاینت مرورگری)

از **v1.3.0**، `termgram` یک کلاینت مرورگری کامل زیر `web-ui/` همراه دارد. اجرا:

```bash
python3 termgram.py web \
    --host 127.0.0.1 \
    --port 8081 \
    --password "your-secret" \
    --session-ttl 86400 \
    --cache-max-mb 512
```

سپس `http://127.0.0.1:8081/` را باز کنید و وارد شوید.

**چه چیزی می‌گیرید**

- **نوار کنار** — همه‌ی چت‌های `tg.db` با بج منشن‌های خوانده‌نشده
- **نمایش پیام** — حباب‌ها، پیش‌نمایش پاسخ، فوروارد از، بج مدیر فرستنده، واکنش‌های درون‌خطی
- **ارسال** — متن، واکنش، فوروارد، آپلود (عکس/ویدیو/سند/صدا/ویس/انیمیشن/استیکر/ویدیو نوت)
- **منشن‌ها** — منشن گروهی اعضا با همان منطق HTML `tg://user` منوی 58
- **مدیای ذخیره‌شده** — ذخیره/ستاره/ارسال استیکر و انیمیشن (جدول `saved_media`)
- **اطلاعات چت** — `getChat` زنده + شمارش اعضا + لیست مدیران (کش در `chat_admins`)
- **جست‌وجوی اعضا** — `chat_users` کش‌شده با تعداد پیام
- **واکنش‌ها** — مرتب‌شده بر اساس استفاده (`reaction_usage`)، ارسال با `setMessageReaction`
- **آواتارها** — کش روی دیسک زیر `cache/avatars/` و `cache/chat_avatars/`
- **کش فایل** — فایل‌های دانلودشده زیر `cache/files/` با سقف دیسک (`--cache-max-mb`)
- **پولر (اختیاری)** — یک کلید **Sync & auto-refresh** یک thread پس‌زمینه راه می‌اندازد که `getUpdates` صدا می‌زند و در `tg.db` می‌نویسد، تا UI زنده بماند. با `--no-poller` غیرفعال کنید.

**امنیت**

- همه‌ی endpointهای تغییردهنده‌ی وضعیت (`POST`) نیازمند هدر `X-CSRF-Token` منطبق با توکن CSRF نشست هستند.
- ورود محدود به نرخ (۵ تلاش/دقیقه/IP) است.
- کوکی نشست `HttpOnly; SameSite=Strict` است.
- `--https-cert` و `--https-key` را بدهید تا HTTPS فعال شود؛ bind به `0.0.0.0` بدون HTTPS پرامپت تأیید نشان می‌دهد.

**مسیرها (برای کنجکاوها)**

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

### 📡 مانیتور و اتوماسیون

حالت مانیتور (به‌روزرسانی زنده) · پاسخ خودکار · واکنش خودکار · ویرایش واکنش‌های درون‌خطی

### 💾 پایگاه داده‌ی محلی (SQLite)

Silent fetch · کاوشگر چت · نمایش‌گر تاریخچه · پاک‌سازی / پاکسازی — هر پیام دریافتی در `tg.db` ذخیره می‌شود

اسکیما شامل جدول‌های `messages`، `message_files`، `message_edits`، `message_reactions`، `entities`، `chat_users`، `chat_admins`، `chat_photos`، `user_photos`، `mention_flags`، `saved_media`، `reaction_usage`، `file_cache`، `web_sessions`، `managed_bots`، `bot_permissions` و `state` است.

### 🌐 پشتیبانی پروکسی

`socks5://` و `http://` — از طریق `config.json`، به‌صورت تعاملی در **منوی 17**، و **همچنین** به‌طور خودکار توسط API Server داخلی و دانلود فایل‌های Web UI استفاده می‌شود.

### 🧭 TUI بدون پیکربندی & کاسکید منوی نرم

همه‌چیز شماره‌دار است. هیچ فلگی برای استفاده‌ی تعاملی حفظ نیست. فایل‌های پیکربندی و پایگاه داده در اولین اجرا خودکار ساخته می‌شوند. وقتی منوی تعاملی باز می‌شود، با یک کاسکید سریع و نرم انیمیت می‌شود تا از پرش‌های ناگهانی صفحه جلوگیری شود.

### 🎨 بنر نسخه

هنگام راه‌اندازی تعاملی `termgram` یک بنر مرتب چاپ می‌کند:

```
╔════════════════════════════════════════════════════╗
║  📡 termgram  v1.3.0                              ║
║  Terminal client for Telegram bots                 ║
╚════════════════════════════════════════════════════╝
```

در **حالت CLI** بنر به یک خط کوتاه تبدیل می‌شود تا هیچ‌وقت خروجی شل را شلوغ نکند:

```
termgram v1.3.0
```

---

## 📋 پیش‌نیازها

- **Python 3.10+** (تست‌شده روی 3.14.x)
- `requests`
- `PySocks`

اختیاری (برای HTTPS روی Web UI):
- `ssl` — در CPython تعبیه شده؛ فقط `--https-cert` و `--https-key` را بدهید

---

## 🚀 نصب

```bash
git clone https://github.com/amirSAV/termgram.git
cd termgram

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

---

## ⚙️ پیکربندی

### پیکربندی یکپارچه (`config.json`)

همه‌ی پیکربندی — توکن ربات، پروکسی، Base URL سفارشی، تنظیمات API Server، فلگ guest-mode، قفل chat_id، و واکنش‌های سفارشی — در یک فایل `config.json` ذخیره می‌شود. می‌توانید از قالب ارائه‌شده بسازید:

```bash
cp config.json.example config.json
```

یا صرفاً `termgram` را مستقیم اجرا کنید (`python3 termgram.py`): `termgram` به‌طور خودکار `config.json` و `tg.db` را در اولین اجرا می‌سازد و به‌صورت تعاملی از شما می‌خواهد توکن ربات معتبر وارد کنید!

نمونه‌ی `config.json`:

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

1. **توکن ربات**: از [@BotFather](https://t.me/BotFather) بگیرید. برای **Managed Bots**، **Bot Management Mode** را در `@BotFather` فعال کنید.
2. **پروکسی (اختیاری)**: اسکیم‌های پشتیبانی‌شده: `socks5://`، `http://`، `https://`. برای اتصال مستقیم `""` بگذارید.
3. **واکنش‌ها**: لیست گلچین‌شده‌ی ایموجی‌ها. از طریق **منوی 51) Manage reactions** قابل تنظیم است.
4. **`base_url`** (اختیاری): آدرس ریشه‌ی سفارشی برای Bot API (پیش‌فرض `https://api.telegram.org`).
5. **`api_server_*`** (اختیاری): فعال‌سازی بریج داخلی، انتخاب host/port، و اختیاراً تنظیم `api_server_token` اختصاصی (خالی = استفاده‌ی مجدد از توکن ربات). منوی **52**.
6. **`guest_chat_mode`** (اختیاری): محدود کردن مانیتور به پیام‌های guest/business. منوی **56**.
7. **`locked_chat_id`** (اختیاری): پین یک chat ID تا هر پرامپتی که در غیر این صورت یکی می‌خواست بی‌صدا از این استفاده کند. منوی **55**.

> 💡 **ارتقای خودکار & مهاجرت**: اگر از نسخه‌ی قدیمی‌تر ارتقا می‌دهید، `termgram` به‌طور خودکار `token.txt`، `proxy.txt` و `reactions.txt` موجود را می‌خواند، تنظیماتشان را به `config.json` منتقل می‌کند و فایل‌های قدیمی را پاک‌سازی می‌کند.

---

## ▶️ استفاده

### TUI تعاملی

```bash
python3 termgram.py
```

خواهید دید:

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

فقط یک شماره انتخاب کنید و پرامپت‌ها را دنبال کنید.

#### مثال: ارسال متن با دکمه‌ها

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

#### مثال: ساخت یک Managed Bot

```
choice: 60

--- Create Managed Bot Invite Link ---
Suggested username for new bot (e.g. MyCoolBot): MyShopBot
Suggested display name (optional): My Shop Assistant

✔ Link generated:
  https://t.me/newbot/MyManagerBot/MyShopBot?name=My%20Shop%20Assistant

Share this link with users so they can create a bot managed by you.
```

وقتی کاربر آن لینک را باز می‌کند و تأیید می‌کند، ربات مدیر شما `updateManagedBot` دریافت می‌کند و `termgram` اطلاعات ربات جدید به‌همراه توکنش را به‌طور خودکار چاپ می‌کند.

---

### حالت CLI

هر آرگومان بعد از نام اسکریپت `termgram` را به حالت غیرتعاملی می‌برد. هر ساب‌کامند یک exit code شل برمی‌گرداند (`0` = موفق، غیر صفر = خطا)، پس با اسکریپت‌ها خوب ترکیب می‌شود.

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

هر ساب‌کامند هم `--help` مخصوص خودش را دارد:

```bash
python3 termgram.py photo --help
python3 termgram.py ban --help
python3 termgram.py reply --help
python3 termgram.py web --help
```

#### مثال‌های CLI

```bash
# ── ارسال ─────────────────────────────────────────────────
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

# ── مدیریت پیام ────────────────────────────────────────────
python3 termgram.py react  -1001234567890 99 👍
python3 termgram.py edit   -1001234567890 99 "updated text"
python3 termgram.py delete -1001234567890 99
python3 termgram.py pin    -1001234567890 99
python3 termgram.py unpin  -1001234567890            # unpin all
python3 termgram.py forward @src 42 @dst
python3 termgram.py chat-action @mychannel typing
python3 termgram.py reply @news 100 -1001234567890 "this is important"

# ── چت / اعضا ─────────────────────────────────────────────
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

# ── پروفایل ربات ──────────────────────────────────────────
python3 termgram.py me
python3 termgram.py profile
python3 termgram.py set-name "My Cool Bot"
python3 termgram.py set-bio "I help you do X." --lang en
python3 termgram.py set-bio --bio-file bio.txt
python3 termgram.py set-short-bio "Fast & simple."
python3 termgram.py remove-photo

# ── فایل‌ها ───────────────────────────────────────────────
python3 termgram.py download AgACAgQAAxkBAA... --out pic.jpg
python3 termgram.py upload -1001234567890 ./img.png --as photo

# ── Web UI ────────────────────────────────────────────────
# فقط localhost، HTTP، رمز = توکن ربات
python3 termgram.py web

# پورت سفارشی + رمز صریح
python3 termgram.py web --host 0.0.0.0 --port 9090 --password "s3cr3t"

# HTTPS با گواهی خودتان (برای هاست عمومی توصیه می‌شود)
python3 termgram.py web --host 0.0.0.0 --port 443 \
    --https-cert ./cert.pem --https-key ./key.pem \
    --password "s3cr3t"

# فقط localhost، پولر غیرفعال (اگر Monitor جای دیگر اجرا می‌کنید)
python3 termgram.py web --no-poller
```

##### منابع متن و کپشن

چند ساب‌کامند متن را **درون‌خطی** یا **از فایل** می‌پذیرند:

| ساب‌کامند | شکل درون‌خطی | شکل فایل |
|-----------|-------------|-----------|
| `text` | `text` موقعیتی | `--text-file F` |
| `edit` | `text` موقعیتی | `--text-file F` |
| `reply` | `text` موقعیتی | `--text-file F` |
| `set-bio` | `description` موقعیتی | `--bio-file F` |
| `set-short-bio` | `description` موقعیتی | `--bio-file F` |

ساب‌کامندهای فایل‌محور (photo، document، video، audio، voice، animation) دو گزینه‌ی متقابلاً انحصاری برای کپشن دارند:

| گزینه | معنی |
|-------|------|
| `--caption TEXT` | رشته‌ی کپشن درون‌خطی. |
| `--caption-file F` | خواندن کپشن از فایل `F` (UTF-8، چندخطی امن). |

اگر هر دو داده شوند، `--caption-file` اولویت دارد.

##### کدهای خروج

| کد | معنی |
|----|------|
| `0` | موفق (تلگرام `ok` برگرداند) |
| `1` | تلگرام خطا برگرداند |
| `2` | خطای استفاده/فایل محلی (فایل گم‌شده، …) |

##### بنر CLI

در حالت CLI بنر عمداً کوچک است تا با خیال راحت pipe شود:

```
termgram v1.3.0
```

بدون پرامپت اتصال، بدون «press any key» — یک دستور یک‌باره اجرا می‌شود، نتیجه‌اش را چاپ می‌کند و خارج می‌شود.

---

### Web UI (کلاینت مرورگری)

سرور را اجرا کنید:

```bash
python3 termgram.py web --host 127.0.0.1 --port 8081 --password "your-secret"
```

سپس **http://127.0.0.1:8081/** را باز کنید و وارد شوید.

| فلگ | پیش‌فرض | کاربرد |
|-----|---------|--------|
| `--host` | `127.0.0.1` | آدرس bind (`0.0.0.0` برای LAN — نیازمند تأیید) |
| `--port` | `8081` | پورت TCP |
| `--password` | توکن ربات | رمز ورود — **همیشه برای هاست عمومی یک رمز جداگانه تنظیم کنید** |
| `--session-ttl` | `86400` | طول عمر نشست به ثانیه |
| `--cache-max-mb` | `512` | حداکثر کش دیسک برای فایل‌های دانلودشده |
| `--https-cert` / `--https-key` | — | گواهی PEM + کلید خصوصی برای فعال‌سازی HTTPS |
| `--no-poller` | خاموش | پولر `getUpdates` پس‌زمینه را راه‌اندازی نکن |

**Web UI نیازمند وجود پوشه‌ی `web-ui/`** (شامل `index.html`، `app.js`، `style.css`، `favicon.svg`) در کنار `termgram.py` است. اگر مخزن را clone کرده‌اید، آن‌ها همان‌جا هستند.

---

## 🖥 نکات پلتفرم

- ✅ **لینوکس / مک**: کاملاً پشتیبانی می‌شود.
- ⚠️ **ویندوز**: کاراکترهای فارسی ممکن است در ترمینال پیش‌فرض درست رندر نشوند. از **Windows Terminal** با فونتی که RTL را پشتیبانی می‌کند (مثل *Cascadia Code*، *Vazirmatn*) استفاده کنید یا داخل **WSL** اجرا کنید. Web UI تحت تأثیر نیست و در هر مرورگری کار می‌کند.

---

| فایل | کاربرد | commit شده؟ |
|------|--------|-------------|
| `termgram.py` | برنامه‌ی اصلی | ✅ |
| `requirements.txt` | وابستگی‌های پایتون | ✅ |
| `README.md` | نسخه‌ی انگلیسی | ✅ |
| `README.fa.md` | این فایل | ✅ |
| `LICENSE` | مجوز MIT | ✅ |
| `config.json.example` | قالب پیکربندی | ✅ |
| `web-ui/` | کلاینت مرورگری (`index.html` + `static/`) | ✅ |
| `config.json` | پیکربندی و اسرار واقعی شما | ❌ (gitignored) |
| `tg.db` | پایگاه داده‌ی پیام محلی | ❌ (gitignored) |
| `cache/` | کش فایل/آواتار/مدیا برای Web UI | ❌ (gitignored) |
| `get_updates_py.sh` | اسکریپت شل قدیمی (منسوخ با Silent fetch) | ❌ |

---

## 🤝 مشارکت

مشارکت از **همکاران دعوت‌شده** استقبال می‌شود. اگر می‌خواهید کمک کنید، ابتدا یک issue باز کنید تا در مورد تغییراتی که می‌خواهید بدهید بحث شود.

---

## 📜 مجوز

[MIT](LICENSE)