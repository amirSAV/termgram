# termgram

> یک کلاینت ترمینالی (TUI + CLI) و کلاینت مرورگری برای **ربات‌های تلگرام** — ارسال، مدیریت، مانیتور، بریج، و حتی ساخت ربات‌های مدیریت‌شده، مستقیم از ترمینال یا مرورگر شما.

`termgram` یک TUI تک‌فایلی و منو-محور است که با پایتون خالص نوشته شده. با **Bot API** تلگرام از طریق HTTPS (با `requests`) صحبت می‌کند و پشتیبانی از **پروکسی SOCKS5 / HTTP** را به‌صورت پیش‌فرض دارد (با `PySocks`). همه‌ی پیام‌های دریافتی در SQLite محلی ذخیره می‌شوند برای مرور بعدی.

**تاریخچه‌ی نسخه‌ها**

- **v1.1.0** — حالت **CLI غیرتعاملی**
- **v1.2.0** — **API Server** داخلی (پروکسی/بریج)
- **v1.3.0** — **Web UI** کامل + **Managed Bots**
- **v1.4.0** — **TUI ریسپانسیو**، **نوارهای پیشرفت درجا**، **قفل انحصاری `getUpdates`**، **منوی تنظیمات**، **مرورگر آهنگ‌های پروفایل**

> 🌐 **English version:** [README.md](README.md)

---

## ✨ امکانات

### 📨 ارسال همه‌ی نوع‌های پیام

متن · عکس · انیمیشن (GIF) · ویدیو · سند · صدا · ویس · ویدیو نوت · استیکر · موقعیت · مخاطب · نظرسنجی · تاس · واکنش

### 🖥 چهار روش برای استفاده

- **TUI تعاملی** — منوی شماره‌دار و پرامپت‌محور؛ ایده‌آل برای کشف دستی API.
- **حالت CLI** — ساب‌کامندهای یک‌باره برای اسکریپت‌نویسی، cron، یا ارسال سریع.
- **API Server** — یک بریج HTTP داخلی (تنظیمات → API server) که روی `host:port` گوش می‌دهد و درخواست‌های `/bot<token>/<method>` را به Telegram Bot API واقعی پروکسی می‌کند.
- **Web UI** — کلاینت مرورگری با دیوار ورود، لیست چت، نمایش پیام، واکنش‌ها، مدیای ذخیره‌شده، جست‌وجوی اعضا، ارسال گروهی منشن، آپلود فایل، و پولر پس‌زمینه‌ی اختیاری.

### 🎨 TUI ریسپانسیو با انیمیشن دو مرحله‌ای

منوی تعاملی با عرض ترمینال شما سازگار می‌شود: **۱ تا ۵ ستون**، که هر بار رندر مجدد محاسبه می‌شود. چه در یک نشست SSH با ۸۰ ستون باشید چه یک نمایشگر عریض با ۲۴۰ ستون، همه چیز تمیز جا می‌گیرد.

- خط **تیتر** با افکت typewriter ظاهر می‌شود.
- **سطرهای منو** یکی‌یکی fade-in می‌شوند — به‌قدری سریع که فوری حس شود، به‌قدری نرم که پرش نباشد.
- سرعت از طریق `MENU_SPEED` در `config.json` قابل تنظیم است: `off` · `fast` (پیش‌فرض) · `normal` · `slow`.
- صفحه (شامل **تاریخچه‌ی scrollback**) قبل از هر رندر با `\033[H\033[2J\033[3J` پاک می‌شود.
- با **Enter روی پرامپت خالی** منو دوباره بارگذاری می‌شود.
- بعد از هر اقدام، برنامه با `Press Enter to return to main menu...` توقف می‌کند قبل از رندر مجدد.

### 📊 نوارهای پیشرفت درجا

هر دانلود و آپلود یک نوار تک‌خطی زنده نشان می‌دهد که خودش را بازنویسی می‌کند:

```
⬇ [████████████░░░░░░░░░░░░░░░░░░░░]  38.4%  1.8MB/4.7MB  420.5KB/s ETA 7s
```

- عرض تطبیقی بر اساس اندازه‌ی ترمینال.
- **حجم انجام‌شده / کل**، **سرعت**، و **ETA** — یا یک spinner وقتی سرور `Content-Length` برنمی‌گرداند.
- به‌طور خودکار **وقتی stdout یک TTY نیست غیرفعال** می‌شود (امن برای pipe و redirect).
- فعال برای: دانلود فایل از منوی تعاملی (گزینه ۳۷)، دانلود آهنگ پروفایل (گزینه ۶۰)، `download`/`upload` در CLI، و جریان‌های `send_*`.

