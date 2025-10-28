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
import csv, os, requests, time
import json
from werkzeug.utils import secure_filename

# --- Konfigurasi Aplikasi ---
app = Flask(__name__)

# ! --- بارگذاری متغیرهای محیطی حساس از ENV ---
# اگر متغیر محیطی تنظیم نشده باشد، از مقداری که کاربر در درخواست فرستاده بود استفاده می‌شود (فقط برای تست).
SECRET_KEY = os.environ.get("SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# تنظیم کلید مخفی Flask
app.secret_key = SECRET_KEY

# --- Konfigurasi Folder Upload ---
# ! بررسی اینکه آیا روی Render با دیسک دائمی اجرا می‌شود یا محلی
DISK_MOUNT_PATH = os.environ.get("RENDER_DISK_MOUNT_PATH")
if DISK_MOUNT_PATH:
    UPLOAD_FOLDER = os.path.join(DISK_MOUNT_PATH, "uploads")
    print(f"--- در حال استفاده از دیسک دائمی Render در مسیر: {UPLOAD_FOLDER} ---")
else:
    UPLOAD_FOLDER = "uploads"  # حالت موقت (Ephemeral/Local)
    print(f"--- WARNING: در حال استفاده از پوشه موقت: {UPLOAD_FOLDER}. فایل‌ها با ری‌استارت پاک می‌شوند. ---")

# اطمینان از وجود پوشه در هر دو حالت
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# --- Variabel Global و اطلاعات کارت ---
CSV_FILE = "registrations.csv"
ADMIN_USER = "admin"
# ! رمز ادمین از متغیر محیطی SECRET_KEY خوانده می‌شود
ADMIN_PASS = SECRET_KEY 

# اطلاعات کارت را از محیط بخوانید
YOUR_CARD_NAME = os.environ.get("YOUR_CARD_NAME")
RAW_CARD_NUMBER = os.environ.get("YOUR_CARD_NUMBER")

# فرمت کردن شماره کارت (62861872975239 -> 6286-1872-9752-39)
YOUR_CARD_NUMBER_DISPLAY = "-".join([RAW_CARD_NUMBER[i:i+4] for i in range(0, len(RAW_CARD_NUMBER), 4)])

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
    # استفاده از متغیرهای بارگذاری شده در بالای فایل
    bot_token = TELEGRAM_BOT_TOKEN
    chat_id = TELEGRAM_CHAT_ID

    if not bot_token or not chat_id or bot_token == 'default_token':
        print("توکن یا شماره چت تلگرام تنظیم نشده است!")
        return

    # ساخت پیام زیبا با emoji و قالب خوانا
    message = "🎉 **ثبت‌نام جدید کارگاه مقاله نویسی** 🎉\n\n"
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
def send_admin_list(chat_id):
    """
    ارسال دکمه کیبورد برای دیدن لیست ثبت‌نام‌ها
    """
    bot_token = TELEGRAM_BOT_TOKEN
    if not bot_token or bot_token == 'default_token':
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": "برای مشاهده لیست ثبت‌نام‌ها، لطفا از پنل وب ادمین استفاده کنید."})


def send_admin_list_with_keyboard(chat_id):
    """
    ارسال دکمه‌های اینلاین برای مشاهده و ویرایش جزئیات
    """
    if not os.path.exists(CSV_FILE):
        return
        
    bot_token = TELEGRAM_BOT_TOKEN
    if not bot_token or bot_token == 'default_token':
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
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
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
        text = f"📊 گزارش سریع:\nکل ثبت‌نام‌ها: {total}\nخواهان گواهی: {certified}\nرایگان: {total - certified}"
        url = (
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
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
        
    bot_token = TELEGRAM_BOT_TOKEN
    if not bot_token or bot_token == 'default_token':
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

# ---------------- Routes -----------------
FORM_ACTIVE = True


@app.route("/", methods=["GET"])
def index():
    if not FORM_ACTIVE:
        return """
        <!DOCTYPE html>
        <html lang="fa" dir="rtl">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>پرسشنامه غیر‌فعال</title>
        <style>
        body { 
            margin: 0; 
            font-family: 'Vazir', sans-serif; 
            background: linear-gradient(135deg,#1e3c72,#2a5298); 
            color: #fff; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            min-height: 100vh; 
        }
        .card { 
            background: rgba(255,255,255,0.1); 
            backdrop-filter: blur(10px); 
            border-radius: 20px; 
            padding: 2rem; 
            max-width: 480px; 
            width: 90%; 
            box-shadow: 0 8px 20px rgba(0,0,0,0.2); 
            text-align: center; 
        }
        h1 { 
            font-size: 1.4rem; 
            color: #ff5c5c;  /* رنگ قرمز برای پیام اصلی */
            margin-bottom: 1rem; 
            line-height: 1.8; 
        }
        p { 
            font-size: 1.1rem; 
            line-height: 1.8;
        }
        a.btn { 
            display: inline-block; 
            margin-top: 1.5rem; 
            background: linear-gradient(90deg,#ffdf5d,#ffb84d); 
            color: #000; 
            border: none; 
            border-radius: 10px; 
            padding: 0.6rem 1.2rem; 
            text-decoration: none; 
            font-weight: bold;
            transition: all 0.3s ease; 
        }
        a.btn:hover { 
            background: linear-gradient(90deg,#ffd633,#ffa31a); 
            transform: scale(1.05); 
        }
        </style>
        </head>
        <body>
        <div class="card">
          <h1>به علت تکمیل ظرفیت پذیرش، این پرسشنامه غیر‌فعال است و امکان ثبت پاسخ ندارد</h1>
          <p>متعاقباً اطلاعات تکمیلی در کانال تلگرام بارگذاری خواهد شد.</p>
          <a href="https://t.me/article_workshop1" class="btn" target="_blank">ورود به کانال تلگرام</a>
        </div>
        </body>
        </html>
        """

    """صفحه قوانین و شروع ثبت نام"""
    # پاک کردن سشن در شروع
    session.clear()
    return render_template_string(rules_html)

@app.route("/start_form", methods=["POST"])
def start_form():
    if not FORM_ACTIVE:
        return """
        <!DOCTYPE html>
        <html lang="fa" dir="rtl">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>پرسشنامه غیر‌فعال</title>
        <style>
        body { 
            margin: 0; 
            font-family: 'Vazir', sans-serif; 
            background: linear-gradient(135deg,#1e3c72,#2a5298); 
            color: #fff; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            min-height: 100vh; 
        }
        .card { 
            background: rgba(255,255,255,0.1); 
            backdrop-filter: blur(10px); 
            border-radius: 20px; 
            padding: 2rem; 
            max-width: 480px; 
            width: 90%; 
            box-shadow: 0 8px 20px rgba(0,0,0,0.2); 
            text-align: center; 
        }
        h1 { 
            font-size: 1.4rem; 
            color: #ff5c5c;  /* رنگ قرمز برای پیام اصلی */
            margin-bottom: 1rem; 
            line-height: 1.8; 
        }
        p { 
            font-size: 1.1rem; 
            line-height: 1.8;
        }
        a.btn { 
            display: inline-block; 
            margin-top: 1.5rem; 
            background: linear-gradient(90deg,#ffdf5d,#ffb84d); 
            color: #000; 
            border: none; 
            border-radius: 10px; 
            padding: 0.6rem 1.2rem; 
            text-decoration: none; 
            font-weight: bold;
            transition: all 0.3s ease; 
        }
        a.btn:hover { 
            background: linear-gradient(90deg,#ffd633,#ffa31a); 
            transform: scale(1.05); 
        }
        </style>
        </head>
        <body>
        <div class="card">
          <h1>به علت تکمیل ظرفیت پذیرش، این پرسشنامه غیر‌فعال است و امکان ثبت پاسخ ندارد</h1>
          <p>متعاقباً اطلاعات تکمیلی در کانال تلگرام بارگذاری خواهد شد.</p>
          <a href="https://t.me/article_workshop1" class="btn" target="_blank">ورود به کانال تلگرام</a>
        </div>
        </body>
        </html>
        """

    """شروع فرآیند ثبت نام و هدایت به فرم"""
    session.clear()
    session["step"] = "form"  # مرحله اول شروع شد
    return redirect("/form")
    
@app.route("/form", methods=["GET", "POST"])
def form_page():
    if not FORM_ACTIVE:
        return """
        <!DOCTYPE html>
        <html lang="fa" dir="rtl">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>پرسشنامه غیر‌فعال</title>
        <style>
        body { 
            margin: 0; 
            font-family: 'Vazir', sans-serif; 
            background: linear-gradient(135deg,#1e3c72,#2a5298); 
            color: #fff; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            min-height: 100vh; 
        }
        .card { 
            background: rgba(255,255,255,0.1); 
            backdrop-filter: blur(10px); 
            border-radius: 20px; 
            padding: 2rem; 
            max-width: 480px; 
            width: 90%; 
            box-shadow: 0 8px 20px rgba(0,0,0,0.2); 
            text-align: center; 
        }
        h1 { 
            font-size: 1.4rem; 
            color: #ff5c5c;  /* رنگ قرمز برای پیام اصلی */
            margin-bottom: 1rem; 
            line-height: 1.8; 
        }
        p { 
            font-size: 1.1rem; 
            line-height: 1.8;
        }
        a.btn { 
            display: inline-block; 
            margin-top: 1.5rem; 
            background: linear-gradient(90deg,#ffdf5d,#ffb84d); 
            color: #000; 
            border: none; 
            border-radius: 10px; 
            padding: 0.6rem 1.2rem; 
            text-decoration: none; 
            font-weight: bold;
            transition: all 0.3s ease; 
        }
        a.btn:hover { 
            background: linear-gradient(90deg,#ffd633,#ffa31a); 
            transform: scale(1.05); 
        }
        </style>
        </head>
        <body>
        <div class="card">
          <h1>به علت تکمیل ظرفیت پذیرش، این پرسشنامه غیر‌فعال است و امکان ثبت پاسخ ندارد</h1>
          <p>متعاقباً اطلاعات تکمیلی در کانال تلگرام بارگذاری خواهد شد.</p>
          <a href="https://t.me/article_workshop1" class="btn" target="_blank">ورود به کانال تلگرام</a>
        </div>
        </body>
        </html>
        """

    """فرم ثبت نام"""
    # جلوگیری از ورود مستقیم (فقط اگر از start_form آمده باشد)
    if session.get("step") != "form":
        return redirect("/")

    if request.method == "POST":
        # ذخیره اطلاعات فرم در سشن
        session["reg_data"] = request.form.to_dict()
        session["step"] = "certificate"  # اجازه مرحله بعد
        return redirect("/certificate")

    return render_template_string(form_html)


@app.route("/certificate", methods=["GET", "POST"])
def certificate_choice():
    if not FORM_ACTIVE:
        return """
        <!DOCTYPE html>
        <html lang="fa" dir="rtl">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>پرسشنامه غیر‌فعال</title>
        <style>
        body { 
            margin: 0; 
            font-family: 'Vazir', sans-serif; 
            background: linear-gradient(135deg,#1e3c72,#2a5298); 
            color: #fff; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            min-height: 100vh; 
        }
        .card { 
            background: rgba(255,255,255,0.1); 
            backdrop-filter: blur(10px); 
            border-radius: 20px; 
            padding: 2rem; 
            max-width: 480px; 
            width: 90%; 
            box-shadow: 0 8px 20px rgba(0,0,0,0.2); 
            text-align: center; 
        }
        h1 { 
            font-size: 1.4rem; 
            color: #ff5c5c;  /* رنگ قرمز برای پیام اصلی */
            margin-bottom: 1rem; 
            line-height: 1.8; 
        }
        p { 
            font-size: 1.1rem; 
            line-height: 1.8;
        }
        a.btn { 
            display: inline-block; 
            margin-top: 1.5rem; 
            background: linear-gradient(90deg,#ffdf5d,#ffb84d); 
            color: #000; 
            border: none; 
            border-radius: 10px; 
            padding: 0.6rem 1.2rem; 
            text-decoration: none; 
            font-weight: bold;
            transition: all 0.3s ease; 
        }
        a.btn:hover { 
            background: linear-gradient(90deg,#ffd633,#ffa31a); 
            transform: scale(1.05); 
        }
        </style>
        </head>
        <body>
        <div class="card">
          <h1>به علت تکمیل ظرفیت پذیرش، این پرسشنامه غیر‌فعال است و امکان ثبت پاسخ ندارد</h1>
          <p>متعاقباً اطلاعات تکمیلی در کانال تلگرام بارگذاری خواهد شد.</p>
          <a href="https://t.me/article_workshop1" class="btn" target="_blank">ورود به کانال تلگرام</a>
        </div>
        </body>
        </html>
        """

    """انتخاب گزینه گواهی و هدایت به مرحله بعد"""
    # جلوگیری از ورود مستقیم یا رفرش
    if session.get("step") != "certificate":
        return redirect("/")

    if request.method == "POST":
        choice = request.form.get("certificate")
        if not session.get("reg_data"):
            return redirect("/")  # اگر داده‌های مرحله قبل وجود ندارد

        session["reg_data"]["certificate"] = choice
        
        if choice and "خواهان گواهی هستم" in choice:
            # اگر گواهی می‌خواهد، برود مرحله پرداخت
            session["step"] = "payment"
            return redirect("/payment_upload")
        else:
            # اگر گواهی نمی‌خواهد، پایان ثبت نام
            final_data = session.pop("reg_data")
            save_to_csv(final_data)
            send_to_telegram(final_data)
            session.clear()
            return redirect("/thanks")

    return render_template_string(certificate_html)


@app.route("/payment_upload", methods=["GET", "POST"])
def payment_upload():
    if not FORM_ACTIVE:
        return """
        <!DOCTYPE html>
        <html lang="fa" dir="rtl">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>پرسشنامه غیر‌فعال</title>
        <style>
        body { 
            margin: 0; 
            font-family: 'Vazir', sans-serif; 
            background: linear-gradient(135deg,#1e3c72,#2a5298); 
            color: #fff; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            min-height: 100vh; 
        }
        .card { 
            background: rgba(255,255,255,0.1); 
            backdrop-filter: blur(10px); 
            border-radius: 20px; 
            padding: 2rem; 
            max-width: 480px; 
            width: 90%; 
            box-shadow: 0 8px 20px rgba(0,0,0,0.2); 
            text-align: center; 
        }
        h1 { 
            font-size: 1.4rem; 
            color: #ff5c5c;  /* رنگ قرمز برای پیام اصلی */
            margin-bottom: 1rem; 
            line-height: 1.8; 
        }
        p { 
            font-size: 1.1rem; 
            line-height: 1.8;
        }
        a.btn { 
            display: inline-block; 
            margin-top: 1.5rem; 
            background: linear-gradient(90deg,#ffdf5d,#ffb84d); 
            color: #000; 
            border: none; 
            border-radius: 10px; 
            padding: 0.6rem 1.2rem; 
            text-decoration: none; 
            font-weight: bold;
            transition: all 0.3s ease; 
        }
        a.btn:hover { 
            background: linear-gradient(90deg,#ffd633,#ffa31a); 
            transform: scale(1.05); 
        }
        </style>
        </head>
        <body>
        <div class="card">
          <h1>به علت تکمیل ظرفیت پذیرش، این پرسشنامه غیر‌فعال است و امکان ثبت پاسخ ندارد</h1>
          <p>متعاقباً اطلاعات تکمیلی در کانال تلگرام بارگذاری خواهد شد.</p>
          <a href="https://t.me/article_workshop1" class="btn" target="_blank">ورود به کانال تلگرام</a>
        </div>
        </body>
        </html>
        """

    """آپلود رسید پرداخت"""
    if session.get("step") != "payment":
        return redirect("/")

    if request.method == "POST":
        # نام فیلد HTML = receipt_file
        file = request.files.get("receipt_file")
        if not file or file.filename == "":
            return Response("خطا در ارسال فیش. لطفاً فایل دیگری را امتحان کنید.", status=400)

        os.makedirs("uploads", exist_ok=True)
        filename = file.filename
        unique_filename = f"{int(time.time())}_{filename}"
        filepath = os.path.join("uploads", unique_filename)

        try:
            file.save(filepath)
        except Exception as e:
            print("❌ خطا در ذخیره فایل:", e)
            return Response("خطا در ذخیره فیش. لطفاً دوباره تلاش کنید.", status=500)

        try:
            final_data = session.pop("reg_data", {})
            final_data["receipt_file"] = unique_filename
            save_to_csv(final_data)
            send_to_telegram(final_data, receipt_filepath=filepath)
        except Exception as e:
            print("❌ خطا در ارسال به تلگرام:", e)
            return Response("خطا در ارسال فیش. لطفاً فایل دیگری را امتحان کنید.", status=500)

        session.clear()
        return Response("ثبت نهایی موفق", status=200)

    return render_template_string(payment_upload_html)


@app.route("/thanks", methods=["GET"])
def thanks():
    if not FORM_ACTIVE:
        return """
        <!DOCTYPE html>
        <html lang="fa" dir="rtl">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>پرسشنامه غیر‌فعال</title>
        <style>
        body { 
            margin: 0; 
            font-family: 'Vazir', sans-serif; 
            background: linear-gradient(135deg,#1e3c72,#2a5298); 
            color: #fff; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            min-height: 100vh; 
        }
        .card { 
            background: rgba(255,255,255,0.1); 
            backdrop-filter: blur(10px); 
            border-radius: 20px; 
            padding: 2rem; 
            max-width: 480px; 
            width: 90%; 
            box-shadow: 0 8px 20px rgba(0,0,0,0.2); 
            text-align: center; 
        }
        h1 { 
            font-size: 1.4rem; 
            color: #ff5c5c;  /* رنگ قرمز برای پیام اصلی */
            margin-bottom: 1rem; 
            line-height: 1.8; 
        }
        p { 
            font-size: 1.1rem; 
            line-height: 1.8;
        }
        a.btn { 
            display: inline-block; 
            margin-top: 1.5rem; 
            background: linear-gradient(90deg,#ffdf5d,#ffb84d); 
            color: #000; 
            border: none; 
            border-radius: 10px; 
            padding: 0.6rem 1.2rem; 
            text-decoration: none; 
            font-weight: bold;
            transition: all 0.3s ease; 
        }
        a.btn:hover { 
            background: linear-gradient(90deg,#ffd633,#ffa31a); 
            transform: scale(1.05); 
        }
        </style>
        </head>
        <body>
        <div class="card">
          <h1>به علت تکمیل ظرفیت پذیرش، این پرسشنامه غیر‌فعال است و امکان ثبت پاسخ ندارد</h1>
          <p>متعاقباً اطلاعات تکمیلی در کانال تلگرام بارگذاری خواهد شد.</p>
          <a href="https://t.me/article_workshop1" class="btn" target="_blank">ورود به کانال تلگرام</a>
        </div>
        </body>
        </html>
        """

    """صفحه تشکر نهایی"""
    if session.get("step") not in [None, "done"]:
        return redirect("/")
    return render_template_string(thanks_html)

# ---------------- Admin Routes -----------------

@app.route("/admin", methods=["GET"])
@requires_auth
def admin_panel():
    """نمایش پنل ادمین و لیست ثبت نام‌ها"""
    rows = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    
    # render_template_string به جای render_template برای سازگاری با محیط
    return render_template_string(admin_html, rows=rows, headers=PERSIAN_HEADERS)

@app.route("/uploads/<filename>")
@requires_auth
def uploaded_file(filename):
    """سرویس دهی فایل‌های آپلودی (فیش‌ها)"""
    # تضمین امنیت برای جلوگیری از دسترسی به فایل‌های خارج از پوشه آپلود
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/download_csv", methods=["GET"])
@requires_auth
def download_csv():
    """دانلود کل فایل CSV"""
    if not os.path.exists(CSV_FILE):
        return "فایل CSV وجود ندارد", 404
    
    # ارسال فایل با نام مناسب برای دانلود
    return send_file(CSV_FILE, as_attachment=True, download_name="registrations_all.csv", mimetype="text/csv")

@app.route("/download_csv_filtered", methods=["GET"])
@requires_auth
def download_csv_filtered():
    """دانلود فایل CSV فیلتر شده بر اساس فیلد گواهی"""
    filter_value = request.args.get("certificate")
    
    if not filter_value:
        return "لطفاً مقدار فیلتر را مشخص کنید (certificate=...)", 400
        
    if not os.path.exists(CSV_FILE):
        return "فایل CSV وجود ندارد", 404
        
    filtered_rows = []
    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("گواهی") == filter_value:
                filtered_rows.append(row)

    # ساخت یک فایل CSV موقت برای ارسال
    temp_csv_filename = f"registrations_filtered_{filter_value.replace(' ', '_').replace('(50_هزار_تومان)', 'certified').replace('(رایگان)', 'free')}.csv"
    temp_csv_path = os.path.join(app.config["UPLOAD_FOLDER"], temp_csv_filename)
    
    with open(temp_csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=PERSIAN_HEADERS)
        writer.writeheader()
        writer.writerows(filtered_rows)

    return send_file(temp_csv_path, as_attachment=True, download_name=temp_csv_filename, mimetype="text/csv")

# ---------------- Admin Edit/Delete -----------------

@app.route("/admin_delete/<int:index>", methods=["GET"])
@requires_auth
def admin_delete(index):
    """حذف یک رکورد بر اساس ایندکس"""
    if not os.path.exists(CSV_FILE):
        return redirect("/admin")

    rows = []
    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    
    if 0 <= index < len(rows):
        deleted_row = rows.pop(index)
        
        # حذف فایل فیش واریزی در صورت وجود
        receipt_file = deleted_row.get("فیش واریزی")
        if receipt_file:
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], receipt_file)
            if os.path.exists(filepath):
                os.remove(filepath)

        # بازنویسی کامل فایل CSV
        with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=PERSIAN_HEADERS)
            writer.writeheader()
            writer.writerows(rows)
            
    return redirect("/admin")

