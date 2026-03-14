from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import pickle
import smtplib
from email.mime.text import MIMEText
import random
import re
import os
import requests 
from googleapiclient.discovery import build
API_KEY = "AIzaSyCmxXAUkGdLrivSlnFThdppoGFya6WLGx4"
YOUTUBE_API_KEY = "AIzaSyAYwMmLVb-e4gYbZ9FTiqNOCjVEx5SXzQc"
# Load ML Model
with open("phishing_model.pkl", "rb") as f:
     model = pickle.load(f)

def extract_features(url):
    return [
        len(url),
        url.count("-"),
        url.count("@"),
        url.count("https"),
        url.count("http"),
        url.count(".")
    ]
def check_google_safe(url):

    api_url = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={API_KEY}"

    data = {
        "client": {
            "clientId": "phishing-detector",
            "clientVersion": "1.0"
        },
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}]
        }
    }

    response = requests.post(api_url, json=data)

    if response.json():
        return "Phishing Detected ⚠️"
    else:
        return "Safe ✅"

def get_video_id(url):
    # Works for youtube.com, youtu.be, shorts
    pattern = r"(?:v=|\/shorts\/|youtu\.be\/|embed\/)([0-9A-Za-z_-]{11})"
    match = re.search(pattern, url)

    if match:
        return match.group(1)

    return None
def get_video_details(video_id):

    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

    request = youtube.videos().list(
        part="snippet,statistics",
        id=video_id
    )

    response = request.execute()

    if response["items"]:
        video = response["items"][0]

        title = video["snippet"]["title"]
        description = video["snippet"]["description"]
        channel = video["snippet"]["channelTitle"]

        views = video["statistics"].get("viewCount", "0")

        thumbnail = video["snippet"]["thumbnails"]["high"]["url"]

        return title, description, views, channel, thumbnail

    return None, None, None, None, None
app = Flask(__name__)
app.secret_key = "supersecretkey123"


# ✅ FIXED OTP FUNCTION (Environment Variables Used)
import requests
import os 
def send_otp_email(to_email, otp):
    api_key = os.environ.get("BREVO_API_KEY")

    if not api_key:
        print("Brevo API key missing!")
        return

    url = "https://api.brevo.com/v3/smtp/email"

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    data = {
        "sender": {
            "name": "Phishing Detection",
            "email": "abusameer967@gmail.com"
        },
        "to": [
            {
                "email": to_email
            }
        ],
        "subject": "Phishing Detection OTP",
        "htmlContent": f"<p>Your OTP is: <b>{otp}</b></p>"
    }

    response = requests.post(url, json=data, headers=headers)

    print("Brevo response:", response.text)


