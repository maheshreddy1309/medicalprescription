import os
from pathlib import Path
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId

from ocr_utils import analyze_prescription

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "tiff"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production-abc123")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["med_app"]
users_col = db["users"]
prescriptions_col = db["prescriptions"]

users_col.create_index("username", unique=True)
prescriptions_col.create_index("user")


def hash_password(password: str) -> str:
    return generate_password_hash(password, method="pbkdf2:sha256")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def get_history(username: str, limit: int = 10):
    history = list(
        prescriptions_col.find({"user": username})
        .sort("uploaded_at", -1)
        .limit(limit)
    )
    for item in history:
        item["_id"] = str(item["_id"])
        item.setdefault("medicines", [])
    return history


@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            error = "Please fill in all fields."
        else:
            user = users_col.find_one({"username": username})
            if user and check_password_hash(user["password"], password):
                session["user"] = username
                session["user_id"] = str(user["_id"])
                return redirect(url_for("dashboard"))
            error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user" in session:
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not username or not password or not confirm_password:
            error = "Please fill in all fields."
        elif len(username) < 3:
            error = "Username must be at least 3 characters."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif password != confirm_password:
            error = "Passwords do not match."
        elif users_col.find_one({"username": username}):
            error = "Username already exists."
        else:
            users_col.insert_one({
                "username": username,
                "password": hash_password(password),
                "created_at": datetime.utcnow(),
            })
            return redirect(url_for("login"))

    return render_template("register.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    history = get_history(session["user"])
    return render_template(
        "dashboard.html",
        user=session["user"],
        history=history,
        result=None,
        error=None,
        image_path=None,
        quality=None,
        interactions=[],
    )


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    error = None
    result = None
    image_path = None
    quality = None
    interactions = []

    if "file" not in request.files:
        error = "No file uploaded."
    else:
        file = request.files["file"]

        if file.filename == "":
            error = "No file selected."
        elif not allowed_file(file.filename):
            error = "Allowed formats: PNG, JPG, JPEG, WEBP, BMP, TIFF."
        else:
            try:
                filename = secure_filename(file.filename)
                filename = f"{session['user']}_{int(datetime.utcnow().timestamp())}_{filename}"
                save_path = UPLOAD_FOLDER / filename
                file.save(str(save_path))

                image_path = f"static/uploads/{filename}"
                analysis = analyze_prescription(str(save_path))

                result = analysis.get("prescription", {})
                quality = analysis.get("quality", {})
                interactions = analysis.get("interactions", [])

                prescriptions_col.insert_one({
                    "user": session["user"],
                    "image_path": image_path,
                    "patient_name": result.get("name", ""),
                    "diagnosis": result.get("diagnosis", ""),
                    "medicines": result.get("medicines", []),
                    "quality": quality,
                    "interactions": interactions,
                    "uploaded_at": datetime.utcnow(),
                })

            except Exception as exc:
                error = f"Upload failed: {exc}"

    history = get_history(session["user"])

    return render_template(
        "dashboard.html",
        user=session["user"],
        history=history,
        result=result,
        error=error,
        image_path=image_path,
        quality=quality,
        interactions=interactions,
    )


@app.route("/scan/<scan_id>")
@login_required
def scan_detail(scan_id):
    try:
        doc = prescriptions_col.find_one({
            "_id": ObjectId(scan_id),
            "user": session["user"],
        })
    except Exception:
        doc = None

    if not doc:
        return redirect(url_for("dashboard"))

    history = get_history(session["user"])

    return render_template(
        "dashboard.html",
        user=session["user"],
        history=history,
        result={
            "name": doc.get("patient_name", ""),
            "diagnosis": doc.get("diagnosis", ""),
            "medicines": doc.get("medicines", []),
        },
        error=None,
        image_path=doc.get("image_path"),
        quality=doc.get("quality"),
        interactions=doc.get("interactions", []),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)