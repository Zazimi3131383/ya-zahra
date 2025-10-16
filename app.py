from flask import Flask, render_template_string, request, redirect

app = Flask(__name__)

# صفحه اصلی (سؤال اول)
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        answer = request.form.get("choice")
        if answer == "pay":
            # اگر پرداخت را انتخاب کرد
            return redirect("https://zarinpal.com/payment-link")  # لینک درگاه پرداخت
        else:
            return redirect("/next")
    return render_template_string("""
    <h2>آیا مایل هستید پرداخت را انجام دهید؟</h2>
    <form method="POST">
        <button name="choice" value="pay">✅ بله، مایل به پرداخت هستم</button>
        <button name="choice" value="no">❌ خیر، فقط ادامه می‌دهم</button>
    </form>
    """)

# صفحه دوم
@app.route("/next")
def next_page():
    return render_template_string("""
    <h2>سؤال دوم: از کدام شهر هستید؟</h2>
    <form method="POST" action="/thank">
        <input type="text" name="city" placeholder="نام شهر" required>
        <button type="submit">ارسال</button>
    </form>
    """)

# صفحه تشکر
@app.route("/thank", methods=["POST"])
def thank():
    city = request.form.get("city")
    # می‌تونی این داده را در فایل ذخیره کنی (در مراحل بعد یاد می‌گیریم)
    return f"<h3>سپاس از شرکت شما! شهر شما: {city}</h3>"

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