# Create DB
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        password TEXT
    )
    """)

    # History table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        url TEXT,
        result TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # YouTube history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS youtube_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        video_url TEXT,
        title TEXT,
        result TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create admin account
    cursor.execute("SELECT * FROM users WHERE email=?", ("abusameer967@gmail.com",))
    admin = cursor.fetchone()

    if not admin:
        cursor.execute(
            "INSERT INTO users (email,password) VALUES (?,?)",
            ("abusameer967@gmail.com", "sameersameer")
        )

    conn.commit()
    conn.close()

@app.route('/')
def home():
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        otp = random.randint(100000, 999999)

        session["otp"] = str(otp)
        session["temp_email"] = email
        session["temp_password"] = password

        send_otp_email(email, otp)

        return redirect(url_for("verify_otp"))

    return render_template("register.html")


@app.route("/verify", methods=["GET", "POST"])
def verify_otp():
    if request.method == "POST":
        user_otp = request.form["otp"]

        if user_otp == session.get("otp"):
            email = session.get("temp_email")
            password = session.get("temp_password")

            conn = sqlite3.connect("users.db")
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (email, password) VALUES (?, ?)",
                (email, password)
            )
            conn.commit()
            conn.close()

            return redirect(url_for("home"))
        else:
            return "Invalid OTP"

    return render_template("verify.html")


@app.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")

        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user:
            otp = random.randint(100000, 999999)
            session["reset_otp"] = str(otp)
            session["reset_email"] = email

            send_otp_email(email, otp)

            return redirect(url_for("verify_reset_otp"))
        else:
            return "Email not found"

    return render_template("forgot.html")


@app.route("/verify-reset", methods=["GET", "POST"])
def verify_reset_otp():
    if request.method == "POST":
        user_otp = request.form.get("otp")

        if user_otp == session.get("reset_otp"):
            return redirect(url_for("new_password"))
        else:
            return "Invalid OTP"

    return render_template("verify_reset.html")


@app.route("/new-password", methods=["GET", "POST"])
def new_password():
    if request.method == "POST":
        new_pass = request.form.get("password")
        email = session.get("reset_email")

        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password=? WHERE email=?",
            (new_pass, email)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("home"))

    return render_template("new_password.html")


@app.route('/login', methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
    "SELECT * FROM users WHERE email=? AND password=?",
    (email, password)
)
    user = cursor.fetchone()
    conn.close()

    if user:
        session["user"] = email

        if email == "abusameer967@gmail.com":
            return redirect(url_for("admin"))
        else:
            return redirect(url_for("dashboard"))

    return "Invalid Credentials"


@app.route("/dashboard")
def dashboard():

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # total scans
    cursor.execute("SELECT COUNT(*) FROM history")
    total_scans = cursor.fetchone()[0]

    # phishing detected
    cursor.execute("SELECT COUNT(*) FROM history WHERE result='PHISHING'")
    phishing_count = cursor.fetchone()[0]

    # safe websites
    cursor.execute("SELECT COUNT(*) FROM history WHERE result='SAFE'")
    safe_count = cursor.fetchone()[0]

    # accuracy
    if total_scans == 0:
        accuracy = 0
    else:
        accuracy = round((safe_count / total_scans) * 100)

    conn.close()

    # Threat level calculation

    if total_scans == 0:
     phishing_ratio = 0
    else:
     phishing_ratio = phishing_count / total_scans

    if phishing_ratio >= 0.6:
     threat_status = "High"
    elif phishing_ratio >= 0.3:
     threat_status = "Medium"
    else:
     threat_status = "Low"
 
    return render_template(
    "dashboard.html",
    total_scans=total_scans,
    phishing_count=phishing_count,
    safe_count=safe_count,
    accuracy=accuracy,
    threat_status=threat_status
)
@app.route("/history")
def history():

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("SELECT url, result FROM history ORDER BY id DESC")
    data = cursor.fetchall()

    conn.close()

    return render_template("history.html", data=data)

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/detect", methods=["GET", "POST"])
def detect():

    result = None
    confidence = None
    result_text = None

    if request.method == "POST":

        url = request.form["url"].strip()

        # -----------------------------
        # 1️⃣ Invalid protocol check
        # -----------------------------
        if not url.startswith("http://") and not url.startswith("https://"):

            result = "PHISHING"
            result_text = "PHISHING"
            confidence = 95

        # -----------------------------
        # 2️⃣ Fake https check
        # -----------------------------
        elif "httt" in url or "httpssss" in url:

            result = "PHISHING"
            result_text = "PHISHING"
            confidence = 95

        # -----------------------------
        # 3️⃣ IP address URL check
        # -----------------------------
        elif re.match(r'http[s]?://\d{1,3}(\.\d{1,3}){3}', url):

            result = "PHISHING"
            result_text = "PHISHING"
            confidence = 95

        # -----------------------------
        # 4️⃣ @ phishing trick
        # -----------------------------
        elif "@" in url:

            result = "PHISHING"
            result_text = "PHISHING"
            confidence = 95

        else:

            # -----------------------------
            # 5️⃣ URL format validation
            # -----------------------------
            pattern = re.compile(
                r'^(http://|https://)'
                r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
            )

            if not re.match(pattern, url):

                result = "PHISHING"
                result_text = "PHISHING"
                confidence = 90

            else:

                try:

                    # -----------------------------
                    # 6️⃣ Google Safe Browsing
                    # -----------------------------
                    google_result = check_google_safe(url)

                    # -----------------------------
                    # 7️⃣ ML Model Prediction
                    # -----------------------------
                    features = [extract_features(url)]

                    prediction = model.predict(features)[0]

                    # Real ML confidence
                    if hasattr(model, "predict_proba"):
                        confidence = int(model.predict_proba(features)[0][1] * 100)
                    else:
                        confidence = random.randint(85,95)

                    # -----------------------------
                    # 8️⃣ Final decision
                    # -----------------------------
                    if google_result == "Phishing Detected ⚠️" or prediction == 1:

                        result = "PHISHING"
                        result_text = "PHISHING"

                    else:

                        result = "SAFE"
                        result_text = "SAFE"

                except Exception as e:

                    result = "ERROR"
                    confidence = 0
                    print("Detection Error:", e)

        # -----------------------------
        # 9️⃣ Save history
        # -----------------------------
        try:

            conn = sqlite3.connect("users.db")
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO history (username, url, result) VALUES (?, ?, ?)",
                (session.get("user", "guest"), url, result_text)
            )

            conn.commit()
            conn.close()

        except Exception as db_error:

            print("Database Error:", db_error)

    return render_template(
        "detect.html",
        result=result,
        confidence=confidence
    )
@app.route("/reset_history")
def reset_history():

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM history")
    conn.commit()
    conn.close()

    return redirect("/dashboard")


@app.route("/change_password")
def change_password():
    return render_template("new_password.html")

@app.route("/admin")
def admin():

    if "user" not in session:
        return redirect(url_for("home"))

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Website history count
    cursor.execute("SELECT COUNT(*) FROM history")
    web_total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM history WHERE result='SAFE'")
    web_safe = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM history WHERE result='PHISHING'")
    web_phish = cursor.fetchone()[0]

    # YouTube history count
    cursor.execute("SELECT COUNT(*) FROM youtube_history")
    yt_total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM youtube_history WHERE result='Safe Video'")
    yt_safe = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM youtube_history WHERE result='Possible Phishing Video'")
    yt_phish = cursor.fetchone()[0]
    cursor.execute("""
    SELECT username, url, result
    FROM history
    ORDER BY id DESC
    LIMIT 5
     """)

    recent = cursor.fetchall()
    conn.close()

    total = web_total + yt_total
    safe = web_safe + yt_safe
    phishing = web_phish + yt_phish

    return render_template(
"admin.html",
total_urls=total,
phishing=phishing,
safe=safe,
recent=recent
)
@app.route("/admin/settings")
def admin_settings():

    if "user" not in session:
        return redirect(url_for("login"))

    return render_template("settings.html")
@app.route("/admin/web-history")
def web_history():

    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM history ORDER BY id DESC")

    history = cursor.fetchall()

    conn.close()

    return render_template("web_history.html", history=history)
@app.route("/admin/youtube-history")
def youtube_history():

    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("SELECT username, title, result, date FROM youtube_history ORDER BY id DESC")

    history = cursor.fetchall()

    conn.close()

    return render_template("youtube_history.html", history=history)
@app.route("/admin/graph")
def admin_graph():

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM history WHERE result='SAFE'")
    safe = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM history WHERE result='PHISHING'")
    phishing = cursor.fetchone()[0]

    conn.close()

    return render_template("graph.html", safe=safe, phishing=phishing)

@app.route('/logout')
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))
@app.route("/youtube", methods=["GET", "POST"])
def youtube_analysis():

    result = None
    title = None
    channel = None
    views = None
    thumbnail = None
    video_id = None   # IMPORTANT

    if request.method == "POST":

        video_url = request.form["youtube_url"]   # MATCH HTML

        video_id = get_video_id(video_url)

        if not video_id:
            return render_template("youtube.html", result="Invalid YouTube Link")

        title, description, views, channel, thumbnail = get_video_details(video_id)

        if title:
            text = (title + " " + description).lower()

            keywords = ["free money","bitcoin","earn money","investment","giveaway","crypto"]

            if any(word in text for word in keywords):
                result = "⚠ Possible Phishing Video"
            else:
                result = "✅ Safe Video"

            # SAVE TO DATABASE
            conn = sqlite3.connect("users.db")
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO youtube_history (username, video_url, title, result) VALUES (?, ?, ?, ?)",
                (session.get("user"), video_url, title, result)
            )

            conn.commit()
            conn.close()

    return render_template(
        "youtube.html",
        result=result,
        title=title,
        channel=channel,
        views=views,
        thumbnail=thumbnail,
        video_id=video_id
    )
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    # deploy update