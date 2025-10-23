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
# ! توجه: در صورتی که از کتابخانه python-telegram-bot استفاده می‌کنید، باید آن را در محیط اجرا تنظیم کنید.
# ! توابع تلگرام شما از طریق HTTP Request (requests) کار می‌کنند که برای Flask کافی است.
# از آنجایی که ممکن است کتابخانه telegram نصب نباشد، از آن در توابعی که فقط به API نیاز دارند استفاده نمی‌کنیم.
try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
except ImportError:
    # تعریف کلاس‌های دامی برای جلوگیری از خطا اگر telegram نصب نباشد
    class InlineKeyboardButton:
        def __init__(self, text, callback_data=None): pass
    class InlineKeyboardMarkup:
        def __init__(self, keyboard): self.keyboard = keyboard
        def to_dict(self): return {'inline_keyboard': self.keyboard}
        
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
    UPLOAD_FOLDER = "uploads"  # حالت موقت (Ephemeral/Local)
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

# ! اصلاح شد: شماره کارت انگلیسی و با خط تیره برای خوانایی بهتر
YOUR_CARD_NUMBER = "6219-8618-7279-5239"

# ! نام صاحب کارت: اول از متغیر محیطی بخوان، اگر نبود از مقدار پیش‌فرض استفاده کن
YOUR_CARD_NAME = os.environ.get("YOUR_CARD_NAME", "زهرا پرتوی زیناب")


# ---------------- Authentication -----------------


def check_auth(username, password):
    """بررسی اعتبار سنجی کاربر ادمین"""
    return username == ADMIN_USER and password == ADMIN_PASS


def authenticate():
    """ساخت پاسخ 401 برای درخواست احراز هویت"""
    return Response(
        "احراز هویت لازم است",
        401,
        {"WWW-Authenticate": 'Basic realm="Login Required"'},
    )


def requires_auth(f):
    """دکوراتور برای اعمال احراز هویت Basic"""
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
    # ! اضافه شدن شماره دانشجویی به پیام تلگرام
    message += f"🔢 شماره دانشجویی: {data.get('student_number','')}\n"
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
# ! این توابع نیاز به راه‌اندازی Webhook تلگرام دارند که خارج از محدوده این فایل است.