### 🔒 قفل انحصاری `getUpdates` (به سبک apt)

تلگرام اجازه می‌دهد **فقط یک `getUpdates` فعال به ازای هر بات** داشته باشید. `termgram` این را با یک قفل cross-platform مبتنی بر `flock` (`.getupdates.lock`) اعمال می‌کند:

- **Monitor mode**، **Silent fetch**، **پولر پس‌زمینه‌ی Web UI**، و **API Server** هر کدام قفل را هنگام نیاز می‌گیرند.
- اگر یکی از قبل در حال اجرا باشد، بقیه سریع با پیام روشن شکست می‌خورند:

  ```
  ✘ Cannot start Monitor Mode
    ✘ getUpdates lock held by: api-server (pid 12345, age 8s)
  ```

- فایل قفل **روی دیسک باقی می‌ماند** — OS خودِ `flock` را هنگام خروج یا کرش آزاد می‌کند، پس قفل کهنه غیرممکن است. هرگز دستی پاکش نکن مگر اینکه فایل خراب شده باشد.
- `acquire_getupdates_lock()` و `release_getupdates_lock()` برای اسکریپت‌ها export شده‌اند.

### 🔗 دکمه‌های URL درون‌خطی

زیر هر پیامی که می‌فرستید می‌توانید **دکمه‌های کیبورد درون‌خطی** بگذارید. دکمه‌ها سطر به سطر چیده می‌شوند.

```
Row 1 — number of buttons: 2
  button 1 — text: 🌐 Website   url: https://example.com
  button 2 — text: 📢 Channel   url: https://t.me/mychannel
Row 2 — number of buttons: 1
  button 1 — text: 💬 Support   url: https://t.me/support
Row 3 — number of buttons:            ← empty = finish
```

> ⚠️ `sendVideoNote` از دکمه پشتیبانی **نمی‌کند** (محدودیت Telegram API).

### 💬 Quote-reply (پاسخ نقل‌قولی)

به یک **بخش مشخص** از یک پیام موجود پاسخ دهید با استفاده از `reply_parameters.quote`:

```
reply_to_message_id (empty = no reply): 12913
  ↳ cross-chat reply (source msg in another chat)? [y/N]: n
  ↳ quote a specific part of the message? [y/N]: y
  ↳ quote text (must be an exact substring of the original): hello world
```

همین رفتار در TUI، حالت مانیتور (دستور `r`)، Web UI، و CLI (`--quote "..."`) یکسان است. نقل‌قول **باید دقیقاً یک زیررشته‌ی** متن/کپشن پیام منبع باشد، وگرنه تلگرام `QUOTE_TEXT_INVALID` برمی‌گرداند.

### 🔀 پاسخ بین‌چتی — بومی، بدون copy

پاسخ به پیامی که در **چت دیگری** قرار دارد کاملاً بومی است، با `reply_parameters` و `chat_id` جاسازی‌شده:

```json
{
  "reply_parameters": {
    "message_id": 42,
    "chat_id": -1001234567890,
    "quote": "optional fragment"
  }
}
```

پاسخ **مستقیماً زیر پیام اصلی** نمایش داده می‌شود، حتی بین چت‌ها.

> ⚠️ تلگرام پاسخ بین‌چتی را فقط وقتی می‌پذیرد که ربات به پیام مبدأ دسترسی داشته باشد. در غیر این صورت `MESSAGE_TO_BE_REPLIED_NOT_FOUND` می‌گیرید.

### 💬 واکنش‌های سفارشی

`termgram` مجموعه‌ی **۶۱ واکنش استاندارد تلگرام** را در `config.json` همراه دارد. از **تنظیمات → Manage reactions** (منوی 54 → 4) مدیریت کنید:

```json
{ "emoji": "👍", "label": "Thumbs Up" }
```

- فیلد `emoji` به تلگرام ارسال می‌شود.
- فیلد `label` توضیح نمایشی در انتخاب‌گر است.
- تغییرات ذخیره‌شده در `config.json` بدون ری‌استارت دوباره بارگذاری می‌شوند.

در **Web UI**، استفاده‌ی واکنش‌ها در جدول `reaction_usage` ذخیره می‌شود.

### 🔑 مدیریت توکن ربات و اعتبارسنجی سرور

