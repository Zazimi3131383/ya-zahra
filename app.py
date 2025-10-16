from flask import Flask, render_template_string, request, redirect, send_file
from markupsafe import Markup
import csv, os

app = Flask(__name__)

CSV_FILE = "registrations.csv"

# ---------------------- صفحه اصلی ----------------------
home_html = '''
<!doctype html>
<html lang="fa">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ثبت نام کارگاه</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"/>
<style>
body {background-color:#f2f2f2;}
.card {margin-top:30px; padding:20px; border-radius:15px; box-shadow:0 5px 15px rgba(0,0,0,0.1);}
.btn-primary:hover {background-color:#0d6efd; transform:scale(1.05); transition:0.2s;}
</style>
</head>
<body>
<div class="container">
<div class="card col-12 col-md-8 mx-auto animate__animated animate__fadeIn">
<h2 class="mb-3 text-center">فرم ثبت‌نام کارگاه</h2>
<form method="POST" action="/register">
  <div class="mb-3">
    <label>نام:</label>
    <input type="text" class="form-control" name="first_name" required>
  </div>
  <div class="mb-3">
    <label>نام خانوادگی:</label>
    <input type="text" class="form-control" name="last_name" required>
  </div>
  <div class="mb-3">
    <label>کد ملی:</label>
    <input type="text" class="form-control" name="national_code" required pattern="\\d{10}" title="کد ملی باید ۱۰ رقم باشد">
  </div>
  <div class="mb-3">
    <label>شماره دانشجویی:</label>
    <input type="text" class="form-control" name="student_number" required pattern="\\d+" title="فقط عدد وارد کنید">
  </div>
  <div class="mb-3">
    <label>نام دانشگاه:</label>
    <input type="text" class="form-control" name="university_name" required>
  </div>
  <div class="mb-3">
    <label>نام دانشکده:</label>
    <input type="text" class="form-control" name="faculty_name" required>
  </div>
  <div class="mb-3">
    <label>جنسیت:</label>
    <select class="form-select" name="gender" required>
      <option value="">انتخاب کنید</option>
      <option value="مرد">مرد</option>
      <option value="زن">زن</option>
    </select>
  </div>
  <div class="mb-3">
    <label>شماره تلفن:</label>
    <input type="text" class="form-control" name="phone_number" required pattern="\\d+" title="فقط عدد وارد کنید">
  </div>
  <div class="mb-3">
    <label>مقطع تحصیلی:</label>
    <input type="text" class="form-control" name="degree" required>
  </div>
  <div class="mb-3">
    <label>رشتهٔ تحصیلی:</label>
    <input type="text" class="form-control" name="major" required>
  </div>
  <div class="form-check mb-3">
    <input class="form-check-input" type="checkbox" id="agree" required>
    <label class="form-check-label" for="agree">
      با نکات مطالعه شده موافقم
      <ul>
        <li>حضور در جلسات به عنوان مستمع آزاد رایگان است.</li>
        <li>هزینه واریزی برای صدور گواهی به هیچ عنوان عودت داده نمی‌شود.</li>
        <li>در صورت تمایل به صدور گواهی، عکس فیش را ذخیره کنید تا در سامانه بارگذاری شود.</li>
      </ul>
    </label>
  </div>
  <button type="submit" class="btn btn-primary w-100">ثبت و ادامه</button>
</form>
</div>
</div>
</body>
</html>
'''

