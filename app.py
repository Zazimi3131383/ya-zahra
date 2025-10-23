import flask
from flask import (
    Flask,
    render_template_string,
    request,
    redirect,
    send_file,
    session,
    Response,
    send_from_directory,
)
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from functools import wraps
import csv, os, requests
import json
from werkzeug.utils import secure_filename

# --- Konfigurasi Aplikasi ---
app = Flask(__name__)
# برای استفاده از session، حتماً یک کلید امن و مخفی در محیط واقعی تنظیم کنید
app.secret_key = os.environ.get(
    "SECRET_KEY", "a_very_secret_key_that_you_should_change"
)

# --- Konfigurasi Folder Upload ---
# ! بررسی اینکه آیا روی Render با دیسک دائمی اجرا می‌شود یا محلی
# ! اگر روی دیسک دائمی نباشد، فایل‌های آپلودی (uploads) و CSV با ری‌استارت پاک می‌شوند.
DISK_MOUNT_PATH = os.environ.get("RENDER_DISK_MOUNT_PATH")
if DISK_MOUNT_PATH:
    UPLOAD_FOLDER = DISK_MOUNT_PATH
    print(f"--- در حال استفاده از دیسک دائمی Render در مسیر: {UPLOAD_FOLDER} ---")
else:
    UPLOAD_FOLDER = "uploads" # حالت موقت (Ephemeral/Local)
    print(f"--- WARNING: در حال استفاده از پوشه موقت: {UPLOAD_FOLDER}. فایل‌ها با ری‌استارت پاک می‌شوند. ---")

# اطمینان از وجود پوشه در هر دو حالت
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# --- Variabel Global ---
CSV_FILE = "registrations.csv"
ADMIN_USER = "admin"
ADMIN_PASS = "z.azimi3131383"

# ! ستون جدید "فیش واریزی" اضافه شد
PERSIAN_HEADERS = [
    "نام",
    "نام خانوادگی",
    "کد ملی",
    "شماره دانشجویی",
    "نام دانشگاه",
    "نام دانشکده",
    "جنسیت",
    "شماره تلفن",
    "مقطع تحصیلی",
    "رشتهٔ تحصیلی",
    "گواهی",
    "فیش واریزی",  # ستون جدید
]

# شماره کارت شما برای نمایش در صفحه پرداخت
YOUR_CARD_NUMBER = "۶۰۳۷-۹۹۷۷-۹۹۷۷-۹۹۷۷"

# ! نام صاحب کارت: اول از متغیر محیطی بخوان، اگر نبود از مقدار پیش‌فرض استفاده کن
YOUR_CARD_NAME = os.environ.get("YOUR_CARD_NAME", "زهرا پرتوی زیناب")


# ---------------- Authentication -----------------


def check_auth(username, password):
    return username == ADMIN_USER and password == ADMIN_PASS


def authenticate():
    return Response(
        "احراز هویت لازم است",
        401,
        {"WWW-Authenticate": 'Basic realm="Login Required"'},
    )


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)

    return decorated


