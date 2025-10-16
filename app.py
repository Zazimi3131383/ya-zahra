from flask import Flask, render_template_string, request, redirect, send_file, session, Response
from functools import wraps
import csv, os

app = Flask(__name__)
# برای امنیت در production مقدار SECRET_KEY را در تنظیمات Render قرار بده
app.secret_key = os.environ.get("SECRET_KEY", "change_this_secret_at_prod")

CSV_FILE = "registrations.csv"

# -------- Admin Basic Auth ----------
ADMIN_USER = "admin"
ADMIN_PASS = "z.azimi3131383"

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

# -------- Persian headers for CSV (consistent order) ----------
PERSIAN_HEADERS = ["نام", "نام خانوادگی", "کد ملی", "شماره دانشجویی",
                   "نام دانشگاه", "نام دانشکده", "جنسیت", "شماره تلفن",
                   "مقطع تحصیلی", "رشتهٔ تحصیلی", "گواهی"]

# -------- Save to CSV with BOM (utf-8-sig) so Excel reads correctly ----------
def save_to_csv(final_dict):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=PERSIAN_HEADERS)
        if not file_exists:
            writer.writeheader()
        row = {
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
        }
        writer.writerow(row)

# -------------------- HTML templates (embedded) --------------------
# All pages: RTL, gradient backgrounds, validation and UX improvements.
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
body { background: linear-gradient(180deg,#e6f7ff,#ffffff); font-family: Tahoma, sans-serif; }
.card {
  margin-top:30px; padding:20px; border-radius:15px;
  box-shadow:0 8px 30px rgba(0,0,0,0.08);
  background: linear-gradient(135deg,#ffffff,#f4fdff);
}
.form-control:focus { box-shadow:0 0 10px rgba(13,110,253,0.12); border-color:#0d6efd; transition:0.25s; }
input[type="text"] { background: linear-gradient(to right,#f8ffff,#ffffff); }
input:invalid { border-color: #dc3545; box-shadow: 0 0 6px rgba(220,53,69,0.08); }
.invalid-feedback { display:block; }
.btn-primary:hover { transform: translateY(-2px); box-shadow:0 6px 18px rgba(13,110,253,0.08); }
.progress { height:18px; border-radius:10px; }
.admin-btn { position: absolute; top: 14px; left: 14px; z-index: 10; }
.text-end label { float: right; }
ul { padding-inline-start: 18px; margin-bottom: 0; }
@media (max-width:575px){
  .card { padding:16px; margin-top:15px; }
}
</style>
</head>
<body>
<div class="container position-relative">
  <!-- admin button (goes to protected panel, browser will ask for credentials) -->
  <a href="/admin_pannel" class="btn btn-outline-dark admin-btn">ورود ادمین</a>

  <div class="card col-12 col-md-8 mx-auto animate__animated animate__fadeIn">
    <h2 class="mb-3 text-center">فرم ثبت‌نام کارگاه</h2>

    <div class="progress mb-3">
      <div class="progress-bar progress-bar-striped progress-bar-animated bg-info" id="progressBar" role="progressbar" style="width:33%">مرحله 1 از 3</div>
    </div>

    <form method="POST" action="/register" class="needs-validation" novalidate>
      <div class="mb-3 text-end">
        <label class="form-label">نام:</label>
        <input type="text" class="form-control" name="first_name" required>
      </div>

      <div class="mb-3 text-end">
        <label class="form-label">نام خانوادگی:</label>
        <input type="text" class="form-control" name="last_name" required>
      </div>

      <div class="mb-3 text-end">
        <label class="form-label">کد ملی:</label>
        <input type="text" class="form-control" name="national_code" required pattern="\\d{10}" title="کد ملی باید ۱۰ رقم باشد">
        <div class="invalid-feedback">کد ملی باید ۱۰ رقم باشد.</div>
      </div>

      <div class="mb-3 text-end">
        <label class="form-label">شماره دانشجویی:</label>
        <input type="text" class="form-control" name="student_number" required pattern="\\d+" title="فقط عدد وارد کنید">
        <div class="invalid-feedback">لطفاً فقط عدد وارد کنید.</div>
      </div>

      <div class="mb-3 text-end">
        <label class="form-label">نام دانشگاه:</label>
        <input type="text" class="form-control" name="university" required>
      </div>

      <div class="mb-3 text-end">
        <label class="form-label">نام دانشکده:</label>
        <input type="text" class="form-control" name="faculty" required>
      </div>

      <div class="mb-3 text-end">
        <label class="form-label">جنسیت:</label>
        <select class="form-select" name="gender" required>
          <option value="">انتخاب کنید</option>
          <option value="مرد">مرد</option>
          <option value="زن">زن</option>
        </select>
      </div>

      <div class="mb-3 text-end">
        <label class="form-label">شماره تلفن:</label>
        <input type="text" class="form-control" name="phone" required pattern="\\d+" title="فقط عدد وارد کنید">
        <div class="invalid-feedback">لطفاً فقط عدد وارد کنید.</div>
      </div>

      <div class="mb-3 text-end">
        <label class="form-label">مقطع تحصیلی:</label>
        <select class="form-select" name="degree" required>
          <option value="">انتخاب کنید</option>
          <option value="کارشناسی">کارشناسی</option>
          <option value="کارشناسی ارشد">کارشناسی ارشد</option>
          <option value="دکتری">دکتری</option>
          <option value="دیگر">دیگر</option>
        </select>
      </div>

      <div class="mb-3 text-end">
        <label class="form-label">رشتهٔ تحصیلی:</label>
        <input type="text" class="form-control" name="major" required>
      </div>

      <div class="form-check mb-3 text-end">
        <input class="form-check-input" type="checkbox" id="agree" required>
        <label class="form-check-label" for="agree">
          موارد زیر را مطالعه کردم:
          <ul class="mb-0">
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

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
(() => {
  'use strict';
  const forms = document.querySelectorAll('.needs-validation');
  Array.from(forms).forEach(form => {
    form.addEventListener('submit', event => {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      } else {
        // UX: update progress before redirect
        var pb = document.getElementById("progressBar");
        if (pb) { pb.style.width = "66%"; pb.innerText = "مرحله 2 از 3"; }
      }
      form.classList.add('was-validated');
    }, false);
  });
})();
</script>
</body>
</html>
'''

certificate_html = '''
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>درخواست گواهی</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body { background: linear-gradient(180deg,#e6f7ff,#ffffff); font-family: Tahoma, sans-serif; }
.card { margin-top:30px; padding:20px; border-radius:15px; box-shadow:0 8px 30px rgba(0,0,0,0.06); background: linear-gradient(135deg,#ffffff,#f4fdff); }
.notice { transition:0.4s; }
</style>
</head>
<body>
<div class="container">
  <div class="card col-12 col-md-6 mx-auto animate__animated animate__fadeIn">
    <h2 class="text-center mb-3">درخواست گواهی</h2>
    <div class="progress mb-3">
      <div class="progress-bar bg-info" style="width:100%">مرحله 3 از 3</div>
    </div>

    <form method="POST" action="/finish" id="certForm">
      <div class="form-check text-end">
        <input class="form-check-input" type="radio" name="certificate" value="خواهان گواهی هستم" required id="certYes">
        <label class="form-check-label" for="certYes">خواهان گواهی هستم</label>
      </div>
      <div class="form-check text-end">
        <input class="form-check-input" type="radio" name="certificate" value="خواهان گواهی نیستم (رایگان)" required id="certNo">
        <label class="form-check-label" for="certNo">خواهان گواهی نیستم (رایگان)</label>
      </div>

      <div id="paymentInfo" style="display:none; margin-top:12px;" class="notice">
        <div class="alert alert-info">پس از انتخاب «خواهان گواهی هستم»، به صفحه پرداخت منتقل خواهید شد. لطفاً فیش پرداخت را نگه دارید.</div>
      </div>

      <button type="submit" class="btn btn-primary w-100 mt-3">ثبت و ادامه</button>
    </form>
  </div>
</div>

<script>
document.getElementById("certYes").addEventListener("change", function(){ document.getElementById("paymentInfo").style.display='block'; });
document.getElementById("certNo").addEventListener("change", function(){ document.getElementById("paymentInfo").style.display='none'; });
</script>
</body>
</html>
'''

thanks_html = '''
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>تشکر</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body { background: linear-gradient(180deg,#e6f7ff,#ffffff); font-family: Tahoma, sans-serif; }
.card { margin-top:50px; padding:30px; border-radius:15px; box-shadow:0 8px 30px rgba(0,0,0,0.06); background: linear-gradient(135deg,#ffffff,#f4fff8); }
</style>
</head>
<body>
<div class="container">
  <div class="card col-12 col-md-6 mx-auto text-center animate__animated animate__fadeIn">
    <h2 class="mb-3">ثبت شما با موفقیت انجام شد!</h2>
    <p>لطفا کانال زیر را در بستر تلگرام دنبال کنید:</p>
    <a href="https://t.me/article_workshop1" class="btn btn-info">@article_workshop1</a>
    <p class="mt-3">سپاس از همراهی شما.</p>
  </div>
</div>
</body>
</html>
'''

admin_html = '''
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>پنل ادمین</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css"/>
<style>
body { background: linear-gradient(180deg,#f0f9ff,#ffffff); font-family: Tahoma, sans-serif; }
.card { margin-top:30px; padding:18px; border-radius:12px; box-shadow:0 10px 30px rgba(0,0,0,0.06); background: linear-gradient(135deg,#ffffff,#f7ffff); }
#adminTable tbody tr:hover { background-color:#e0f7fa; transition:0.2s; }
th, td { text-align:center; vertical-align:middle; }
</style>
</head>
<body>
<div class="container">
  <div class="card col-12 animate__animated animate__fadeIn">
    <h2 class="text-center mb-3">پنل مدیریت ثبت‌نام‌ها</h2>
    <div class="mb-3 text-end">
      <a href="/download_csv" class="btn btn-success">دانلود CSV</a>
    </div>
    <div class="table-responsive">
      <table id="adminTable" class="table table-striped table-bordered" dir="rtl">
        <thead class="table-dark">
          <tr>
            {% for h in headers %}<th>{{h}}</th>{% endfor %}
          </tr>
        </thead>
        <tbody>
          {% for r in rows %}
          <tr>
            {% for h in headers %}<td>{{ r[h] }}</td>{% endfor %}
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>

<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<script>
$(document).ready(function(){
  $('#adminTable').DataTable({
    "paging": true,
    "searching": true,
    "info": false,
    "scrollX": true,
    "language": {
      "search": "جستجو:",
      "paginate": { "next": "بعدی", "previous": "قبلی" },
      "zeroRecords": "هیچ موردی یافت نشد"
    }
  });
});
</script>
</body>
</html>
'''

# ---------------------- Routes & Logic ----------------------

@app.route("/", methods=["GET"])
def home():
    return render_template_string(home_html)

@app.route("/register", methods=["POST"])
def register():
    # save form data into session for final save after certificate choice
    form = request.form.to_dict()
    session['form_data'] = {
        "first_name": form.get("first_name","").strip(),
        "last_name": form.get("last_name","").strip(),
        "national_code": form.get("national_code","").strip(),
        "student_number": form.get("student_number","").strip(),
        "university": form.get("university","").strip(),
        "faculty": form.get("faculty","").strip(),
        "gender": form.get("gender","").strip(),
        "phone": form.get("phone","").strip(),
        "degree": form.get("degree","").strip(),
        "major": form.get("major","").strip()
    }
    return redirect("/certificate")

@app.route("/certificate", methods=["GET"])
def certificate():
    if 'form_data' not in session:
        return redirect("/")
    return render_template_string(certificate_html)

@app.route("/finish", methods=["POST"])
def finish():
    if 'form_data' not in session:
        return redirect("/")
    cert_choice = request.form.get("certificate", "")
    data = session.get('form_data', {})
    data['certificate'] = cert_choice
    save_to_csv(data)
    # clear session
    session.pop('form_data', None)
    # if certificate requested -> simulate redirect to payment (replace with real gateway link)
    if cert_choice == "خواهان گواهی هستم":
        return "<h3 style='text-align:center;margin-top:50px;'>درحال انتقال به صفحه پرداخت... (برای تست اینجا پیام نمایش داده می‌شود)</h3>"
    return redirect("/thanks")

@app.route("/thanks", methods=["GET"])
def thanks():
    return render_template_string(thanks_html)

# Admin panel (protected)
@app.route("/admin_pannel", methods=["GET"])
@requires_auth
def admin_pannel():
    rows = []
    headers = PERSIAN_HEADERS
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    return render_template_string(admin_html, rows=rows, headers=headers)

@app.route("/download_csv", methods=["GET"])
@requires_auth
def download_csv():
    if os.path.exists(CSV_FILE):
        # send_file will return the CSV with BOM we wrote (utf-8-sig)
        return send_file(CSV_FILE, as_attachment=True, download_name="registrations.csv")
    return "فایلی برای دانلود موجود نیست."

# ---------------------- Run ----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
