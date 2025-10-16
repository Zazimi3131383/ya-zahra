from flask import Flask, render_template_string, request, redirect
import csv
import os

app = Flask(__name__)
CSV_FILE = "responses.csv"

# تابع ذخیره داده‌ها
def save_to_csv(data):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)

# قالب پایه با Bootstrap
base_head = """
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body { font-family: Vazir, Tahoma, sans-serif; background-color: #f7f7f7; direction: rtl; }
.card { margin-top: 50px; padding: 20px; border-radius: 10px; background-color: #fff; box-shadow: 0px 5px 15px rgba(0,0,0,0.1); }
button { margin-top: 15px; }
</style>
"""

# صفحه اول
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        agree = request.form.get("agree")
        if agree == "on":
            return redirect("/form")
        else:
            return render_template_string(base_head + """
            <div class="container">
                <div class="card mx-auto col-md-6 text-center">
                    <h3>لطفاً برای ادامه تیک مطالعه موارد فوق را بزنید.</h3>
                    <a href="/" class="btn btn-warning mt-3">بازگشت</a>
                </div>
            </div>
            """)
    return render_template_string(base_head + """
    <div class="container">
      <div class="card mx-auto col-md-6">
        <h2 class="mb-3">با سلام</h2>
        <p>لطفا نکات زیر را به دقت مطالعه فرمایید:</p>
        <ol>
            <li>حضور در جلسات به عنوان مستمع آزاد بدون درخواست صدور گواهی، رایگان است.</li>
            <li>هزینه واریزی برای صدور گواهی به هیچ عنوان عودت داده نمی‌شود.</li>
            <li>در صورت تمایل به صدور گواهی، پس از ثبت اطلاعات و واریز هزینه، عکس فیش را ذخیره کرده و در سامانه بارگذاری کنید.</li>
        </ol>
        <form method="POST">
            <div class="form-check">
              <input class="form-check-input" type="checkbox" name="agree" id="agree">
              <label class="form-check-label" for="agree">موارد فوق را مطالعه کردم</label>
            </div>
            <button type="submit" class="btn btn-primary">تایید و ادامه</button>
        </form>
      </div>
    </div>
    """)

# صفحه دوم: اطلاعات شخصی
@app.route("/form", methods=["GET", "POST"])
def form_page():
    if request.method == "POST":
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
        request.environ['form_data'] = data
        return redirect("/certificate")
    return render_template_string(base_head + """
    <div class="container">
      <div class="card mx-auto col-md-6">
        <h2 class="mb-3">فرم اطلاعات شخصی</h2>
        <form method="POST">
            <div class="mb-3">
              <label class="form-label">نام:</label>
              <input type="text" class="form-control" name="first_name" required>
            </div>
            <div class="mb-3">
              <label class="form-label">نام خانوادگی:</label>
              <input type="text" class="form-control" name="last_name" required>
            </div>
            <div class="mb-3">
              <label class="form-label">کد ملی:</label>
              <input type="number" class="form-control" name="national_code" required>
            </div>
            <div class="mb-3">
              <label class="form-label">شماره دانشجویی:</label>
              <input type="number" class="form-control" name="student_number" required>
            </div>
            <div class="mb-3">
              <label class="form-label">نام دانشگاه:</label>
              <input type="text" class="form-control" name="university" required>
            </div>
            <div class="mb-3">
              <label class="form-label">نام دانشکده:</label>
              <input type="text" class="form-control" name="faculty" required>
            </div>
            <div class="mb-3">
              <label class="form-label">جنسیت:</label>
              <select class="form-select" name="gender" required>
                <option value="">انتخاب کنید</option>
                <option value="مرد">مرد</option>
                <option value="زن">زن</option>
              </select>
            </div>
            <div class="mb-3">
              <label class="form-label">شماره تلفن:</label>
              <input type="tel" class="form-control" name="phone" required>
            </div>
            <div class="mb-3">
              <label class="form-label">مقطع تحصیلی:</label>
              <select class="form-select" name="level" required>
                <option value="">انتخاب کنید</option>
                <option value="کارشناسی">کارشناسی</option>
                <option value="ارشد">ارشد</option>
                <option value="دکتری">دکتری</option>
              </select>
            </div>
            <div class="mb-3">
              <label class="form-label">رشته تحصیلی:</label>
              <input type="text" class="form-control" name="major" required>
            </div>
            <button type="submit" class="btn btn-success">ادامه</button>
        </form>
      </div>
    </div>
    """)

# صفحه سوم: سوال شرطی گواهی
@app.route("/certificate", methods=["GET", "POST"])
def certificate_page():
    if request.method == "POST":
        choice = request.form.get("certificate")
        data = request.environ.get('form_data', {})
        data["گواهی"] = choice
        save_to_csv(data)
        if choice == "yes":
            return redirect("https://zarinpal.com/payment-link")  # لینک پرداخت
        else:
            return redirect("/thankyou")
    return render_template_string(base_head + """
    <div class="container">
      <div class="card mx-auto col-md-6">
        <h2 class="mb-3">درخواست گواهی</h2>
        <form method="POST">
            <div class="form-check">
              <input class="form-check-input" type="radio" name="certificate" value="yes" required>
              <label class="form-check-label">خواهان گواهی هستم</label>
            </div>
            <div class="form-check">
              <input class="form-check-input" type="radio" name="certificate" value="no" required>
              <label class="form-check-label">خواهان گواهی نیستم (رایگان)</label>
            </div>
            <button type="submit" class="btn btn-primary mt-3">ثبت و ادامه</button>
        </form>
      </div>
    </div>
    """)

# صفحه تشکر و لینک تلگرام
@app.route("/thankyou")
def thankyou():
    return render_template_string(base_head + """
    <div class="container">
      <div class="card mx-auto col-md-6 text-center">
        <h2 class="mb-3">ثبت شما با موفقیت انجام شد!</h2>
        <p>لطفا کانال زیر را در بستر تلگرام دنبال کنید:</p>
        <a href="https://t.me/article_workshop1" class="btn btn-info">@article_workshop1</a>
        <p class="mt-3">سپاس از همراهی شما.</p>
      </div>
    </div>
    """)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
