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
    url_for,
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
import uuid
from datetime import datetime

# --- Konfigurasi Aplikasi ---
app = Flask(__name__)

# ! --- بارگذاری متغیرهای محیطی حساس از ENV ---
# اگر متغیر محیطی تنظیم نشده باشد، از مقداری که کاربر در درخواست فرستاده بود استفاده می‌شود (فقط برای تست).
SECRET_KEY = os.environ.get("SECRET_KEY", "your_secret_key_for_session_management")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "adminpass")

app.secret_key = SECRET_KEY
UPLOAD_FOLDER = 'uploads'
DB_FILE = 'registrations.csv'
ADMIN_LOG_FILE = 'admin_log.csv'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

# --- توابع کمکی ---
def allowed_file(filename):
    """بررسی می‌کند آیا پسوند فایل مجاز است یا خیر."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_data(file_path):
    """بارگذاری داده‌ها از فایل CSV."""
    if not os.path.exists(file_path):
        return []
    with open(file_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

def save_data(file_path, data, fieldnames):
    """ذخیره داده‌ها در فایل CSV."""
    with open(file_path, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

def get_fieldnames():
    """لیست نام فیلدهای ثبت نام."""
    return [
        "unique_id", "نام", "نام خانوادگی", "کدملی", "شماره تماس", 
        "فیش واریزی", "مبلغ واریزی", "استان", "شهر", 
        "نحوه آشنایی", "گواهی", "تاریخ ثبت نام", "وضعیت", "تاریخ تایید/رد"
    ]

def find_data_by_id(file_path, unique_id):
    """پیدا کردن یک سطر بر اساس unique_id."""
    data = load_data(file_path)
    for row in data:
        if row.get('unique_id') == unique_id:
            return row
    return None

def update_data_by_id(file_path, unique_id, data_to_update):
    """آپدیت یک سطر بر اساس unique_id."""
    data = load_data(file_path)
    fieldnames = get_fieldnames()
    found = False
    
    # فیلدهای جدید را به فیلدنامه‌ها اضافه کنید اگر وجود ندارند
    for key in data_to_update.keys():
        if key not in fieldnames:
            fieldnames.append(key)

    for i, row in enumerate(data):
        if row.get('unique_id') == unique_id:
            # اعمال آپدیت‌ها و اطمینان از حفظ فیلدهای موجود
            updated_row = row.copy()
            for key, value in data_to_update.items():
                updated_row[key] = value
            data[i] = updated_row
            found = True
            break

    if found:
        # ذخیره با لیست فیلدنامه‌های به‌روز شده
        save_data(file_path, data, fieldnames)
    return found

def send_telegram_notification(message, keyboard=None):
    """ارسال پیام به تلگرام."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram tokens not set. Skipping notification.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    if keyboard:
        payload["reply_markup"] = json.dumps(keyboard.to_dict())

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram notification: {e}")
        return None

def log_admin_action(admin_username, action_type, target_id=None, details=''):
    """ثبت اقدامات ادمین در فایل لاگ."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_data = load_data(ADMIN_LOG_FILE)
    fieldnames = ["timestamp", "admin", "action_type", "target_id", "details"]
    
    log_entry = {
        "timestamp": timestamp,
        "admin": admin_username,
        "action_type": action_type,
        "target_id": target_id if target_id else '',
        "details": details
    }
    
    log_data.append(log_entry)
    save_data(ADMIN_LOG_FILE, log_data, fieldnames)

# --- دکوراتورها ---
def admin_required(f):
    """دکوراتور برای احراز هویت ادمین."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('logged_in') != True:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def get_flash_message():
    """دریافت پیام فلش از سشن."""
    message = session.pop('flash_message', None)
    return message

# --- قالب های HTML/Jinja (به دلیل استفاده از render_template_string) ---