# ---------------------- صفحه گواهی ----------------------
certificate_html = '''
<!doctype html>
<html lang="fa">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>گواهی کارگاه</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"/>
<style>
.card {margin-top:30px; padding:20px; border-radius:15px; box-shadow:0 5px 15px rgba(0,0,0,0.1);}
.btn-primary:hover {background-color:#0d6efd; transform:scale(1.05); transition:0.2s;}
#paymentInfo {transition:0.5s;}
</style>
</head>
<body>
<div class="container">
<div class="card col-12 col-md-6 mx-auto animate__animated animate__fadeIn">
  <h2 class="mb-3 text-center">درخواست گواهی</h2>
  <form method="POST" action="/finish">
      <div class="form-check">
        <input class="form-check-input" type="radio" name="certificate" value="yes" required id="certYes">
        <label class="form-check-label" for="certYes">خواهان گواهی هستم</label>
      </div>
      <div class="form-check">
        <input class="form-check-input" type="radio" name="certificate" value="no" required id="certNo">
        <label class="form-check-label" for="certNo">خواهان گواهی نیستم (رایگان)</label>
      </div>

      <div id="paymentInfo" style="display:none; margin-top:15px;">
          <div class="alert alert-info animate__animated animate__fadeIn">
              بعد از انتخاب «خواهان گواهی هستم»، به صفحه پرداخت منتقل خواهید شد.
          </div>
      </div>

      <button type="submit" class="btn btn-primary mt-3 w-100">ثبت و ادامه</button>
  </form>
</div>
</div>

<script>
document.getElementById("certYes").addEventListener("change", function() {
    document.getElementById("paymentInfo").style.display = 'block';
});
document.getElementById("certNo").addEventListener("change", function() {
    document.getElementById("paymentInfo").style.display = 'none';
});
</script>
</body>
</html>
'''

# ---------------------- صفحه تشکر ----------------------
thanks_html = '''
<!doctype html>
<html lang="fa">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>تشکر</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
<div class="container">
<div class="card col-12 col-md-6 mx-auto mt-5 text-center">
<h2>ثبت نام شما با موفقیت انجام شد</h2>
<p>لطفا کانال زیر را در بستر تلگرام دنبال کنید:</p>
<p><strong>@article_workshop1</strong></p>
</div>
</div>
</body>
</html>
'''

# ---------------------- صفحه ادمین ----------------------
admin_html = '''
<!doctype html>
<html lang="fa">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>پنل ادمین</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"/>
<style>
.card {margin-top:30px; padding:20px; border-radius:15px; box-shadow:0 5px 15px rgba(0,0,0,0.1);}
#adminTable tbody tr:hover {background-color: #ffe082; cursor:pointer; transition:0.2s;}
</style>
</head>
<body>
<div class="container">
<div class="card col-12 mx-auto shadow-lg p-3 mb-5 bg-white rounded animate__animated animate__fadeIn">
<h2 class="mb-3 text-center">ثبت‌نامی‌ها</h2>
<div class="mb-3">
<input type="text" id="searchInput" class="form-control" placeholder="جستجو در ثبت‌نامی‌ها...">
</div>
<div class="table-responsive">
<table id="adminTable" class="table table-striped table-hover table-bordered align-middle">
<thead class="table-dark sticky-top">
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
<a href="/admin_pannel/download" class="btn btn-success btn-lg shadow-sm">دانلود CSV</a>
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
</body>
</html>
'''

# ---------------------- روت‌ها ----------------------
@app.route("/")
def home():
    return render_template_string(home_html)

@app.route("/register", methods=["POST"])
def register():
    data = {
        "نام": request.form["first_name"],
        "نام خانوادگی": request.form["last_name"],
        "کد ملی": request.form["national_code"],
        "شماره دانشجویی": request.form["student_number"],
        "نام دانشگاه": request.form["university_name"],
        "نام دانشکده": request.form["faculty_name"],
        "جنسیت": request.form["gender"],
        "شماره تلفن": request.form["phone_number"],
        "مقطع تحصیلی": request.form["degree"],
        "رشتهٔ تحصیلی": request.form["major"]
    }

    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=data.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)
    return render_template_string(certificate_html)

@app.route("/finish", methods=["POST"])
def finish():
    cert = request.form.get("certificate")
    if cert == "yes":
        # جای صفحه پرداخت
        return "<h2 style='text-align:center;margin-top:50px;'>به صفحه پرداخت منتقل می‌شوید...</h2>"
    return render_template_string(thanks_html)

@app.route("/admin_pannel")
def admin_panel():
    rows = []
    headers = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            rows = list(reader)
    return render_template_string(admin_html, rows=rows, headers=headers)

@app.route("/admin_pannel/download")
def download_csv():
    if os.path.exists(CSV_FILE):
        return send_file(CSV_FILE, as_attachment=True)
    return "فایلی برای دانلود موجود نیست."

# ---------------------- اجرا ----------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
