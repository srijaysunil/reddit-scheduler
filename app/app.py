import os
import sqlite3
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, send_from_directory
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
from pathlib import Path
from zoneinfo import ZoneInfo
import praw
import pytz

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

# Uploads
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/data/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Timezone
APP_TZ = ZoneInfo(os.getenv("APP_TIMEZONE", "America/Chicago"))

# Database
DB_FILE = os.getenv("DB_FILE", "/data/posts.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS scheduled_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subreddit TEXT,
        title TEXT NOT NULL,
        post_type TEXT NOT NULL,
        content TEXT NOT NULL,
        post_time TEXT NOT NULL,
        posted INTEGER DEFAULT 0,
        last_error TEXT DEFAULT NULL,
        created_at TEXT NOT NULL,
        flair_id TEXT,
        target_type TEXT DEFAULT 'subreddit'
    )
    """)
    conn.commit()
    conn.close()

init_db()

# Reddit API
reddit = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    username=os.getenv("REDDIT_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD"),
    user_agent=os.getenv("REDDIT_USER_AGENT", f"reddit-scheduler/0.3 by u/{os.getenv('REDDIT_USERNAME')}")
)

# Function to post to reddit
def post_to_reddit(subreddit, title, post_type, content, flair_id, target_type):
    try:
        if target_type == "subreddit":
            sub = reddit.subreddit(subreddit)
            if post_type == "link":
                sub.submit(title=title, url=content, flair_id=flair_id)
            elif post_type == "text":
                sub.submit(title=title, selftext=content, flair_id=flair_id)
            elif post_type == "image":
                sub.submit_image(title=title, image_path=str(UPLOAD_DIR / content), flair_id=flair_id)
            else:
                raise ValueError(f"Unknown post_type: {post_type}")
        else:  # profile
            redditor = reddit.redditor(os.getenv("REDDIT_USERNAME"))
            if post_type == "link":
                redditor.submit(title=title, url=content)
            elif post_type == "text":
                redditor.submit(title=title, selftext=content)
            elif post_type == "image":
                redditor.submit_image(title=title, image_path=str(UPLOAD_DIR / content))
            else:
                raise ValueError(f"Unknown post_type: {post_type}")
        return None
    except Exception as e:
        return str(e)

# Scheduler job
def check_scheduled_posts():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    try:
        c.execute("SELECT id, subreddit, title, post_type, content, flair_id, target_type FROM scheduled_posts WHERE post_time<=? AND posted=0", (now_utc,))
        rows = c.fetchall()
        for row in rows:
            post_id, subreddit, title, post_type, content, flair_id, target_type = row
            err = post_to_reddit(subreddit, title, post_type, content, flair_id, target_type)
            if err is None:
                c.execute("UPDATE scheduled_posts SET posted=1, last_error=NULL WHERE id=?", (post_id,))
            else:
                c.execute("UPDATE scheduled_posts SET last_error=? WHERE id=?", (err, post_id))
        conn.commit()
    except Exception as e:
        print("Scheduler error:", e)
    finally:
        conn.close()

scheduler = BackgroundScheduler()
scheduler.add_job(func=check_scheduled_posts, trigger="interval", minutes=1)
scheduler.start()

# Jinja filter to convert UTC to Central
@app.template_filter('to_central')
def to_central(value):
    dt = datetime.strptime(value, "%Y-%m-%d %H:%M")
    dt = dt.replace(tzinfo=timezone.utc)
    central = pytz.timezone("America/Chicago")
    return dt.astimezone(central).strftime("%Y-%m-%d %H:%M")

# Route to fetch subreddit flairs
@app.route("/flairs/<subreddit>")
def get_flairs(subreddit):
    try:
        flairs = reddit.subreddit(subreddit).flair.link_templates
        return jsonify([{"id": f["id"], "text": f["text"]} for f in flairs])
    except Exception:
        return jsonify([])

# Serve uploaded images
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)

# Main page
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Safely get form fields
        title = (request.form.get("title") or "").strip()
        post_type = (request.form.get("post_type") or "").strip()
        flair_id = request.form.get("flair_id") or None
        post_time_str = (request.form.get("post_time") or "").strip()
        target_type = (request.form.get("target_type") or "subreddit").strip()
        subreddit = (request.form.get("subreddit") or "").strip() if target_type=="subreddit" else None

        # Validate required fields
        if not title:
            flash("Title is required.")
            return redirect(url_for("index"))
        if post_type not in ["link", "text", "image"]:
            flash("Invalid post type.")
            return redirect(url_for("index"))
        if target_type=="subreddit" and not subreddit:
            flash("Subreddit is required for subreddit posts.")
            return redirect(url_for("index"))
        if not post_time_str:
            flash("Post time is required.")
            return redirect(url_for("index"))

        # Convert datetime-local to UTC
        try:
            local_dt = datetime.strptime(post_time_str, "%Y-%m-%dT%H:%M")
            local_dt = local_dt.replace(tzinfo=APP_TZ)
            post_time_utc = local_dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
        except Exception:
            flash("Invalid date/time format")
            return redirect(url_for("index"))

        # Handle content
        content_value = ""
        if post_type in ["link", "text"]:
            content_value = (request.form.get("content") or "").strip()
            if not content_value:
                flash("Content cannot be empty")
                return redirect(url_for("index"))
        elif post_type == "image":
            file = request.files.get("image_file")
            if file and file.filename:
                if not allowed_file(file.filename):
                    flash("Invalid image format")
                    return redirect(url_for("index"))
                safe = secure_filename(file.filename)
                filename = f"{int(datetime.now().timestamp())}_{safe}"
                save_path = UPLOAD_DIR / filename
                file.save(save_path)
                content_value = filename
            else:
                flash("Image file required")
                return redirect(url_for("index"))

        # Save to database
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""INSERT INTO scheduled_posts
            (subreddit, title, post_type, content, post_time, posted, last_error, created_at, flair_id, target_type)
            VALUES (?, ?, ?, ?, ?, 0, NULL, ?, ?, ?)""",
            (subreddit, title, post_type, content_value, post_time_utc,
             datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), flair_id, target_type)
        )
        conn.commit()
        conn.close()
        flash("Scheduled successfully")
        return redirect(url_for("index"))

    # GET request
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM scheduled_posts ORDER BY post_time")
    posts = c.fetchall()
    conn.close()
    return render_template("index.html", posts=posts, app_tz=str(APP_TZ))

@app.post("/delete/<int:post_id>")
def delete_post(post_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM scheduled_posts WHERE id=?", (post_id,))
    conn.commit()
    conn.close()
    flash("Deleted")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