مدیریت توکن از **تنظیمات → Manage bot token** (منوی 54 → 3):

- نمایش توکن ماسک‌شده یا کامل.
- به‌روزرسانی با اعتبارسنجی فوری Telegram API (`getMe`).
- تست اتصال بدون خروج از کلاینت.
- تنظیم **Base URL سفارشی** (از تنظیمات → Set Base URL).

هنگام راه‌اندازی، `termgram` توکن شما را اعتبارسنجی می‌کند. اگر نامعتبر باشد، پرامپت توکن معتبر، Base URL سفارشی، پروکسی، یا خروج می‌دهد.

### 🌐 Base URL سفارشی

اگر `api.telegram.org` مسدود است، از **تنظیمات → Set Base URL** (منوی 54 → 2)، از پرامپت خطا، یا در `config.json` تنظیم کنید:

```json
{ "base_url": "https://tg-bridge.example.com" }
```

سپس فراخوانی‌ها به `https://tg-bridge.example.com/bot<token>/<method>` می‌روند. خالی = endpoint پیش‌فرض.

### 🛡 راه‌اندازی بدون کرش

حتی اگر `termgram.py` را در یک پوشه‌ی خالی اجرا کنید، به‌طور خودکار `config.json` را می‌سازد و اسکیمای `tg.db` را بدون کرش مقداردهی می‌کند.

### 🤖 پروفایل ربات

هویت و پروفایل فعلی ربات را یک‌جا بخوانید:

- **`getMe`** — شناسه، نام، یوزرنیم، قابلیت‌ها
- **`getMyName`** — نام نمایشی سراسری (Bot API 9.0+)
- **`getMyDescription`** — بیوگرافی صفحه‌ی پروفایل
- **`getMyShortDescription`** — متن کوتاه نمایش در چت‌های اشتراکی
- **`getUserProfilePhotos`** — مجموعه‌ی عکس پروفایل

و همه را **تغییر** دهید:

تنظیم نام · تنظیم بیو · تنظیم بیوی کوتاه · تنظیم / حذف عکس پروفایل

- **TUI:** منوی **36) Get current profile**
- **CLI:** `python3 termgram.py profile`

جریان **تنظیم عکس پروفایل** (منوی 34) از **استاتیک** (JPG/PNG، پیشنهاد 512×512) و **انیمیشن** (MP4) از طریق `setMyProfilePhoto` پشتیبانی می‌کند.

### 👤 اطلاعات حساب کاربر

هر پروفایل عمومی کاربر را با **منوی 50** ببینید:

- **`getUserProfilePhotos`** — آخرین عکس پروفایل + `file_id` بزرگ‌ترین سایز
- **`getUserProfileAudios`** — آهنگ‌های پروفایل کاربر (Bot API 7.0+)
- **`getChat`** — اطلاعات عمومی حساب (اگر ربات چت خصوصی با کاربر داشته باشد)

### 🎵 مرورگر آهنگ‌های پروفایل

یک **منوی اختصاصی برای آهنگ‌های پروفایل کاربر** (منوی **60**، یا از طریق **50**) با دانلودر داخلی:

```
--- 3 profile audio(s) ---
    1) 🎵 Love Story — Taylor Swift
         duration=235s  size=3520123B
    2) 🎵 Blinding Lights — The Weeknd
         duration=200s  size=2988771B
    3) 🎵 Shape of You — Ed Sheeran
         duration=233s  size=3412345B

  type a number to download that song
  a) Download all   j) Export JSON   0) Back
```

- پوشه‌ی خروجی **یک بار در هر نشست** پرسیده می‌شود.
- یک **شماره آهنگ** بزنید تا مستقیم دانلود شود. بعد از هر دانلود، لیست دوباره کشیده می‌شود، پس می‌توانید چند آهنگ پشت‌سرهم بگیرید.
- **`a`** — همه را دانلود کن، با پیشرفت هر فایل و خلاصه‌ی نهایی.
- **`j`** — متادیتای خام `getUserProfileAudios` را در یک فایل JSON ذخیره می‌کند.
- از همان نوار پیشرفت درجای بقیه‌ی برنامه استفاده می‌کند.

### 🛠 مدیریت پیام

ویرایش · حذف (تکی **یا** بازه‌ای) · سنجاق · برداشتن سنجاق · فوروارد · اکشن‌های چت

**حذف بازه‌ای** — یک `chat_id` از DB انتخاب کنید و بازه‌ی `from → to` بدهید. flood-control (`429 retry_after`) را رعایت می‌کند و خلاصه‌ی کامل می‌دهد:

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