# ---------------- Telegram Notify (Updated) -----------------
def send_to_telegram(data, receipt_filepath=None):
    """
    ارسال پیام به تلگرام.
    اگر 'receipt_filepath' داده شود، فیش را به عنوان عکس ارسال می‌کند.
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("توکن یا شماره چت تلگرام تنظیم نشده است!")
        return

    # ساخت پیام زیبا با emoji و قالب خوانا
    message = "🎉 **ثبت‌نام جدید کارگاه** 🎉\n\n"
    message += (
        f"👤 نام و نام خانوادگی: {data.get('first_name','')} {data.get('last_name','')}\n"
    )
    message += f"🆔 کد ملی: {data.get('national_code','')}\n"
    message += (
        f"🎓 دانشگاه: {data.get('university','')} - {data.get('faculty','')}\n"
    )
    message += f"📚 مقطع و رشته: {data.get('degree','')} - {data.get('major','')}\n"
    message += f"📞 شماره تماس: {data.get('phone','')}\n"
    message += f"✅ درخواست گواهی: {data.get('certificate','')}\n"

    try:
        # اگر فایل فیش وجود داشت، با sendPhoto ارسال شود
        if receipt_filepath and os.path.exists(receipt_filepath):
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            with open(receipt_filepath, "rb") as photo_file:
                files = {"photo": photo_file}
                payload = {
                    "chat_id": chat_id,
                    "caption": message,
                    "parse_mode": "Markdown",
                }
                resp = requests.post(url, data=payload, files=files)
        # در غیر این صورت، فقط متن ارسال شود
        else:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
            resp = requests.post(url, data=payload)

        # بررسی وضعیت ارسال
        if resp.status_code == 200:
            print("پیام به تلگرام با موفقیت ارسال شد ✅")
        else:
            print("ارسال پیام به تلگرام موفق نبود ❌:", resp.status_code, resp.text)
    except Exception as e:
        print(f"خطا در ارسال به تلگرام: {e}")


# --- توابع ربات تلگرام (بدون تغییر رها شدن) ---
# ... (توابع handle_callback_query و غیره از کد شما در اینجا قرار می‌گیرند)
# ... (این توابع به دلیل اینکه PERSIAN_HEADERS آپدیت شده، فیلد جدید را نشان خواهند داد)
def send_admin_list(chat_id):
    """
    ارسال دکمه کیبورد برای دیدن لیست ثبت‌نام‌ها
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return

    bot = Bot(token=bot_token)

    # خواندن داده‌ها از CSV
    rows = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

    # اگر لیست خالی بود
    if not rows:
        bot.send_message(chat_id=chat_id, text="🚫 هنوز ثبت‌نامی وجود ندارد.")
        return

    # دکمه‌ها: هر ثبت‌نام یک دکمه
    buttons = []
    for idx, row in enumerate(rows):
        text = f"{row.get('نام','')} {row.get('نام خانوادگی','')}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=str(idx))])

    keyboard = InlineKeyboardMarkup(buttons)
    bot.send_message(chat_id=chat_id, text="📋 لیست ثبت‌نامی‌ها:", reply_markup=keyboard)


def send_admin_list_with_keyboard(chat_id):
    if not os.path.exists(CSV_FILE):
        return
    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    for idx, r in enumerate(rows):
        text = f"نام: {r['نام']} {r['نام خانوادگی']}\n"
        text += f"دانشگاه: {r['نام دانشگاه']}\nرشته: {r['رشتهٔ تحصیلی']}\nگواهی: {r['گواهی']}"
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "مشاهده جزئیات", callback_data=f"view_{idx}"
                    ),
                    InlineKeyboardButton("ویرایش", callback_data=f"edit_{idx}"),
                ]
            ]
        )
        url = (
            f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN')}/sendMessage"
        )
        requests.post(
            url,
            data={
                "chat_id": chat_id,
                "text": text,
                "reply_markup": json.dumps(keyboard.to_dict()), # .to_dict() اضافه شد
            },
        )


def handle_callback_query(data, chat_id):
    # data مثل: view_0 یا edit_3
    if not os.path.exists(CSV_FILE):
        return
    if data == "report":
        with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        total = len(rows)
        certified = sum(1 for r in rows if r["گواهی"].startswith("خواهان گواهی"))
        free = total - certified
        text = f"📊 گزارش سریع:\nکل ثبت‌نام‌ها: {total}\nخواهان گواهی: {certified}\nرایگان: {free}"
        url = (
            f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN')}/sendMessage"
        )
        requests.post(url, data={"chat_id": chat_id, "text": text})
        return

    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    action, idx_str = data.split("_")
    idx = int(idx_str)
    if idx >= len(rows):
        return
    
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return

    if action == "view":
        r = rows[idx]
        # ستون جدید فیش واریزی به طور خودکار نمایش داده می‌شود
        text = "\n".join([f"{h}: {r.get(h, '')}" for h in PERSIAN_HEADERS])
    elif action == "edit":
        r = rows[idx]
        text = f"برای ویرایش این رکورد لطفاً به پنل وب مراجعه کنید:\n{r['نام']} {r['نام خانوادگی']}"
    else:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})