@app.route("/admin_edit/<int:index>", methods=["GET"])
@requires_auth
def admin_edit(index):
    """نمایش فرم ویرایش برای یک رکورد"""
    if not os.path.exists(CSV_FILE):
        return redirect("/admin")
        
    rows = []
    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        
    if 0 <= index < len(rows):
        record = rows[index]
        return render_template_string(admin_edit_html, index=index, record=record, headers=PERSIAN_HEADERS)
    
    return "رکورد مورد نظر یافت نشد", 404

@app.route("/admin_edit/<int:index>/save", methods=["POST"])
@requires_auth
def admin_edit_save(index):
    """ذخیره تغییرات اعمال شده در فرم ویرایش"""
    if not os.path.exists(CSV_FILE):
        return redirect("/admin")

    rows = []
    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        
    if 0 <= index < len(rows):
        updated_data = request.form.to_dict()
        
        # کپی کردن مقدار فیش واریزی از رکورد قدیمی، چون در فرم ویرایش نمی‌توان آن را تغییر داد
        updated_data["فیش واریزی"] = rows[index].get("فیش واریزی", "")
        
        # به‌روز رسانی رکورد در لیست
        rows[index] = updated_data
        
        # بازنویسی کامل فایل CSV
        with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=PERSIAN_HEADERS)
            writer.writeheader()
            writer.writerows(rows)
            
    return redirect("/admin")