همه‌ی پیام‌های دریافتی در `tg.db`. **منوی 53**:

1. پاک‌سازی **چت خاص** (از DB)
2. پاک‌سازی **بر اساس نوع چت** (private / group / supergroup / channel)
3. پاک‌سازی **بر اساس بازه‌ی تاریخ** (unix ts)
4. پاک‌سازی **بر اساس بازه‌ی message_id** داخل یک چت
5. **پاک‌سازی یتیم‌ها** — ردیف‌های `entities` / `chat_users` بدون پیام

### 👥 اعضای چت (از DB)

**منوی 48** همه‌ی اعضای شناخته‌شده‌ی یک گروه/سوپرگروه را نشان می‌دهد:

```
--- Members of chat -1001234567890 (12) ---
  1) id=8195921211    Sarina            @Sarina_girl_bot   msgs=42   last=2026-...
  2) id=123456789     Ali Rezaei        @ali_reza          msgs=120  last=2026-...
  d) Delete one   r) Reset all   e) Export JSON   0) Back
```

- `d` — حذف یک کاربر از لیست DB (او را از گروه **بیرون نمی‌کند**)
- `r` — بازنشانی کل لیست
- `e` — خروجی به `members_<chat>_<ts>.json`

> ⚠️ **اعضا فقط از پیام‌های دریافتی جمع‌آوری می‌شوند.** کاربرانی که هرگز پیامی نفرستاده‌اند در لیست نیستند. تلگرام لیست کامل اعضا را به بات‌ها نمی‌دهد.

### 📣 منشن گروهی اعضا

**منوی 49** @-منشن اعضا از DB:

- **همه‌ی اعضا** یا **لیست سفارشی** (`123, @ali, 456` — ترکیبی)
- تقسیم خودکار بر اساس **اندازه‌ی دسته** (پیش‌فرض ۳۰) و **محدودیت کاراکتر** (۳۸۰۰)
- از HTML `<a href="tg://user?id=...">` استفاده می‌کند تا برای کاربران بدون یوزرنیم هم کار کند
- متن سرصفحه‌ی اختیاری، پاسخ اختیاری (با پشتیبانی پاسخ بین‌چتی)
- خلاصه در پایان: تعداد اعضای منشن‌شده / پیام‌های ارسالی / خطاها

**Web UI** همین را از طریق `POST /api/chats/<id>/mention` ارائه می‌دهد.

### 🧭 قفل chat_id

**تنظیمات → Lock / Unlock chat_id** (منوی 54 → 5) یک `chat_id` را سراسری پین می‌کند:

- هر پرامپتی که `chat_id` می‌خواهد بی‌صدا از مقدار قفل استفاده می‌کند.
- قفل فعلی در بالای منوی اصلی: `Locked chat_id: -1001   Guest: OFF   API: OFF`
- دستی قفل کنید، از DB انتخاب کنید، یا پاک کنید.

### 👻 حالت Guest در مانیتور

**تنظیمات → Toggle guest chat mode** (منوی 54 → 6) مانیتور را به فیلتر **فقط guest-chat** تغییر می‌دهد. فقط پیام‌هایی که از طریق business connection / guest bot می‌آیند (تشخیص با `business_connection_id`، `sender_business_bot`، `via_bot`، `sender_boost_count`) نمایش داده می‌شوند. وضعیت در هدر: `Guest: ON` / `Guest: OFF`.

### 📡 تشخیص منشن/پاسخ در Silent Fetch

وقتی یک `Silent fetch` تمام می‌شود، `termgram` همه‌ی پیام‌ها را برای این‌ها اسکن می‌کند:

- **@-منشن‌های ربات** (از entityها یا `@username`)
- **پاسخ‌ها به پیام‌های خود ربات**

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

انتخاب `y` هر پیام را باز می‌کند و اجازه‌ی پاسخ درجا می‌دهد. **Web UI** این‌ها را در `mention_flags` ذخیره می‌کند و یک بج **Unseen mentions** نشان می‌دهد.

### 🤖 حالت مدیریت ربات (رجیستری محلی)

**منوی 51** یک رجیستری محلی:

- لیست هر ربات مدیریت‌شده با id، username، `added_at`، `last_seen_at`
- مشاهده‌ی توکن ذخیره‌شده
- مشاهده / بررسی مجوزها
- حذف ردیف یک ربات (و مجوزهایش)
- **افزودن ربات جدید** — یک deeplink قابل اشتراک تولید می‌کند

