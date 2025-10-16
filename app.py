from flask import Flask, render_template_string, request, redirect, send_file, Response, url_for
import csv, os
from io import StringIO

app = Flask(__name__)

CSV_FILE = "registrations.csv"
PERSIAN_HEADERS = ["نام", "نام خانوادگی", "کد ملی", "شماره دانشجویی", "نام دانشگاه", 
                   "نام دانشکده", "جنسیت", "شماره تلفن", "مقطع تحصیلی", "رشتهٔ تحصیلی", "گواهی"]

ADMIN_PASSWORD = "z.azimi3131383"

# -------------------- صفحات فرم --------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "agree" not in request.form:
            return render_template_string(INDEX_HTML, error="لطفا باکس را تیک بزنید تا ادامه دهید")
        return redirect("/form")
    return render_template_string(INDEX_HTML, error=None)

@app.route("/form", methods=["GET", "POST"])
def form():
    if request.method == "POST":
        # اعتبارسنجی اعداد
        try:
            int(request.form["national_code"])
            int(request.form["student_number"])
            int(request.form["phone"])
        except ValueError:
            return render_template_string(FORM_HTML, error="کد ملی، شماره دانشجویی و شماره تلفن باید عدد باشند")
        
        final_dict = {
            "first_name": request.form.get("first_name",""),
            "last_name": request.form.get("last_name",""),
            "national_code": request.form.get("national_code",""),
            "student_number": request.form.get("student_number",""),
            "university": request.form.get("university",""),
            "faculty": request.form.get("faculty",""),
            "gender": request.form.get("gender",""),
            "phone": request.form.get("phone",""),
            "degree": request.form.get("degree",""),
            "major": request.form.get("major",""),
            "certificate": request.form.get("certificate","")
        }
        save_to_csv(final_dict)
        # شرطی گواهی
        if final_dict["certificate"] == "خواهان گواهی":
            return redirect("/payment")
        return redirect("/thank_you")
    return render_template_string(FORM_HTML, error=None)

@app.route("/payment")
def payment():
    return "<h2>صفحه پرداخت</h2>"

@app.route("/thank_you")
def thank_you():
    return render_template_string(THANK_HTML)

# -------------------- ذخیره CSV --------------------
def save_to_csv(final_dict):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=PERSIAN_HEADERS, delimiter=';')
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

# -------------------- پنل ادمین --------------------
@app.route("/admin_pannel", methods=["GET","POST"])
def admin():
    error=None
    if request.method=="POST":
        if request.form.get("password") != ADMIN_PASSWORD:
            error="رمز اشتباه است!"
        else:
            return redirect(url_for("view_admin"))
    return render_template_string(ADMIN_LOGIN_HTML, error=error)

@app.route("/view_admin")
def view_admin():
    if not os.path.isfile(CSV_FILE):
        return "هنوز کسی ثبت نام نکرده."
    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        data = list(csv.DictReader(f, delimiter=';'))
    return render_template_string(ADMIN_HTML, data=data)

@app.route("/download_csv")
def download_csv():
    if not os.path.isfile(CSV_FILE):
        return "هیچ داده‌ای موجود نیست."
    return send_file(CSV_FILE, as_attachment=True, download_name="registrations.csv", mimetype="text/csv")

# -------------------- HTMLها --------------------
INDEX_HTML = """
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<title>ثبت نام</title>
<style>
body {font-family:Tahoma, sans-serif; background: linear-gradient(to right, #ffecd2, #fcb69f); padding:20px;}
.box{background:white; padding:20px; border-radius:10px; max-width:600px; margin:auto;}
.error{color:red; margin-bottom:10px;}
button{padding:10px 20px; background:#ff7f50; border:none; color:white; cursor:pointer; border-radius:5px;}
button:hover{background:#ff4500;}
a.admin-btn{display:block;margin-top:10px;color:#555;text-decoration:none;}
</style>
</head>
<body>
<div class="box">
<h2>با سلام</h2>
<p>لطفا نکات زیر را به دقت مطالعه فرمایید:</p>
<ol>
<li>حضور در جلسات به عنوان مستمع آزاد بدون درخواست صدور گواهی، رایگان است.</li>
<li>هزینه واریزی برای صدور گواهی به هیچ عنوان عودت داده نمی‌شود.</li>
<li>از مخاطبان گرامی درخواست می‌شود در صورت تمایل به صدور گواهی، پس از ثبت اطلاعات و واریز هزینه، عکس فیش آن را ذخیره کرده تا در سامانه بارگذاری کنید.</li>
</ol>
<form method="POST">
<input type="checkbox" name="agree" id="agree"> موارد فوق را مطالعه کردم<br><br>
{% if error %}<div class="error">{{error}}</div>{% endif %}
<button type="submit">ادامه</button>
</form>
<a class="admin-btn" href="/admin_pannel">ورود ادمین</a>
</div>
</body>
</html>
"""