def handle_callback(update, context):
    query = update.callback_query
    idx = int(query.data)
    with open(CSV_FILE, 'r', newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    
    if 0 <= idx < len(rows):
        row = rows[idx]
        # متن جزئیات ثبت‌نام (فیلد جدید خودکار اضافه می‌شود)
        message = "📌 جزئیات ثبت‌نام:\n"
        for key in PERSIAN_HEADERS:
            message += f"{key}: {row.get(key,'')}\n"
        query.answer()
        query.edit_message_text(message)
    else:
        query.answer("خطا: رکورد یافت نشد.")


# ---------------- Save to CSV (Updated) -----------------
def save_to_csv(final_dict):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=PERSIAN_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "نام": final_dict.get("first_name", ""),
                "نام خانوادگی": final_dict.get("last_name", ""),
                "کد ملی": final_dict.get("national_code", ""),
                "شماره دانشجویی": final_dict.get("student_number", ""),
                "نام دانشگاه": final_dict.get("university", ""),
                "نام دانشکده": final_dict.get("faculty", ""),
                "جنسیت": final_dict.get("gender", ""),
                "شماره تلفن": final_dict.get("phone", ""),
                "مقطع تحصیلی": final_dict.get("degree", ""),
                "رشتهٔ تحصیلی": final_dict.get("major", ""),
                "گواهی": final_dict.get("certificate", ""),
                "فیش واریزی": final_dict.get(
                    "receipt_file", ""
                ),  # ذخیره نام فایل
            }
        )


# ---------------- HTML Templates -----------------