### 🆕 Managed Bots (Bot API 9.6+)

`termgram` از قابلیت **Managed Bots** تلگرام پشتیبانی می‌کند. رباتی با `can_manage_bots: true` (فعال‌شده از طریق **Bot Management Mode** در `@BotFather`) می‌تواند ربات‌های دیگر بسازد و مدیریت کند — **بدون نیاز به باز کردن `@BotFather`**.

**چطور کار می‌کند**

1. **منوی 52) Managed bot link** — یا **51 → a** — یک لینک قابل اشتراک تولید می‌کند:
   ```
   https://t.me/newbot/<manager_bot_username>/<suggested_username>?name=<suggested_display_name>
   ```
   ساخته‌شده **به‌صورت محلی** با `urllib.parse.quote`.

2. لینک را برای کاربر بفرستید. در اپ تلگرام باز می‌کند، تأیید می‌کند، ربات جدید زیر ربات مدیر شما ساخته می‌شود.

3. تلگرام `updateManagedBot` برای ربات مدیر می‌فرستد. `termgram` آن را در **هر چهار حلقه‌ی دریافت** پردازش می‌کند و به‌طور خودکار:
   - id، username، name، و owner را چاپ می‌کند
   - `getManagedBotToken` را صدا می‌زند تا توکن را بگیرد
   - ربات را در `managed_bots` ذخیره می‌کند

4. مدیریت از **منوی 51 → انتخاب ربات**:
   - **`getManagedBotToken`** — دریافت/به‌روزرسانی توکن
   - **`replaceManagedBotToken`** — چرخش توکن
   - **`bots.getAccessSettings`** / **`bots.editAccessSettings`** — مشاهده یا تغییر مجوزها
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
| `updateManagedBot` | نوع آپدیت دریافتی |

> 💡 **توجه:** `bots.createBot` یک متد MTProto است و **هرگز** مستقیماً توسط `termgram` فراخوانی نمی‌شود. ساخت ربات همیشه **سمت کلاینت** اتفاق می‌افتد وقتی کاربر deeplink را باز می‌کند.

> ⚠️ **پیش‌نیاز:** **Bot Management Mode** را در `@BotFather` فعال کنید.

### 🛰 API Server (بریج / پروکسی)

**تنظیمات → API server** (منوی **54 → 7**) یک HTTP server خودکفا راه می‌اندازد که مثل `api.telegram.org` رفتار می‌کند:

- روی `api_server_host:api_server_port` گوش می‌دهد (پیش‌فرض `127.0.0.1:8080`)
- فراخوانی‌های Bot API را در `/bot<token>/<method>` و دانلود فایل را در `/file/bot<token>/<file_path>` می‌پذیرد
- از `api_server_token` استفاده می‌کند، یا به توکن ربات برمی‌گردد
- هر درخواست را به Bot API بالادست فوروارد می‌کند (از طریق `PROXY` / `HTTPS_PROXY`)
- **آپلودهای multipart خام forward می‌شوند** — `sendDocument`، `sendPhoto`، `sendVideo`، `sendAudio`، `sendVoice`، `sendAnimation`، `sendSticker`، `sendVideoNote` همگی از پراکسی بدون خرابی کار می‌کنند.
- **دانلود فایل کار می‌کند** — `getFile` یک `file_path` برمی‌گرداند که از `http://host:port/file/bot<token>/<file_path>` قابل دریافت است (streamed).
- **هر پاسخ `getUpdates` را** در `tg.db` ذخیره می‌کند (پیام‌ها، ویرایش‌ها، فایل‌ها، واکنش‌ها، entityها، mention flagها) **قبل از** بازگشت به فراخواننده. `state.offset` را هم جلو می‌برد تا اجرای بعدی Monitor / Silent fetch همان آپدیت‌ها را دوباره پردازش نکند.
- **هر پاسخی که شامل یک Message باشد** (`sendMessage`، `editMessageText`، `forwardMessage`) را در `tg.db` ذخیره می‌کند، تا پیام‌هایی که از پراکسی فرستاده شده‌اند در Web UI دیده شوند.
- به **قفل انحصاری `getUpdates`** احترام می‌گذارد — اگر Monitor یا پولر Web UI فعال باشد، `getUpdates` از پراکسی `503` با نام owner و PID صاحب قفل برمی‌گرداند.
- بی‌خطر برای اجرا در پس‌زمینه؛ اگر `api_server_enabled` برابر `true` باشد، هنگام راه‌اندازی خودکار فعال می‌شود.

