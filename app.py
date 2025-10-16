from flask import Flask, render_template_string, request, redirect
import csv
import os

app = Flask(__name__)

# مسیر فایل CSV برای ذخیره پاسخ‌ها
CSV_FILE = "responses.csv"

# تابع ذخیره داده‌ها در CSV
def save_to_csv(data):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)

# صفحه اول: توضیحات و تیک مطالعه
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        agree = request.form.get("agree")
        if agree == "on":
            return redirect("/form")
        else:
            return render_template_string("""
                <h3>لطفاً برای ادامه تیک مطالعه موارد فوق را بزنید.</h3>
                <a href="/">بازگشت</a>
            """)
    return render_template_string("""
    <h2>با سلام</h2>
    <p>لطفا نکات زیر را به دقت مطالعه فرمایید:</p>
    <ol>
        <li>حضور در جلسات به عنوان مستمع آزاد بدون درخواست صدور گواهی، رایگان است.</li>
        <li>هزینه واریزی برای صدور گواهی به هیچ عنوان عودت داده نمی‌شود.</li>
        <li>در صورت تمایل به صدور گواهی، پس از ثبت اطلاعات و واریز هزینه، عکس فیش را ذخیره کرده و در سامانه بارگذاری کنید.</li>
    </ol>
    <form method="POST">
        <input type="checkbox" name="agree"> موارد فوق را مطالعه کردم<br><br>
        <button type="submit">تایید و ادامه</button>
    </form>
    """)

# صفحه دوم: اطلاعات شخصی
@app.route("/form", methods=["GET", "POST"])
def form_page():
    if request.method == "POST":
        # جمع‌آوری اطلاعات
        data = {
            "نام": request.form.get("first_name"),
            "نام خانوادگی": request.form.get("last_name"),
            "کد ملی": request.form.get("national_code"),
            "شماره دانشجویی": request.form.get("student_number"),
            "نام دانشگاه": request.form.get("university"),
            "نام دانشکده": request.form.get("faculty"),
            "جنسیت": request.form.get("gender"),
            "شماره تلفن": request.form.get("phone"),
            "مقطع تحصیلی": request.form.get("level"),
            "رشته تحصیلی": request.form.get("major")
        }
        # ذخیره موقت در session یا فایل ساده
        # برای سادگی، می‌گذاریم در global dict (ساده‌ترین روش برای مثال)
        request.environ['form_data'] = data
        return redirect("/certificate")
    return render_template_string("""
    <h2>فرم اطلاعات شخصی</h2>
    <form method="POST">
        <label>نام:</label><br>
        <input type="text" name="first_name" required><br>
        <label>نام خانوادگی:</label><br>
        <input type="text" name="last_name" required><br>
        <label>کد ملی:</label><br>
        <input type="number" name="national_code" required><br>
        <label>شماره دانشجویی:</label><br>
        <input type="number" name="student_number" required><br>
        <label>نام دانشگاه:</label><br>
        <input type="text" name="university" required><br>
        <label>نام دانشکده:</label><br>
        <input type="text" name="faculty" required><br>
        <label>جنسیت:</label><br>
        <select name="gender" required>
            <option value="">انتخاب کنید</option>
            <option value="مرد">مرد</option>
            <option value="زن">زن</option>
        </select><br>
        <label>شماره تلفن:</label><br>
        <input type="tel" name="phone" required><br>
        <label>مقطع تحصیلی:</label><br>
        <select name="level" required>
            <option value="">انتخاب کنید</option>
            <option value="کارشناسی">کارشناسی</option>
            <option value="ارشد">ارشد</option>
            <option value="دکتری">دکتری</option>
        </select><br>
        <label>رشته تحصیلی:</label><br>
        <input type="text" name="major" required><br><br>
        <button type="submit">ادامه</button>
    </form>
    """)

# صفحه سوم: سوال شرطی گواهی
@app.route("/certificate", methods=["GET", "POST"])
def certificate_page():
    if request.method == "POST":
        choice = request.form.get("certificate")
        # گرفتن داده‌های فرم دوم
        data = request.environ.get('form_data', {})
        data["گواهی"] = choice
        save_to_csv(data)
        if choice == "yes":
            return redirect("https://zarinpal.com/payment-link")  # لینک پرداخت
        else:
            return redirect("/thankyou")
    return render_template_string("""
    <h2>درخواست گواهی</h2>
    <form method="POST">
        <input type="radio" name="certificate" value="yes" required> خواهان گواهی هستم<br>
        <input type="radio" name="certificate" value="no" required> خواهان گواهی نیستم (رایگان)<br><br>
        <button type="submit">ثبت و ادامه</button>
    </form>
    """)

# صفحه تشکر و لینک تلگرام
@app.route("/thankyou")
def thankyou():
    return render_template_string("""
    <h2>ثبت شما با موفقیت انجام شد!</h2>
    <p>لطفا کانال زیر را در بستر تلگرام دنبال کنید:</p>
    <a href="https://t.me/article_workshop1">@article_workshop1</a>
    <p>سپاس از همراهی شما.</p>
    """)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