template_base = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        @font-face {
            font-family: 'Vazirmatn';
            src: url('https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.0.3/fonts/webfonts/Vazirmatn-Regular.woff2') format('woff2');
            font-weight: 400;
            font-style: normal;
        }
        body {
            font-family: 'Vazirmatn', Tahoma, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f4f7f6;
            color: #333;
            line-height: 1.6;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: #ffffff;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        }
        h1, h2 {
            text-align: center;
            color: #007bff;
            margin-bottom: 20px;
        }
        form {
            display: grid;
            gap: 15px;
        }
        label {
            font-weight: bold;
            display: block;
            margin-bottom: 5px;
        }
        input[type="text"], input[type="file"], input[type="password"], select {
            width: 100%;
            padding: 12px;
            border: 1px solid #ccc;
            border-radius: 8px;
            box-sizing: border-box;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input[type="text"]:focus, input[type="file"]:focus, input[type="password"]:focus, select:focus {
            border-color: #007bff;
            outline: none;
        }
        button {
            background-color: #007bff;
            color: white;
            padding: 12px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 18px;
            transition: background-color 0.3s, transform 0.2s;
            margin-top: 10px;
        }
        button:hover {
            background-color: #0056b3;
            transform: translateY(-2px);
        }
        .flash {
            background-color: #d4edda;
            color: #155724;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
            border: 1px solid #c3e6cb;
        }
        .error {
            background-color: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
            border: 1px solid #f5c6cb;
        }
        a {
            color: #007bff;
            text-decoration: none;
            transition: color 0.3s;
        }
        a:hover {
            color: #0056b3;
            text-decoration: underline;
        }
        .admin-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        .admin-table th, .admin-table td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: right;
        }
        .admin-table th {
            background-color: #f8f9fa;
            color: #333;
        }
        .status-pending { color: orange; font-weight: bold; }
        .status-approved { color: green; font-weight: bold; }
        .status-rejected { color: red; font-weight: bold; }
        .receipt-link {
            display: inline-block;
            margin-top: 5px;
            padding: 5px 10px;
            background-color: #e9ecef;
            border-radius: 4px;
        }
        .flex-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid #eee;
        }
        .admin-edit-form {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        .admin-edit-form > div {
            grid-column: span 1;
        }
        .admin-edit-form > button {
            grid-column: 1 / span 2;
        }
        @media (max-width: 600px) {
            .admin-edit-form {
                grid-template-columns: 1fr;
            }
            .admin-edit-form > div {
                grid-column: span 1;
            }
            .admin-edit-form > button {
                grid-column: span 1;
            }
            .admin-table th, .admin-table td {
                padding: 8px;
                font-size: 14px;
            }
        }
    </style>
    <!-- اضافه کردن اسکریپت حذف پیام فلش بعد از چند ثانیه -->
    <script>
        document.addEventListener('DOMContentLoaded', (event) => {
            const flashMessage = document.querySelector('.flash');
            if (flashMessage) {
                setTimeout(() => {
                    flashMessage.style.transition = 'opacity 1s';
                    flashMessage.style.opacity = '0';
                    setTimeout(() => flashMessage.remove(), 1000);
                }, 5000); // 5 ثانیه
            }
        });
    </script>
</head>
<body>
    <div class="container">
        {% if flash_message %}
        <div class="flash">{{ flash_message }}</div>
        {% endif %}
        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

template_index = template_base + """
{% block content %}
<h1>فرم ثبت نام</h1>
<form method="POST" enctype="multipart/form-data">
    <div>
        <label for="نام">نام:</label>
        <input type="text" id="نام" name="نام" required value="{{ form_data.get('نام', '') }}">
    </div>
    <div>
        <label for="نام خانوادگی">نام خانوادگی:</label>
        <input type="text" id="نام خانوادگی" name="نام خانوادگی" required value="{{ form_data.get('نام خانوادگی', '') }}">
    </div>
    <div>
        <label for="کدملی">کدملی:</label>
        <input type="text" id="کدملی" name="کدملی" required value="{{ form_data.get('کدملی', '') }}">
    </div>
    <div>
        <label for="شماره تماس">شماره تماس:</label>
        <input type="text" id="شماره تماس" name="شماره تماس" required value="{{ form_data.get('شماره تماس', '') }}">
    </div>
    <div>
        <label for="استان">استان:</label>
        <input type="text" id="استان" name="استان" required value="{{ form_data.get('استان', '') }}">
    </div>
    <div>
        <label for="شهر">شهر:</label>
        <input type="text" id="شهر" name="شهر" required value="{{ form_data.get('شهر', '') }}">
    </div>
    <div>
        <label for="مبلغ واریزی">مبلغ واریزی (به تومان):</label>
        <input type="text" id="مبلغ واریزی" name="مبلغ واریزی" required value="{{ form_data.get('مبلغ واریزی', '') }}">
    </div>
    <div>
        <label for="فیش واریزی">فیش واریزی (عکس یا PDF):</label>
        <input type="file" id="فیش واریزی" name="فیش واریزی" required>
    </div>
    <div>
        <label for="نحوه آشنایی">نحوه آشنایی با دوره:</label>
        <select id="نحوه آشنایی" name="نحوه آشنایی" required>
            <option value="">انتخاب کنید</option>
            <option value="اینستاگرام" {% if form_data.get('نحوه آشنایی') == 'اینستاگرام' %}selected{% endif %}>اینستاگرام</option>
            <option value="تلگرام" {% if form_data.get('نحوه آشنایی') == 'تلگرام' %}selected{% endif %}>تلگرام</option>
            <option value="دوستان" {% if form_data.get('نحوه آشنایی') == 'دوستان' %}selected{% endif %}>دوستان</option>
            <option value="دیگر" {% if form_data.get('نحوه آشنایی') == 'دیگر' %}selected{% endif %}>دیگر</option>
        </select>
    </div>
    <div>
        <label for="گواهی">درخواست گواهی حضور:</label>
        <select id="گواهی" name="گواهی" required>
            <option value="">انتخاب کنید</option>
            <option value="خواهان گواهی هستم (50 هزار تومان)" {% if form_data.get('گواهی') == 'خواهان گواهی هستم (50 هزار تومان)' %}selected{% endif %}>خواهان گواهی هستم (50 هزار تومان)</option>
            <option value="خواهان گواهی نیستم (رایگان)" {% if form_data.get('گواهی') == 'خواهان گواهی نیستم (رایگان)' %}selected{% endif %}>خواهان گواهی نیستم (رایگان)</option>
        </select>
    </div>
    <button type="submit">ثبت نام</button>
</form>
{% endblock %}
"""

template_submit_success = template_base + """
{% block content %}
<h1>ثبت نام موفق!</h1>
<p style="text-align: center; font-size: 1.2rem; color: green;">{{ form_data.get('نام') }} عزیز، ثبت نام شما با موفقیت انجام شد.</p>
<p style="text-align: center;">کد رهگیری شما: <strong>{{ form_data.get('unique_id') }}</strong></p>
<p style="text-align: center;">لطفا برای پیگیری و ویرایش فیش واریزی، این لینک را ذخیره کنید:</p>
<div style="text-align: center; margin-top: 20px;">
    <a href="{{ url_for('receipt_edit', unique_id=form_data.get('unique_id')) }}" class="receipt-link" style="font-size: 1.1rem; padding: 10px 20px; background-color: #28a745; color: white;">ویرایش فیش واریزی</a>
</div>
<p style="text-align: center; margin-top: 30px;">در صورت نیاز به هرگونه ویرایش دیگر، از طریق لینک بالا اقدام کنید. وضعیت نهایی ثبت نام توسط ادمین تایید و از طریق تلگرام به شما اطلاع داده خواهد شد.</p>
{% endblock %}
"""

template_receipt_edit = template_base + """
{% block content %}
<h2>ویرایش فیش واریزی (کد رهگیری: {{ unique_id }})</h2>
{% if data %}
<form method="POST" class="admin-edit-form" enctype="multipart/form-data">
    <div style="grid-column: 1 / -1;">
        <label>نام و نام خانوادگی:</label>
        <p style="font-weight: bold; color: #007bff;">{{ data.get('نام') }} {{ data.get('نام خانوادگی') }}</p>
    </div>
    <div style="grid-column: 1 / -1;">
        <label>وضعیت فعلی:</label>
        <p class="status-{{ data.get('وضعیت', 'pending').lower() }}" style="font-size: 1.1rem;">{{ data.get('وضعیت', 'در انتظار بررسی') }}</p>
    </div>
    <div>
        <label for="مبلغ واریزی">مبلغ واریزی (به تومان):</label>
        <input type="text" id="مبلغ واریزی" name="مبلغ واریزی" required value="{{ data.get('مبلغ واریزی', '') }}">
    </div>
    <div>
        <label for="فیش واریزی">فیش واریزی جدید (عکس یا PDF):</label>
        <input type="file" id="فیش واریزی" name="فیش واریزی">
        {% if data.get('فیش واریزی') %}
            <p style="margin-top: 5px; font-size: 0.9rem;">فایل فعلی: <a href="{{ url_for('uploaded_file', filename=data.get('فیش واریزی')) }}" target="_blank" class="receipt-link">مشاهده</a></p>
        {% else %}
            <p style="margin-top: 5px; font-size: 0.9rem; color: red;">فیشی بارگذاری نشده است.</p>
        {% endif %}
    </div>
    <button type="submit" style="grid-column: 1 / -1;">ذخیره تغییرات فیش و مبلغ</button>
</form>
{% else %}
<p class="error" style="text-align: center;">اطلاعاتی با این کد رهگیری یافت نشد.</p>
{% endif %}
{% endblock %}
"""

template_admin_login = template_base + """
{% block content %}
<h1>ورود مدیر سیستم</h1>
<form method="POST">
    <div>
        <label for="username">نام کاربری:</label>
        <input type="text" id="username" name="username" required>
    </div>
    <div>
        <label for="password">رمز عبور:</label>
        <input type="password" id="password" name="password" required>
    </div>
    <button type="submit">ورود</button>
</form>
{% endblock %}
"""

template_admin_panel = template_base + """
{% block content %}
<div class="flex-row">
    <h2>پنل مدیریت</h2>
    <a href="{{ url_for('admin_logout') }}" style="color: red; font-weight: bold;">خروج</a>
</div>
{% if data %}
    <table class="admin-table">
        <thead>
            <tr>
                <th>کد رهگیری</th>
                <th>نام و نام خانوادگی</th>
                <th>کدملی</th>
                <th>وضعیت</th>
                <th>عملیات</th>
            </tr>
        </thead>
        <tbody>
            {% for row in data %}
            <tr>
                <td>{{ row.get('unique_id', 'N/A') }}</td>
                <td>{{ row.get('نام', '') }} {{ row.get('نام خانوادگی', '') }}</td>
                <td>{{ row.get('کدملی', 'N/A') }}</td>
                <td class="status-{{ row.get('وضعیت', 'در انتظار بررسی').lower().replace(' ', '') }}">
                    {{ row.get('وضعیت', 'در انتظار بررسی') }}
                </td>
                <td>
                    <a href="{{ url_for('admin_edit', unique_id=row.get('unique_id')) }}">ویرایش/تایید</a>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
{% else %}
<p style="text-align: center;">هیچ ثبت نامی یافت نشد.</p>
{% endif %}
{% endblock %}
"""

template_admin_edit = template_base + """
{% block content %}
<div class="flex-row">
    <h2>ویرایش ثبت نام (کد رهگیری: {{ unique_id }})</h2>
    <a href="{{ url_for('admin_panel') }}">بازگشت به لیست</a>
</div>
{% if data %}
<form method="POST" class="admin-edit-form" enctype="multipart/form-data">
    <!-- فیلدهای نمایش/ورودی -->
    {% for h, v in data.items() %}
    {% if h != 'unique_id' and h != 'تاریخ ثبت نام' and h != 'تاریخ تایید/رد' %}
        <div style="grid-column: span 1;">
        <label>{{ h }}:</label>
        {% if h == 'وضعیت' %}
            <select name="{{ h }}" required>
                <option value="در انتظار بررسی" {% if v == 'در انتظار بررسی' %}selected{% endif %}>در انتظار بررسی</option>
                <option value="تایید شده" {% if v == 'تایید شده' %}selected{% endif %}>تایید شده</option>
                <option value="رد شده" {% if v == 'رد شده' %}selected{% endif %}>رد شده</option>
            </select>
        {% elif h == 'نحوه آشنایی' %}
            <select name="{{ h }}" required>
                <option value="اینستاگرام" {% if v == 'اینستاگرام' %}selected{% endif %}>اینستاگرام</option>
                <option value="تلگرام" {% if v == 'تلگرام' %}selected{% endif %}>تلگرام</option>
                <option value="دوستان" {% if v == 'دوستان' %}selected{% endif %}>دوستان</option>
                <option value="دیگر" {% if v == 'دیگر' %}selected{% endif %}>دیگر</option>
            </select>
        {% elif h == 'گواهی' %}
            <select name="{{ h }}" required>
                <option value="خواهان گواهی هستم (50 هزار تومان)" {% if v == 'خواهان گواهی هستم (50 هزار تومان)' %}selected{% endif %}>خواهان گواهی هستم (50 هزار تومان)</option>
                <option value="خواهان گواهی نیستم (رایگان)" {% if v == 'خواهان گواهی نیستم (رایگان)' %}selected{% endif %}>خواهان گواهی نیستم (رایگان)</option>
            </select>
        {% elif h == 'فیش واریزی' %}
            <label>فیش واریزی:</label>
            {% if v %}
                <p style="margin-top: 0; margin-bottom: 1rem;"><a href="{{ url_for('uploaded_file', filename=v) }}" target="_blank" class="receipt-link">مشاهده فایل فعلی: {{ v }}</a></p>
                <!-- امکان حذف فایل موجود (اختیاری) -->
                <!-- <button type="button" onclick="document.getElementById('file-input').value = '';">حذف فایل فعلی</button> -->
            {% else %}
                <p style="margin-top: 0; margin-bottom: 1rem;">فیشی بارگذاری نشده است.</p>
            {% endif %}
            <input type="file" id="file-input" name="فیش واریزی_جدید">
        {% else %}
            <input type="text" name="{{ h }}" value="{{ v }}" required>
        {% endif %}
        </div>
    {% endif %}
{% endfor %}
<div style="grid-column: 1 / -1;">
    <p style="margin-top: 0; font-size: 0.9rem; color: #6c757d;">تاریخ ثبت نام: {{ data.get('تاریخ ثبت نام', 'N/A') }} | تاریخ آخرین تغییر وضعیت: {{ data.get('تاریخ تایید/رد', 'N/A') }}</p>
</div>
<button type="submit">ذخیره تغییرات</button>
</form>
{% else %}
<p class="error" style="text-align: center;">اطلاعاتی با این کد رهگیری یافت نشد.</p>
{% endif %}
{% endblock %}
"""

# --- مسیرها و منطق برنامه ---

@app.route('/', methods=['GET', 'POST'])
def index():
    """فرم اصلی ثبت نام."""
    flash_message = get_flash_message()
    # اگر در سشن داده‌ی فرم باقی مانده باشد (به دلیل POST ناموفق)، نمایش داده می‌شود
    context = {'title': 'فرم ثبت نام دوره', 'flash_message': flash_message, 'form_data': session.pop('form_data', {})}
    
    if request.method == 'POST':
        form_data = request.form.to_dict()
        f = request.files.get('فیش واریزی')

        # اعتبارسنجی فایل
        if not f or f.filename == '':
            context['flash_message'] = "لطفا فایل فیش واریزی را انتخاب کنید."
            context['form_data'] = form_data # حفظ داده‌های فرم
            return render_template_string(template_index, **context)
        
        if not allowed_file(f.filename):
            context['flash_message'] = "فقط فایل‌های PNG، JPG، JPEG یا PDF مجاز هستند."
            context['form_data'] = form_data # حفظ داده‌های فرم
            return render_template_string(template_index, **context)

        # پردازش فایل
        filename = secure_filename(str(uuid.uuid4()) + '.' + f.filename.rsplit('.', 1)[1].lower())
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        # تکمیل داده‌ها
        form_data['unique_id'] = str(uuid.uuid4())
        form_data['فیش واریزی'] = filename
        form_data['تاریخ ثبت نام'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        form_data['وضعیت'] = 'در انتظار بررسی'
        form_data['تاریخ تایید/رد'] = '' # خالی می‌ماند تا زمانی که ادمین تایید/رد کند

        # ذخیره داده
        data = load_data(DB_FILE)
        fieldnames = get_fieldnames()
        data.append(form_data)
        save_data(DB_FILE, data, fieldnames)
        
        # اعلان تلگرام
        telegram_msg = f"<b>ثبت نام جدید:</b>\n" \
                       f"نام: {form_data['نام']} {form_data['نام خانوادگی']}\n" \
                       f"شماره تماس: {form_data['شماره تماس']}\n" \
                       f"مبلغ واریزی: {form_data['مبلغ واریزی']} تومان\n" \
                       f"کد رهگیری: {form_data['unique_id']}\n"
        
        # ساخت دکمه‌های اینلاین برای تلگرام
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("مشاهده فیش واریزی", url=request.url_root + 'uploads/' + filename)],
            [InlineKeyboardButton("تایید", callback_data=f"approve_{form_data['unique_id']}"),
             InlineKeyboardButton("رد", callback_data=f"reject_{form_data['unique_id']}")],
            [InlineKeyboardButton("ویرایش اطلاعات", url=request.url_root + 'admin-edit/' + form_data['unique_id'])]
        ])

        send_telegram_notification(telegram_msg, keyboard)

        # انتقال داده‌های موقت به سشن برای نمایش در صفحه موفقیت
        session['form_data'] = form_data
        
        # الگوی PRG (Post/Redirect/Get): پس از POST موفق، به صفحه موفقیت هدایت می‌کنیم.
        return redirect(url_for('submit_success'))

    return render_template_string(template_index, **context)

