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
YOUTUBE_API_KEY = "AIzaSyAYwMmLVb-e4gYbZ9FTiqNOCjVEx5SXzQc"
# Load ML Model
# with open("phishing_model.pkl", "rb") as f:
#     model = pickle.load(f)

def extract_features(url):
    return [
        len(url),
        url.count("-"),
        url.count("@"),
        url.count("https"),
        url.count("http"),
        url.count(".")
    ]


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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            password TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            url TEXT,
            result TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
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

    conn.commit()
    conn.close()

init_db()


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


@app.route('/dashboard')
def dashboard():
    if "user" in session:
        return render_template("dashboard.html")
    return redirect(url_for("home"))


@app.route("/detect", methods=["GET", "POST"])
def detect():
    result = None

    if request.method == "POST":
        url = request.form["url"]

        pattern = re.compile(
            r'^(http://|https://)?'
            r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
        )

        if not re.match(pattern, url):
            result = "⚠️ Phishing (Invalid URL Format)"
            return render_template("detect.html", result=result)

        features = [extract_features(url)]
        prediction = model.predict(features)[0]

        result_text = "SAFE" if prediction == 0 else "PHISHING"

        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO history (username, url, result) VALUES (?, ?, ?)",
            (session.get("user", "guest"), url, result_text)
        )
        conn.commit()
        conn.close()

        if prediction == 1:
            result = "⚠️ This URL is PHISHING!"
        else:
            result = "✅ This URL is SAFE!"

    return render_template("detect.html", result=result)


@app.route('/admin')
def admin():
    if "user" not in session:
        return redirect(url_for("home"))

    if session["user"] != "abusameer967@gmail.com":
        return "⛔ Access Denied! Admin Only."

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM history")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM history WHERE result='SAFE'")
    safe = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM history WHERE result='PHISHING'")
    phishing = cursor.fetchone()[0]

    cursor.execute("SELECT * FROM history ORDER BY date DESC")
    history = cursor.fetchall()
    
    cursor.execute("SELECT * FROM youtube_history ORDER BY date DESC")
    youtube_history = cursor.fetchall()

    conn.close()

    return render_template(
    "admin.html",
    total=total,
    safe=safe,
    phishing=phishing,
    history=history,
    youtube_history=youtube_history
)


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

    if request.method == "POST":

        video_url = request.form["video_url"]

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

    # Save YouTube analysis history
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
        thumbnail=thumbnail
    )
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
    # deploy update