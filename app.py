from flask import Flask, render_template_string, request, redirect, send_file
import csv, os

app = Flask(__name__)
CSV_FILE = "registrations.csv"

# -------------------- صفحات HTML --------------------
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
.form-control:focus {box-shadow:0 0 10px #0dcaf0; border-color:#0dcaf0; transition:0.3s;}
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

<form method="POST" action="/register" id="regForm">
  <div class="mb-3"><label>نام:</label><input type="text" class="form-control" name="first_name" required></div>
  <div class="mb-3"><label>نام خانوادگی:</label><input type="text" class="form-control" name="last_name" required></div>
  <div class="mb-3"><label>کد ملی:</label><input type="text" class="form-control" name="national_code" required pattern="\\d{10}" title="کد ملی باید ۱۰ رقم باشد"></div>
  <div class="mb-3"><label>شماره دانشجویی:</label><input type="text" class="form-control" name="student_number" required pattern="\\d+" title="فقط عدد وارد کنید"></div>
  <div class="mb-3"><label>نام دانشگاه:</label><input type="text" class="form-control" name="university_name" required></div>
  <div class="mb-3"><label>نام دانشکده:</label><input type="text" class="form-control" name="faculty_name" required></div>
  <div class="mb-3"><label>جنسیت:</label>
    <select class="form-select" name="gender" required>
      <option value="">انتخاب کنید</option><option value="مرد">مرد</option><option value="زن">زن</option>
    </select>
  </div>
  <div class="mb-3"><label>شماره تلفن:</label><input type="text" class="form-control" name="phone_number" required pattern="\\d+" title="فقط عدد وارد کنید"></div>
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
</body>
</html>
'''

certificate_html = '''
<!doctype html>
<html lang="fa">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>گواهی کارگاه</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
.card {margin-top:30px; padding:20px; border-radius:15px; box-shadow:0 5px 15px rgba(0,0,0,0.1);}
#paymentInfo {transition:0.5s;}
</style>
</head>
<body>
<div class="container">
<div class="card col-12 col-md-6 mx-auto">
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
  <div class="alert alert-info">بعد از انتخاب «خواهان گواهی هستم»، به صفحه پرداخت منتقل خواهید شد.</div>
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

admin_html = '''
<!doctype html>
<html lang="fa">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>پنل ادمین</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css"/>
<style>
.card {margin-top:30px; padding:20px; border-radius:15px; box-shadow:0 5px 15px rgba(0,0,0,0.1);}
#adminTable tbody tr:hover {background-color:#e0f7fa; transition:0.3s;}
.btn:hover {transform:scale(1.05); transition:0.2s;}
</style>
</head>
<body>
<div class="container">
<div class="card col-12">
<h2 class="text-center mb-3">پنل مدیریت ثبت‌نام‌ها</h2>
<a href="/download_csv" class="btn btn-success mb-3">دانلود CSV</a>
<table class="table table-striped table-bordered" id="adminTable">
<thead class="table-dark">
<tr>
  <th>نام</th><th>نام خانوادگی</th><th>کد ملی</th><th>شماره دانشجویی</th><th>دانشگاه</th><th>دانشکده</th><th>جنسیت</th><th>شماره تلفن</th><th>مقطع</th><th>رشته</th><th>گواهی</th>
</tr>
</thead>
<tbody>
{% for row in data %}
<tr>
  <td>{{row.first_name}}</td>
  <td>{{row.last_name}}</td>
  <td>{{row.national_code}}</td>
  <td>{{row.student_number}}</td>
  <td>{{row.university_name}}</td>
  <td>{{row.faculty_name}}</td>
  <td>{{row.gender}}</td>
  <td>{{row.phone_number}}</td>
  <td>{{row.degree}}</td>
  <td>{{row.major}}</td>
  <td>{{row.certificate}}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</div>
<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<script>
$(document).ready(function(){
  $('#adminTable').DataTable({
    "paging":true,
    "searching":true,
    "info":false,
    "scrollX": true
  });
});
</script>
</body>
</html>
'''

# ---------------------- مسیرها ----------------------
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
    return redirect("/certificate")

@app.route("/finish", methods=["POST"])
def finish():
    cert = request.form.get("certificate")
    return redirect("/thanks?certificate=" + cert)

@app.route("/thanks")
def thanks():
    return render_template_string(thanks_html)

@app.route("/admin_pannel")
def admin_panel():
    if not os.path.exists(CSV_FILE):
        data = []
    else:
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            data = list(reader)
    return render_template_string(admin_html, data=data)

@app.route("/download_csv")
def download_csv():
    return send_file(CSV_FILE, as_attachment=True)

# ---------------------- اجرا ----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # پورت Render
    app.run(host="0.0.0.0", port=port, debug=True)