@app.route('/success')
def submit_success():
    """صفحه موفقیت پس از ثبت نام."""
    form_data = session.pop('form_data', None)
    flash_message = get_flash_message()
    
    if form_data is None:
        # اگر کاربر مستقیماً به این صفحه آمد یا رفرش کرد، به صفحه اصلی هدایت شود
        # این بخش، جلوی رفرش شدن موفقیت‌آمیز را پس از یک بار نمایش می‌گیرد.
        return redirect(url_for('index'))

    context = {'title': 'ثبت نام موفق', 'form_data': form_data, 'flash_message': flash_message}
    return render_template_string(template_submit_success, **context)

@app.route('/receipt-edit/<unique_id>', methods=['GET', 'POST'])
def receipt_edit(unique_id):
    """ویرایش فیش واریزی توسط کاربر نهایی. (PRG پیاده‌سازی شده)"""
    data = find_data_by_id(DB_FILE, unique_id)
    flash_message = get_flash_message()
    
    if not data:
        context = {'title': 'خطا', 'flash_message': flash_message, 'unique_id': unique_id, 'data': None}
        return render_template_string(template_receipt_edit, **context)

    if request.method == 'POST':
        data_to_update = request.form.to_dict()
        f = request.files.get('فیش واریزی')

        new_filename = data.get('فیش واریزی')
        
        # بررسی و آپلود فایل جدید در صورت وجود
        if f and f.filename != '':
            if not allowed_file(f.filename):
                session['flash_message'] = "فقط فایل‌های PNG، JPG، JPEG یا PDF مجاز هستند."
                return redirect(url_for('receipt_edit', unique_id=unique_id)) # PRG
            
            # حذف فایل قدیمی در صورت وجود
            if new_filename and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], new_filename)):
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))

            # ذخیره فایل جدید
            new_filename = secure_filename(str(uuid.uuid4()) + '.' + f.filename.rsplit('.', 1)[1].lower())
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
        
        # اعمال تغییرات
        data_to_update['فیش واریزی'] = new_filename
        data_to_update['وضعیت'] = 'در انتظار بررسی' # با هر بار ویرایش، وضعیت به حالت انتظار برمی‌گردد
        data_to_update['تاریخ تایید/رد'] = '' # وضعیت تایید/رد قبلی پاک می‌شود
        
        if update_data_by_id(DB_FILE, unique_id, data_to_update):
            session['flash_message'] = 'تغییرات با موفقیت ذخیره شد. وضعیت شما مجدداً در انتظار بررسی است.'
            
            # اعلان تلگرام برای اطلاع رسانی به ادمین
            telegram_msg = f"<b>ویرایش فیش واریزی:</b>\n" \
                           f"کد رهگیری: {unique_id}\n" \
                           f"توسط کاربر ویرایش و مجدداً برای بررسی ارسال شد."
            send_telegram_notification(telegram_msg)
            
            # --- الگوی PRG (Post/Redirect/Get) ---
            # به متد GET همین صفحه ریدایرکت می‌کنیم تا از ارسال مجدد فرم جلوگیری شود.
            return redirect(url_for('receipt_edit', unique_id=unique_id)) 
        else:
            session['flash_message'] = 'خطا در ذخیره تغییرات.'
            # اگر خطایی در ذخیره رخ دهد، رندر می‌کند (بدون PRG) تا پیام خطا نمایش داده شود

    # اگر GET request باشد
    # داده را مجدداً بارگذاری می‌کنیم تا آخرین وضعیت نمایش داده شود
    data = find_data_by_id(DB_FILE, unique_id)
    context = {'title': 'ویرایش فیش واریزی', 'flash_message': flash_message, 'unique_id': unique_id, 'data': data}
    return render_template_string(template_receipt_edit, **context)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """سرو کردن فایل‌های آپلود شده."""
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except FileNotFoundError:
        return "فایل یافت نشد", 404