### 🌐 Web UI (کلاینت مرورگری)

کلاینت مرورگری کامل زیر `web-ui/`:

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

- **نوار کنار** — همه‌ی چت‌ها با بج منشن‌های خوانده‌نشده
- **نمایش پیام** — حباب‌ها، پیش‌نمایش پاسخ، فوروارد از، بج مدیر فرستنده، واکنش‌های درون‌خطی
- **ارسال** — متن، واکنش، فوروارد، آپلود
- **منشن‌ها** — منشن گروهی با همان منطق HTML `tg://user`
- **مدیای ذخیره‌شده** — ذخیره/ستاره/ارسال استیکر و انیمیشن
- **اطلاعات چت** — `getChat` زنده + شمارش اعضا + لیست مدیران
- **جست‌وجوی اعضا** — `chat_users` کش‌شده
- **واکنش‌ها** — مرتب بر اساس استفاده (`reaction_usage`)
- **آواتارها** — کش زیر `cache/avatars/` و `cache/chat_avatars/`
- **کش فایل** — زیر `cache/files/` با سقف دیسک
- **پولر (اختیاری)** — کلید **Sync & auto-refresh** یک thread پس‌زمینه راه می‌اندازد

**امنیت**

- همه‌ی endpointهای تغییردهنده‌ی وضعیت (`POST`) نیازمند `X-CSRF-Token`
- ورود محدود به نرخ (۵ تلاش/دقیقه/IP)
- کوکی نشست `HttpOnly; SameSite=Strict`
- `--https-cert` و `--https-key` برای HTTPS

**مسیرها**

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

Monitor mode توسط **قفل انحصاری `getUpdates`** محافظت می‌شود — دو کامپوننت نمی‌توانند همزمان poll کنند.

### 💾 پایگاه داده‌ی محلی (SQLite)

Silent fetch · کاوشگر چت · نمایش‌گر تاریخچه · پاک‌سازی / پاکسازی — هر پیام دریافتی در `tg.db`.

جدول‌ها: `messages`، `message_files`، `message_edits`، `message_reactions`، `entities`، `chat_users`، `chat_admins`، `chat_photos`، `user_photos`، `mention_flags`، `saved_media`، `reaction_usage`، `file_cache`، `web_sessions`، `managed_bots`، `bot_permissions`، `state`.

### 🌐 پشتیبانی پروکسی

`socks5://` و `http://` — از طریق `config.json`، از **تنظیمات → Configure proxy** (منوی 54 → 1)، و **همچنین** به‌طور خودکار توسط API Server و دانلود فایل‌های Web UI.

### ⚙️ منوی Settings یکپارچه

همه‌ی تنظیمات غیر-پیامی زیر **منوی 54) Settings & Config**:

```
--- Settings & Config ---
--- Network --------------------------------------
   1) Configure proxy / retry    2) Set Base URL
--- Bot ------------------------------------------
   3) Manage bot token           4) Manage reactions
--- Chat Behavior --------------------------------
   5) Lock / Unlock chat_id      6) Toggle guest chat mode
--- Server ---------------------------------------
   7) API server

   0) Back to main menu
```

از **همان رندر ریسپانسیو و انیمیشن منوی اصلی** استفاده می‌کند. Enter روی پرامپت خالی آن را بازنویسی می‌کند؛ بعد از هر اقدام با `Press Enter to return...` توقف می‌کند.

### 🎨 بنر نسخه

هنگام راه‌اندازی تعاملی:

```
╔════════════════════════════════════════════════════╗
║  📡 termgram  v1.4.0                              ║
║  Terminal client for Telegram bots                 ║
╚════════════════════════════════════════════════════╝
```

در **حالت CLI** بنر به یک خط کوتاه تبدیل می‌شود:

```
termgram v1.4.0
```

---

## 📋 پیش‌نیازها

- **Python 3.10+** (تست‌شده روی 3.14.x)
- `requests`
- `PySocks`

اختیاری (برای HTTPS روی Web UI): `ssl` — در CPython تعبیه شده؛ فقط `--https-cert` و `--https-key` را بدهید.

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

همه‌ی پیکربندی — توکن ربات، پروکسی، Base URL سفارشی، تنظیمات API Server، فلگ guest-mode، قفل chat_id، واکنش‌های سفارشی، و سرعت انیمیشن منو — در `config.json`. از قالب بسازید:

