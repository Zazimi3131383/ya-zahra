from flask import Flask, render_template_string, request, redirect, send_file, session, Response
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from functools import wraps
import csv, os, requests  # اضافه شده برای تلگرام
import json

app = Flask(__name__)
# برای استفاده از session، حتماً یک کلید امن و مخفی در محیط واقعی تنظیم کنید
app.secret_key = os.environ.get("SECRET_KEY", "a_very_secret_key_that_you_should_change")

CSV_FILE = "registrations.csv"
ADMIN_USER = "admin"
ADMIN_PASS = "z.azimi3131383"

PERSIAN_HEADERS = ["نام", "نام خانوادگی", "کد ملی", "شماره دانشجویی", "نام دانشگاه", "نام دانشکده", "جنسیت", "شماره تلفن", "مقطع تحصیلی", "رشتهٔ تحصیلی", "گواهی"]

# ---------------- Authentication -----------------
def check_auth(username, password):
    return username == ADMIN_USER and password == ADMIN_PASS

def authenticate():
    return Response('احراز هویت لازم است', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# ---------------- Telegram Notify -----------------
def send_to_telegram(data):
    """
    ارسال پیام زیبا به تلگرام بعد از ثبت‌نام
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("توکن یا شماره چت تلگرام تنظیم نشده است!")
        return
    
    # ساخت پیام زیبا با emoji و قالب خوانا
    message = "🎉 **ثبت‌نام جدید کارگاه** 🎉\n\n"
    message += f"👤 نام و نام خانوادگی: {data.get('first_name','')} {data.get('last_name','')}\n"
    message += f"🆔 کد ملی: {data.get('national_code','')}\n"
    message += f"🎓 دانشگاه: {data.get('university','')} - {data.get('faculty','')}\n"
    message += f"📚 مقطع و رشته: {data.get('degree','')} - {data.get('major','')}\n"
    message += f"📞 شماره تماس: {data.get('phone','')}\n"
    message += f"✅ درخواست گواهی: {data.get('certificate','')}\n"

    # API تلگرام
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(url, data={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    })

    # بررسی وضعیت ارسال
    if resp.status_code == 200:
        print("پیام به تلگرام با موفقیت ارسال شد ✅")
    else:
        print("ارسال پیام به تلگرام موفق نبود ❌:", resp.text)

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
        with open(CSV_FILE, 'r', newline='', encoding='utf-8-sig') as f:
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
    with open(CSV_FILE,'r',encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    
    for idx, r in enumerate(rows):
        text = f"نام: {r['نام']} {r['نام خانوادگی']}\n"
        text += f"دانشگاه: {r['نام دانشگاه']}\nرشته: {r['رشتهٔ تحصیلی']}\nگواهی: {r['گواهی']}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("مشاهده جزئیات", callback_data=f"view_{idx}"),
             InlineKeyboardButton("ویرایش", callback_data=f"edit_{idx}")]
        ])
        url = f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN')}/sendMessage"
        requests.post(url, data={
            "chat_id": chat_id,
            "text": text,
            "reply_markup": json.dumps(keyboard)
        })
 def handle_callback_query(data, chat_id):
    # data مثل: view_0 یا edit_3
    if not os.path.exists(CSV_FILE):
        return
    with open(CSV_FILE,'r',encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))

    action, idx_str = data.split('_')
    idx = int(idx_str)
    if idx >= len(rows):
        return

    if action == "view":
        r = rows[idx]
        text = "\n".join([f"{h}: {r[h]}" for h in PERSIAN_HEADERS])
    elif action == "edit":
        r = rows[idx]
        text = f"برای ویرایش این رکورد لطفاً به پنل وب مراجعه کنید:\n{r['نام']} {r['نام خانوادگی']}"
    else:
        return

    url = f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN')}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})

def handle_callback(update, context):
    query = update.callback_query
    idx = int(query.data)
    with open(CSV_FILE, 'r', newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    row = rows[idx]
    # متن جزئیات ثبت‌نام
    message = "📌 جزئیات ثبت‌نام:\n"
    for key in PERSIAN_HEADERS:
        message += f"{key}: {row.get(key,'')}\n"
    query.answer()
    query.edit_message_text(message)

# ---------------- Save to CSV -----------------
def save_to_csv(final_dict):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=PERSIAN_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
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
            "گواهی": final_dict.get("certificate", "")
        })

# ---------------- HTML Templates -----------------
rules_html = '''
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
'''

form_html = '''
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
'''

certificate_html = '''
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
    <input type="radio" name="certificate" value="خواهان گواهی هستم" id="certYes" required>
    <label for="certYes">خواهان گواهی هستم</label>
  </div>
  <div>
    <input type="radio" name="certificate" value="خواهان گواهی نیستم (رایگان)" id="certNo" required>
    <label for="certNo">خواهان گواهی نیستم (رایگان)</label>
  </div>
  <div id="paymentInfo" class="alert" style="display:none; background:rgba(255,255,255,0.2); color:#fff;">
    پس از انتخاب گواهی، به صفحه پرداخت هدایت خواهید شد.
  </div>
  <button type="submit">ثبت نهایی</button>
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
'''

thanks_html = '''
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
a.btn { display:inline-block; margin-top:1rem; background:linear-gradient(90deg,#ffdf5d,#ffb84d); color:#000; border:none; border-radius:10px; padding:0.5rem 1rem; text-decoration:none; transition:all 0.3s ease; }
a.btn:hover { background:linear-gradient(90deg,#ffd633,#ffa31a); transform:scale(1.05); }
</style>
</head>
<body>
<div class="card">
<h1>ثبت‌نام شما با موفقیت انجام شد!</h1>
<p>لطفاً کانال زیر را دنبال کنید:</p>
<a href="https://t.me/article_workshop1" class="btn" target="_blank">@article_workshop1</a>
</div>
</body>
</html>
'''

admin_html = '''
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>پنل ادمین</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css"/>
<style>
body { margin:0; font-family:'Vazir',sans-serif; background:linear-gradient(135deg,#1e3c72,#2a5298); color:#fff; display:flex; justify-content:center; align-items:flex-start; min-height:100vh; padding-top:40px; }
.card { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius:20px; padding:2rem; max-width:960px; width:90%; box-shadow:0 8px 20px rgba(0,0,0,0.2); transition:transform 0.3s ease, box-shadow 0.3s ease; }
.card:hover { transform: scale(1.01); box-shadow:0 10px 25px rgba(0,0,0,0.3); }
h3 { text-align:center; margin-bottom:1.5rem; color:#ffdf5d; }
table.dataTable thead { background: rgba(255,255,255,0.2); color:#fff; }
table.dataTable tbody tr:hover { background: rgba(255,255,255,0.1); }
table.dataTable tbody td, table.dataTable tbody th { color:#000; text-align:center; }
a.btn { margin-bottom:1rem; background: linear-gradient(90deg,#ffdf5d,#ffb84d); color:#000; border:none; border-radius:10px; padding:0.5rem 1rem; text-decoration:none; transition: all 0.3s ease; }
a.btn:hover { background: linear-gradient(90deg,#ffd633,#ffa31a); transform:scale(1.05); }
</style>
</head>
<body>
<div class="card">
<h3>پنل مدیریت</h3>
<a href="/download_csv" class="btn">دانلود CSV</a>
<a href="/download_csv_filtered?certificate=خواهان گواهی هستم" class="btn btn-info">دانلود CSV گواهی</a>
<div class="table-responsive">
<table id="adminTable" class="table table-bordered table-striped">
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
  <td>{{r[h]}}</td>
  {% endfor %}
  <td>
    <a href="/admin_delete/{{loop.index0}}" class="btn btn-danger btn-sm">حذف</a>
    <a href="/admin_edit/{{loop.index0}}" class="btn btn-warning btn-sm">ویرایش</a>
  </td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</div>
<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<script>
$(document).ready(()=>$('#adminTable').DataTable({
language:{search:"جستجو:",paginate:{next:"بعدی",previous:"قبلی"}}
}));
</script>
</body>
</html>
'''

# ---------------- Routes -----------------
@app.route("/")
def rules():
    session.clear()
    return render_template_string(rules_html)

@app.route("/start_form", methods=["POST"])
def start_form():
    session['step'] = 1
    return redirect("/form")

@app.route("/form", methods=["GET", "POST"])
def form_page():
    if session.get('step') != 1:
        return redirect("/")

    if request.method == "POST":
        session['form_data'] = request.form.to_dict()
        session['step'] = 2
        return redirect("/certificate")
    
    return render_template_string(form_html)

@app.route("/certificate", methods=["GET", "POST"])
def certificate():
    if session.get('step') != 2:
        return redirect("/")

    if request.method == "POST":
        data = session.get('form_data', {})
        data['certificate'] = request.form.get('certificate', '')
        save_to_csv(data)
        send_to_telegram(data)  # ارسال به تلگرام

        session['step'] = 3
        if data['certificate'].startswith("خواهان گواهی هستم"):
            return "<h3 style='text-align:center;margin-top:50px;'>درحال انتقال به صفحه پرداخت...</h3>"

        return redirect("/thanks")

    return render_template_string(certificate_html)

@app.route("/thanks")
def thanks():
    if session.get('step') != 3:
        return redirect("/")
    session.clear()
    return render_template_string(thanks_html)

@app.route("/admin_pannel")
@requires_auth
def admin_pannel():
    headers = PERSIAN_HEADERS
    rows = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r', newline='', encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
    return render_template_string(admin_html, headers=headers, rows=rows)

@app.route("/admin_delete/<int:idx>")
@requires_auth
def admin_delete(idx):
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE,'r',encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
        if 0 <= idx < len(rows):
            rows.pop(idx)
        with open(CSV_FILE,'w',newline='',encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=PERSIAN_HEADERS)
            writer.writeheader()
            writer.writerows(rows)
    return redirect("/admin_pannel")

@app.route("/admin_edit/<int:idx>", methods=['GET','POST'])
@requires_auth
def admin_edit(idx):
    rows=[]
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE,'r',encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
    if request.method=='POST':
        for i,key in enumerate(PERSIAN_HEADERS):
            rows[idx][key] = request.form.get(key,'')
        with open(CSV_FILE,'w',newline='',encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=PERSIAN_HEADERS)
            writer.writeheader()
            writer.writerows(rows)
        return redirect("/admin_pannel")
    # نمایش فرم ویرایش
    form_html_edit = "<form method='POST'>"
    for key in PERSIAN_HEADERS:
        form_html_edit += f"<label>{key}</label><input name='{key}' value='{rows[idx][key]}'><br>"
    form_html_edit += "<button type='submit'>ذخیره</button></form>"
    return form_html_edit

@app.route("/download_csv")
@requires_auth
def download_csv():
    return send_file(CSV_FILE, as_attachment=True)

@app.route("/download_csv_filtered")
@requires_auth
def download_csv_filtered():
    filter_cert = request.args.get("certificate","")
    rows=[]
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE,'r',encoding='utf-8-sig') as f:
            all_rows = list(csv.DictReader(f))
        if filter_cert:
            rows = [r for r in all_rows if r["گواهی"]==filter_cert]
        else:
            rows = all_rows
    # ایجاد CSV موقت
    tmp_file = "filtered.csv"
    with open(tmp_file,'w',newline='',encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=PERSIAN_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    return send_file(tmp_file, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)