# --- مسیرهای ادمین ---

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    """صفحه ورود ادمین."""
    flash_message = get_flash_message()
    context = {'title': 'ورود مدیر', 'flash_message': flash_message}
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            log_admin_action(username, 'Login')
            session['flash_message'] = "با موفقیت وارد شدید."
            return redirect(url_for('admin_panel'))
        else:
            context['flash_message'] = "نام کاربری یا رمز عبور اشتباه است."
            
    return render_template_string(template_admin_login, **context)

@app.route('/admin-logout')
@admin_required
def admin_logout():
    """خروج ادمین."""
    log_admin_action(ADMIN_USERNAME, 'Logout')
    session.pop('logged_in', None)
    session['flash_message'] = "با موفقیت خارج شدید."
    return redirect(url_for('admin_login'))

@app.route('/admin-panel')
@admin_required
def admin_panel():
    """پنل مدیریت: نمایش لیست ثبت نام‌ها."""
    data = load_data(DB_FILE)
    # مرتب‌سازی: نمایش موارد "در انتظار بررسی" در ابتدا
    data.sort(key=lambda x: (x.get('وضعیت') != 'در انتظار بررسی', x.get('تاریخ ثبت نام', '')))
    
    flash_message = get_flash_message()
    context = {'title': 'پنل مدیریت', 'flash_message': flash_message, 'data': data}
    return render_template_string(template_admin_panel, **context)

