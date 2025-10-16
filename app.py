from flask import Flask, render_template_string, request, redirect, send_file, Response
import csv, os
from functools import wraps

app = Flask(__name__)
CSV_FILE = "registrations.csv"

# ------------------- Basic Auth برای پنل ادمین -------------------
def check_auth(username, password):
    return username == 'admin' and password == 'z.azimi3131383'

def authenticate():
    return Response(
        'لطفا وارد شوید', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# -------------------- صفحات HTML --------------------
home_html = '''
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ثبت نام کارگاه</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"/>
<style>
body {background-color:#f2f2f2;}
.card {
  margin-top:30px; padding:20px; border-radius:15px;
  box-shadow:0 5px 15px rgba(0,0,0,0.1);
  background: linear-gradient(135deg, #0dcaf0, #ffffff);
}
.form-control:focus {box-shadow:0 0 10px #0dcaf0; border-color:#0dcaf0; transition:0.3s;}
input[type="text"] {background: linear-gradient(to right, #e0f7fa, #ffffff);}
input:invalid {border: 2px solid red;}
.invalid-feedback {display:block;}
.btn-primary:hover {background-color:#0d6efd; transform:scale(1.05); transition:0.2s;}
.progress {height:20px; border-radius:10px;}
</style>
</head>
<body>
<div class="container">
<div class="card col-12 col-md-8 mx-auto animate__animated animate__fadeIn">
<h2 class="mb-3 text-center">فرم ثبت‌نام کارگاه</h2>
<div class="progress mb-4">
  <div class="progress-bar progress-bar-striped progress-bar-animated bg-info" role="progressbar" style="width:33%" id="progressBar">مرحله 1 از 3</div>
</div>

<form method="POST" action="/register" class="needs-validation" novalidate>
  <div class="mb-3"><label>نام:</label><input type="text" class="form-control" name="first_name" required></div>
  <div class="mb-3"><label>نام خانوادگی:</label><input type="text" class="form-control" name="last_name" required></div>
  <div class="mb-3"><label>کد ملی:</label><input type="text" class="form-control" name="national_code" required pattern="\\d{10}" title="کد ملی باید ۱۰ رقم باشد"><div class="invalid-feedback">کد ملی باید ۱۰ رقم باشد.</div></div>
  <div class="mb-3"><label>شماره دانشجویی:</label><input type="text" class="form-control" name="student_number" required pattern="\\d+" title="فقط عدد وارد کنید"><div class="invalid-feedback">لطفاً فقط عدد وارد کنید.</div></div>
  <div class="mb-3"><label>نام دانشگاه:</label><input type="text" class="form-control" name="university_name" required></div>
  <div class="mb-3"><label>نام دانشکده:</label><input type="text" class="form-control" name="faculty_name" required></div>
  <div class="mb-3"><label>جنسیت:</label>
    <select class="form-select" name="gender" required>
      <option value="">انتخاب کنید</option><option value="مرد">مرد</option><option value="زن">زن</option>
    </select>
  </div>
  <div class="mb-3"><label>شماره تلفن:</label><input type="text" class="form-control" name="phone_number" required pattern="\\d+" title="فقط عدد وارد کنید"><div class="invalid-feedback">لطفاً فقط عدد وارد کنید.</div></div>
  <div class="mb-3"><label>مقطع تحصیلی:</label><input type="text" class="form-control" name="degree" required></div>
  <div class="mb-3"><label>رشتهٔ تحصیلی:</label><input type="text" class="form-control" name="major" required></div>

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
  <button type="submit" class="btn btn-primary w-100 mt-3">ثبت و ادامه</button>
</form>
</div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
(() => {
  'use strict';
  const forms = document.querySelectorAll('.needs-validation')
  Array.from(forms).forEach(form => {
    form.addEventListener('submit', event => {
      if (!form.checkValidity()) event.preventDefault(), event.stopPropagation();
      form.classList.add('was-validated');
    }, false)
  })
})();
</script>
</body>
</html>
'''

# ------------------ صفحات دیگر مانند certificate_html و thanks_html مشابه قبل -------------------

# ------------------ مسیرهای اصلی -------------------
@app.route("/", methods=["GET"])
def home():
    return render_template_string(home_html)

@app.route("/register", methods=["POST"])
def register():
    data = request.form.to_dict()
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=data.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)
    return redirect("/certificate")  # ادامه به صفحه بعد

@app.route("/admin_pannel")
@requires_auth
def admin_panel():
    if not os.path.exists(CSV_FILE):
        data = []
    else:
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            data = list(reader)
    return render_template_string(admin_html, data=data)

@app.route("/download_csv")
@requires_auth
def download_csv():
    return send_file(CSV_FILE, as_attachment=True)

# ------------------ اجرا -------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
