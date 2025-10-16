from flask import Flask, render_template_string, request, redirect, send_file
import csv
import os
from io import StringIO

app = Flask(__name__)

CSV_FILE = "registrations.csv"

PERSIAN_HEADERS = [
    "نام", "نام خانوادگی", "کد ملی", "شماره دانشجویی",
    "نام دانشگاه", "نام دانشکده", "جنسیت",
    "شماره تلفن", "مقطع تحصیلی", "رشتهٔ تحصیلی", "گواهی"
]

# صفحه اول اطلاعیه
HOME_PAGE = """
<!doctype html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8">
  <title>ثبت نام</title>
  <style>
    body { font-family: Tahoma, sans-serif; background: linear-gradient(to bottom, #f0f8ff, #dbeeff); padding: 20px; }
    .container { max-width: 600px; margin: auto; background: white; padding: 20px; border-radius: 15px; box-shadow: 0 0 15px rgba(0,0,0,0.2); }
    input[type=checkbox]{transform: scale(1.5);}
    button { background-color: #4CAF50; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
    button:hover { background-color: #45a049; }
  </style>
</head>
<body>
<div class="container">
<h2>با سلام</h2>
<p>لطفا نکات زیر را به دقت مطالعه فرمایید.</p>
<ol>
<li>حضور در جلسات به عنوان مستمع آزاد بدون درخواست صدور گواهی، رایگان است.</li>
<li>هزینه واریزی برای صدور گواهی به هیچ عنوان عودت داده نمی‌شود.</li>
<li>از مخاطبان گرامی درخواست می‌شود در صورت تمایل به صدور گواهی، پس از ثبت اطلاعات و واریز هزینه، عکس فیش آن را ذخیره کرده تا در سامانه بارگذاری کنید.</li>
</ol>
<form method="post" action="/form">
  <label><input type="checkbox" name="read_rules" required> موارد فوق را مطالعه کردم</label><br><br>
  <button type="submit">تایید و ادامه</button>
</form>
</div>
</body>
</html>
"""

# صفحه فرم ثبت نام
FORM_PAGE = """
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>فرم ثبت نام</title>
<style>
body { font-family: Tahoma, sans-serif; background: linear-gradient(to bottom, #f0f8ff, #dbeeff); padding: 20px; }
.container { max-width: 700px; margin:auto; background: white; padding:20px; border-radius:15px; box-shadow:0 0 20px rgba(0,0,0,0.2); }
input, select { width:100%; padding:10px; margin:5px 0 15px 0; border-radius:5px; border:1px solid #ccc; }
input:invalid { background: #ffe6e6; }
button { background-color:#4CAF50; color:white; padding:10px 20px; border:none; border-radius:5px; cursor:pointer; }
button:hover { background-color:#45a049; }
</style>
</head>
<body>
<div class="container">
<h2>فرم ثبت نام</h2>
<form method="post" action="/submit">
  <label>نام:</label>
  <input type="text" name="first_name" required>

  <label>نام خانوادگی:</label>
  <input type="text" name="last_name" required>

  <label>کد ملی:</label>
  <input type="text" name="national_code" required pattern="\\d{10}" title="کد ملی باید ۱۰ رقم باشد">

  <label>شماره دانشجویی:</label>
  <input type="text" name="student_number" required pattern="\\d+" title="شماره دانشجویی باید عدد باشد">

  <label>نام دانشگاه:</label>
  <input type="text" name="university" required>

  <label>نام دانشکده:</label>
  <input type="text" name="faculty" required>

  <label>جنسیت:</label>
  <select name="gender" required>
    <option value="">انتخاب کنید</option>
    <option value="مرد">مرد</option>
    <option value="زن">زن</option>
  </select>

  <label>شماره تلفن:</label>
  <input type="text" name="phone" required pattern="\\d+" title="شماره تلفن باید عدد باشد">

  <label>مقطع تحصیلی:</label>
  <select name="degree" required>
    <option value="">انتخاب کنید</option>
    <option value="کارشناسی">کارشناسی</option>
    <option value="کارشناسی ارشد">کارشناسی ارشد</option>
    <option value="دکتری">دکتری</option>
  </select>

  <label>رشتهٔ تحصیلی:</label>
  <input type="text" name="major" required>

  <label>گزینه گواهی:</label>
  <select name="certificate" required>
    <option value="">انتخاب کنید</option>
    <option value="می‌خواهم گواهی بگیرم">می‌خواهم گواهی بگیرم</option>
    <option value="نمی‌خواهم گواهی بگیرم">رایگان</option>
  </select>

  <button type="submit">ثبت</button>
</form>
</div>
</body>
</html>
"""