def send_admin_list(chat_id):
    """
    ارسال دکمه کیبورد برای دیدن لیست ثبت‌نام‌ها
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return

    # ! در این سورس، از کتابخانه 'telegram' استفاده شده که نیاز به نصب دارد.
    # ! در صورتی که این کتابخانه نصب نباشد، خطای Import خواهید داشت.
    # bot = Bot(token=bot_token)
    
    # برای جلوگیری از خطای ایمپورت در محیط اجرا، فعلا از Bot استفاده نمی‌کنیم و فقط یک پیام ارسال می‌کنیم
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": "برای مشاهده لیست ثبت‌نام‌ها، لطفا از پنل وب ادمین استفاده کنید."})


def send_admin_list_with_keyboard(chat_id):
    """
    ارسال دکمه‌های اینلاین برای مشاهده و ویرایش جزئیات
    """
    if not os.path.exists(CSV_FILE):
        return
    
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return

    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    for idx, r in enumerate(rows):
        text = f"نام: {r['نام']} {r['نام خانوادگی']}\n"
        text += f"دانشگاه: {r['نام دانشگاه']}\nرشته: {r['رشتهٔ تحصیلی']}\nگواهی: {r['گواهی']}"
        
        # استفاده از کلاس‌های دامی برای جلوگیری از خطای ایمپورت
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
        # استفاده از to_dict() برای سازگاری با کلاس دامی و تبدیل به JSON
        requests.post(
            url,
            data={
                "chat_id": chat_id,
                "text": text,
                "reply_markup": json.dumps(keyboard.to_dict()), 
            },
        )


def handle_callback_query(data, chat_id):
    """
    پردازش کوئری‌های Callback تلگرام
    """
    if not os.path.exists(CSV_FILE):
        return
    
    # بخش گزارش
    if data == "report":
        with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        total = len(rows)
        # استفاده از get برای جلوگیری از خطا اگر ستون وجود نداشت
        certified = sum(1 for r in rows if r.get("گواهی", "").startswith("خواهان گواهی"))
        free = total - certified
        text = f"📊 گزارش سریع:\nکل ثبت‌نام‌ها: {total}\nخواهان گواهی: {certified}\nرایگان: {free}"
        url = (
            f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN')}/sendMessage"
        )
        requests.post(url, data={"chat_id": chat_id, "text": text})
        return

    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    # بررسی ساختار داده
    if "_" not in data:
        return
        
    action, idx_str = data.split("_")
    
    try:
        idx = int(idx_str)
    except ValueError:
        return # اگر index عدد نبود

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

# ! تابع handle_callback که از سورس اصلی حذف شده بود و به نظر می‌رسید به
# ! یک فریم‌ورک بالاتر تعلق دارد، برای جلوگیری از خطاهای ناشناخته حذف شد.
# ! اگر به آن نیاز دارید، مطمئن شوید که فریم‌ورک آن (مثل python-telegram-bot) را نصب و تنظیم کرده‌اید.

# ---------------- Save to CSV (Updated) -----------------
def save_to_csv(final_dict):
    """ذخیره یا اضافه کردن یک رکورد جدید به فایل CSV"""
    file_exists = os.path.isfile(CSV_FILE)
    # اضافه کردن encoding='utf-8-sig' برای سازگاری بهتر با نرم‌افزارهای ایرانی و Excel
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

# --- ! صفحه جدید برای پرداخت و آپلود با نوار پیشرفت ---
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
    /* ! شماره کارت به صورت انگلیسی نمایش داده می‌شود */
    direction: ltr; 
    font-family: monospace, sans-serif;
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
    direction: rtl; /* نام فارسی به درستی نمایش داده شود */
    font-family:'Vazir',sans-serif;
    font-size: 0.9rem;
    letter-spacing: 0px;
    margin-top: 0.5rem;
    color: #fff;
    opacity: 0.9;
}}

#copyMessage {{ text-align:center; color:#ffdf5d; font-size:0.9rem; visibility:hidden; }}
#errorMessage {{ text-align:center; color:#ff6b6b; font-size:0.9rem; margin-top: 1rem; display: none; }}

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

/* ! نوار پیشرفت */
#uploadProgress {{
    margin-top: 1.5rem;
}}
#progressContainer {{
    background-color: rgba(255,255,255,0.3); 
    border-radius: 5px; 
    height: 10px;
    overflow: hidden;
}}
#progressBar {{
    width: 0%; 
    height: 100%; 
    border-radius: 5px; 
    background-color: #ffdf5d; 
    transition: width 0.3s ease;
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
<!-- ! فرم با ID برای ارسال AJAX -->
<form id="receiptForm" method="POST" action="/payment_upload" enctype="multipart/form-data">
    <label for="receipt">تصویر فیش واریزی:</label>
    <input type="file" id="receipt" name="receipt_file" accept="image/*" required>
    
    <!-- ! نوار پیشرفت -->
    <div id="uploadProgress" style="display:none; margin-top: 1rem;">
        <p style="text-align: right; margin-bottom: 0.5rem; font-size: 0.9rem;">در حال ارسال فیش... <span id="progressPercent">0%</span></p>
        <div id="progressContainer">
            <div id="progressBar"></div>
        </div>
    </div>
    <p id="errorMessage">خطا در ارسال فیش. لطفاً فایل دیگری را امتحان کنید.</p>

    <button type="submit" id="submitButton">ثبت نهایی و ارسال فیش</button>
</form>
</div>
<script>
function copyCardNumber() {{
    const cardNumber = "{YOUR_CARD_NUMBER.replace('-', '')}"; 
    
    // اگر مرورگر از navigator.clipboard پشتیبانی نکرد، از document.execCommand استفاده کنید.
    if (navigator.clipboard) {{
        navigator.clipboard.writeText(cardNumber).then(() => {{
            const msg = document.getElementById('copyMessage');
            msg.style.visibility = 'visible';
            setTimeout(() => {{ msg.style.visibility = 'hidden'; }}, 2000);
        }}, (err) => {{
            console.error('خطا در کپی (clipboard API): ', err);
            fallbackCopy(cardNumber);
        }});
    }} else {{
        fallbackCopy(cardNumber);
    }}
}}

function fallbackCopy(text) {{
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    try {{
        // استفاده از execCommand برای کپی
        document.execCommand('copy');
        const msg = document.getElementById('copyMessage');
        msg.innerText = 'شماره کارت کپی شد (فال‌بک)!';
        msg.style.visibility = 'visible';
        setTimeout(() => {{ msg.style.visibility = 'hidden'; }}, 2000);
    }} catch (err) {{
        console.error('Fallback copy failed: ', err);
    }}
    document.body.removeChild(textarea);
}}


// ! منطق ارسال AJAX برای نمایش نوار پیشرفت
document.getElementById('receiptForm').addEventListener('submit', function(e) {{
    e.preventDefault(); 
    
    const form = e.target;
    const formData = new FormData(form);
    const submitButton = document.getElementById('submitButton');
    const uploadProgress = document.getElementById('uploadProgress');
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');
    const errorMessage = document.getElementById('errorMessage');

    // مخفی کردن پیام خطا اگر قبلاً نمایش داده شده بود
    errorMessage.style.display = 'none';

    // غیرفعال کردن دکمه و نمایش نوار پیشرفت
    submitButton.disabled = true;
    submitButton.innerText = 'در حال ارسال... لطفا صبر کنید';
    uploadProgress.style.display = 'block';

    const xhr = new XMLHttpRequest();

    // ردیابی پیشرفت آپلود
    xhr.upload.onprogress = function(event) {{
        if (event.lengthComputable) {{
            const percentComplete = (event.loaded / event.total) * 100;
            progressBar.style.width = percentComplete.toFixed(0) + '%';
            progressPercent.innerText = percentComplete.toFixed(0) + '%';
        }}
    }};

    // پاسخ نهایی
    xhr.onload = function() {{
        // پس از اتمام آپلود، نوار را کامل کن
        progressBar.style.width = '100%';
        
        if (xhr.status === 200) {{
            // فرض می‌کنیم در صورت موفقیت (کد 200)، Flask کار ثبت اطلاعات و ارسال تلگرام را انجام داده 
            // و پاسخ 200 نشان دهنده موفقیت و نیاز به ریدایرکت است.
            window.location.href = '/thanks'; 
        }} else {{
            // نمایش خطا در صورت عدم موفقیت
            console.error('Upload failed with status:', xhr.status, xhr.responseText);
            errorMessage.style.display = 'block';
            
            // بازگرداندن دکمه و پنهان کردن نوار پیشرفت
            submitButton.disabled = false;
            submitButton.innerText = 'ثبت نهایی و ارسال فیش';
            uploadProgress.style.display = 'none';
        }}
    }};

    // رسیدگی به خطاهای شبکه
    xhr.onerror = function() {{
        console.error('Network error during upload.');
        errorMessage.style.display = 'block';

        submitButton.disabled = false;
        submitButton.innerText = 'ثبت نهایی و ارسال فیش';
        uploadProgress.style.display = 'none';
    }};

    xhr.open('POST', form.action, true);
    xhr.send(formData);
}});
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
            "sEmptyTable":      "هیچ داده‌ای در جدول وجود ندارد",
            "sInfo":            "نمایش _START_ تا _END_ از _TOTAL_ رکورد",
            "sInfoEmpty":       "نمایش ۰ تا ۰ از ۰ رکورد",
            "sInfoFiltered":    "(فیلتر شده از _MAX_ رکورد)",
            "sInfoPostFix":     "",
            "sInfoThousands":   ",",
            "sLengthMenu":      "نمایش _MENU_ رکورد",
            "sLoadingRecords": "در حال بارگزاری...",
            "sProcessing":      "در حال پردازش...",
            "sSearch":          "جستجو:",
            "sZeroRecords":     "رکوردی با این مشخصات یافت نشد",
            "oPaginate": {
                "sFirst":    "ابتدا",
                "sLast":     "انتها",
                "sNext":     "بعدی",
                "sPrevious": "قبلی"
            },
            "oAria": {
                "sSortAscending":  ": فعال سازی مرتب سازی صعودی",
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

# --- ! قالب HTML برای صفحه ویرایش ادمین (جدید) ---
admin_edit_html = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>ویرایش رکورد (شماره {{ index + 1 }})</title>
<style>
body { margin:0; font-family:'Vazir',sans-serif; background:linear-gradient(135deg,#1e3c72,#2a5298); color:#fff; display:flex; justify-content:center; align-items:center; min-height:100vh; }
.card { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius:20px; padding:2rem; max-width:480px; width:90%; box-shadow:0 8px 20px rgba(0,0,0,0.2); }
h1 { text-align:center; font-size:1.3rem; margin-bottom:1rem; color:#ffdf5d; }
label { display:block; margin-bottom:0.3rem; margin-top: 1rem; }
input, select { width:100%; padding:0.5rem; border-radius:8px; border:none; margin-bottom:0.5rem; box-sizing: border-box; }
.form-group { margin-bottom: 1rem; }
.read-only { background-color: rgba(255,255,255,0.2); color: #ccc; cursor: not-allowed; }

button { display:block; width:100%; background:linear-gradient(90deg,#ffdf5d,#ffb84d); color:#000; border:none; border-radius:10px; padding:0.7rem; cursor:pointer; transition:all 0.3s ease; margin-top: 1.5rem; }
button:hover { background:linear-gradient(90deg,#ffd633,#ffa31a); transform:scale(1.05); }
.back-link { display: block; text-align: center; margin-top: 1rem; color: #ffdf5d; text-decoration: none; }
</style>
</head>
<body>
<div class="card">
<h1>ویرایش رکورد: {{ row['نام'] }} {{ row['نام خانوادگی'] }}</h1>
<form method="POST">
{% for h in headers %}
    {% set value = row.get(h, '') %}
    <div class="form-group">
        <label>{{ h }}:</label>
        {% if h == 'فیش واریزی' %}
            <input type="text" value="{{ value }}" readonly class="read-only">
            {% if value %}
                <a href="/uploads/{{ value }}" target="_blank" style="color: #ffdf5d; display: block; margin-top: 5px;">مشاهده فیش</a>
            {% else %}
                <span style="display: block; color: #ccc;">فیشی بارگذاری نشده است.</span>
            {% endif %}
        {% elif h == 'جنسیت' %}
            <select name="{{ h }}" required>
                <option value="مرد" {% if value == 'مرد' %}selected{% endif %}>مرد</option>
                <option value="زن" {% if value == 'زن' %}selected{% endif %}>زن</option>
            </select>
        {% else %}
            <input type="text" name="{{ h }}" value="{{ value }}" required>
        {% endif %}
    </div>
{% endfor %}
<button type="submit">ذخیره ویرایش‌ها</button>
<a href="/admin_pannel" class="back-link">بازگشت به پنل</a>
</form>
</div>
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
    if session.get("step") != 2.5:
        # اگر مرحله اشتباه است، کاربر را به شروع یا مرحله قبل هدایت کن
        return redirect("/") 
        
    if request.method == "POST":
        # 1. مدیریت آپلود فایل
        if "receipt_file" not in request.files:
            return "فایل فیش وجود ندارد", 400

        receipt_file = request.files["receipt_file"]
        if receipt_file.filename == "":
            return "نام فایل فیش خالی است", 400

        # اگر فایل وجود داشت، آن را ذخیره کن
        if receipt_file:
            # ایجاد یک نام فایل امن و یونیک (اگرچه secure_filename کافیست، اما برای جلوگیری از تکرار، می‌توان UUID هم اضافه کرد)
            filename = secure_filename(receipt_file.filename)
            # برای جلوگیری از تداخل، از یک پیشوند زمان‌دار یا یونیک استفاده می‌کنیم
            import time
            unique_filename = f"{int(time.time())}_{filename}"
            receipt_filepath = os.path.join(
                app.config["UPLOAD_FOLDER"], unique_filename
            )
            try:
                receipt_file.save(receipt_filepath)
                
                # 2. به‌روزرسانی داده‌ها و ذخیره در CSV
                data = session.get("form_data", {})
                data["receipt_file"] = unique_filename
                
                # 3. ذخیره نهایی
                save_to_csv(data)
                
                # 4. ارسال به تلگرام (با فیش)
                send_to_telegram(data, receipt_filepath)
                
                # 5. پاکسازی و ریدایرکت نهایی (در حالت AJAX، جاوا اسکریپت ریدایرکت را هندل می‌کند)
                session["step"] = 3
                return "ثبت نام موفق", 200 # پاسخ موفق 200 برای AJAX
            
            except Exception as e:
                print(f"خطا در ذخیره فایل یا پردازش: {e}")
                return "خطا در پردازش فایل یا اطلاعات", 500

    # نمایش صفحه پرداخت و آپلود در متد GET
    # ! به روز رسانی شده برای استفاده از f-string و متغیرهای تنظیم شده
    return render_template_string(payment_upload_html)


@app.route("/thanks")
def thanks():
    if session.get("step") != 3:
        return redirect("/")
    
    # حذف سشن پس از اتمام
    session.clear() 
    return render_template_string(thanks_html)


# --- ادمین پنل و توابع مدیریتی ---

@app.route("/admin_pannel")
@requires_auth
def admin_pannel():
    # خواندن داده‌ها
    if not os.path.exists(CSV_FILE):
        return render_template_string(admin_html, headers=PERSIAN_HEADERS, rows=[])
        
    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    
    return render_template_string(admin_html, headers=PERSIAN_HEADERS, rows=rows)

# ! روت جدید برای نمایش فایل‌های آپلودی (فیش‌ها)
@app.route("/uploads/<filename>")
@requires_auth
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ! تابع کمکی برای خواندن و نوشتن مجدد CSV پس از عملیات حذف/ویرایش
def update_csv(rows):
    """بازنویسی کل فایل CSV با ردیف‌های جدید"""
    if not rows:
        if os.path.exists(CSV_FILE):
             os.remove(CSV_FILE)
        return

    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=PERSIAN_HEADERS)
        writer.writeheader()
        writer.writerows(rows)

@app.route("/admin_delete/<int:index>")
@requires_auth
def admin_delete(index):
    if not os.path.exists(CSV_FILE):
        return redirect("/admin_pannel")

    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if 0 <= index < len(rows):
        # حذف فایل فیش اگر وجود داشته باشد
        receipt_filename = rows[index].get("فیش واریزی")
        if receipt_filename:
            receipt_filepath = os.path.join(app.config["UPLOAD_FOLDER"], receipt_filename)
            if os.path.exists(receipt_filepath):
                os.remove(receipt_filepath)
        
        del rows[index]
        update_csv(rows)
    
    return redirect("/admin_pannel")

@app.route("/admin_edit/<int:index>", methods=["GET", "POST"])
@requires_auth
def admin_edit(index):
    if not os.path.exists(CSV_FILE):
        return redirect("/admin_pannel")

    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if not (0 <= index < len(rows)):
        return redirect("/admin_pannel")

    row_to_edit = rows[index]

    if request.method == "POST":
        # به‌روزرسانی داده‌های رکورد از فرم POST
        for header in PERSIAN_HEADERS:
            # فیش واریزی به صورت متنی در فرم ویرایش، قابل تغییر نیست
            if header != "فیش واریزی":
                # از request.form.get(header) استفاده می‌کنیم
                new_value = request.form.get(header)
                if new_value is not None:
                    row_to_edit[header] = new_value
        
        # ذخیره مجدد کل CSV
        update_csv(rows)
        return redirect("/admin_pannel")

    return render_template_string(admin_edit_html, row=row_to_edit, index=index, headers=PERSIAN_HEADERS)

@app.route("/download_csv")
@requires_auth
def download_csv():
    if not os.path.exists(CSV_FILE):
        return "فایل CSV پیدا نشد.", 404
    
    # تنظیم هدرها برای دانلود
    return send_file(
        CSV_FILE,
        mimetype="text/csv",
        as_attachment=True,
        download_name="registrations_all.csv",
    )

@app.route("/download_csv_filtered")
@requires_auth
def download_csv_filtered():
    if not os.path.exists(CSV_FILE):
        return "فایل CSV پیدا نشد.", 404
    
    # پارامتر فیلتر (مثلاً certificate)
    filter_key = request.args.keys()
    if not filter_key:
        return redirect("/download_csv")

    filter_key = list(filter_key)[0] # اولین پارامتر
    filter_value = request.args.get(filter_key)

    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        all_rows = list(csv.DictReader(f))
    
    # فیلتر کردن
    filtered_rows = [row for row in all_rows if row.get(filter_key) == filter_value]

    # ایجاد یک فایل موقت برای دانلود فیلتر شده
    import io
    temp_output = io.StringIO()
    writer = csv.DictWriter(temp_output, fieldnames=PERSIAN_HEADERS)
    writer.writeheader()
    writer.writerows(filtered_rows)
    temp_output.seek(0)

    # تعیین نام فایل بر اساس فیلتر
    download_name = f"registrations_filtered_{filter_key}.csv"
    if filter_value:
        # برای حذف ( و ) و تبدیل به نام فایل مناسب
        safe_value = filter_value.replace('(', '').replace(')', '').replace(' ', '_')
        download_name = f"registrations_{safe_value}.csv"

    # تنظیم هدرها برای دانلود
    return Response(
        temp_output.getvalue().encode('utf-8-sig'),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment;filename={download_name.replace(' ', '_')}",
            "Content-type": "text/csv; charset=utf-8-sig"
        }
    )

if __name__ == "__main__":
    # ! تنظیمات Vazir Font برای نمایش بهتر فونت فارسی (فقط برای حالت اجرای لوکال)
    # ! در محیط Canvas، فونت Vazir باید قبلا تنظیم شده باشد.
    
    # این خط را برای تست لوکال برگردانید: app.run(debug=True)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
