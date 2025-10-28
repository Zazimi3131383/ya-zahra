from flask import Flask, render_template_string, request, redirect, send_file, session, Response
from functools import wraps
import csv, os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change_this_secret_at_prod")

CSV_FILE = "registrations.csv"
ADMIN_USER = "admin"
ADMIN_PASS = "z.azimi3131383"

# 🔒 تعیین وضعیت ظرفیت کارگاه (True = فعال، False = غیرفعال)
WORKSHOP_ACTIVE = False  # اینجا False یعنی ظرفیت پر شده است

# دکوراتور برای بررسی لاگین ادمین
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/admin")
        return f(*args, **kwargs)
    return decorated_function

# صفحه اصلی (فرم ثبت نام)
@app.route("/", methods=["GET", "POST"])
def register():
    if not WORKSHOP_ACTIVE:
        return render_template_string('''
            <html lang="fa" dir="rtl">
            <head>
                <meta charset="UTF-8">
                <title>پرسشنامه غیرفعال</title>
                <style>
                    body { font-family: 'Tahoma'; background-color: #f9f9f9; text-align: center; padding-top: 100px; }
                    .box { background: white; border-radius: 15px; padding: 40px; width: 400px; margin: auto; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
                    h2 { color: #c0392b; }
                </style>
            </head>
            <body>
                <div class="box">
                    <h2>این پرسشنامه غیرفعال است و امکان ثبت پاسخ ندارد</h2>
                </div>
            </body>
            </html>
        ''')

    if request.method == "POST":
        data = [
            request.form.get("name"),
            request.form.get("phone"),
            request.form.get("field"),
            request.form.get("grade"),
        ]
        file_exists = os.path.isfile(CSV_FILE)
        with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["نام", "شماره تماس", "رشته", "پایه"])
            writer.writerow(data)
        return redirect("/success")

    return render_template_string('''
        <html lang="fa" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <title>ثبت نام کارگاه مقاله نویسی</title>
            <style>
                body { font-family: 'Tahoma'; background-color: #eef2f3; }
                form { background: white; border-radius: 10px; padding: 30px; width: 400px; margin: 100px auto; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
                label { display: block; margin-top: 15px; }
                input, select { width: 100%; padding: 8px; margin-top: 5px; }
                button { background-color: #3498db; color: white; border: none; padding: 10px; margin-top: 20px; width: 100%; cursor: pointer; border-radius: 5px; }
                button:hover { background-color: #2980b9; }
            </style>
        </head>
        <body>
            <form method="POST">
                <h2 style="text-align:center;color:#2c3e50;">فرم ثبت نام کارگاه مقاله‌نویسی</h2>
                <label>نام و نام خانوادگی:</label>
                <input type="text" name="name" required>

                <label>شماره تماس:</label>
                <input type="text" name="phone" pattern="[0-9۰-۹]+" inputmode="numeric" required>

                <label>رشته:</label>
                <input type="text" name="field" required>

                <label>پایه تحصیلی:</label>
                <select name="grade" required>
                    <option value="">انتخاب کنید</option>
                    <option value="هفتم">هفتم</option>
                    <option value="هشتم">هشتم</option>
                    <option value="نهم">نهم</option>
                </select>

                <button type="submit">ارسال</button>
            </form>
        </body>
        </html>
    ''')

# صفحه موفقیت
@app.route("/success")
def success():
    if not WORKSHOP_ACTIVE:
        return redirect("/")
    return render_template_string('''
        <html lang="fa" dir="rtl">
        <head><meta charset="UTF-8"><title>ثبت موفق</title></head>
        <body style="text-align:center;font-family:Tahoma;padding-top:100px;">
            <h2 style="color:green;">✅ ثبت نام شما با موفقیت انجام شد!</h2>
            <a href="/">بازگشت به صفحه اصلی</a>
        </body>
        </html>
    ''')

# صفحه ادمین برای مشاهده داده‌ها
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USER and request.form.get("password") == ADMIN_PASS:
            session["logged_in"] = True
            return redirect("/panel")
    return render_template_string('''
        <html lang="fa" dir="rtl">
        <head><meta charset="UTF-8"><title>ورود مدیر</title></head>
        <body style="font-family:Tahoma;text-align:center;padding-top:100px;">
            <form method="POST" style="display:inline-block;background:#fff;padding:30px;border-radius:10px;box-shadow:0 0 10px rgba(0,0,0,0.1);">
                <h3>ورود مدیر</h3>
                <input name="username" placeholder="نام کاربری"><br><br>
                <input type="password" name="password" placeholder="رمز عبور"><br><br>
                <button type="submit">ورود</button>
            </form>
        </body>
        </html>
    ''')

@app.route("/panel")
@login_required
def panel():
    if not os.path.isfile(CSV_FILE):
        return "هنوز داده‌ای ثبت نشده است."

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    table = "<table border='1' style='margin:auto;border-collapse:collapse;'>"
    for row in rows:
        table += "<tr>" + ''.join([f"<td style='padding:8px;'>{cell}</td>" for cell in row]) + "</tr>"
    table += "</table>"

    return f"<h2 style='text-align:center'>📋 لیست ثبت‌نام‌ها</h2>{table}"

if __name__ == "__main__":
    app.run(debug=True)