# صفحه تشکر
THANK_PAGE = """
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>ثبت شد</title>
<style>
body { font-family: Tahoma, sans-serif; background: linear-gradient(to bottom, #e0f7fa, #b2ebf2); padding:20px; }
.container { max-width:600px; margin:auto; background:white; padding:20px; border-radius:15px; box-shadow:0 0 20px rgba(0,0,0,0.2);}
a { text-decoration:none; color:#2196F3; }
</style>
</head>
<body>
<div class="container">
<h2>ثبت شما با موفقیت انجام شد</h2>
<p>لطفا کانال زیر را در بستر تلگرام دنبال کنید.</p>
<p>@article_workshop1</p>
</div>
</body>
</html>
"""

def save_to_csv(final_dict):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=PERSIAN_HEADERS, delimiter=';')  # <- تغییر برای اکسل
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

@app.route("/", methods=["GET","POST"])
def home():
    return render_template_string(HOME_PAGE)

@app.route("/form", methods=["POST"])
def form_page():
    return render_template_string(FORM_PAGE)

@app.route("/submit", methods=["POST"])
def submit():
    data = request.form.to_dict()
    save_to_csv(data)
    return render_template_string(THANK_PAGE)

# صفحه ادمین
ADMIN_PAGE = """
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>پنل ادمین</title>
<style>
body { font-family: Tahoma, sans-serif; background: linear-gradient(to bottom, #f5f5f5, #e0e0e0); padding:20px;}
.container { max-width:900px; margin:auto; background:white; padding:20px; border-radius:15px; box-shadow:0 0 25px rgba(0,0,0,0.2);}
table { border-collapse: collapse; width:100%; }
th, td { border:1px solid #ccc; padding:10px; text-align:center; }
th { background: linear-gradient(to bottom, #4CAF50, #45a049); color:white; }
tr:hover { background-color: #f1f1f1; }
input[type=text]{padding:5px; width:200px; margin-bottom:10px;}
button { padding:8px 15px; margin-bottom:10px; border:none; border-radius:5px; background:#4CAF50; color:white; cursor:pointer;}
button:hover{background:#45a049;}
</style>
<script>
function filterTable() {
  var input = document.getElementById("searchInput").value.toLowerCase();
  var table = document.getElementById("regTable");
  var trs = table.getElementsByTagName("tr");
  for (var i=1;i<trs.length;i++){
    trs[i].style.display = trs[i].innerText.toLowerCase().includes(input) ? "" : "none";
  }
}
</script>
</head>
<body>
<div class="container">
<h2>پنل ادمین</h2>
<input type="text" id="searchInput" onkeyup="filterTable()" placeholder="جستجو سریع...">
<form method="get" action="/download">
<button type="submit">دانلود CSV</button>
</form>
<table id="regTable">
<tr>
{% for header in headers %}
<th>{{ header }}</th>
{% endfor %}
</tr>
{% for row in rows %}
<tr>
{% for header in headers %}
<td>{{ row[header] }}</td>
{% endfor %}
</tr>
{% endfor %}
</table>
</div>
</body>
</html>
"""

from flask import Response

ADMIN_PASSWORD = "z.azimi3131383"

@app.route("/admin_pannel", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        password = request.form.get("password")
        if password != ADMIN_PASSWORD:
            return "رمز اشتباه است"
        # بارگذاری CSV
        if not os.path.exists(CSV_FILE):
            rows = []
        else:
            with open(CSV_FILE, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f, delimiter=';')
                rows = list(reader)
        return render_template_string(ADMIN_PAGE, headers=PERSIAN_HEADERS, rows=rows)
    return """
    <form method='post'>
      <input type='password' name='password' placeholder='رمز ادمین'>
      <button type='submit'>ورود</button>
    </form>
    """

@app.route("/download")
def download_csv():
    if not os.path.exists(CSV_FILE):
        return "فایل موجود نیست"
    return send_file(CSV_FILE, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