rules_html = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>ثبت‌نام کارگاه</title>
<style>
body { margin: 0; font-family: 'Vazir', sans-serif; background: linear-gradient(135deg,#1e3c72,#2a5298); color: #fff; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
.card { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 20px; padding: 2rem; max-width: 480px; width: 90%; box-shadow: 0 8px 20px rgba(0,0,0,0.2); transition: transform 0.3s ease, box-shadow 0.3s ease; }
.card:hover { transform: scale(1.02); box-shadow: 0 10px 25px rgba(0,0,0,0.3); }
h1 { text-align: center; font-size: 1.3rem; margin-bottom: 1rem; color: #ffdf5d; line-height: 1.8; }
ul { list-style-type: disc; padding-right: 20px; font-size: 0.95rem; line-height: 1.8; }
button { display: block; margin: 1.5rem auto 0; background: linear-gradient(90deg,#ffdf5d,#ffb84d); color: #000; border: none; border-radius: 10px; padding: 0.7rem 1.5rem; font-size: 1rem; cursor: pointer; transition: all 0.3s ease; }
button:hover { background: linear-gradient(90deg,#ffd633,#ffa31a); transform: scale(1.05); }
</style>
</head>
<body>
<div class="card">
  <h1>با سلام<br>لطفا نکات زیر را به دقت مطالعه فرمایید.</h1>
  <ul>
    <li>1_ حضور در جلسات به عنوان مستمع آزاد بدون درخواست صدور گواهی، رایگان است.</li>
    <li>2_ هزینه واریزی برای صدور گواهی به هیچ عنوان عودت داده نمی‌شود.</li>
    <li>3_ از مخاطبان گرامی درخواست می‌شود در صورت تمایل به صدور گواهی، پس از ثبت اطلاعات و واریز هزینه، عکس فیش آن را ذخیره کرده تا در سامانه بارگذاری کنید.</li>
  </ul>
  <form action="/start_form" method="POST">
    <button type="submit">تأیید و ادامه</button>
  </form>
</div>
</body>
</html>
"""

form_html = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>فرم ثبت نام</title>
<style>
body { margin:0; font-family:'Vazir',sans-serif; background:linear-gradient(135deg,#1e3c72,#2a5298); color:#fff; display:flex; justify-content:center; align-items:center; min-height:100vh; }
.card { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius:20px; padding:2rem; max-width:480px; width:90%; box-shadow:0 8px 20px rgba(0,0,0,0.2); }
h1 { text-align:center; font-size:1.3rem; margin-bottom:1rem; color:#ffdf5d; }
label { display:block; margin-bottom:0.3rem; }
input, select { width:100%; padding:0.5rem; border-radius:8px; border:none; margin-bottom:1rem; box-sizing: border-box; }
button { display:block; width:100%; background:linear-gradient(90deg,#ffdf5d,#ffb84d); color:#000; border:none; border-radius:10px; padding:0.7rem; cursor:pointer; transition:all 0.3s ease; }
button:hover { background:linear-gradient(90deg,#ffd633,#ffa31a); transform:scale(1.05); }
</style>
</head>
<body>
<div class="card">
<h1>فرم ثبت نام کارگاه</h1>
<form method="POST" action="/form">
  <label>نام:</label><input type="text" name="first_name" required>
  <label>نام خانوادگی:</label><input type="text" name="last_name" required>
  <label>کد ملی:</label><input type="text" name="national_code" pattern="[0-9۰-۹]{10}" inputmode="numeric" required>
  <label>شماره دانشجویی:</label><input type="text" name="student_number" pattern="[0-9۰-۹]+" inputmode="numeric" required>
  <label>نام دانشگاه:</label><input type="text" name="university" required>
  <label>نام دانشکده:</label><input type="text" name="faculty" required>
  <label>جنسیت:</label>
  <select name="gender" required>
    <option value="">انتخاب کنید</option>
    <option value="مرد">مرد</option>
    <option value="زن">زن</option>
  </select>
  <label>شماره تلفن:</label><input type="text" name="phone" pattern="[0-9۰-۹]+" inputmode="numeric" required>
  <label>مقطع تحصیلی:</label>
  <select name="degree" required>
    <option value="">انتخاب کنید</option>
    <option value="کارشناسی">کارشناسی</option>
    <option value="کارشناسی ارشد">کارشناسی ارشد</option>
    <option value="دکتری">دکتری</option>
    <option value="دیگر">دیگر</option>
  </select>
  <label>رشته تحصیلی:</label><input type="text" name="major" required>
  <button type="submit">ثبت و ادامه</button>
</form>
</div>
</body>
</html>
"""

certificate_html = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>درخواست گواهی</title>
<style>
body { margin:0; font-family:'Vazir',sans-serif; background:linear-gradient(135deg,#1e3c72,#2a5298); color:#fff; display:flex; justify-content:center; align-items:center; min-height:100vh; }
.card { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius:20px; padding:2rem; max-width:480px; width:90%; box-shadow:0 8px 20px rgba(0,0,0,0.2); }
h1 { text-align:center; font-size:1.3rem; margin-bottom:1rem; color:#ffdf5d; }
button { display:block; width:100%; margin-top: 1rem; background:linear-gradient(90deg,#ffdf5d,#ffb84d); color:#000; border:none; border-radius:10px; padding:0.7rem; cursor:pointer; transition:all 0.3s ease; }
button:hover { background:linear-gradient(90deg,#ffd633,#ffa31a); transform:scale(1.05); }
.alert { margin-top:1rem; padding:0.5rem; border-radius:10px; }
</style>
</head>
<body>
<div class="card">
<h1>درخواست گواهی</h1>
<form method="POST" action="/certificate">
  <div>
    <input type="radio" name="certificate" value="خواهان گواهی هستم (50 هزار تومان)" id="certYes" required>
    <label for="certYes">خواهان گواهی هستم (50 هزار تومان)</label>
  </div>
  <div>
    <input type="radio" name="certificate" value="خواهان گواهی نیستم (رایگان)" id="certNo" required>
    <label for="certNo">خواهان گواهی نیستم (رایگان)</label>
  </div>
  <div id="paymentInfo" class="alert" style="display:none; background:rgba(255,255,255,0.2); color:#fff;">
    پس از انتخاب گواهی، به صفحه بارگذاری فیش هدایت خواهید شد.
  </div>
  <button type="submit">ثبت و ادامه</button>
</form>
</div>
<script>
const yes = document.getElementById('certYes');
const no = document.getElementById('certNo');
yes.addEventListener('change',()=>document.getElementById('paymentInfo').style.display='block');
no.addEventListener('change',()=>document.getElementById('paymentInfo').style.display='none');
</script>
</body>
</html>
"""

# --- ! صفحه جدید برای پرداخت و آپلود ---
payment_upload_html = f"""
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>پرداخت و آپلود فیش</title>
<style>
body {{ margin:0; font-family:'Vazir',sans-serif; background:linear-gradient(135deg,#1e3c72,#2a5298); color:#fff; display:flex; justify-content:center; align-items:center; min-height:100vh; }}
.card {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius:20px; padding:2rem; max-width:480px; width:90%; box-shadow:0 8px 20px rgba(0,0,0,0.2); }}
h1 {{ text-align:center; font-size:1.3rem; margin-bottom:1rem; color:#ffdf5d; }}
p {{ text-align:center; }}
.card-number-box {{
    background: rgba(255,255,255,0.2);
    border-radius: 10px;
    padding: 1rem;
    text-align: center;
    font-size: 1.2rem;
    letter-spacing: 2px;
    cursor: pointer;
    margin-bottom: 1rem;
    transition: all 0.3s ease;
}}
.card-number-box:hover {{ background: rgba(255,255,255,0.3); }}

/* ! استایل برای نام صاحب کارت */
.card-name {{
    font-size: 0.9rem;
    letter-spacing: 0px;
    margin-top: 0.5rem;
    color: #fff;
    opacity: 0.9;
}}

#copyMessage {{ text-align:center; color:#ffdf5d; font-size:0.9rem; visibility:hidden; }}
label {{ display:block; margin: 1rem 0 0.3rem; }}
input[type="file"] {{ 
    width: 100%; 
    padding: 0.5rem; 
    border-radius: 8px; 
    border: none; 
    box-sizing: border-box;
    background: rgba(255,255,255,0.8);
    color: #000;
}}
button {{ display:block; width:100%; margin-top: 1.5rem; background:linear-gradient(90deg,#ffdf5d,#ffb84d); color:#000; border:none; border-radius:10px; padding:0.7rem; cursor:pointer; transition:all 0.3s ease; }}
button:hover {{ background:linear-gradient(90deg,#ffd633,#ffa31a); transform:scale(1.05); }}
</style>
</head>
<body>
<div class="card">
<h1>پرداخت و بارگذاری فیش</h1>
<p>لطفاً مبلغ ۵۰ هزار تومان را به شماره کارت زیر واریز نمایید:</p>
<div id="cardNumber" class="card-number-box" onclick="copyCardNumber()">
    {YOUR_CARD_NUMBER}
    <div class="card-name">به نام: {YOUR_CARD_NAME}</div> <!-- ! نام صاحب کارت اضافه شد -->
</div>
<p id="copyMessage">شماره کارت کپی شد!</p>
<p>سپس، تصویر فیش واریزی خود را بارگذاری کنید.</p>
<!-- فرم آپلود باید enctype="multipart/form-data" داشته باشد -->
<form method="POST" action="/payment_upload" enctype="multipart/form-data">
    <label for="receipt">تصویر فیش واریزی:</label>
    <input type="file" id="receipt" name="receipt_file" accept="image/*" required>
    <button type="submit">ثبت نهایی و ارسال فیش</button>
</form>
</div>
<script>
function copyCardNumber() {{
    const cardNumber = "{YOUR_CARD_NUMBER.replace(/-/g, '')}"; // حذف خط تیره برای کپی
    navigator.clipboard.writeText(cardNumber).then(() => {{
        const msg = document.getElementById('copyMessage');
        msg.style.visibility = 'visible';
        setTimeout(() => {{ msg.style.visibility = 'hidden'; }}, 2000);
    }}, (err) => {{
        console.error('خطا در کپی: ', err);
    }});
}}
</script>
</body>
</html>
"""

thanks_html = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>تشکر</title>
<style>
body { margin:0; font-family:'Vazir',sans-serif; background:linear-gradient(135deg,#1e3c72,#2a5298); color:#fff; display:flex; justify-content:center; align-items:center; min-height:100vh; }
.card { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius:20px; padding:2rem; max-width:480px; width:90%; box-shadow:0 8px 20px rgba(0,0,0,0.2); text-align:center; }
h1 { font-size:1.4rem; color:#ffdf5d; margin-bottom:1rem; }
p { font-size: 1.1rem; }
a.btn { display:inline-block; margin-top:1rem; background:linear-gradient(90deg,#ffdf5d,#ffb84d); color:#000; border:none; border-radius:10px; padding:0.5rem 1rem; text-decoration:none; transition:all 0.3s ease; }
a.btn:hover { background:linear-gradient(90deg,#ffd633,#ffa31a); transform:scale(1.05); }
</style>
</head>
<body>
<div class="card">
<h1>ثبت‌نام شما با موفقیت انجام شد!</h1>
<p>لطفاً کانال زیر را دنبال کنید:</p>
<a href="https://t.me/article_workshop1" class="btn" target="_blank">کانال تلگرام کارگاه</a>
</div>
</body>
</html>
"""

# --- ! پنل ادمین آپدیت شد ---
admin_html = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>پنل ادمین</title>
<!-- استفاده از CDN های معتبر برای Bootstrap و DataTables -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.datatables.net/2.0.8/css/dataTables.bootstrap5.min.css" rel="stylesheet">
<style>
body { 
    margin:0; 
    font-family:'Vazir', sans-serif; 
    background:linear-gradient(135deg,#1e3c72,#2a5298); 
    color:#fff; 
    padding-top: 40px; 
    padding-bottom: 40px;
    min-height: 100vh;
}
.card { 
    background: rgba(255,255,255,0.95); 
    backdrop-filter: blur(10px); 
    border-radius:20px; 
    padding:2rem; 
    max-width: 1200px; /* افزایش عرض برای جدول */
    width: 95%; 
    margin: auto;
    box-shadow:0 8px 20px rgba(0,0,0,0.2); 
    color: #333; /* رنگ متن داخل کارت تیره شد */
}
h3 { text-align:center; margin-bottom:1.5rem; color:#1e3c72; } /* رنگ عنوان تیره شد */

/* استایل دکمه‌های دانلود */
.btn-download {
    background: linear-gradient(90deg,#ffdf5d,#ffb84d); 
    color:#000; 
    border:none; 
    border-radius:10px; 
    padding:0.5rem 1rem; 
    text-decoration:none; 
    transition: all 0.3s ease;
    margin-bottom: 1rem;
    display: inline-block;
}
.btn-download:hover { 
    background: linear-gradient(90deg,#ffd633,#ffa31a); 
    transform:scale(1.05); 
    color: #000;
}

/* استایل DataTables */
table.dataTable { width: 100% !important; }
table.dataTable th {
    background-color: #f8f9fa;
    color: #333;
}
table.dataTable td {
    vertical-align: middle;
    text-align: center;
}
.dataTables_wrapper .dataTables_paginate .paginate_button {
    padding: 0.3rem 0.7rem;
    margin: 0 2px;
}
.dataTables_wrapper .dataTables_filter input {
    border-radius: 8px;
    padding: 0.3rem;
}
/* لینک مشاهده فیش */
a.receipt-link {
    background-color: #0d6efd;
    color: white;
    padding: 0.2rem 0.5rem;
    border-radius: 5px;
    text-decoration: none;
}
a.receipt-link:hover {
    background-color: #0a58ca;
    color: white;
}
</style>
</head>
<body>
<div class="card">
<h3>پنل مدیریت</h3>
<a href="/download_csv" class="btn-download">دانلود کل CSV</a>
<!-- دکمه‌های فیلتر -->
<a href="/download_csv_filtered?certificate=خواهان گواهی هستم (50 هزار تومان)" class="btn-download" style="background: #28a745; color: white;">دانلود CSV (فقط با گواهی)</a>
<a href="/download_csv_filtered?certificate=خواهان گواهی نیستم (رایگان)" class="btn-download" style="background: #dc3545; color: white;">دانلود CSV (فقط رایگان)</a>

<div class="table-responsive mt-3">
<table id="adminTable" class="table table-bordered table-striped" style="width:100%">
<thead>
<tr>
{% for h in headers %}
    <th>{{h}}</th>
{% endfor %}
    <th>اقدامات</th>
</tr>
</thead>
<tbody>
{% for r in rows %}
<tr>
  {% for h in headers %}
    <td>
      <!-- ! اگر ستون 'فیش واریزی' بود و مقداری داشت، لینک بساز -->
      {% if h == 'فیش واریزی' and r[h] %}
        <a href="/uploads/{{ r[h] }}" target="_blank" class="receipt-link">مشاهده فیش</a>
      {% else %}
        {{ r[h] }}
      {% endif %}
    </td>
  {% endfor %}
  <td>
    <a href="/admin_delete/{{loop.index0}}" class="btn btn-danger btn-sm" onclick="return confirm('آیا از حذف این رکورد مطمئن هستید؟');">حذف</a>
    <a href="/admin_edit/{{loop.index0}}" class="btn btn-warning btn-sm">ویرایش</a>
  </td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</div>
<!-- JS در انتهای body -->
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.datatables.net/2.0.8/js/dataTables.min.js"></script>
<script src="https://cdn.datatables.net/2.0.8/js/dataTables.bootstrap5.min.js"></script>
<script>
// اعمال DataTables با زبان فارسی
$(document).ready(() => {
    $('#adminTable').DataTable({
        language: {
            "sEmptyTable":     "هیچ داده‌ای در جدول وجود ندارد",
            "sInfo":           "نمایش _START_ تا _END_ از _TOTAL_ رکورد",
            "sInfoEmpty":      "نمایش ۰ تا ۰ از ۰ رکورد",
            "sInfoFiltered":   "(فیلتر شده از _MAX_ رکورد)",
            "sInfoPostFix":    "",
            "sInfoThousands":  ",",
            "sLengthMenu":     "نمایش _MENU_ رکورد",
            "sLoadingRecords": "در حال بارگزاری...",
            "sProcessing":     "در حال پردازش...",
            "sSearch":         "جستجو:",
            "sZeroRecords":    "رکوردی با این مشخصات یافت نشد",
            "oPaginate": {
                "sFirst":    "ابتدا",
                "sLast":     "انتها",
                "sNext":     "بعدی",
                "sPrevious": "قبلی"
            },
            "oAria": {
                "sSortAscending":  ": فعال سازی مرتب سازی صعودی",
                "sSortDescending": ": فعال سازی مرتب سازی نزولی"
            }
        },
        // فعال کردن اسکرول افقی در صورت نیاز
        "scrollX": true
    });
});
</script>
</body>
</html>
"""


# ---------------- Routes (Updated Flow) -----------------
@app.route("/")
def rules():
    session.clear()
    return render_template_string(rules_html)


@app.route("/start_form", methods=["POST"])
def start_form():
    session["step"] = 1
    return redirect("/form")


@app.route("/form", methods=["GET", "POST"])
def form_page():
    if session.get("step") != 1:
        return redirect("/")

    if request.method == "POST":
        session["form_data"] = request.form.to_dict()
        session["step"] = 2
        return redirect("/certificate")

    return render_template_string(form_html)


@app.route("/certificate", methods=["GET", "POST"])
def certificate():
    if session.get("step") != 2:
        return redirect("/")

    if request.method == "POST":
        data = session.get("form_data", {})
        certificate_choice = request.form.get("certificate", "")
        data["certificate"] = certificate_choice
        
        # ذخیره انتخاب گواهی در سشن برای مرحله بعد
        session["certificate_choice"] = certificate_choice
        
        # اگر رایگان را انتخاب کرد، همینجا ثبت‌نام را تمام کن
        if certificate_choice == "خواهان گواهی نیستم (رایگان)":
            data["receipt_file"] = "" # فیش واریزی ندارد
            save_to_csv(data)
            send_to_telegram(data)  # ارسال به تلگرام (بدون فیش)
            session["step"] = 3
            return redirect("/thanks")
        
        # اگر گواهی خواست، او را به صفحه آپلود بفرست
        elif certificate_choice.startswith("خواهان گواهی هستم"):
            session["step"] = 2.5  # یک مرحله میانی جدید
            return redirect("/payment_upload")

    return render_template_string(certificate_html)

# --- ! روت جدید برای پرداخت و آپلود ---
@app.route("/payment_upload", methods=["GET", "POST"])
def payment_upload():
    # اطمینان از اینکه کاربر از مرحله قبل آمده
    if session.get("step") != 2.5:
        return redirect("/")

    if request.method == "POST":
        # 1. بررسی فایل آپلود شده
        if "receipt_file" not in request.files:
            return "خطا: فایلی انتخاب نشده است.", 400
        
        file = request.files["receipt_file"]
        
        if file.filename == "":
            return "خطا: نام فایل خالی است.", 400

        if file:
            # 2. دریافت اطلاعات کاربر از سشن
            data = session.get("form_data", {})
            data["certificate"] = session.get("certificate_choice")
            
            # 3. ساخت نام فایل امن و یکتا
            # استفاده از کد ملی و شماره دانشجویی برای یکتا سازی نام فایل
            national_code = data.get("national_code", "NA")
            student_num = data.get("student_number", "NA")
            # استفاده از secure_filename برای امنیت
            safe_filename = secure_filename(file.filename)
            filename = f"{national_code}_{student_num}_{safe_filename}"
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            
            # 4. ذخیره فایل در سرور
            file.save(filepath)
            
            # 5. ذخیره نام فایل در دیتابیس (CSV)
            data["receipt_file"] = filename
            save_to_csv(data)
            
            # 6. ارسال به تلگرام همراه با فایل
            send_to_telegram(data, receipt_filepath=filepath)
            
            # 7. انتقال به صفحه تشکر
            session["step"] = 3
            return redirect("/thanks")

    # متد GET: نمایش صفحه آپلود
    return render_template_string(payment_upload_html)


@app.route("/thanks")
def thanks():
    if session.get("step") != 3:
        return redirect("/")
    session.clear()
    return render_template_string(thanks_html)


# --- ! روت جدید برای دسترسی ادمین به فایل‌های آپلود شده ---
@app.route("/uploads/<path:filename>")
@requires_auth  # ! مهم: فقط ادمین به فیش‌ها دسترسی دارد
def uploaded_file(filename):
    try:
        return send_from_directory(
            app.config["UPLOAD_FOLDER"], filename, as_attachment=False # False یعنی در مرورگر نشان بده
        )
    except FileNotFoundError:
        return "فایل یافت نشد.", 404


@app.route("/admin_pannel")
@requires_auth
def admin_pannel():
    headers = PERSIAN_HEADERS
    rows = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    return render_template_string(admin_html, headers=headers, rows=rows)


@app.route("/admin_delete/<int:idx>")
@requires_auth
def admin_delete(idx):
    rows = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
            
        if 0 <= idx < len(rows):
            # ! قبل از حذف ردیف، فایل آپلود شده را هم حذف کنید
            row_to_delete = rows[idx]
            filename = row_to_delete.get("فیش واریزی")
            if filename:
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        print(f"فایل {filename} حذف شد.")
                    except Exception as e:
                        print(f"خطا در حذف فایل {filename}: {e}")

            # حذف ردیف از لیست
            rows.pop(idx)
            
            # بازنویسی فایل CSV
            with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=PERSIAN_HEADERS)
                writer.writeheader()
                writer.writerows(rows)
                
    return redirect("/admin_pannel")


@app.route("/admin_edit/<int:idx>", methods=["GET", "POST"])
@requires_auth
def admin_edit(idx):
    rows = []
    if not os.path.exists(CSV_FILE):
        return redirect("/admin_pannel")

    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    
    if not (0 <= idx < len(rows)):
        return "ایندکس نامعتبر است", 404

    if request.method == "POST":
        for key in PERSIAN_HEADERS:
            # فیلد فیش واریزی قابل ویرایش نیست، فقط نمایش داده می‌شود
            if key != "فیش واریزی":
                rows[idx][key] = request.form.get(key, rows[idx].get(key, ''))
                
        with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=PERSIAN_HEADERS)
            writer.writeheader()
            writer.writerows(rows)
        return redirect("/admin_pannel")

    # نمایش فرم ویرایش
    # استایل ساده برای فرم ویرایش
    form_html_edit = """
    <style>
        body { font-family: Vazir, sans-serif; direction: rtl; padding: 20px; background: #f4f4f4; }
        form { max-width: 600px; margin: auto; padding: 20px; background: #fff; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        div { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }
        button { background: #0d6efd; color: white; padding: 10px 15px; border: none; border-radius: 5px; cursor: pointer; }
        .readonly { background: #eee; }
        .receipt-link { color: #0d6efd; text-decoration: none; }
    </style>
    <form method='POST'>
    """
    row_data = rows[idx]
    for key in PERSIAN_HEADERS:
        form_html_edit += f"<div><label>{key}</label>"
        if key == "فیش واریزی":
            filename = row_data.get(key, "")
            if filename:
                form_html_edit += f"""
                <input name='{key}' value='{filename}' readonly class='readonly'>
                <a href='/uploads/{filename}' target='_blank' class='receipt-link'>مشاهده فیش</a>
                """
            else:
                 form_html_edit += "<input value='(فاقد فیش)' readonly class='readonly'>"
        else:
            form_html_edit += f"<input name='{key}' value='{row_data.get(key, '')}'>"
        form_html_edit += "</div>"
        
    form_html_edit += "<button type='submit'>ذخیره</button></form>"
    return form_html_edit


@app.route("/download_csv")
@requires_auth
def download_csv():
    return send_file(CSV_FILE, as_attachment=True)


@app.route("/download_csv_filtered")
@requires_auth
def download_csv_filtered():
    filter_cert = request.args.get("certificate", "")
    rows = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
            all_rows = list(csv.DictReader(f))
        if filter_cert:
            rows = [r for r in all_rows if r.get("گواهی") == filter_cert]
        else:
            rows = all_rows
            
    # ایجاد CSV موقت
    tmp_file = "filtered.csv"
    if not rows:
         # اگر ردیفی وجود نداشت، یک فایل خالی با هدرها بفرست
         with open(tmp_file,'w',newline='',encoding='utf-8-sig') as f:
             writer = csv.DictWriter(f, fieldnames=PERSIAN_HEADERS)
             writer.writeheader()
    else:
        with open(tmp_file, "w", newline="", encoding="utf-8-sig") as f:
            # هدرها باید از PERSIAN_HEADERS خوانده شوند تا کامل باشند
            writer = csv.DictWriter(f, fieldnames=PERSIAN_HEADERS)
            writer.writeheader()
            writer.writerows(rows)
            
    return send_file(tmp_file, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # debug=True را برای محیط واقعی به False تغییر دهید
    app.run(host="0.0.0.0", port=port, debug=True)