```bash
cp config.json.example config.json
```

یا `termgram` را مستقیم اجرا کنید — به‌طور خودکار `config.json` و `tg.db` را می‌سازد و از شما توکن می‌خواهد.

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
  "menu_speed": "fast",
  "reactions": [
    { "emoji": "👍", "label": "Thumbs Up" },
    { "emoji": "👎", "label": "Thumbs Down" },
    { "emoji": "❤️", "label": "Red Heart" },
    { "emoji": "🔥", "label": "Fire" }
  ]
}
```

1. **توکن ربات** — از [@BotFather](https://t.me/BotFather). برای **Managed Bots**، **Bot Management Mode** را فعال کنید.
2. **پروکسی (اختیاری)** — `socks5://`، `http://`، `https://`. `""` = مستقیم.
3. **واکنش‌ها** — از **تنظیمات → Manage reactions** (منوی 54 → 4).
4. **`base_url`** (اختیاری) — URL ریشه‌ی سفارشی.
5. **`api_server_*`** (اختیاری) — بریج داخلی.
6. **`guest_chat_mode`** (اختیاری) — محدود کردن مانیتور به guest.
7. **`locked_chat_id`** (اختیاری) — پین یک chat ID بی‌صدا.
8. **`menu_speed`** (اختیاری) — `off` / `fast` / `normal` / `slow`.

> 💡 **مهاجرت خودکار**: اگر از نسخه‌ی قدیمی‌تر ارتقا می‌دهید، `termgram` به‌طور خودکار `token.txt`، `proxy.txt` و `reactions.txt` را می‌خواند، تنظیماتشان را منتقل می‌کند و فایل‌های قدیمی را پاک می‌کند.

---

## ▶️ استفاده

### TUI تعاملی

```bash
python3 termgram.py
```

```
╔════════════════════════════════════════════════════╗
║  📡 termgram  v1.4.0                              ║
║  Terminal client for Telegram bots                 ║
╚════════════════════════════════════════════════════╝
Connecting to Telegram API...
✔ Bot connected: @YourBot (My Bot)

=============== Telegram Bot Sender ===============
  Locked chat_id: (none)   Guest: OFF   API: OFF

--- Send Messages ---------------------------------
   1) Text message              2) Photo
   3) Animation (GIF)           4) Video
   5) Document / File           6) Audio
   7) Voice                     8) Video note
   9) Sticker                  10) Location
  11) Contact                  12) Poll
  13) Dice                     14) Reaction
  15) Edit message             16) Delete message
--- Chat Management -------------------------------
  17) Leave chat               18) Get chat info
  19) Member count             20) Pin message
  21) Unpin message            22) Forward message
  23) Chat action              24) Ban user
  25) Unban user               26) Set chat title
  27) Set chat desc            28) Set admin title
  29) Set bot name             30) Create invite link
--- Bot Profile -----------------------------------
  31) Bot info (getMe)         32) Set bio (desc)
  33) Set short bio            34) Set profile photo
  35) Remove photo             36) Get current profile
--- Files -----------------------------------------
  37) Download by id           38) Upload & get id
--- Monitor & Data --------------------------------
  39) Monitor mode             40) Silent fetch
  41) Chat explorer            42) History viewer
--- Admin & Members -------------------------------
  43) Member info              44) Promote admin
  45) Demote admin             46) Set user title
  47) Set member tag           48) Chat members (DB)
  49) Mention members          50) User account info
--- Bot Management --------------------------------
  51) Bot management           52) Managed bot link
  53) Purge DB data
--- Settings --------------------------------------
  54) Settings & Config

   0) Exit
choice:
```

منو **کاملاً ریسپانسیو** است — اگر ترمینال شما به‌اندازه‌ی کافی عریض باشد، ستون‌ها از ۲ به ۵ به‌طور خودکار گسترش می‌یابند. با Enter روی پرامپت خالی، منو دوباره بارگذاری می‌شود.

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

Press Enter to return to main menu...
```

#### مثال: دانلود آهنگ‌های پروفایل

```
choice: 60

--- User Profile Audios ---
user_id (numeric): 123456789
>> getUserProfileAudios ...
output dir [default: .]: ./songs

--- 3 profile audio(s) ---
    1) 🎵 Love Story — Taylor Swift
         duration=235s  size=3520123B
    2) 🎵 Blinding Lights — The Weeknd
         duration=200s  size=2988771B
    3) 🎵 Shape of You — Ed Sheeran
         duration=233s  size=3412345B

  type a number to download that song
  a) Download all   j) Export JSON   0) Back