# ---------------- HTML Templates (Refactored to use Environment Vars) -----------------

rules_html = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>ثبت‌نام کارگاه مقاله نویسی</title>
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
<h1>فرم ثبت نام کارگاه مقاله نویسی</h1>
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
  <label>شماره تلفن:</label><input type="text" name="phone" pattern="[0-9۰-۹]{11}" inputmode="numeric" required>
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
    {YOUR_CARD_NUMBER_DISPLAY}
    <div class="card-name">به نام: {YOUR_CARD_NAME}</div> <!-- ! نام صاحب کارت از متغیر محیطی -->
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
    const cardNumber = "{RAW_CARD_NUMBER}";  
    
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
    }}
    // پاسخ نهایی
    xhr.onload = function() {{
        // پس از اتمام آپلود، نوار را کامل کن
        progressBar.style.width = '100%';
        
        if (xhr.status === 200) {{
            // پاسخ 200 نشان دهنده موفقیت و نیاز به ریدایرکت است.
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
<a href="https://t.me/article_workshop1" class="btn" target="_blank">کانال تلگرام کارگاه مقاله نویسی</a>
</div>
</body>
</html>
"""

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

# --- ! قالب HTML برای صفحه ویرایش ادمین (کامل شد) ---
admin_edit_html = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>ویرایش رکورد (شماره {{ index + 1 }})</title>
<style>
body { margin:0; font-family:'Vazir',sans-serif; background:linear-gradient(135deg,#1e3c72,#2a5298); color:#fff; display:flex; justify-content:center; align-items:center; min-height:100vh; }
.card { background: rgba(255,255,255,0.9); backdrop-filter: blur(10px); border-radius:20px; padding:2rem; max-width:600px; width:90%; box-shadow:0 8px 20px rgba(0,0,0,0.2); color: #333; }
h1 { text-align:center; font-size:1.5rem; margin-bottom:1.5rem; color:#1e3c72; }
label { display:block; margin-bottom:0.3rem; font-weight: bold; }
input[type="text"], select { width:100%; padding:0.5rem; border-radius:8px; border:1px solid #ccc; margin-bottom:1rem; box-sizing: border-box; background: #fff; color: #333; }
button { display:block; width:48%; background:linear-gradient(90deg,#28a745,#218838); color:#fff; border:none; border-radius:10px; padding:0.7rem; cursor:pointer; transition:all 0.3s ease; float: left; }
button:hover { background:linear-gradient(90deg,#218838,#1e7e34); transform:scale(1.02); }
.btn-cancel { display:block; width:48%; margin-left: 4%; background:linear-gradient(90deg,#dc3545,#c82333); color:#fff; border:none; border-radius:10px; padding:0.7rem; cursor:pointer; text-align: center; text-decoration: none; transition:all 0.3s ease; float: left; }
.btn-cancel:hover { background:linear-gradient(90deg,#c82333,#bd2130); transform:scale(1.02); color: #fff; }
.clearfix::after { content: ""; clear: both; display: table; }
.receipt-link { color: #0d6efd; text-decoration: underline; }
</style>
</head>
<body>
<div class="card">
<h1>ویرایش رکورد (شماره {{ index + 1 }})</h1>
<form method="POST" action="/admin_edit/{{ index }}/save" class="clearfix">
{% for h, v in record.items() %}
    {% if h != 'فیش واریزی' %}
        <label>{{ h }}:</label>
        {% if h == 'جنسیت' %}
            <select name="{{ h }}" required>
                <option value="مرد" {% if v == 'مرد' %}selected{% endif %}>مرد</option>
                <option value="زن" {% if v == 'زن' %}selected{% endif %}>زن</option>
            </select>
        {% elif h == 'مقطع تحصیلی' %}
            <select name="{{ h }}" required>
                <option value="کارشناسی" {% if v == 'کارشناسی' %}selected{% endif %}>کارشناسی</option>
                <option value="کارشناسی ارشد" {% if v == 'کارشناسی ارشد' %}selected{% endif %}>کارشناسی ارشد</option>
                <option value="دکتری" {% if v == 'دکتری' %}selected{% endif %}>دکتری</option>
                <option value="دیگر" {% if v == 'دیگر' %}selected{% endif %}>دیگر</option>
            </select>
        {% elif h == 'گواهی' %}
            <select name="{{ h }}" required>
                <option value="خواهان گواهی هستم (50 هزار تومان)" {% if v == 'خواهان گواهی هستم (50 هزار تومان)' %}selected{% endif %}>خواهان گواهی هستم (50 هزار تومان)</option>
                <option value="خواهان گواهی نیستم (رایگان)" {% if v == 'خواهان گواهی نیستم (رایگان)' %}selected{% endif %}>خواهان گواهی نیستم (رایگان)</option>
            </select>
        {% else %}
            <input type="text" name="{{ h }}" value="{{ v }}" required>
        {% endif %}
    {% else %}
        <!-- نمایش لینک فیش واریزی اما امکان ویرایش متن را نمی‌دهیم -->
        <label>فیش واریزی:</label>
        {% if v %}
            <p style="margin-top: 0; margin-bottom: 1rem;"><a href="/uploads/{{ v }}" target="_blank" class="receipt-link">مشاهده فایل فعلی: {{ v }}</a></p>
        {% else %}
            <p style="margin-top: 0; margin-bottom: 1rem;">فیشی بارگذاری نشده است.</p>
        {% endif %}
    {% endif %}
{% endfor %}
    <button type="submit">ذخیره تغییرات</button>
    <a href="/admin" class="btn-cancel">بازگشت بدون ذخیره</a>
</form>
</div>
</body>
</html>
"""

if __name__ == "__main__":
    # در محیط تولید (Production)، بهتر است از طریق gunicorn یا مشابه آن اجرا شود.
    # در محیط توسعه، این خط اجرا می‌شود:
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True