@app.route('/admin-edit/<unique_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit(unique_id):
    """ویرایش کامل اطلاعات و تغییر وضعیت توسط ادمین. (PRG پیاده‌سازی شده)"""
    data = find_data_by_id(DB_FILE, unique_id)
    flash_message = get_flash_message()
    admin_user = ADMIN_USERNAME 

    if not data:
        context = {'title': 'خطا', 'flash_message': flash_message, 'unique_id': unique_id, 'data': None}
        return render_template_string(template_admin_edit, **context)

    if request.method == 'POST':
        new_data = request.form.to_dict()
        old_status = data.get('وضعیت')
        
        data_to_update = {}
        
        # 1. آپدیت فیلدهای متنی
        for key in new_data:
             if key != 'فیش واریزی_جدید':
                 data_to_update[key] = new_data[key]

        # 2. بررسی فایل جدید (فقط برای ادمین)
        f = request.files.get('فیش واریزی_جدید')
        new_filename = data.get('فیش واریزی') # فرض اولیه: فایل تغییر نکرده
        
        if f and f.filename != '':
            if not allowed_file(f.filename):
                session['flash_message'] = "فقط فایل‌های PNG، JPG، JPEG یا PDF مجاز هستند."
                return redirect(url_for('admin_edit', unique_id=unique_id)) # PRG
            
            # حذف فایل قدیمی در صورت وجود
            if new_filename and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], new_filename)):
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))

            # ذخیره فایل جدید
            new_filename = secure_filename(str(uuid.uuid4()) + '.' + f.filename.rsplit('.', 1)[1].lower())
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
            data_to_update['فیش واریزی'] = new_filename

        # 3. بررسی تغییر وضعیت و به‌روزرسانی تاریخ
        new_status = data_to_update.get('وضعیت')
        if new_status and new_status != old_status:
            data_to_update['تاریخ تایید/رد'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_admin_action(admin_user, 'Change Status', unique_id, f"وضعیت از {old_status} به {new_status} تغییر یافت.")
            
            # ارسال نوتیفیکیشن تلگرام به ادمین (یا بهتر است به کاربر نهایی اگر API مناسبی داشتیم)
            telegram_msg = f"<b>وضعیت ثبت نام تغییر کرد:</b>\n" \
                           f"کد رهگیری: {unique_id}\n" \
                           f"وضعیت جدید: <b>{new_status}</b>\n" \
                           f"توسط ادمین: {admin_user}"
            send_telegram_notification(telegram_msg)
        
        # 4. آپدیت نهایی در CSV
        if update_data_by_id(DB_FILE, unique_id, data_to_update):
            session['flash_message'] = "اطلاعات با موفقیت ذخیره شد."
            log_admin_action(admin_user, 'Update Data', unique_id)
            
            # --- الگوی PRG (Post/Redirect/Get) ---
            # به متد GET همین صفحه ریدایرکت می‌کنیم تا از ارسال مجدد فرم جلوگیری شود.
            return redirect(url_for('admin_edit', unique_id=unique_id))
        else:
            session['flash_message'] = "خطا در ذخیره اطلاعات."
    
    # اگر GET request باشد
    data = find_data_by_id(DB_FILE, unique_id) # بارگذاری مجدد برای اطمینان از نمایش آخرین وضعیت
    context = {'title': 'ویرایش ثبت نام ادمین', 'flash_message': flash_message, 'unique_id': unique_id, 'data': data}
    return render_template_string(template_admin_edit, **context)

@app.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    """وب‌هوک برای دریافت آپدیت‌های تلگرام (برای دکمه‌های اینلاین)."""
    # این تابع منطق دریافت کال‌بک از تلگرام را اجرا می‌کند (مثلاً تایید/رد ثبت نام).
    # به دلیل پیچیدگی نیاز به تایید در محیط عملیاتی، فعلاً یک پاسخ ساده HTTP 200 ارسال می‌شود.
    # در محیط واقعی، باید منطق زیر را اضافه کنید:
    
    # try:
    #     update = request.get_json()
    #     if 'callback_query' in update:
    #         query = update['callback_query']
    #         data_parts = query['data'].split('_')
    #         action = data_parts[0]
    #         unique_id = data_parts[1]
            
    #         # منطق تایید/رد:
    #         if action in ['approve', 'reject']:
    #             new_status = 'تایید شده' if action == 'approve' else 'رد شده'
    #             data_to_update = {'وضعیت': new_status, 'تاریخ تایید/رد': datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    #             if update_data_by_id(DB_FILE, unique_id, data_to_update):
    #                 # ارسال پاسخ به تلگرام که وضعیت تغییر کرده است
    #                 requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={'callback_query_id': query['id'], 'text': f"ثبت نام {unique_id} به {new_status} تغییر یافت."})
    #                 log_admin_action('Telegram Bot', 'Status Change', unique_id, f"وضعیت توسط دکمه تلگرام به {new_status} تغییر یافت.")
                    
    # except Exception as e:
    #     print(f"Error processing webhook: {e}")
    
    return Response('ok', status=200)

if __name__ == '__main__':
    # ایجاد پوشه آپلود در صورت عدم وجود
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # اطمینان از وجود فایل‌های CSV با هدرهای صحیح
    if not os.path.exists(DB_FILE):
        save_data(DB_FILE, [], get_fieldnames())
    if not os.path.exists(ADMIN_LOG_FILE):
        save_data(ADMIN_LOG_FILE, [], ["timestamp", "admin", "action_type", "target_id", "details"])

    app.run(debug=True)