choice: 2

⬇  The Weeknd - Blinding Lights.mp3  (2.9MB)
⬇ [████████████████████████████████████] 100.0%  2.9MB/2.9MB  512.3KB/s ETA 0s
✔ saved: ./songs/The Weeknd - Blinding Lights.mp3  (2918.7 KB)

--- 3 profile audio(s) ---
  ...
choice: 0
```

---

### حالت CLI

هر آرگومان بعد از نام اسکریپت `termgram` را به حالت غیرتعاملی می‌برد. هر ساب‌کامند یک exit code برمی‌گرداند.

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
  web         start the browser client

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
python3 termgram.py unpin  -1001234567890
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
python3 termgram.py web
python3 termgram.py web --host 0.0.0.0 --port 9090 --password "s3cr3t"
python3 termgram.py web --host 0.0.0.0 --port 443 \
    --https-cert ./cert.pem --https-key ./key.pem \
    --password "s3cr3t"
python3 termgram.py web --no-poller
```

##### منابع متن و کپشن

| ساب‌کامند | شکل درون‌خطی | شکل فایل |
|-----------|-------------|-----------|
| `text` | `text` موقعیتی | `--text-file F` |
| `edit` | `text` موقعیتی | `--text-file F` |
| `reply` | `text` موقعیتی | `--text-file F` |
| `set-bio` | `description` موقعیتی | `--bio-file F` |
| `set-short-bio` | `description` موقعیتی | `--bio-file F` |

ساب‌کامندهای فایل‌محور دو گزینه‌ی متقابلاً انحصاری برای کپشن دارند:

| گزینه | معنی |
|-------|------|
| `--caption TEXT` | رشته‌ی کپشن درون‌خطی |
| `--caption-file F` | خواندن کپشن از فایل `F` (UTF-8، چندخطی امن) |

اگر هر دو داده شوند، `--caption-file` اولویت دارد.

##### کدهای خروج

| کد | معنی |
|----|------|
| `0` | موفق |
| `1` | تلگرام خطا برگرداند |
| `2` | خطای استفاده/فایل محلی |

---

### Web UI (کلاینت مرورگری)

```bash
python3 termgram.py web --host 127.0.0.1 --port 8081 --password "your-secret"
```

سپس **http://127.0.0.1:8081/** را باز کنید و وارد شوید.

| فلگ | پیش‌فرض | کاربرد |
|-----|---------|--------|
| `--host` | `127.0.0.1` | آدرس bind |
| `--port` | `8081` | پورت TCP |
| `--password` | توکن ربات | رمز ورود |
| `--session-ttl` | `86400` | طول عمر نشست به ثانیه |
| `--cache-max-mb` | `512` | حداکثر کش دیسک |
| `--https-cert` / `--https-key` | — | گواهی PEM + کلید برای HTTPS |
| `--no-poller` | خاموش | پولر پس‌زمینه را راه‌اندازی نکن |

**Web UI نیازمند وجود پوشه‌ی `web-ui/`** (شامل `index.html`، `app.js`، `style.css`، `favicon.svg`) در کنار `termgram.py` است.

---

## 🖥 نکات پلتفرم

- ✅ **لینوکس / مک**: کاملاً پشتیبانی می‌شود.
- ⚠️ **ویندوز**: کاراکترهای فارسی ممکن است در ترمینال پیش‌فرض درست رندر نشوند. از **Windows Terminal** با فونتی که RTL را پشتیبانی می‌کند (مثل *Cascadia Code*، *Vazirmatn*) استفاده کنید یا داخل **WSL** اجرا کنید. Web UI تحت تأثیر نیست.

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
| `.getupdates.lock` | قفل cross-process getUpdates | ❌ (gitignored) |

---

## 🤝 مشارکت

مشارکت از **همکاران دعوت‌شده** استقبال می‌شود. ابتدا یک issue باز کنید. هنگام تست یک پچ، لطفاً این‌ها را هم بررسی کنید:

- رفتار قفل `getUpdates` بین Monitor / Silent fetch / Web poller / API Server
- آپلود فایل multipart از طریق API Server
- دانلود streamed از `/file/bot<token>/<path>`
- منوی ریسپانسیو در عرض‌های مختلف (80، 120، 200 ستون)

---

## 📜 مجوز

[MIT](LICENSE)