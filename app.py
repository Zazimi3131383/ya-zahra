from flask import Flask, render_template_string, request, redirect, send_file, Markup
import csv
import os

app = Flask(__name__)
CSV_FILE = "responses.csv"
ADMIN_PASSWORD = "1234"  # رمز ورود ادمین

# ---------------------- ذخیره داده‌ها ----------------------
def save_to_csv(data):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)

# ---------------------- قالب پایه ----------------------
base_head = """
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/gh/rastikerdar/vazir-font@v33.003/Vazir-font-face.css" rel="stylesheet" type="text/css" />
<style>
body { font-family: Vazir, Tahoma, sans-serif; background: linear-gradient(to bottom, #e0f7fa, #ffffff); direction: rtl; }
.card { margin-top: 50px; padding: 30px; border-radius: 15px; background-color: #ffffffcc; box-shadow: 0px 8px 25px rgba(0,0,0,0.15); transition: transform 0.2s; }
.card:hover { transform: translateY(-5px); }
button { margin-top: 20px; border-radius: 8px; box-shadow: 0px 4px 10px rgba(0,0,0,0.2); }
button:hover { opacity: 0.9; }
.form-control { border-radius: 8px; }
.table-responsive { max-height: 500px; overflow-y: auto; }
#adminTable th, #adminTable td { text-align: center; vertical-align: middle; }
#adminTable tbody tr:hover { background-color: #ffe082; cursor: pointer; transition: 0.2s; }
</style>
"""

# ---------------------- صفحه اول ----------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        agree = request.form.get("agree")
        if agree == "on":
            return redirect("/form")
        else:
            return render_template_string(base_head + """
            <div class="container">
                <div class="card col-12 col-md-6 mx-auto text-center">
                    <h3>لطفاً برای ادامه تیک مطالعه موارد فوق را بزنید.</h3>
                    <a href="/" class="btn btn-warning mt-3">بازگشت</a>
                </div>
            </div>
            """)
    return render_template_string(base_head + """
    <div class="container">
      <div class="card col-12 col-md-6 mx-auto">
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

# ---------------------- فرم اطلاعات شخصی ----------------------
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
      <div class="card col-12 col-md-6 mx-auto">
        <h2 class="mb-3">فرم اطلاعات شخصی</h2>
        <form method="POST">
            {% for label, name in [('نام','first_name'),('نام خانوادگی','last_name')] %}
            <div class="mb-3">
              <label class="form-label">{{ label }}:</label>
              <input type="text" class="form-control" name="{{ name }}" required>
            </div>
            {% endfor %}

            <div class="mb-3">
              <label class="form-label">کد ملی:</label>
              <input type="text" class="form-control" name="national_code" required pattern="\d{10}" title="کد ملی باید ۱۰ رقم باشد">
            </div>

            <div class="mb-3">
              <label class="form-label">شماره دانشجویی:</label>
              <input type="text" class="form-control" name="student_number" required pattern="\d+" title="فقط اعداد مجاز هستند">
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
              <input type="text" class="form-control" name="phone" required pattern="\d+" title="فقط اعداد مجاز هستند">
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

# ---------------------- صفحه درخواست گواهی ----------------------
@app.route("/certificate", methods=["GET", "POST"])
def certificate_page():
    if request.method == "POST":
        choice = request.form.get("certificate")
        data = request.environ.get('form_data', {})
        data["گواهی"] = choice
        save_to_csv(data)
        if choice == "yes":
            return redirect("https://zarinpal.com/payment-link")  # لینک پرداخت واقعی
        else:
            return redirect("/thankyou")
    return render_template_string(base_head + """
    <div class="container">
      <div class="card col-12 col-md-6 mx-auto">
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

# ---------------------- صفحه تشکر ----------------------
@app.route("/thankyou")
def thankyou():
    return render_template_string(base_head + """
    <div class="container">
      <div class="card col-12 col-md-6 mx-auto text-center">
        <h2 class="mb-3">ثبت شما با موفقیت انجام شد!</h2>
        <p>لطفا کانال زیر را در بستر تلگرام دنبال کنید:</p>
        <a href="https://t.me/article_workshop1" class="btn btn-info">@article_workshop1</a>
        <p class="mt-3">سپاس از همراهی شما.</p>
      </div>
    </div>
    """)

# ---------------------- ورود ادمین ----------------------
@app.route("/admin_pannel", methods=["GET", "POST"])
def admin_panel():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ADMIN_PASSWORD:
            return redirect("/admin_pannel/view")
        else:
            return render_template_string(base_head + """
            <div class="container">
                <div class="card col-12 col-md-6 mx-auto text-center">
                    <h3>رمز عبور اشتباه است!</h3>
                    <a href="/admin_pannel" class="btn btn-warning mt-3">بازگشت</a>
                </div>
            </div>
            """)
    return render_template_string(base_head + """
    <div class="container">
      <div class="card col-12 col-md-6 mx-auto text-center">
        <h2 class="mb-3">ورود به صفحه ادمین</h2>
        <form method="POST">
            <input type="password" class="form-control mb-3" name="password" placeholder="رمز عبور">
            <button type="submit" class="btn btn-primary">ورود</button>
        </form>
      </div>
    </div>
    """)

# ---------------------- مشاهده جدول ادمین و دانلود CSV ----------------------
@app.route("/admin_pannel/view")
def admin_view():
    if not os.path.exists(CSV_FILE):
        return render_template_string(base_head + """
        <div class="container">
            <div class="card col-12 mx-auto text-center">
                <h3>هیچ ثبت‌نامی هنوز انجام نشده.</h3>
            </div>
        </div>
        """)

    rows = []
    with open(CSV_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        return "<h3>هیچ ثبت‌نامی وجود ندارد.</h3>"

    headers = rows[0].keys()

    return render_template_string(base_head + """
    <div class="container">
        <div class="card col-12 mx-auto" style="overflow-x:auto;">
            <h2 class="mb-3 text-center">ثبت‌نامی‌ها</h2>
            <div class="mb-3">
              <input type="text" id="searchInput" class="form-control" placeholder="جستجو در ثبت‌نامی‌ها...">
            </div>
            <div class="table-responsive">
                <table id="adminTable" class="table table-striped table-bordered table-hover">
                    <thead class="table-primary">
                        <tr>
                            {% for header in headers %}<th>{{ header }}</th>{% endfor %}
                        </tr>
                    </thead>
                    <tbody>
                        {% for row in rows %}
                        <tr>
                            {% for value in row.values() %}
                            <td>{{ value }}</td>
                            {% endfor %}
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            <div class="text-center mt-3">
                <a href="/admin_pannel/download" class="btn btn-success">دانلود CSV</a>
            </div>
        </div>
    </div>

    <script>
    document.getElementById("searchInput").addEventListener("keyup", function() {
        var filter = this.value.toLowerCase();
        var rows = document.querySelectorAll("#adminTable tbody tr");
        rows.forEach(row => {
            row.style.display = Array.from(row.cells).some(
                cell => cell.textContent.toLowerCase().includes(filter)
            ) ? "" : "none";
        });
    });
    </script>
    """, rows=rows, headers=headers)

@app.route("/admin_pannel/download")
def download_csv():
    if os.path.exists(CSV_FILE):
        return send_file(CSV_FILE, as_attachment=True)
    return "فایلی برای دانلود موجود نیست."

# ---------------------- اجرا ----------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