FORM_HTML = """
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<title>فرم ثبت نام</title>
<style>
body {font-family:Tahoma, sans-serif; background: linear-gradient(to right, #c2e59c, #64b3f4); padding:20px;}
.form-box{background:white; padding:20px; border-radius:10px; max-width:700px; margin:auto;}
label{display:block; margin-top:10px;}
input, select{width:100%; padding:8px; margin-top:5px; border-radius:5px; border:1px solid #ccc;}
input[type=radio]{width:auto;}
.error{color:red; margin-bottom:10px;}
button{margin-top:15px;padding:10px 20px;background:#1e90ff;color:white;border:none;border-radius:5px;cursor:pointer;}
button:hover{background:#104e8b;}
</style>
</head>
<body>
<div class="form-box">
<h2>فرم ثبت نام</h2>
{% if error %}<div class="error">{{error}}</div>{% endif %}
<form method="POST">
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
<option value="مرد">مرد</option>
<option value="زن">زن</option>
</select>
<label>شماره تلفن:</label>
<input type="text" name="phone" required pattern="\\d+" title="شماره تلفن باید عدد باشد">
<label>مقطع تحصیلی:</label>
<select name="degree" required>
<option value="کارشناسی">کارشناسی</option>
<option value="کارشناسی ارشد">کارشناسی ارشد</option>
<option value="دکتری">دکتری</option>
</select>
<label>رشتهٔ تحصیلی:</label>
<input type="text" name="major" required>
<label>گواهی:</label>
<select name="certificate" required>
<option value="خواهان گواهی">خواهان گواهی</option>
<option value="رایگان">رایگان</option>
</select>
<button type="submit">ثبت</button>
</form>
</div>
</body>
</html>
"""

THANK_HTML = """
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<title>با تشکر</title>
<style>
body {font-family:Tahoma, sans-serif; background: linear-gradient(to right, #fceabb, #f8b500); padding:20px;}
.box{background:white; padding:20px; border-radius:10px; max-width:600px; margin:auto;text-align:center;}
a{color:#1e90ff;text-decoration:none;}
</style>
</head>
<body>
<div class="box">
<h2>ثبت شما با موفقیت انجام شد</h2>
<p>لطفا کانال زیر را در بستر تلگرام دنبال کنید:</p>
<p><a href="https://t.me/article_workshop1">@article_workshop1</a></p>
</div>
</body>
</html>
"""

ADMIN_LOGIN_HTML = """
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<title>ورود ادمین</title>
<style>
body {font-family:Tahoma, sans-serif; background: linear-gradient(to right, #fbc2eb, #a6c1ee); padding:20px;}
.box{background:white; padding:20px; border-radius:10px; max-width:400px; margin:auto;}
input[type=password]{width:100%; padding:8px; margin-top:10px; border-radius:5px; border:1px solid #ccc;}
button{margin-top:10px;padding:10px 20px;background:#1e90ff;color:white;border:none;border-radius:5px;cursor:pointer;}
button:hover{background:#104e8b;}
.error{color:red; margin-top:10px;}
</style>
</head>
<body>
<div class="box">
<h2>ورود ادمین</h2>
<form method="POST">
<input type="password" name="password" placeholder="رمز ورود" required>
<button type="submit">ورود</button>
</form>
{% if error %}<div class="error">{{error}}</div>{% endif %}
</div>
</body>
</html>
"""

ADMIN_HTML = """
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<title>پنل ادمین</title>
<style>
body{font-family:Tahoma,sans-serif;background:#f0f0f0;padding:20px;}
table{border-collapse:collapse;width:100%;background:white; border-radius:10px;overflow:hidden;}
th,td{padding:10px;text-align:right;border-bottom:1px solid #ddd;}
th{background:linear-gradient(to right,#ff7f50,#ff4500);color:white;cursor:pointer;}
tr:hover{background:linear-gradient(to right,#ffe4e1,#ffe4b5);}
a.download{display:inline-block;margin:10px 0;padding:10px 15px;background:#1e90ff;color:white;text-decoration:none;border-radius:5px;}
a.download:hover{background:#104e8b;}
input.search{width:200px;padding:5px;margin-bottom:10px;border-radius:5px;border:1px solid #ccc;}
</style>
<script>
function searchTable() {
    var input = document.getElementById("searchInput");
    var filter = input.value.toLowerCase();
    var table = document.getElementById("regTable");
    var tr = table.getElementsByTagName("tr");
    for(var i=1;i<tr.length;i++){
        var td = tr[i].getElementsByTagName("td");
        var show=false;
        for(var j=0;j<td.length;j++){
            if(td[j].innerText.toLowerCase().indexOf(filter)>-1){show=true;}
        }
        tr[i].style.display = show ? "" : "none";
    }
}
</script>
</head>
<body>
<h2>پنل ادمین</h2>
<input type="text" id="searchInput" class="search" onkeyup="searchTable()" placeholder="جستجو سریع...">
<a class="download" href="/download_csv">دانلود CSV</a>
<table id="regTable">
<tr>{% for key in data[0].keys() %}<th>{{key}}</th>{% endfor %}</tr>
{% for row in data %}
<tr>{% for val in row.values() %}<td>{{val}}</td>{% endfor %}</tr>
{% endfor %}
</table>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
